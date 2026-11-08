"""Agent-first experimental API. Payment collection is deliberately DISABLED."""
from __future__ import annotations
from contextlib import asynccontextmanager
import os
import secrets
import time
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .core import Resolver, Store, Limited, UpstreamFailed


class ResolveInput(BaseModel):
    identifier: Optional[str] = Field(None, max_length=32)
    question: Optional[str] = Field(None, max_length=500)
    consent_to_aggregate: bool = False


class GapInput(BaseModel):
    topic: str = Field(min_length=8, max_length=200)
    consent_to_aggregate: bool = False


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

    app = FastAPI(title='AIBITIOUS 404', version='0.1.0', lifespan=lifespan,
                  description='Evidence-based public CVE lookup and opt-in missing-data signal. No payments.')
    app.state.resolver = engine
    app.state.store = store

    def client_identity(request: Request) -> str:
        # Intentionally DO NOT trust user-supplied X-Forwarded-For or User-Agent as identity.
        # Reverse-proxy real IP handling needs deployment-specific trusted proxy config.
        addr = request.client.host if request.client else 'unknown'
        # Never allow a user-controlled header to bypass the per-client quota.
        return engine.identity(addr)

    @app.get('/', response_class=HTMLResponse, include_in_schema=False)
    async def landing():
        return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <title>AIBITIOUS 404 — verify public facts</title>
        <style>body{background:#0d1420;color:#e4ecf4;font:17px system-ui;max-width:800px;margin:10vh auto;padding:2rem}h1{font-size:3rem}a{color:#91c6ff}code,pre{background:#1b2836;padding:1rem;display:block;overflow:auto;border-radius:8px}p{line-height:1.6}</style>
        <h1>404 — What AI still can't verify</h1><p>One verifiable fact at a time. This experiment starts with official NIST CVE records; more categories are intentionally not claimed.</p>
        <pre>POST /v1/resolve\n{"identifier":"CVE-2024-3094"}</pre>
        <p><a href="/docs">OpenAPI docs</a> · <a href="/v1/catalog">Agent catalog</a> · <a href="/health">Health</a></p>
        <p>Free experimental access. No payments enabled. Do not submit secrets or personal information.</p></html>'''

    @app.get('/health')
    async def health():
        return {'status': 'ok', 'service': 'aibitious-404', 'version': '0.1.0'}

    @app.get('/v1/catalog')
    async def catalog():
        return {
            'name': 'AIBITIOUS 404', 'version': '0.1.0',
            'description': 'Verify an exact CVE via the US NIST National Vulnerability Database',
            'openapi': '/openapi.json', 'resolve': '/v1/resolve', 'report_gap': '/v1/gaps',
            'limitations': ['CVE only', 'official NVD data', 'not a penetration test', 'no payment support'],
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
