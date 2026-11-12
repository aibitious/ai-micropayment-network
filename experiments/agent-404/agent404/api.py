"""Agent-first experimental API. Payment collection is deliberately DISABLED."""
from __future__ import annotations
from contextlib import asynccontextmanager
import os
import ipaddress
import secrets
import time
from pathlib import Path
from typing import Optional, Any
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from .core import Resolver, Store, Limited, UpstreamFailed
from .lab import LabInputError, TOOLS, LIMITATIONS, describe_tools, run_lab
from . import web_ui
from . import wave2


class ResolveInput(BaseModel):
    identifier: Optional[str] = Field(None, max_length=32)
    question: Optional[str] = Field(None, max_length=500)
    consent_to_aggregate: bool = False


class GapInput(BaseModel):
    topic: str = Field(min_length=8, max_length=200)
    consent_to_aggregate: bool = False


class InterestInput(BaseModel):
    signal: str


def create_app(*, db_path: str | None = None, secret: str | None = None,
               resolver: Resolver | None = None) -> FastAPI:
    path = db_path or os.environ.get('DB_PATH', '/tmp/agent404-test.sqlite3')
    store = Store(path)
    # For production, provide an actual secret; ephemeral fallback weakens longitudinal metrics only.
    hash_secret = secret or os.environ.get('ANON_HASH_SECRET') or secrets.token_hex(32)
    engine = resolver or Resolver(store, hash_secret=hash_secret,
        daily_limit=int(os.environ.get('CLIENT_DAILY_LIMIT', '100')),
        per_minute_limit=int(os.environ.get('CLIENT_MINUTE_LIMIT', '5')),
        upstream_daily_limit=int(os.environ.get('UPSTREAM_DAILY_LIMIT', '150')))
    admin = os.environ.get('ADMIN_TOKEN', '')

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.prune()
        yield

    app = FastAPI(title='AIBITIOUS 404', version='0.3.0', lifespan=lifespan,
                  description='10 original LAB tools and an isolated second-wave prototype cohort. No payments.')
    app.state.resolver = engine
    app.state.store = store

    @app.middleware('http')
    async def canonical_prefix(request: Request, call_next):
        # Only the reverse proxy sets this exact header for /404/ requests.
        if (request.headers.get('host', '').lower() == 'aibitious.com'
                and request.headers.get('x-forwarded-prefix') == '/404'
                and not request.scope.get('path', '').startswith('/mcp')):
            request.scope['root_path'] = '/404'
        # Measure discovery separately from calls; never mistake these for people.
        path = request.scope.get('path', '')
        response = await call_next(request)
        path = path.rstrip('/') or '/'
        route_map = {
            '/': 'landing', '/tools': 'tools_directory',
            '/docs': 'docs', '/openapi.json': 'openapi',
            '/v1/catalog': 'catalog', '/v1/lab/catalog': 'lab_catalog',
            '/llms.txt': 'llms', '/robots.txt': 'robots',
            '/sitemap.xml': 'sitemap', '/.well-known/agent.json': 'agent_metadata',
            '/health': 'health_probe', '/wave2': 'wave2_directory',
            '/v1/wave2/catalog': 'wave2_catalog',
        }
        route = route_map.get(path)
        if path.startswith('/tools/') and request.method in ('GET', 'HEAD'):
            route = 'tool_detail'
        if path == '/mcp' or path.startswith('/mcp/'):
            route = 'mcp_http'  # HTTP requests, NOT individual agents or MCP sessions
        if route and request.method in ('GET', 'HEAD', 'POST'):
            ua = request.headers.get('user-agent', '').lower()
            segment = ('declared_automated' if any(word in ua for word in (
                'bot', 'crawler', 'spider', 'curl/', 'wget/', 'python-requests',
                'httpx/', 'headlesschrome', 'go-http-client', 'uptime'))
                       else 'unclassified')
            hints = {'landing', 'directory', 'docs', 'github', 'mcp',
                     'experiment', 'social', 'demo', 'site'}
            hint = request.query_params.get('src', '').lower()
            campaign = hint if hint in hints else 'unattributed'
            internal = bool(admin) and secrets.compare_digest(
                request.headers.get('x-404-internal-test', ''), admin)
            try:
                store.discovery_event(route, request.method, client_identity(request),
                                      segment, campaign, response.status_code, internal)
            except Exception:
                # Telemetry failures must not break user traffic. No sensitive input logged.
                import logging
                logging.getLogger(__name__).warning('404 discovery telemetry unavailable')
        return response

    trusted_proxies = {v.strip() for v in os.environ.get('TRUSTED_PROXY_IPS', '').split(',') if v.strip()}

    def client_identity(request: Request) -> str:
        # Never trust X-Forwarded-For, User-Agent or X-Real-IP from arbitrary peers.
        # The Caddy gateway overwrites X-Real-IP; only its exact Docker IP is trusted.
        peer = request.client.host if request.client else 'unknown'
        addr = peer
        if peer in trusted_proxies:
            raw = request.headers.get('x-real-ip', '').strip()
            if len(raw) <= 45:
                try:
                    parsed = ipaddress.ip_address(raw)
                except ValueError:
                    pass
                else:
                    if not (parsed.is_loopback or parsed.is_multicast or parsed.is_unspecified):
                        addr = str(parsed)
        return engine.identity(addr)

    # Some catalog crawlers use HEAD rather than GET to validate a public URL.
    @app.head('/', include_in_schema=False)
    @app.head('/tools/', include_in_schema=False)
    @app.head('/docs', include_in_schema=False)
    @app.head('/llms.txt', include_in_schema=False)
    @app.head('/sitemap.xml', include_in_schema=False)
    @app.head('/v1/catalog', include_in_schema=False)
    @app.head('/v1/lab/catalog', include_in_schema=False)
    @app.head('/health', include_in_schema=False)
    async def public_head():
        return Response(status_code=200)

    @app.head('/tools/{slug}', include_in_schema=False)
    async def public_tool_head(slug: str):
        if slug not in TOOLS:
            raise HTTPException(404, 'Unknown LAB tool')
        return Response(status_code=200)

    @app.get('/', response_class=HTMLResponse, include_in_schema=False)
    async def landing():
        return web_ui.landing()

    @app.get('/tools/', response_class=HTMLResponse, include_in_schema=False)
    async def tools_directory():
        return web_ui.directory()

    @app.get('/tools/{slug}', response_class=HTMLResponse, include_in_schema=False)
    async def tool_page(slug: str, request: Request):
        if slug not in TOOLS:
            raise HTTPException(404, 'Unknown LAB tool')
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        store.lab_event(slug, identity, 'page', 'view', 0, internal)
        return web_ui.tool_detail(slug)

    @app.head('/wave2/', include_in_schema=False)
    async def wave2_directory_head():
        return Response(status_code=200)

    @app.head('/wave2/{slug}', include_in_schema=False)
    async def wave2_tool_head(slug: str):
        if slug not in wave2.TOOLS:
            raise HTTPException(404, 'Unknown prototype')
        return Response(status_code=200)

    @app.get('/wave2/', response_class=HTMLResponse, include_in_schema=False)
    async def wave2_directory(request: Request):
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        for slug in wave2.TOOLS:
            store.wave2_event(slug, identity, 'discovery', 'directory', 'page', internal)
        return web_ui.wave2_directory()

    @app.get('/wave2/{slug}', response_class=HTMLResponse, include_in_schema=False)
    async def wave2_page(slug: str, request: Request):
        if slug not in wave2.TOOLS:
            raise HTTPException(404, 'Unknown prototype')
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        store.wave2_event(slug, identity, 'discovery', 'detail', 'page', internal)
        return web_ui.wave2_detail(slug)

    @app.get('/robots.txt', response_class=PlainTextResponse, include_in_schema=False)
    async def robots():
        return ('User-agent: *\nAllow: /\nDisallow: /v1/metrics\n'
                'Sitemap: https://aibitious.com/404/sitemap.xml\n')

    @app.get('/llms.txt', response_class=PlainTextResponse, include_in_schema=False)
    async def llms():
        return ("# AIBITIOUS 404 – verifiable CVE records\n\n"
                "Free public experiment: ten agent-facing experiments including official CVE lookup and nine offline validators. "
                "Does not scan hosts, execute code, or accept payments.\n\n"
                "- REST docs: https://aibitious.com/404/docs\n"
                "- OpenAPI: https://aibitious.com/404/openapi.json\n"
                "- Agent catalog: https://aibitious.com/404/v1/catalog\n"
                "- Streamable HTTP MCP: https://aibitious.com/404/mcp/\n"
                "- Tools: https://aibitious.com/404/tools/ and machine-readable https://aibitious.com/404/v1/lab/catalog\n"
                "- Limits: 20 KB per validator payload; all nine validators use in-memory input only.\n"
                "- No real secrets, personal records, financial documents or production data should be submitted.\n")

    @app.get('/sitemap.xml', include_in_schema=False)
    async def sitemap():
        xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
               "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
               "<url><loc>https://aibitious.com/404/</loc></url>"
               "<url><loc>https://aibitious.com/404/docs</loc></url>"
               "<url><loc>https://aibitious.com/404/v1/lab/catalog</loc></url>"
               "<url><loc>https://aibitious.com/404/tools/</loc></url>" +
               ''.join(f"<url><loc>https://aibitious.com/404/tools/{slug}</loc></url>" for slug in TOOLS)
               + "<url><loc>https://aibitious.com/404/wave2/</loc></url>"
               + ''.join(f"<url><loc>https://aibitious.com/404/wave2/{slug}</loc></url>" for slug in wave2.TOOLS)
               + "</urlset>")
        return Response(content=xml, media_type='application/xml')

    @app.get('/.well-known/agent.json', include_in_schema=False)
    async def agent_metadata():
        # Descriptive public metadata, NOT a claim of official MCP Registry enrollment.
        return {'name': 'AIBITIOUS 404', 'description': '32 free agent experiments: 10 original validators/CVE evidence and 22 offline decision simulations',
                'mcp': 'https://aibitious.com/404/mcp/',
                'openapi': 'https://aibitious.com/404/openapi.json',
                'registry_status': 'registered' if os.environ.get('MCP_REGISTRY_STATUS') == 'registered' else 'not_registered',
                'registry_name': 'io.github.aibitious/agent404' if os.environ.get('MCP_REGISTRY_STATUS') == 'registered' else None,
                'payments_enabled': False}

    @app.get('/health')
    async def health():
        return {'status': 'ok', 'service': 'aibitious-404', 'version': '0.3.0',
                'experiments': 10, 'wave2_prototypes': len(wave2.TOOLS)}

    @app.get('/v1/catalog')
    async def catalog():
        return {
            'name': 'AIBITIOUS 404 LAB', 'version': '0.2.0',
            'description': '10 free agent-facing experiments; CVE verification plus nine bounded deterministic offline tools',
            'openapi': '/openapi.json', 'resolve': '/v1/resolve', 'report_gap': '/v1/gaps',
            'lab_catalog': '/v1/lab/catalog', 'lab_tools': describe_tools(),
            'wave2_catalog': '/v1/wave2/catalog', 'wave2_prototypes': len(wave2.TOOLS),
            'limitations': ['Only CVE lookup fetches official NVD data', 'offline tools do not certify security, tax compliance or source correctness', 'no payment support'],
            'price': {'amount': 0, 'currency': 'USD', 'note': 'free experiment'},
            'mcp': {'endpoint': '/mcp/', 'note': 'present only when official SDK v2 is installed and enabled'},
            'privacy': 'Gap topics are saved only on explicit consent. Do not submit personal data or secrets.',
        }

    @app.post('/v1/resolve')
    async def resolve(query: ResolveInput, request: Request):
        identity = client_identity(request)
        if not query.identifier and not query.question:
            raise HTTPException(422, 'identifier or question is required')
        try:
            return await engine.resolve(identifier=query.identifier, question=query.question,
                consent_to_aggregate=query.consent_to_aggregate, identity=identity)
        except Limited as e:
            raise HTTPException(429, str(e), headers={'Retry-After': '60'})
        except UpstreamFailed:
            raise HTTPException(503, 'Official source temporarily unavailable',
                                headers={'Retry-After': '120'})

    @app.post('/v1/gaps')
    async def gap(query: GapInput, request: Request):
        identity = client_identity(request)
        try:
            engine.gate(identity, 'gap')
        except Limited as e:
            raise HTTPException(429, str(e), headers={'Retry-After':'60'})
        result = engine.report_gap(query.topic, query.consent_to_aggregate)
        store.event(identity, 'gap', result['status'])
        return result

    @app.get('/v1/lab/catalog')
    async def lab_catalog():
        return {'name': 'AIBITIOUS 404 LAB', 'version': '0.2.0',
                'experiments': 10, 'baseline': {'slug': 'cve_verify', 'endpoint': '/v1/resolve'},
                'tools': describe_tools(), 'billing': 'disabled',
                'privacy': 'Inputs processed in memory; no raw input stored in LAB telemetry. Use synthetic/public data only.'}

    @app.get('/v1/wave2/catalog')
    async def wave2_catalog(request: Request):
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        for slug in wave2.TOOLS:
            store.wave2_event(slug, identity, 'discovery', 'catalog', 'rest', internal)
        return {'name': 'AIBITIOUS 404 LAB wave two', 'version': '0.1.0',
                'prototypes': wave2.describe_tools(), 'billing': 'disabled',
                'privacy': 'No raw inputs are stored; use synthetic or public data only.'}

    @app.get('/v1/wave2/metrics', include_in_schema=False)
    async def wave2_metrics(authorization: str = Header(default='')):
        if not admin: raise HTTPException(503, 'admin metrics not configured')
        if not secrets.compare_digest(authorization, 'Bearer '+admin): raise HTTPException(403, 'forbidden')
        return store.wave2_metrics()

    @app.post('/v1/wave2/{slug}/interest')
    async def wave2_interest(slug: str, data: InterestInput, request: Request):
        if slug not in wave2.TOOLS: raise HTTPException(404, 'Unknown prototype')
        if data.signal not in ('pricing', 'pilot'): raise HTTPException(422, 'Invalid interest signal')
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        try: engine.gate(identity, 'wave2:interest:'+slug)
        except Limited as exc: raise HTTPException(429, str(exc), headers={'Retry-After':'60'})
        channel = ('rest_playground' if request.headers.get(
            'x-404-client-surface', '').lower() == 'web-playground' else 'rest')
        store.wave2_event(slug, identity, 'paid_demand_signal', data.signal, channel, internal)
        return {'status':'recorded', 'signal':data.signal,
                'note':'Self-reported interest only; no price, contact or payment is collected.'}

    @app.post('/v1/wave2/{slug}')
    async def wave2_call(slug: str, payload: dict[str, Any], request: Request):
        if slug not in wave2.TOOLS: raise HTTPException(404, 'Unknown prototype')
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        outcome = 'error'
        try:
            engine.gate(identity, 'wave2:'+slug)
            result = wave2.run(slug, payload)
            outcome = result['status']
            return result
        except Limited as exc:
            outcome = 'rate_limited'
            raise HTTPException(429, str(exc), headers={'Retry-After':'60'})
        except LabInputError as exc:
            outcome = 'invalid_input'
            raise HTTPException(422, str(exc))
        finally:
            channel = ('rest_playground' if request.headers.get(
                'x-404-client-surface', '').lower() == 'web-playground' else 'rest')
            store.wave2_event(slug, identity, 'launch', outcome, channel, internal)

    @app.post('/v1/lab/{slug}')
    async def lab_call(slug: str, payload: dict[str, Any], request: Request):
        if slug not in TOOLS:
            raise HTTPException(404, 'Unknown LAB experiment')
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        start = time.perf_counter()
        outcome = 'error'
        try:
            engine.gate(identity, 'lab:' + slug)
            result = run_lab(slug, payload)
            outcome = result['status']
            return result
        except Limited as exc:
            outcome = 'rate_limited'
            raise HTTPException(429, str(exc), headers={'Retry-After': '60'})
        except LabInputError as exc:
            outcome = 'invalid_input'
            raise HTTPException(422, str(exc))
        finally:
            ms = int((time.perf_counter()-start)*1000)
            # Browser demo is self-declared; it is REST but not an agent integration.
            channel = ('rest_playground' if request.headers.get(
                'x-404-client-surface', '').lower() == 'web-playground' else 'rest')
            store.lab_event(slug, identity, channel, outcome, ms, internal)

    @app.get('/v1/lab/metrics', include_in_schema=False)
    async def lab_metrics(authorization: str = Header(default='')):
        if not admin:
            raise HTTPException(503, 'admin metrics not configured')
        if not secrets.compare_digest(authorization, 'Bearer '+admin):
            raise HTTPException(403, 'forbidden')
        report = store.lab_metrics()
        report['discovery'] = store.discovery_metrics()
        return report

    @app.get('/v1/results/{result_id}')
    async def result(result_id: str):
        from uuid import UUID
        try: UUID(result_id)
        except (ValueError, AttributeError): raise HTTPException(404, 'not found')
        value = store.result(result_id)
        if not value: raise HTTPException(404, 'not found')
        return value

    @app.get('/v1/metrics', include_in_schema=False)
    async def metrics(authorization: str = Header(default='')):
        if not admin:
            raise HTTPException(503, 'admin metrics not configured')
        if not secrets.compare_digest(authorization, 'Bearer '+admin):
            raise HTTPException(403, 'forbidden')
        return store.metrics()

    @app.get('/v1/payments')
    async def payments():
        return {'enabled': False, 'protocol': 'x402', 'reason': 'testnet integration not yet verified; never accept funds in MVP'}

    return app


app = create_app()
