# AIBITIOUS 404 — agent-first missing-information experiment

**Status: LIVE free API experiment at https://aibitious.com/404/; no payments enabled. MCP Registry publishing is configured through GitHub Actions OIDC; verify public listing separately.**

Goal: test whether independently operated AI agents discover and reuse a small, evidence-backed information API. The *first vertical* is deliberately narrow: resolving exact CVE IDs against the official NIST National Vulnerability Database (NVD). The project's long-term idea is to detect recurring missing-information needs, but this repository does **not** claim to verify arbitrary facts.

## What is implemented

- `POST /v1/resolve` — identifier or question containing **one** `CVE-YYYY-NNNN...`, return official metadata with source URL and observation time; `unsupported` or `not_verified` instead of fabricating a fact.
- `POST /v1/gaps` — opt-in registration of public missing-information topics, with basic sensitive-input rejection and deduplication.
- `GET /v1/results/{id}` — retrieve previously resolved public result by UUID.
- `GET /v1/catalog`, `/health`, `/openapi.json`, `/docs`, `/llms.txt`, `/robots.txt`, `/sitemap.xml`, `/.well-known/agent.json` — agent/web discovery, operational health and API schema. The `agent.json` is only descriptive metadata, not a claim of official registry support.
- `GET /v1/metrics` — protected by bearer admin token; returns 30-day event totals and frequent public gaps. User/client counts are **estimates** based on HMAC-hashed network addresses, not verified humans or agents.
- SQLite cache, retention pruning, API quotas, 80/day default global upstream ceiling plus one uncached NVD fetch per ten seconds (to protect the NVD no-key rate allowance), short HTTP timeouts and a fixed upstream hostname (no arbitrary URL fetching).
- Official MCP SDK v2 adapter (`/mcp/`) with two tools. SDK dependency is required. Remote HTTPS MCP initialization and a real SDK `tools/list` and `tools/call` were successfully validated. All MCP clients share a conservative quota.
- Payments are explicitly **disabled**. `GET /v1/payments` states this; no wallet, facilitator or paid mainnet route is configured.

## Start locally

Requires Python 3.11+.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
export DB_PATH="$PWD/local-404.sqlite3"
export ANON_HASH_SECRET="$(python -c 'import secrets;print(secrets.token_hex(32))')"
export ADMIN_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export MCP_ALLOWED_HOSTS='127.0.0.1:*,localhost:*'
uvicorn agent404.mcp_server:app --host 127.0.0.1 --port 8080 --workers 1 --no-access-log
```

In a second terminal:

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/v1/catalog
curl -fsS -X POST http://127.0.0.1:8080/v1/resolve \
  -H 'Content-Type: application/json' \
  -d '{"identifier":"CVE-2024-3094"}'
# JSON-RPC MCP Streamable HTTP is at http://127.0.0.1:8080/mcp/
pytest -q
```

The default dev REST entrypoint `uvicorn agent404.api:app` works without the MCP extra for offline smoke tests; it is not the full product.

## Isolated Docker staging (tested on an existing controlled HTTPS domain)

```bash
cp .env.example .env
# Replace placeholders with cryptographically random secrets; update allowed hostnames.
cd deploy
# docker compose config  # first validate
# docker compose up -d --build  # only in an authorized, isolated deployment directory
```

The compose file exposes only `127.0.0.1:18044` on the Docker host, runs as non-root with dropped capabilities and CPU/memory limits. It cannot directly modify other project databases. A separate TLS reverse proxy and DNS are required for a NEW deployment. The controlled experiment has already been installed behind Caddy; there is **no automatic install, DNS edit, service restart or GitHub Action deployment** for subsequent clones.

## Experiment success thresholds (pre-registered, not forecasts)

Within 30 days of a **public** launch: 100 independent external integrations (estimated), 20 separate payers **only after payments are properly enabled**, 25% returning integrations, positive per-request contribution margin, and zero critical security incidents. Before payment integration, substitute measurable repeat intent (returning use of the free endpoint) and treat willingness-to-pay as unproven. The live experiment began on **9 November 2026**; end-of-window analysis is due around **8 December 2026**.

