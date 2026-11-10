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
        return await call_next(request)

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

    @app.get('/', response_class=HTMLResponse, include_in_schema=False)
    async def landing():
        return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <title>AIBITIOUS 404 — verify public facts</title>
        <style>body{background:#0d1420;color:#e4ecf4;font:17px system-ui;max-width:800px;margin:10vh auto;padding:2rem}h1{font-size:3rem}a{color:#91c6ff}code,pre{background:#1b2836;padding:1rem;display:block;overflow:auto;border-radius:8px}p{line-height:1.6}</style>
        <h1>404 LAB — Ten experiments for AI agents</h1><p>Free machine-readable tools for data quality, security signals, API preflight and official CVE evidence. No promises of guaranteed compliance or autonomous discovery.</p>
        <pre>POST v1/resolve\n{"identifier":"CVE-2024-3094"}</pre>
        <p><a href="docs">OpenAPI docs</a> · <a href="tools/">10 tools</a> · <a href="wave2/">New prototypes</a> · <a href="v1/catalog">Agent catalog</a> · <a href="health">Health</a></p>
        <p>Free experimental access. No payments enabled. Do not submit secrets or personal information.</p></html>'''

    @app.get('/tools/', response_class=HTMLResponse, include_in_schema=False)
    async def tools_directory():
        links = ''.join(
            f'<li><a href="{slug}">{title}</a> — {desc}</li>'
            for slug, (title, desc) in TOOLS.items()
        )
        return ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>AIBITIOUS 404 LAB: 10 free agent tools</title>'
                '<style>body{max-width:800px;margin:5vh auto;padding:1em;font:17px system-ui;line-height:1.7}</style>'
                '<h1>Ten experiments. One shared scoreboard.</h1>'
                '<p>CVE Verify is already running at <a href="../docs">/v1/resolve</a>. '
                'The other nine experiments run offline and are free.</p><ol>' + links + '</ol>'
                '<p><a href="../v1/lab/catalog">Machine-readable catalog</a> · '
                '<a href="../docs">OpenAPI documentation</a> · '
                '<a href="../">AIBITIOUS 404</a></p>'
                '<p>Experimental checks are not compliance, legal or tax certification. '
                'Do not submit sensitive or private real-world data.</p></html>')

    @app.get('/tools/{slug}', response_class=HTMLResponse, include_in_schema=False)
    async def tool_page(slug: str, request: Request):
        if slug not in TOOLS:
            raise HTTPException(404, 'Unknown LAB tool')
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        store.lab_event(slug, identity, 'page', 'view', 0, internal)
        title, desc = TOOLS[slug]
        from html import escape
        title = escape(title)
        desc = escape(desc)
        return ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{title} — AIBITIOUS 404 LAB</title>'
                '<style>body{max-width:800px;margin:5vh auto;padding:1em;font:17px system-ui;line-height:1.7}</style>'
                f'<h1>{title}</h1><p>{desc}</p>'
                f'<p><strong>REST:</strong> POST https://aibitious.com/404/v1/lab/{slug}</p>'
                '<p><strong>MCP:</strong> https://aibitious.com/404/mcp/ (find matching tool name in tools/list)</p>'
                f'<p>Free experimental use. {escape(LIMITATIONS[slug])}</p>'
                '<p><a href="../v1/lab/catalog">Input specifications</a> · '
                '<a href="../docs">API schema</a> · <a href="./">All tools</a></p>'
                '<p>Process only synthetic or non-sensitive data. No payments accepted.</p></html>')

    @app.get('/wave2/', response_class=HTMLResponse, include_in_schema=False)
    async def wave2_directory(request: Request):
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        for slug in wave2.TOOLS:
            store.wave2_event(slug, identity, 'discovery', 'directory', 'page', internal)
        links = ''.join(f'<li><a href="{slug}">{name}</a> — {desc}</li>'
                        for slug, (name, desc) in wave2.TOOLS.items())
        return ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>404 LAB — wave two</title><h1>{len(wave2.TOOLS)} agent-first prototypes</h1><ul>'
                + links + '</ul><p>Free, offline simulations. Do not send private or sensitive data.</p>'
                '<p><a href="../tools/">Original 10 LAB tools</a> · '
                '<a href="../v1/wave2/catalog">Agent catalog</a></p></html>')

    @app.get('/wave2/{slug}', response_class=HTMLResponse, include_in_schema=False)
    async def wave2_page(slug: str, request: Request):
        if slug not in wave2.TOOLS: raise HTTPException(404, 'Unknown prototype')
        identity = client_identity(request)
        internal = bool(admin) and secrets.compare_digest(request.headers.get('x-404-internal-test', ''), admin)
        store.wave2_event(slug, identity, 'discovery', 'detail', 'page', internal)
        from html import escape
        name, desc = wave2.TOOLS[slug]
        return ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{escape(name)} — 404 LAB</title><h1>{escape(name)}</h1>'
                f'<p>{escape(desc)}</p><p>POST /404/v1/wave2/{slug} · MCP /404/mcp/</p>'
                f'<p>{escape(wave2.LIMITATIONS[slug])}</p>'
                '<p>Would you consider a paid version?</p>'
                '<button type="button" data-signal="pricing">Show me pricing later</button> '
                '<button type="button" data-signal="pilot">I would test a paid pilot</button>'
                '<p id="signal-result" role="status"></p>'
                '<script>document.querySelectorAll("[data-signal]").forEach(button => '
                'button.addEventListener("click", async () => {'
                f'const response = await fetch("../v1/wave2/{slug}/interest", {{'
                'method:"POST", headers:{"Content-Type":"application/json"},'
                'body:JSON.stringify({signal:button.dataset.signal})});'
                'document.getElementById("signal-result").textContent = response.ok ? '
                '"Thanks. This is an anonymous interest signal, not a purchase." : '
                '"Could not record this signal."; }));</script>'
                '<p>No contact details or payment are collected.</p>'
                '<p><a href="../v1/wave2/catalog">Input catalog</a> · '
                '<a href="./">All prototypes</a></p></html>')

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
        return {'name': 'AIBITIOUS 404', 'description': '10 free agent tools: official CVE evidence and nine deterministic checks',
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
        store.wave2_event(slug, identity, 'paid_demand_signal', data.signal, 'rest', internal)
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
            store.wave2_event(slug, identity, 'launch', outcome, 'rest', internal)

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
            store.lab_event(slug, identity, 'rest', outcome, ms, internal)

    @app.get('/v1/lab/metrics', include_in_schema=False)
    async def lab_metrics(authorization: str = Header(default='')):
        if not admin:
            raise HTTPException(503, 'admin metrics not configured')
        if not secrets.compare_digest(authorization, 'Bearer '+admin):
            raise HTTPException(403, 'forbidden')
        return store.lab_metrics()

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
