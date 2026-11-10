"""Official MCP SDK v2 adapter, shared engine; no fabricated payment support.

Run via `uvicorn agent404.mcp_server:app --host 127.0.0.1 --port 8080`.
The same FastAPI app serves REST and Streamable HTTP `/mcp/`.
"""
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from .api import create_app
from .core import Limited, UpstreamFailed
from .lab import LabInputError, run_lab
from . import wave2

mcp = MCPServer('AIBITIOUS 404 LAB - Ten Agent Experiments')
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


def _mcp_lab(slug: str, payload: dict) -> dict:
    # MCP is anonymous: one shared identity means MCP unique-agent count is unknown.
    engine = rest.state.resolver
    identity = engine.identity('mcp-public')
    start = time.perf_counter()
    outcome = 'error'
    try:
        engine.gate(identity, 'lab:' + slug)
        result = run_lab(slug, payload)
        outcome = result['status']
        return result
    except Limited:
        outcome = 'rate_limited'
        return {'status': 'rate_limited', 'tool': slug, 'retry_after_seconds': 60}
    except LabInputError as exc:
        outcome = 'invalid_input'
        return {'status': 'invalid_input', 'tool': slug, 'message': str(exc)}
    finally:
        rest.state.store.lab_event(slug, identity, 'mcp', outcome,
                                   int((time.perf_counter()-start)*1000))


@mcp.tool()
async def json_schema_guard(document: dict, schema: dict) -> dict:
    """Validate one JSON object against a SAFE subset of JSON Schema. No remote refs. Offline."""
    return _mcp_lab('json_guard', {'document': document, 'schema': schema})


@mcp.tool()
async def csv_data_doctor(csv_text: str, key_columns: list[str] | None = None,
                          delimiter: str = ',') -> dict:
    """Find missing fields, ragged CSV rows and duplicate key values; no raw rows are stored."""
    return _mcp_lab('csv_doctor', {'csv_text': csv_text,
                                  'key_columns': key_columns or [], 'delimiter': delimiter})


@mcp.tool()
async def invoice_math_audit(lines: list[dict], currency: str = '',
                             declared_net: str | None = None,
                             declared_tax: str | None = None,
                             declared_gross: str | None = None) -> dict:
    """Independently recalculate invoice arithmetic, NOT legal/tax compliance. Synthetic data only."""
    payload = {'lines': lines, 'currency': currency}
    for key,value in (('declared_net',declared_net),('declared_tax',declared_tax),('declared_gross',declared_gross)):
        if value is not None: payload[key] = value
    return _mcp_lab('invoice_audit', payload)


@mcp.tool()
async def secret_pattern_shield(text: str) -> dict:
    """Detect probable token patterns without returning or storing secret values. Never send real secrets."""
    return _mcp_lab('secret_shield', {'text': text})


@mcp.tool()
async def openapi_contract_preflight(spec: dict) -> dict:
    """Static OpenAPI 3.x lint: missing operation IDs, responses and malformed operations. Offline."""
    return _mcp_lab('openapi_preflight', {'spec': spec})


@mcp.tool()
async def mcp_registry_preflight(server: dict) -> dict:
    """Check a candidate MCP server.json metadata structure; this is NOT official validation."""
    return _mcp_lab('mcp_preflight', {'server': server})


@mcp.tool()
async def http_headers_audit(headers: dict[str, str]) -> dict:
    """Assess supplied HTTP security response headers. No network or live website probe."""
    return _mcp_lab('header_audit', {'headers': headers})


@mcp.tool()
async def robots_policy_check(robots_txt: str, agent: str = '*', path: str = '/') -> dict:
    """Evaluate supplied robots.txt for one agent/path. Not a legal scraping permission."""
    return _mcp_lab('robots_check', {'robots_txt': robots_txt, 'agent': agent, 'path': path})


@mcp.tool()
async def json_shape_diff(before: dict, after: dict) -> dict:
    """Compare JSON object shapes for added, deleted or changed field types. Offline."""
    return _mcp_lab('schema_diff', {'before': before, 'after': after})


def _mcp_wave2(slug: str, payload: dict) -> dict:
    engine = rest.state.resolver
    identity = engine.identity('mcp-public')
    outcome = 'error'
    try:
        engine.gate(identity, 'wave2:' + slug)
        result = wave2.run(slug, payload)
        outcome = result['status']
        return result
    except Limited:
        outcome = 'rate_limited'
        return {'status': 'rate_limited', 'tool': slug}
    except LabInputError as exc:
        outcome = 'invalid_input'
        return {'status': 'invalid_input', 'tool': slug, 'message': str(exc)}
    finally:
        rest.state.store.wave2_event(slug, identity, 'launch', outcome, 'mcp')


@mcp.tool()
async def simulate_agent_action_policy(action: dict, rules: list[dict]) -> dict:
    """Dry-run one proposed tool action against explicit allow/deny/approval rules; no enforcement."""
    return _mcp_wave2('action_policy', {'action': action, 'rules': rules})


@mcp.tool()
async def plan_workflow_recovery(steps: list[dict]) -> dict:
    """Plan reverse-order compensations for a supplied workflow DAG; never execute actions."""
    return _mcp_wave2('workflow_recovery', {'steps': steps})


@mcp.tool()
async def triage_webhook_deliveries(attempts: list[dict]) -> dict:
    """Find duplicate, failed and rate-limited deliveries from supplied HTTP status metadata."""
    return _mcp_wave2('webhook_triage', {'attempts': attempts})


@mcp.tool()
async def check_claim_provenance(claims: list[dict], sources: list[dict]) -> dict:
    """Check whether supplied claim references reach at least one declared source; not fact checking."""
    return _mcp_wave2('claim_provenance', {'claims': claims, 'sources': sources})


@mcp.tool()
async def minimize_agent_data(fields: list[dict], allowed_fields: list[str],
                              max_retention_days: int) -> dict:
    """Check declared fields, retention and model transfer against a supplied local policy."""
    return _mcp_wave2('data_minimizer', {'fields': fields, 'allowed_fields': allowed_fields,
                                        'max_retention_days': max_retention_days})


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
