"""Official MCP SDK v2 adapter, shared engine; no fabricated payment support.

Run via `uvicorn agent404.mcp_server:app --host 127.0.0.1 --port 8080`.
The same FastAPI app serves REST and Streamable HTTP `/mcp/`.
"""
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from .api import create_app
from .core import Limited, UpstreamFailed

mcp = MCPServer('AIBITIOUS 404 - Official CVE Evidence')
rest = create_app()


@mcp.tool()
async def resolve_public_fact(identifier: str) -> dict:
    """Resolve one CVE identifier (e.g. CVE-2024-3094) using NIST NVD records.
    This tool does not execute code, scan targets, or accept arbitrary URLs.
    """
    engine = rest.state.resolver
    try:
        return await engine.resolve(identifier=identifier, identity=engine.identity('mcp-public'))
    except Limited:
        return {'status': 'rate_limited', 'message': 'Daily or per-minute request limit reached'}
    except UpstreamFailed:
        return {'status': 'unavailable', 'message': 'Official source temporarily unavailable'}


@mcp.tool()
async def report_missing_information(topic: str, consent_to_aggregate: bool = False) -> dict:
    """Opt-in report of a PUBLIC missing-data topic, never include private data or secrets."""
    engine = rest.state.resolver
    try:
        engine.gate(engine.identity('mcp-public'), 'gap')
    except Limited:
        return {'status': 'rate_limited'}
    return engine.report_gap(topic, consent_to_aggregate)


# One server-wide MCP quota rather than trusting an easily spoofed claim of client identity.
allowed = [s.strip() for s in os.getenv('MCP_ALLOWED_HOSTS', 'localhost:*,127.0.0.1:*').split(',') if s.strip()]
security = TransportSecuritySettings(allowed_hosts=allowed, allowed_origins=[])
rest.mount('/mcp', mcp.streamable_http_app(streamable_http_path='/', transport_security=security))

# Mount lifespan must start MCP session manager (the subapp lifespan does not run).
old_lifespan = rest.router.lifespan_context
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with old_lifespan(app):
        async with mcp.session_manager.run():
            yield
rest.router.lifespan_context = lifespan
app = rest
