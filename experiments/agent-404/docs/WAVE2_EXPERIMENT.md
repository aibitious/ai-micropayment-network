# AIBITIOUS 404 LAB — wave two, 10 November 2026

## Decision basis

This is an exploratory ranking, not proof that a market is empty. Scores are 1–5
for specific unmet job, agent fit, potential paid value, safe zero-cost prototype,
and differentiation. Maximum 25. Competitor examples are direct vendor or project
sources checked 10 November 2026:

- [LangSmith](https://www.langchain.com/langsmith/observability) and
  [Braintrust](https://www.braintrust.dev/) already cover broad agent tracing and evaluations.
- [Arize Phoenix](https://arize.com/phoenix) offers open-source tracing and evals.
- [Cedar](https://docs.cedarpolicy.com/auth/authorization.html) has mature allow/deny authorization semantics.
- [Temporal](https://docs.temporal.io/design-patterns) supports durable retries and Saga compensation.
- [Svix](https://docs.svix.com/ai/dashboard-mcp) exposes webhook diagnosis and replay through MCP.
- [NVIDIA SkillSpector](https://github.com/NVIDIA/skillspector) scans agent skills for security risks.

The opportunity hypothesis is a **small, framework-neutral, offline decision aid**
that an agent can call before a risky next step. None of the selected tools claims
to replace the production systems above.

| Candidate | Need | Agent fit | Paid value | Safe build | Difference | Total | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Action Policy Simulator | 5 | 5 | 5 | 5 | 3 | 23 | Build |
| Workflow Recovery Planner | 5 | 5 | 5 | 5 | 3 | 23 | Build |
| Claim Provenance Check | 5 | 5 | 4 | 5 | 4 | 23 | Build |
| Data Minimizer | 5 | 5 | 4 | 5 | 3 | 22 | Build |
| Webhook Delivery Triage | 4 | 5 | 4 | 5 | 3 | 21 | Build |
| Agent cost budget planner | 4 | 5 | 4 | 4 | 2 | 19 | Defer: overlaps monitoring |
| Human approval handoff linter | 4 | 4 | 4 | 5 | 2 | 19 | Defer: overlaps policy simulator |
| Incident timeline assembler | 4 | 4 | 4 | 4 | 2 | 18 | Defer: broad incident tools |
| Agent skill risk scanner | 5 | 5 | 4 | 4 | 1 | 19 | Defer: existing strong scanner |
| Agent trace anomaly detector | 4 | 5 | 4 | 2 | 1 | 16 | Defer: tracing stack and data costs |
| Live website permission auditor | 4 | 4 | 3 | 1 | 2 | 14 | Defer: SSRF and outbound probing |
| Multi-provider agent router | 4 | 5 | 4 | 1 | 1 | 15 | Defer: provider fees and mature gateways |

Scores are judgments for prioritizing this test, not market measurements. The
research does not establish that customers will pay or that the five jobs are
unserved. In particular, Cedar, Temporal and Svix solve parts of these jobs.

## Isolation and interfaces

The five new implementations live in `agent404/wave2.py`. They accept bounded
JSON, use no network or LLM, run no caller command and persist no payload.
REST endpoints are `POST /v1/wave2/{slug}`. The same five tools appear in the
existing MCP server. `GET /v1/wave2/catalog` provides examples; `/wave2/`
provides pages. The original `/v1/lab/*`, ten-tool directory and CVE resolver
are left intact. `GET /health` retains `experiments: 10` and reports
`wave2_prototypes: 5` separately.

## Pre-registered funnel

The new `wave2_events` SQLite table is isolated from `lab_events` and the CVE
baseline. Per prototype, record:

1. `discovery`: directory, detail page or machine catalog exposure;
2. `launch`: REST or MCP execution and outcome (`ok`, `issues`, invalid, limited, error);
3. `return`: estimated REST network IDs launching on two distinct UTC days;
4. `paid_demand_signal`: voluntary `pricing` or `pilot` POST to
   `/v1/wave2/{slug}/interest`.

`GET /v1/wave2/metrics` is admin-only. It returns aggregate counts, distinct
estimated REST network IDs and marked internal tests separately. Public pages
and catalog calls can be crawlers, so exposure is not a user. Anonymous MCP
shares an identity, so MCP agent counts and return rates are unavailable.
Interest is unverified self-report; it is not a sale, payment authorization or
validated willingness to pay. No email, contact, budget, private document or
raw request body is saved. An authenticated internal-test header excludes
labeled REST/page probes; unlabeled tests and malicious submissions may still
contaminate counts. Prefer repeated external use plus an independent user
conversation before product promotion. Compare both waves over their own
launch windows; never merge wave-two counts into the original 30-day cohort.

## Release boundary

The code requires targeted regression tests, a branch PR and the repository's
reviewed, typed Git-to-VPS operation at an exact merged SHA before a public
deployment. A healthy local test or PR does not establish production state.
Keep payments and paid providers disabled. Do not change unrelated routes,
domains, Caddy configuration or EOStorm.
