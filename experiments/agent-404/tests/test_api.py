import os
import pytest
from fastapi.testclient import TestClient
from agent404.api import create_app
from agent404.core import Resolver, Limited, UpstreamFailed

CVE = 'CVE-2024-3094'
FAKE_NVD = {
    'vulnerabilities': [
        {'cve': {'id': CVE, 'published':'2024-03-29T15:15:47.000',
                 'lastModified':'2024-04-02T12:00:00.000',
                 'vulnStatus':'Analyzed',
                 'descriptions':[{'lang':'en','value':'Test fixture: xz compromised distribution'}],
                 'metrics':{'cvssMetricV31':[{'cvssData':{'baseScore':10.0}}]},
                 'cisaExploitAdd': None}}
    ]
}


def test_health_and_catalog(client):
    assert client.get('/health').json()['status'] == 'ok'
    catalog = client.get('/v1/catalog').json()
    assert catalog['price']['amount'] == 0
    assert 'CVE' in catalog['description']
    assert client.get('/v1/payments').json()['enabled'] is False


def test_resolve_evidence_and_cache(client, app, monkeypatch):
    count={'n':0}
    async def fake_fetch(identifier):
        count['n'] += 1
        assert identifier == CVE
        return FAKE_NVD
    monkeypatch.setattr(app.state.resolver,'fetch_nvd',fake_fetch)
    first = client.post('/v1/resolve',json={'question':f'Is {CVE} official?'}).json()
    assert first['status']=='verified'
    assert first['answer']['cvss'][0]['score'] == 10.0
    assert first['evidence'][0]['publisher'].startswith('NIST')
    assert first['evidence'][0]['api_url'].endswith(CVE)
    assert first['reused'] is False
    second=client.post('/v1/resolve',json={'identifier': CVE}).json()
    assert second['reused'] is True
    assert first['id'] == second['id']
    assert count['n'] == 1
    assert client.get('/v1/results/'+first['id']).json()['identifier'] == CVE


def test_nvd_empty_not_verified(client,app,monkeypatch):
    async def empty(identifier): return {'vulnerabilities':[]}
    monkeypatch.setattr(app.state.resolver,'fetch_nvd',empty)
    out=client.post('/v1/resolve',json={'identifier':'CVE-2026-999999999'}).json()
    assert out['status']=='not_verified' and out['answer'] is None
    assert out['evidence']==[]


def test_upstream_failure_is_not_fabricated(client,app,monkeypatch):
    async def bad(identifier): raise UpstreamFailed('fail')
    monkeypatch.setattr(app.state.resolver,'fetch_nvd',bad)
    res=client.post('/v1/resolve',json={'identifier':CVE})
    assert res.status_code == 503 and 'temporarily' in res.text


def test_unsupported_and_opt_in_gaps(client):
    r=client.post('/v1/resolve',json={'question':'What is the current berth status at Port X?'}).json()
    assert r['status']=='unsupported' and r['gap']['status']=='not_recorded'
    r=client.post('/v1/gaps',json={'topic':'public rates on port dues', 'consent_to_aggregate':True}).json()
    assert r['status']=='recorded'
    r=client.post('/v1/gaps',json={'topic':'please use sk-p3456PrivateToken and email user@example.com', 'consent_to_aggregate':True}).json()
    assert r['status']=='not_recorded'


def test_no_user_url_fetch(client,app,monkeypatch):
    async def fail_if_called(identifier): raise AssertionError('unexpected network access')
    monkeypatch.setattr(app.state.resolver,'fetch_nvd',fail_if_called)
    r=client.post('/v1/resolve',json={'question':'Open http://169.254.169.254/latest/meta-data/'}).json()
    assert r['status']=='unsupported'


def test_multiple_cves_are_not_implicitly_summarized(client):
    out=client.post('/v1/resolve',json={'question':'compare CVE-2024-3094 and CVE-2023-4863'}).json()
    assert out['status']=='unsupported'


def test_rate_limiter(tmp_path):
    app=create_app(db_path=str(tmp_path/'tiny.sqlite3'),secret='secret')
    app.state.resolver.daily_limit=1
    with TestClient(app) as c:
        assert c.post('/v1/resolve',json={'question':'unsupported test query'}).status_code==200
        assert c.post('/v1/resolve',json={'question':'unsupported test query'}).status_code==429


def test_upstream_budget_shared(tmp_path,monkeypatch):
    app=create_app(db_path=str(tmp_path/'budget.sqlite3'),secret='secret')
    app.state.resolver.upstream_daily_limit=1
    async def fake_fetch(identifier):return {'vulnerabilities':[]}
    monkeypatch.setattr(app.state.resolver,'fetch_nvd',fake_fetch)
    with TestClient(app) as c:
        assert c.post('/v1/resolve',json={'identifier':'CVE-2025-99999999'}).status_code==200
        assert c.post('/v1/resolve',json={'identifier':'CVE-2025-99999998'}).status_code==429


