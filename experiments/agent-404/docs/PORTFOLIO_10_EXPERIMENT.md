# AIBITIOUS 404 LAB — pre-registered 10-tool experiment

## Hypothesis

Can independent AI agents discover, complete and repeatedly use a free, deterministic tool without outbound sales? Product discovery and willingness to pay are **different hypotheses**. This experiment tests only the first.

## Portfolio

| Slug | Job | Network |
| --- | --- | --- |
| cve_verify | Query one official NVD CVE record (original baseline) | Only fixed NVD host |
| json_guard | Validate JSON under a safe JSON Schema subset | None |
| csv_doctor | Report missing CSV cells and duplicate keys | None |
| invoice_audit | Check invoice arithmetic | None |
| secret_shield | Flag possible tokens without returning token values | None |
| openapi_preflight | Find incomplete OpenAPI operations | None |
| mcp_preflight | Lint server.json metadata | None |
| header_audit | Check supplied HTTP security headers | None |
| robots_check | Interpret supplied robots.txt content | None |
| schema_diff | Find added/deleted/changed JSON fields | None |

All nine LAB validators accept only bounded JSON POST bodies and use no external network calls. The existing CVE resolver remains on its legacy endpoint.

## Public surface and data safety

- Canonical root: https://aibitious.com/404/
- OpenAPI: https://aibitious.com/404/openapi.json
- MCP Streamable HTTP: https://aibitious.com/404/mcp/
- Per-tool REST: POST /404/v1/lab/{slug}; metadata GET /404/v1/lab/catalog
- No payments or user registration; x402 is off.
- Do not submit real private invoices, credentials, sensitive documents, live tokens or personal information.
- Raw requests and tool responses are **not** stored by LAB telemetry; event rows store time, HMAC network identity, tool, outcome, channel, test flag and latency.
- A *human* or *agent* identity is **not verified** by an anonymous request. Multiple agents behind NAT may share an identity and one agent may use several addresses.
- MCP identities are deliberately shared; number of independent MCP agents is unknown, so only call counts can be reported.
- Internal smoke tests must be labeled using a verified administrative token; unlabelled developer requests could contaminate the cohort.

## Exposure and fairness

All tools are published together, on the same host and under one MCP server. Compare only from the time the entire portfolio becomes live, and distinguish catalog visibility from actual calls. They have equal limits, same cost (free) and no paid promotions. Record any differences in descriptive documentation and placement; those may affect usage.

## Daily dashboard

Per tool:
1. successful calls (REST vs MCP);
2. requests resulting in issue findings versus malformed input;
3. distinct **estimated** REST client network IDs (not users);
4. returns: compare REST network IDs with calls on separate days (requires aggregate query, never unmask IP);
5. call share and completion rate; median/p95 latency where measurable;
6. CPU/memory usage and maintenance burden;
7. material privacy/security failures and abuse.

Count the CVE baseline separately and flag that it launched earlier. Prefer cross-tool comparisons for the common observation window.

## Decision rule

Run 30 full days from the first confirmed simultaneous public deployment (do not claim that prior CVE-only traffic is new portfolio traffic). Do not rank until the sample is meaningful.

- **Advance** up to two finalists only if there is credible repeated, non-internal usage, low error rate, nontrivial problem value and affordable servicing.
- **Improve/retest** if agent discovery seems blocked or observability cannot separate tests from external usage.
- **Reject** tools with no meaningful usage, avoidable unsafe inputs, poor reliability or unjustified marginal costs.
- Free usage is not evidence of willingness to pay. Payment tests belong to a separately approved phase, with explicit budget and settlement checks.

## Security: no "certified" claims

This is an experimental analysis suite, **not** a tax auditor, full JSON Schema compiler, credential verifier, penetration test, definitive robots permission service or MCP Registry validator. Inputs are untrusted. Returned "ok" means the checks implemented by that experiment did not detect a problem, not that the subject is safe or compliant.

The only external upstream in the portfolio is the original fixed NVD URL; never add arbitrary URL fetches.
