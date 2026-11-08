"""NVD CVE evidence resolver; only fixed, allowlisted upstream endpoints."""
from __future__ import annotations
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any
import httpx
from .store import Store

CVE_PATTERN = re.compile(r'\bCVE-\d{4}-\d{4,12}\b', re.I)
FULL_CVE = re.compile(r'^CVE-\d{4}-\d{4,12}$')
PERSONAL_OR_SECRET = re.compile(r'(?i)([\w.+-]+@[\w.-]+\.[a-z]{2,}|(?:https?://)|(?:\b(?:AKIA|sk-|ghp_|Bearer\s+)\w+)|(?:\b\d{1,3}(?:\.\d{1,3}){3}\b))')
UPSTREAM_URL = 'https://services.nvd.nist.gov/rest/json/cves/2.0'


class Limited(Exception):
    pass


class UpstreamFailed(Exception):
    pass


class Resolver:
    def __init__(self, store: Store, *, hash_secret: str, daily_limit: int = 100,
                 per_minute_limit: int = 5, upstream_daily_limit: int = 150):
        self.store = store
        self.secret = hash_secret.encode('utf-8')
        self.daily_limit = daily_limit
        self.per_minute_limit = per_minute_limit
        self.upstream_daily_limit = upstream_daily_limit

    def identity(self, ip: str, agent_id: str = '') -> str:
        # HMAC instead of recording client IP; caller-supplied agent_id is not verified identity.
        data = (ip + '|' + agent_id[:64]).encode('utf-8')
        return hmac.new(self.secret, data, hashlib.sha256).hexdigest()[:24]

    def gate(self, identity: str, action: str):
        # Count limits BEFORE any network access. No implicit subscription or billing.
        minute = int(time.time() // 60)
        day = time.strftime('%Y%m%d', time.gmtime())
        if not self.store.consume_limit(f'minute:{minute}:{action}', identity, self.per_minute_limit):
            raise Limited('per-minute quota exceeded')
        if not self.store.consume_limit(f'day:{day}:{action}', identity, self.daily_limit):
            raise Limited('daily quota exceeded')

    def eligible_gap(self, topic: str) -> bool:
        return 8 <= len(topic) <= 200 and not PERSONAL_OR_SECRET.search(topic)

    def report_gap(self, topic: str, consent: bool) -> dict:
        cleaned = ' '.join(topic.split()).strip()[:201]
        if not consent:
            return {'status': 'not_recorded', 'reason': 'explicit consent required'}
        if not self.eligible_gap(cleaned):
            return {'status': 'not_recorded', 'reason': 'private, unsafe or malformed input'}
        normalized = cleaned.casefold()
        fingerprint = hashlib.sha256(normalized.encode()).hexdigest()
        self.store.gap(fingerprint, cleaned)
        return {'status': 'recorded', 'gap_id': fingerprint[:16]}

    @staticmethod
    def get_cve(identifier: str | None, question: str | None) -> str | None:
        if identifier:
            candidate = identifier.strip().upper()
            return candidate if FULL_CVE.fullmatch(candidate) else None
        matches = CVE_PATTERN.findall(question or '')
        return matches[0].upper() if len(set(map(str.upper,matches))) == 1 else None

    async def resolve(self, *, question: str | None = None, identifier: str | None = None,
                      consent_to_aggregate: bool = False, identity: str = 'anonymous') -> dict:
        self.gate(identity, 'resolve')
        cve = self.get_cve(identifier, question)
        if cve is None:
            gap = self.report_gap(question or identifier or '', consent_to_aggregate)
            self.store.event(identity, 'resolve', 'unsupported')
            return {'status': 'unsupported', 'message': 'MVP supports one public CVE identifier per query', 'gap': gap}
        existing = self.store.cached(cve)
        if existing:
            self.store.event(identity, 'resolve', existing['status'], True)
            return {**existing, 'reused': True}
        day = time.strftime('%Y%m%d', time.gmtime())
        if not self.store.consume_limit(f'upstream:{day}', 'global', self.upstream_daily_limit):
            self.store.event(identity, 'resolve', 'budget_exceeded')
            raise Limited('global upstream budget reached')
        try:
            document = await self.fetch_nvd(cve)
        except (httpx.HTTPError, ValueError, UpstreamFailed) as exc:
            self.store.event(identity, 'resolve', 'upstream_error')
            raise UpstreamFailed('official source temporarily unavailable') from exc
        vulnerabilities = document.get('vulnerabilities', [])
        matched = [v.get('cve', {}) for v in vulnerabilities if v.get('cve', {}).get('id', '').upper() == cve]
        now = datetime.now(timezone.utc).isoformat()
        ident = str(uuid.uuid4())
        if not matched:
            result = {'id': ident, 'status': 'not_verified', 'identifier': cve,
                      'answer': None, 'evidence': [], 'checked_at': now,
                      'reason': 'No matching record returned by NVD', 'reused': False}
            ttl = 3600
        else:
            entry = matched[0]
            descriptions = [d.get('value','') for d in entry.get('descriptions',[]) if d.get('lang')=='en']
            cvss = []
            metrics = entry.get('metrics') or {}
            for key in ('cvssMetricV40','cvssMetricV31','cvssMetricV30','cvssMetricV2'):
                for metric in metrics.get(key, [])[:2]:
                    score = (metric.get('cvssData') or {}).get('baseScore')
                    if score is not None: cvss.append({'version': key, 'score': score})
                if cvss: break
            result = {'id': ident, 'status': 'verified', 'identifier': cve, 'answer': {
                'description_en': descriptions[0][:1000] if descriptions else None,
                'published': entry.get('published'), 'last_modified': entry.get('lastModified'),
                'nvd_status': entry.get('vulnStatus'), 'cvss': cvss,
                'cisa_known_exploited_added': entry.get('cisaExploitAdd'),
            }, 'evidence': [{
                'publisher': 'NIST National Vulnerability Database',
                'url': f'https://nvd.nist.gov/vuln/detail/{cve}',
                'api_url': UPSTREAM_URL + '?cveId=' + cve,
                'observed_at': now,
                'provenance': 'official registry record; not independent validation of exploitability'
            }], 'checked_at': now, 'reused': False}
            ttl = 86400
        self.store.save(ident, cve, result, ttl)
        self.store.event(identity, 'resolve', result['status'])
        return result

    async def fetch_nvd(self, identifier: str) -> dict[str, Any]:
        # No user-controlled URL or redirects: prevents the service from becoming an SSRF proxy.
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0), follow_redirects=False,
                                     trust_env=False) as client:
            response = await client.get(UPSTREAM_URL, params={'cveId': identifier},
                                        headers={'User-Agent': 'AIBITIOUS-404-experiment/0.1'})
        if response.status_code != 200 or len(response.content) > 1_000_000:
            raise UpstreamFailed('NVD rejected or oversized response')
        return response.json()