def test_admin_denied_without_secret(client):
    assert client.get('/v1/metrics').status_code == 503


def test_admin_protected(tmp_path,monkeypatch):
    monkeypatch.setenv('ADMIN_TOKEN', 'strong-example-admin')
    app=create_app(db_path=str(tmp_path/'admin.sqlite3'),secret='secret')
    with TestClient(app) as c:
        assert c.get('/v1/metrics').status_code==403
        assert c.get('/v1/metrics',headers={'Authorization':'Bearer strong-example-admin'}).status_code==200


def test_invalid_identifier_does_not_query(client, app, monkeypatch):
    async def fail_if_called(identifier): raise AssertionError('should not fetch')
    monkeypatch.setattr(app.state.resolver,'fetch_nvd',fail_if_called)
    assert client.post('/v1/resolve',json={'identifier':'../../etc/passwd'}).json()['status']=='unsupported'
    assert client.post('/v1/resolve',json={'identifier':'CVE-2025-12'}).json()['status']=='unsupported'


def test_nonexistent_result(client):
    assert client.get('/v1/results/abc').status_code==404
    assert client.get('/v1/results/00000000-0000-0000-0000-000000000000').status_code==404


def test_discovery_endpoints(client):
    assert 'https://aibitious.com/404/mcp/' in client.get('/llms.txt').text
    assert 'Sitemap:' in client.get('/robots.txt').text
    assert '<urlset' in client.get('/sitemap.xml').text
    data = client.get('/.well-known/agent.json').json()
    assert data['payments_enabled'] is False
    assert data['registry_status'] == 'not_registered'


def test_global_nvd_short_window_limit(tmp_path, monkeypatch):
    app = create_app(db_path=str(tmp_path/'global-short.sqlite3'), secret='secret')
    app.state.resolver.daily_limit = 100
    app.state.resolver.per_minute_limit = 100
    async def fake_fetch(identifier):
        return {'vulnerabilities': []}
    monkeypatch.setattr(app.state.resolver, 'fetch_nvd', fake_fetch)
    with TestClient(app) as client:
        first = client.post('/v1/resolve', json={'identifier': 'CVE-2026-77777701'})
        second = client.post('/v1/resolve', json={'identifier': 'CVE-2026-77777702'})
        assert first.status_code == 200
        assert second.status_code == 429
        assert 'short-window' in second.text


def test_prefixed_openapi_docs(client):
    headers={'Host':'aibitious.com','X-Forwarded-Prefix':'/404'}
    response=client.get('/docs',headers=headers)
    assert response.status_code==200
    assert '/404/openapi.json' in response.text
    assert client.get('/health',headers=headers).status_code==200


def test_untrusted_forwarded_client_ip_cannot_bypass_quota(tmp_path):
    app=create_app(db_path=str(tmp_path/'untrusted.sqlite3'),secret='secret')
    app.state.resolver.daily_limit=1
    with TestClient(app) as c:
        assert c.post('/v1/resolve',json={'question':'public unknown item'}, headers={'X-Real-IP':'198.51.100.1'}).status_code==200
        assert c.post('/v1/resolve',json={'question':'public unknown item'}, headers={'X-Real-IP':'198.51.100.2'}).status_code==429


def test_trusted_reverse_proxy_separates_client_quotas(tmp_path,monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXY_IPS','testclient')
    app=create_app(db_path=str(tmp_path/'trusted.sqlite3'),secret='secret')
    app.state.resolver.daily_limit=1
    with TestClient(app) as c:
        assert c.post('/v1/resolve',json={'question':'public unknown item'}, headers={'X-Real-IP':'198.51.100.1'}).status_code==200
        assert c.post('/v1/resolve',json={'question':'public unknown item'}, headers={'X-Real-IP':'198.51.100.2'}).status_code==200
        assert c.post('/v1/resolve',json={'question':'public unknown item'}, headers={'X-Real-IP':'198.51.100.2'}).status_code==429


def test_registry_flag_can_reflect_verified_publication(tmp_path, monkeypatch):
    monkeypatch.setenv('MCP_REGISTRY_STATUS', 'registered')
    app=create_app(db_path=str(tmp_path/'registry.sqlite3'),secret='secret')
    with TestClient(app) as c:
        metadata=c.get('/.well-known/agent.json').json()
        assert metadata['registry_status'] == 'registered'
        assert metadata['registry_name'] == 'io.github.aibitious/agent404'
