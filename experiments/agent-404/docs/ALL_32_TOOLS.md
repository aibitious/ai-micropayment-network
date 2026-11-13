# AIBITIOUS 404 LAB: all 32 free tools

The [original catalog](https://aibitious.com/404/tools/) contains CVE Verify and nine offline data/API checks. The [second-wave catalog](https://aibitious.com/404/wave2/) contains 22 offline agent-decision simulations. Each tool has its own page in the [32-page sitemap](https://aibitious.com/404/sitemap.xml). The [OpenAPI schema](https://aibitious.com/404/openapi.json), [original machine catalog](https://aibitious.com/404/v1/lab/catalog) and [second-wave machine catalog](https://aibitious.com/404/v1/wave2/catalog) provide current request shapes, examples and limitations.

## Reproduce a safe REST result

Use a synthetic input with a specific problem. For example, JSON Guard checks a required field and Action Policy simulates an approval decision:

```sh
curl -sS https://aibitious.com/404/v1/lab/json_guard \
  -H 'Content-Type: application/json' \
  -d '{"document":{"id":3},"schema":{"type":"object","required":["id"],"properties":{"id":{"type":"integer"}}}}'
```

```sh
curl -sS https://aibitious.com/404/v1/wave2/catalog
```

Select the `action_policy` example from the second response, then send it to `POST https://aibitious.com/404/v1/wave2/action_policy`. The catalog is the source for the full 22-example set. CVE Verify is different: `POST /404/v1/resolve` with a public CVE identifier contacts NVD when uncached and is subject to a separate upstream quota.

## Connect an MCP client

Configure an MCP client that supports Streamable HTTP with server URL `https://aibitious.com/404/mcp/` and registry name `io.github.aibitious/agent404`. Its `tools/list` should return 33 functions: 32 tools plus `report_missing_information`. For a first safe call, use `json_guard` with the synthetic JSON above. MCP transport requests or discovery do not count as tool completions.

## Usage and measurement

The service is free, has no payments and has bounded client and upstream quotas. Offline tools process bounded JSON in memory. Do not send secrets, personal records, real invoices or production payloads. These are advisory checks, not certification or production enforcement.

Use [the measurement protocol](GROWTH_MEASUREMENT.md) when reporting traffic. A catalog request is one discovery request, not 22 visitors. Page views, crawler requests, web demos, REST calls and completed MCP tool calls must remain distinct. HMAC network IDs are estimates and must not appear in reports. No user adoption is inferred from a registry listing.
