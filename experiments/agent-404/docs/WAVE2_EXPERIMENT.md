# AIBITIOUS 404 LAB — broad wave two, 10 November 2026

The owner chose breadth after the first five felt arbitrary. This cohort tests
**22 distinct, bounded agent jobs** beside the original ten. Each must perform
a deterministic offline transformation, return structured findings, have an
example and a separate funnel. Scores below are prioritization judgments,
not observed market demand or proof that a market is empty.

Current first-party competitors: [LangSmith](https://www.langchain.com/langsmith/observability),
[Braintrust](https://www.braintrust.dev/), [Arize Phoenix](https://arize.com/phoenix)
and [Datadog](https://docs.datadoghq.com/llm_observability/guide/agent_monitoring/)
cover broad agent tracing and evaluation. [Cedar](https://docs.cedarpolicy.com/auth/authorization.html)
and [OPA](https://www.openpolicyagent.org/docs/policy-testing) cover production
authorization; [Temporal](https://docs.temporal.io/design-patterns) covers
durable retries and Sagas; [Svix](https://docs.svix.com/ai/dashboard-mcp)
covers webhook diagnosis; [NVIDIA SkillSpector](https://github.com/NVIDIA/skillspector)
scans agent skills. [OpenTelemetry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
notes privacy risks in tool arguments and traces. The niche hypothesis is a
small framework-neutral **pre-action check** with no integration bill.
The MCP community's [tool-annotation discussion](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/)
explicitly treats risk flags as untrusted hints, while an open
[tool-scope proposal](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1880)
shows that fine-grained scope communication is still being worked through.
These are evidence of a design gap, not evidence that this implementation
solves production authorization or that buyers exist.

## Forty ideas screened

Scores 1–5: job urgency J, agent fit A, plausible paid value P, zero-cost safe
testability Z, focused differentiation D. Total is out of 25. Competitor
proximity and overlap with the existing ten reduce D. These are hypotheses.

| Candidate | J | A | P | Z | D | Total | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Action Policy Simulator | 5 | 5 | 5 | 5 | 3 | 23 | Build |
| Workflow Recovery Planner | 5 | 5 | 5 | 5 | 3 | 23 | Build |
| Claim Provenance Check | 5 | 5 | 4 | 5 | 4 | 23 | Build |
| Data Minimizer | 5 | 5 | 4 | 5 | 3 | 22 | Build |
| Webhook Delivery Triage | 4 | 5 | 4 | 5 | 3 | 21 | Build |
| Permission Scope Delta | 5 | 5 | 5 | 5 | 3 | 23 | Build |
| Approval Packet Check | 5 | 5 | 5 | 5 | 3 | 23 | Build |
| Budget Envelope | 5 | 5 | 5 | 5 | 3 | 23 | Build |
| Retry Schedule | 4 | 5 | 4 | 5 | 3 | 21 | Build |
| Idempotency Audit | 5 | 5 | 4 | 5 | 3 | 22 | Build |
| Prerequisite Gate | 5 | 5 | 4 | 5 | 3 | 22 | Build |
| Evidence Freshness | 5 | 5 | 4 | 5 | 4 | 23 | Build |
| Citation Matrix | 4 | 5 | 3 | 5 | 3 | 20 | Build |
| Consumer Schema Impact | 5 | 5 | 4 | 5 | 3 | 22 | Build |
| Boundary Case Builder | 4 | 5 | 3 | 5 | 3 | 20 | Build |
| SLO Burn Check | 4 | 5 | 4 | 5 | 2 | 20 | Build |
| Queue Capacity Forecast | 4 | 5 | 4 | 5 | 3 | 21 | Build |
| Permission Path Explorer | 5 | 5 | 5 | 5 | 3 | 23 | Build |
| Context Budget Packer | 4 | 5 | 4 | 5 | 3 | 21 | Build |
| Release Gate Check | 5 | 5 | 4 | 5 | 3 | 22 | Build |
| Manifest Drift | 4 | 5 | 4 | 5 | 3 | 21 | Build |
| Receipt Chain Check | 4 | 5 | 4 | 5 | 3 | 21 | Build |
| General agent trace platform | 5 | 5 | 5 | 1 | 1 | 17 | Defer: competitors, storage |
| Agent skill malware scanner | 5 | 5 | 4 | 3 | 1 | 18 | Defer: existing scanner |
| Live prompt-injection firewall | 5 | 5 | 5 | 1 | 1 | 17 | Defer: safety proof |
| Live website permission auditor | 4 | 4 | 3 | 1 | 2 | 14 | Defer: outbound probe risk |
| Multi-provider model router | 5 | 5 | 4 | 1 | 1 | 16 | Defer: fees, gateways |
| Hosted webhook delivery service | 5 | 5 | 5 | 1 | 1 | 17 | Defer: Svix overlap |
| Full workflow engine | 5 | 5 | 5 | 1 | 1 | 17 | Defer: Temporal overlap |
| Production policy enforcement | 5 | 5 | 5 | 1 | 1 | 17 | Defer: authority risk |
| Live secret scanner of customer repos | 5 | 5 | 4 | 1 | 1 | 16 | Defer: private data |
| Autonomous incident fixer | 5 | 5 | 5 | 1 | 2 | 18 | Defer: external effects |
| Automatic paid budget controller | 5 | 5 | 5 | 1 | 2 | 18 | Defer: no proven hard stop |
| Identity verification for agents | 5 | 5 | 5 | 2 | 1 | 18 | Defer: credential handling |
| Browser task recorder | 4 | 5 | 4 | 1 | 2 | 16 | Defer: sensitive traces |
| Full tax invoice certification | 4 | 4 | 5 | 1 | 1 | 15 | Defer: legal correctness |
| CVE exploitation predictor | 4 | 4 | 4 | 2 | 1 | 15 | Defer: weak evidence |
| Agent marketplace crawler | 3 | 5 | 3 | 2 | 2 | 15 | Defer: crawl cost |
| Customer data lineage platform | 5 | 5 | 5 | 1 | 1 | 17 | Defer: integration cost |
| Autonomous payment reconciliation | 5 | 5 | 5 | 1 | 1 | 17 | Defer: financial effects |

## Interfaces and isolation

The 22 implementations live in `agent404/wave2.py` and `wave2_more.py`.
They process bounded JSON in memory, make no outbound call, execute no supplied
code and persist no payload. REST uses `POST /v1/wave2/{slug}`. MCP exposes
22 wave-two tools, five with explicit parameters and 17 with a `payload`
object and an example in their tool description. `/v1/wave2/catalog` provides
all examples and limitations; `/wave2/` provides pages. The original ten LAB
tools and CVE resolver remain in their existing endpoints and tables. Health
keeps `experiments: 10` and separately reports `wave2_prototypes: 22`.

## Measurement and decision rule

The isolated `wave2_events` table records discovery (directory, detail,
catalog), launch (REST/MCP and outcome), return (estimated REST network IDs
launching on two distinct UTC days), and voluntary `pricing` or `pilot`
signals. Admin-only `/v1/wave2/metrics` separates marked internal tests.
The return estimate requires successful REST launches on two UTC days;
invalid inputs and rate limits do not qualify. A separate interest estimate
counts only REST network IDs with a successful launch before their signal.
No raw inputs, contact information, budgets or payment details are stored.
REST HMAC network IDs are not people; anonymous MCP cannot count distinct
agents. Directory traffic may be crawlers and self-reported interest is not
a sale. Unlabeled tests may contaminate counts. Do not combine the wave-two
cohort with the original 30-day series.

After at least 30 full days, first check uptime and test exclusion. Promote
no more than three tools for deeper research only if each has at least five
estimated non-internal REST network IDs, three returning IDs on different
days, completion above 90%, and at least one independently corroborated
problem interview. Low data means inconclusive. These thresholds are
guardrails, not proof of willingness to pay.

## Release boundary

This code needs tests, review and an existing typed Git-to-VPS operation at
an exact merged SHA. The current canonical `docs/AUTOPILOT_BRIDGE_V026.md`
contains no Agent404 deploy/inspect/rollback selector. A local pass or draft
PR does not establish production. Keep billing off; do not touch EOStorm,
unrelated routes, Caddy or the original LAB data.
