"""Conservative public website extraction. No LLM, purchased data or inferred intent."""
from __future__ import annotations
import asyncio
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import httpx
from .lab import LabInputError

TOOLS = {
    'company_card': 'CompanyCard — public company identity from its own website',
    'project_signals': 'ProjectSignals — sourced project candidates from a supplier website',
}
AGENT = 'AIBITIOUS-CompanyData/0.1'


def safe_url(value):
    if not isinstance(value, str) or len(value) > 500:
        raise LabInputError('Supply a public HTTPS domain or URL')
    if '://' not in value:
        value = 'https://' + value
    u = urlsplit(value)
    host = (u.hostname or '').encode('idna').decode().lower()
    if (u.scheme != 'https' or u.username or u.password or u.port not in (None, 443)
            or u.query or u.fragment or not host or '.' not in host or '%' in host
            or host.endswith(('.local', '.localhost', '.internal'))):
        raise LabInputError('Only public HTTPS URLs without credentials, query or fragment')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise LabInputError('IP literals are unsupported')
    return 'https://' + host + (u.path or '/')


async def fetch(url):
    """Resolve and pin a public address for every hop, retaining TLS hostname checks."""
    current = safe_url(url)
    async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
        for _ in range(4):
            u = urlsplit(current)
            records = await asyncio.get_running_loop().getaddrinfo(
                u.hostname, 443, type=socket.SOCK_STREAM)
            addresses = sorted({r[4][0] for r in records})
            if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
                raise LabInputError('Source resolves to a non-public address')
            address = addresses[0]
            netloc = '[' + address + ']' if ':' in address else address
            pinned = 'https://' + netloc + u.path
            async with client.stream('GET', pinned,
                    headers={'Host': u.hostname, 'User-Agent': AGENT, 'Accept-Encoding': 'identity'},
                    extensions={'sni_hostname': u.hostname.encode()}) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    target = safe_url(urljoin(current, response.headers.get('location', '')))
                    if urlsplit(target).hostname != u.hostname:
                        raise LabInputError('Cross-domain redirects need a separate source request')
                    current = target
                    continue
                if response.status_code != 200:
                    raise LabInputError('Public source unavailable')
                if not any(t in response.headers.get('content-type', '') for t in ('text/html', 'text/plain', 'application/xhtml+xml')):
                    raise LabInputError('Only HTML/text sources supported')
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 300_000:
                        raise LabInputError('Source exceeds 300 KB')
                return current, data.decode('utf-8', errors='replace')
    raise LabInputError('Too many redirects')


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.meta, self.links, self.nodes = {}, [], []
        self.title, self.text, self.script = '', [], ''
        self.in_title = False
        self.in_json = False
        self.hidden = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title': self.in_title = True
        if tag in ('style', 'script'): self.hidden += 1
        if tag == 'script' and a.get('type') == 'application/ld+json':
            self.in_json, self.script = True, ''
        if tag == 'meta': self.meta[a.get('property', a.get('name', ''))] = a.get('content', '')
        if tag == 'a' and a.get('href'): self.links.append(a['href'])

    def handle_data(self, data):
        if self.in_title: self.title += data
        if self.in_json: self.script += data
        if not self.hidden: self.text.append(data)

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag == 'script' and self.in_json:
            try: self.nodes.extend(flatten(json.loads(self.script)))
            except (ValueError, RecursionError): pass
            self.in_json = False
        if tag in ('style', 'script'): self.hidden = max(0, self.hidden - 1)


def flatten(value, depth=0):
    if depth > 12: return []
    if isinstance(value, list): return [n for v in value for n in flatten(v, depth + 1)]
    if isinstance(value, dict): return [value] + flatten(value.get('@graph', []), depth + 1)
    return []


def types(node):
    value = node.get('@type', [])
    return {value} if isinstance(value, str) else set(x for x in value if isinstance(x, str)) if isinstance(value, list) else set()


def short(value):
    return ' '.join(value.split())[:500] if isinstance(value, str) else None


def company(page, url):
    orgs = [n for n in page.nodes if types(n) & {'Organization', 'Corporation', 'LocalBusiness', 'ProfessionalService'}]
    host = urlsplit(url).hostname
    matching = [n for n in orgs if isinstance(n.get('url'), str) and urlsplit(n['url']).hostname == host]
    org = matching[0] if len(matching) == 1 else orgs[0] if len(orgs) == 1 else {}
    fields = {}
    for key in ('name', 'legalName', 'description', 'taxID', 'vatID'):
        value = short(org.get(key))
        if value:
            fields[key] = {'value': value, 'source_url': url, 'basis': 'publisher_jsonld', 'independently_verified': False}
    if 'description' not in fields:
        value = short(page.meta.get('description'))
        if value: fields['description'] = {'value': value, 'source_url': url, 'basis': 'publisher_meta', 'independently_verified': False}
    return {'domain': host, 'fields': fields, 'missing_fields': [k for k in ('name', 'legalName', 'description', 'taxID', 'vatID') if k not in fields]}