**No automatic customer discovery guarantee:** listing MCP or publishing an API does not cause ChatGPT or other agents to install it. Distinguish visitors, crawlers, API clients, controlled tests and payment-capable autonomous agents. Use the public tool protocol and discovery routes as the experiment, not as evidence of traction.

## Privacy and limitations

- Do not send secrets, private company data, personal data or IP addresses as gap topics; the demo's PII filter is not exhaustive. The API refuses obvious emails, links, credential prefixes and IPv4 strings, but a human security review is still required before opening user-supplied text to the public.
- Gap topics are stored **only** with explicit `consent_to_aggregate=true`. They are retained up to 90 days since last observation. Event identity is an HMAC of network address with a deployment secret; never log raw IP in application telemetry. Reverse proxy access logs need separate retention controls.
- A NVD record is evidence that NVD currently lists a given CVE, **not proof** of actual exploitation, completeness or the correctness of every description. Citation links are public record pages. Do not interpret CVSS and CISA fields as independent validation.
- NVD may reject, rate-limit or be unavailable. The API returns 503, does not hallucinate. Data can become stale; cache TTL is 24h for found records, 1h for absent records.
- Single-process, single-worker SQLite implementation. For significant public traffic use managed Postgres, a central rate limiter, abuse controls and security testing before expanding. No claims of production grade robustness.
- No billing, wallets, transactions, user accounts, admin UI, database of all knowledge, web scraper, or self-directed outbound requests.

## Developer workflow

Run `pytest -q` locally. CI is supplied at `.github/workflows/test.yml` for a standalone repository. It checks tests only and does not deploy automatically. Local env secrets are gitignored.

Current research references:

- [Official MCP Python SDK v2](https://py.sdk.modelcontextprotocol.io/)
- [Mount MCP in existing ASGI app](https://py.sdk.modelcontextprotocol.io/run/asgi/)
- [MCP Registry publishing requirements](https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/official-registry-requirements.md)
- [x402 V2 specification](https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md)
- [NVD API](https://nvd.nist.gov/developers/vulnerabilities)

## Roadmap — remaining external steps

1. **Completed:** Provisioned a new isolated writable service at `/srv/agent404-experiment` with generated local-only secrets. Do not reuse an unrelated project's directory.
2. **Completed in draft PR #1:** source on an isolated branch of `aibitious/ai-micropayment-network`, with dedicated CI and 18 local tests (16 at initial go-live). No merge to its default branch.
3. **Completed:** TLS hostname `aibitious.com/404` and restricted MCP allowed Hosts, trusted proxy forwarding, quotas and privacy controls. Still a pilot, not an audited security product.
4. **Completed:** isolated Docker instance, Caddy HTTPS, real NVD lookup, remote MCP initialization and SDK tool call. Existing site sanity checks returned their expected responses.
5. **Partially completed:** `server.json` passed official registry validation; an Ed25519 public DNS TXT proof was published, but publisher identity authentication and official registry publishing remain blocked/not performed. Do not claim official listing.
6. For x402 use a **testnet only** first; require an authenticated facilitator supporting V2 and an authorized settlement destination. Never copy private keys to source files or enable mainnet without a separate financial/legal gate.
7. **Started:** 30 daily read-only check-ins for 9 November–8 December 2026. Internal smoke tests exist in the counters; do not mislabel them as organic traffic. Measure real traffic, costs and retention before a go/no-go decision.

## Live experiment and safety

- **Website:** https://aibitious.com/404/ · [OpenAPI](https://aibitious.com/404/docs) · [MCP endpoint](https://aibitious.com/404/mcp/)
- **Development branch:** https://github.com/aibitious/ai-micropayment-network/pull/1 (draft; not merged).
- **Registry:** metadata validated but **not published**. Merely hosting an MCP endpoint does not make it automatically discoverable by every AI agent.
- **No money movement:** `x402` is deliberately disabled and no live wallet, settlement or payment collection has been configured.
- **Caveat:** counting hashed IPs approximates API clients, not agent identities or unique users. Operators must mark smoke tests separately from organic traffic.