# AIBITIOUS 404 LAB — deployment history and current release boundary

## 13 November 2026 verification

- Public `GET /404/health` returned HTTP 200, version 0.3.0, `experiments: 10` and `wave2_prototypes: 22`.
- The public `/404/sitemap.xml` returned HTTP 200 with nine original tool pages and 22 second-wave pages; the CVE Verify page and `/robots.txt` and `/sitemap.xml` at the root domain returned 404.
- Product PR [#9](https://github.com/aibitious/ai-micropayment-network/pull/9) merged at `b7c8826de005fcc855a06b5b8018b054f4b407d9` after 83 local tests and successful GitHub `test`, `analyze` and `Slither` checks. Its 32-page sitemap, CVE page, corrected copy and directory-count fix are **not yet verified on production**.
- Parent-site PR [#3030](https://github.com/Aibitious-Labs/aibitious/pull/3030) remains draft; required `ci-gate` failed. Its updated homepage and root sitemap are **not live**. The existing static-site bridge manifest accepts only `index.html` and `aibitious.png`; robots/sitemap deployment requires a reviewed typed operation, green CI and exact-SHA receipt.
- Production SentinelX host was connected, but a normal `docker inspect agent404_experiment` returned Docker socket permission denied. Do not infer container resource state from that failed read. Host load was 9.49 (one-minute), memory available 11,707 MiB and swap 4,094/4,095 MiB used at inspection. Confirm capacity and quotas through the reviewed route before broad distribution.

The section below is the original 10 November release record, retained for chronology. Its version and tool counts are not current-status claims.

## Original release record — 10 November 2026

## Canonical service
- Site: https://aibitious.com/404/
- 10-tool directory: https://aibitious.com/404/tools/
- Machine catalog: https://aibitious.com/404/v1/lab/catalog
- OpenAPI: https://aibitious.com/404/docs
- Remote MCP: https://aibitious.com/404/mcp/
- Official MCP Registry: `io.github.aibitious/agent404@0.2.0`
- Code: draft PR #1 at https://github.com/aibitious/ai-micropayment-network/pull/1 (not merged)

## Scope and status
- One CVE Verify baseline + nine new offline validators = 10 experiments.
- Latest public `/health` response reports version 0.2.0 and `experiments:10`.
- Remote MCP initialization and `tools/list` publicly passed: 11 functions (10 tools + one missing-information reporter).
- The nine new REST endpoints each passed one **labeled internal smoke call** and returned HTTP 200.
- GitHub CI test workflow passed; v0.2.0 published through the OIDC-only publisher.
- No account creation, no payment collection or third-party AI API fees. x402 disabled.
- Daily read-only monitoring (30 scheduled runs) records data from 10 November 2026.

## Isolation and rollback
- Host workspace: `/srv/agent404-experiment`.
- Container: `agent404_experiment`; Docker Compose project `aibitious404`, persisted SQLite volume.
- Caddy serves the canonical `/404/` route on AIBITIOUS, has a route-scoped 32 KB body limit and connects to the project's isolated Docker bridge through a persistent Compose network declaration.
- Existing Caddy gateway remains shared with unrelated sites; this is not full machine isolation.
- Release source and pre-release backup are held separately under `/srv/agent404-experiment`; a Caddy configuration backup precedes the new 32 KB limit.
- Do not touch the production main site, mail, or other services. Do not use broad Docker Compose down.
- No DNS changes are required for `aibitious.com/404/`.

## Observability
- `GET /v1/lab/metrics` is bearer-admin protected.
- Privacy-safe lab events: experiment, HMAC client identity, channel (page/REST/MCP), outcome, latency, internal-test flag, timestamp. Raw request documents and matched secrets are not persisted.
- Anonymous MCP calls share a nonunique identity; only total call count can be inferred. REST distinct network IDs are approximate.
- Test calls are excluded when labeled with the administrative probe token; historic unlabeled smoke requests must not be called external users.
- A 200 response from a page or a registry listing proves uptime/discoverability, not adoption.

## Safety boundaries
- Never send real tokens, sensitive documents or customer invoices to a public experimental validator.
- These are bounded heuristics / structural validators, not official tax, legal or security compliance assessments.
- CVE Verify calls only the hardcoded NVD endpoint; all nine new validators are offline with no caller-supplied URL retrieval.
- The deployed app runs nonroot in a read-only container with CPU/RAM/process restrictions.
- Watch traffic, CPU, rate limits and denial-of-service conditions; review any incident before expanding capabilities.