def project(page, url):
    articles = [n for n in page.nodes if types(n) & {'Article', 'BlogPosting', 'CreativeWork', 'CaseStudy'}]
    node = articles[0] if len(articles) == 1 else {}
    title = short(node.get('headline') or node.get('name') or page.title)
    text = ' '.join(' '.join(page.text).split())
    technologies = [t for t in ('Shopify Plus', 'Shopify', 'Magento', 'WooCommerce', 'Salesforce', 'HubSpot', 'SAP')
                    if re.search(r'\b' + re.escape(t) + r'\b', text, re.I)]
    # Mentioning a technology or customer logo does not establish a purchase.
    labeled = '\n'.join(short(part) or '' for part in page.text)
    match = re.search(r'(?im)^\s*(?:client|customer|klient)\s*:\s*([^\n]{2,100})\s*$', labeled)
    customer = ({'value': match.group(1).strip(), 'source_url': url,
                 'excerpt': match.group(0).strip(), 'basis': 'explicit_customer_label',
                 'independently_verified': False} if match else None)
    return {'source_url': url, 'title': title,
            'publication_date_claim': short(node.get('datePublished')),
            'project_date': None, 'customer': customer, 'supplier': None,
            'technology_mentions': technologies,
            'excerpt': text[:500], 'status': 'candidate_needs_verification',
            'purchase_intent': None,
            'note': 'Candidate source only. Customer, supplier, project date and scope require explicit supporting evidence; no current purchase intent inferred.'}


async def run(slug, domain):
    if slug not in TOOLS: raise LabInputError('Unknown business tool')
    origin = safe_url(domain)
    if urlsplit(origin).path != '/': raise LabInputError('Supply a company domain, without a path')
    robots_url = origin + 'robots.txt'
    # A missing robots file permits crawling; other failures remain visible and fail closed.
    try:
        _, rules = await fetch(robots_url)
    except LabInputError as exc:
        # Cannot distinguish 404 from temporary failure through this surface: do not guess permission.
        raise LabInputError('Could not read robots.txt; source not crawled') from exc
    robots = RobotFileParser()
    robots.parse(rules.splitlines())
    if not robots.can_fetch(AGENT, origin): raise LabInputError('Source robots.txt disallows access')
    url, html = await fetch(origin)
    page = Page(html)
    result = {'tool': slug, 'checked_at': datetime.now(timezone.utc).isoformat(),
              'billing': 'disabled', 'source_url': url, 'source_requests': 2}
    if slug == 'company_card':
        card = company(page, url)
        return {**result, 'status': 'partial' if card['missing_fields'] else 'ok', **card,
                'limitations': 'Own-site claims, not a registry verification; homepage structured metadata only.'}
    links = []
    for href in page.links:
        try: target = safe_url(urljoin(url, href))
        except (LabInputError, ValueError): continue
        if (urlsplit(target).hostname == urlsplit(origin).hostname and target not in links
                and re.search(r'case-stud|/projects?/|/portfolio/|/realizacje/', urlsplit(target).path, re.I)
                and robots.can_fetch(AGENT, target)):
            links.append(target)
    records, errors = [], []
    for target in links[:3]:
        try:
            final, document = await fetch(target)
            records.append(project(Page(document), final))
        except (LabInputError, httpx.HTTPError, OSError, ValueError):
            errors.append({'source_url': target, 'status': 'unavailable'})
    return {**result, 'status': 'partial' if records else 'no_candidates',
            'source_requests': 2 + min(len(links), 3), 'candidates': records, 'errors': errors,
            'verified_projects': [], 'limitations': 'Discovery prototype, not yet a verified customer-project dataset. At most three same-site linked candidate pages.'}


async def execute(slug, domain):
    try:
        async with asyncio.timeout(25): return await run(slug, domain)
    except (httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
        raise LabInputError('Source unavailable or invalid; no facts inferred') from exc


def attach(app, engine, store, identity):
    """Separate business cohort: never rewrite the original 32 experiments."""
    from fastapi import Request, HTTPException
    from fastapi.responses import HTMLResponse
    from .core import Limited
    from pydantic import BaseModel, Field

    class Input(BaseModel):
        domain: str = Field(min_length=3, max_length=253)

    @app.get('/v1/business/catalog')
    async def catalog():
        return {'cohort': 'business-v1', 'billing': 'disabled', 'tools': [
            {'slug': slug, 'name': name, 'endpoint': '/v1/business/' + slug,
             'input': {'domain': 'public-company.example'},
             'stage': 'prototype', 'price': None} for slug, name in TOOLS.items()]}

    @app.get('/business/', response_class=HTMLResponse)
    async def directory():
        return '<h1>CompanyCard &amp; ProjectSignals</h1><p>Free public-source prototypes. No payments.</p>' + ''.join(
            '<h2>' + name + '</h2><p>POST /v1/business/' + slug + '</p>' for slug, name in TOOLS.items()) + '<p>CompanyCard extracts publisher metadata. ProjectSignals discovers candidate case studies; verified project database is not yet available.</p><a href="../docs">API documentation</a>'

    async def call(slug, body, request):
        if slug not in TOOLS: raise HTTPException(404, 'Unknown business tool')
        client = identity(request)
        outcome = 'error'
        try:
            # One global budget across REST and MCP, before any source reads.
            engine.gate('business-global', 'business')
            engine.gate(client, 'business-client')
            result = await execute(slug, body.domain)
            outcome = result['status']
            return result
        except Limited as exc: raise HTTPException(429, str(exc))
        except LabInputError as exc:
            outcome = 'invalid_or_unavailable_source'
            raise HTTPException(422, str(exc))
        finally:
            # Separate action namespace avoids affecting legacy cohort totals.
            store.event(client, 'business:' + slug, outcome)

    # Explicit annotations avoid local scope resolution of postponed annotations.
    async def endpoint(slug, body, request): return await call(slug, body, request)
    endpoint.__annotations__ = {'slug': str, 'body': Input, 'request': Request}
    app.post('/v1/business/{slug}')(endpoint)
