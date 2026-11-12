# Agent404 LAB — Distribution and measurement protocol (2026-11-12)

This is an experiment, not a claim that MCP Registry registration produces customers.

## Canonical links

- Product: https://aibitious.com/404/
- Runnable demos: https://aibitious.com/404/tools/
- Typed REST catalog: https://aibitious.com/404/v1/lab/catalog
- MCP Streamable HTTP: https://aibitious.com/404/mcp/
- OpenAPI: https://aibitious.com/404/openapi.json
- Source: https://github.com/aibitious/ai-micropayment-network/tree/main/experiments/agent-404

## Distribution, without fake traffic

1. Create a separate, human-readable landing page for each use case, with working synthetic input and transparent limits. Test the tool before submitting it anywhere.
2. Link directly from the first-party homepage. Serve root-domain robots.txt/sitemap.xml and canonical metadata.
3. Update the official MCP Registry description only via the verified existing publisher. A registry listing is metadata, not an installation.
4. Submit accurate entries to relevant third-party directories only through their documented submission mechanisms; use the exact current URL, no bulk unsolicited messages, no click farms, no fabricated reviews and no claims of verified customers.
5. Publish reproducible tutorials (a REST request and an MCP connection example) in relevant documentation or developer communities where self-promotion is permitted.
6. Record submitted channel, date, accepted/pending/rejected status and *observed* conversions. Do not claim a listing accepted unless independently confirmed.
7. Do not market nine bounded offline validators as generic autonomous website scanners. No personal documents, live credentials, tax-certification, arbitrary URL fetching or code execution.

## Funnel semantics

- `landing / tools_directory / docs / tool_detail`: HTTP requests; may include known crawlers, own probes and browser sessions. Not unique human visitors.
- `mcp_http`: transport HTTP requests only. Not independent agents, not protocol initialization or tool calls.
- `lab_events channel=page`: per-tool page views.
- `lab_events channel=rest_playground`: client-declared web demo calls; HTTP REST requests, **not** external agent integrations.
- `lab_events channel=rest`: REST calls without the playground marker, still could be tests or scripts.
- `lab_events channel=mcp`: actual MCP tool execution, but uses a shared anonymous quota identity; unique agents cannot be inferred.
- `internal=1`: authenticated internal synthetic probe, excluded from acquisition and adoption metrics. All automated checks under our control should carry the existing authenticated internal marker.
- `declared_automated`: User-Agent declares an automated client; spoofable and incomplete.
- `unclassified`: everything else; **not** verified external people.
- `campaign`: allowlisted `src` hint supplied by the request; not authenticated attribution.
- Network identity: stable HMAC network identifier, *not* an account, person or independently installed agent. Returning count requires at least two distinct UTC dates.

## Daily report

Use the protected `GET /v1/lab/metrics` or direct read-only `Store.lab_metrics()` and `Store.discovery_metrics()`. Never expose bearer credentials, hashes, user-submitted data, raw IP addresses or log bodies. Present missing measurements as **brak danych** rather than zero. Keep CVE baseline separate: compare the portfolio only from 2026-11-10 UTC onward. Show tool outcomes, REST vs MCP vs demo, crawler declarations, source hints, estimated returning network IDs, latency, incidents, upstream rate limits and cost indicators. Confirm zero billing rather than assuming zero infrastructure costs.

Before deploying this instrumentation, historical discovery traffic was not measured. A new discovery table does not retrospectively recover it. For 30-day analysis, clearly annotate deployment date and avoid using pre-instrumentation zeros as evidence.

## Success criteria

A good signal is repeated, non-test task completion from multiple network identifiers plus independent evidence of integrations. A paid-market hypothesis needs voluntary pricing interest or real paid conversion after an explicitly authorized, legally reviewed billing rollout. Free API calls alone never prove paid demand.

At the end, select no more than two candidates and reject inconclusive results rather than manufacturing a winner.
