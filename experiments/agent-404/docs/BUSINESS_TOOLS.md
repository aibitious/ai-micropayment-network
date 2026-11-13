# CompanyCard and ProjectSignals — business-v1 prototypes

Implementation stage: review branch only; not deployed, not paid products.

Two tools are isolated from the original 10 + 22 tool cohorts. REST discovery:
`GET /v1/business/catalog`, UI `/business/`, REST calls
`POST /v1/business/company_card` and `POST /v1/business/project_signals`
with `{"domain":"company.example"}`. MCP names: `company_card`, `project_signals`.
Both perform public source reads and use shared global quotas across REST/MCP.

CompanyCard reads homepage Organization JSON-LD and description metadata. Values
carry source and extraction basis; absent fields stay absent. No registry
verification, headcount inference, country inference or legal-identity guarantee.

ProjectSignals discovers at most three same-host case-study/project URLs linked
from the supplied supplier homepage, returning excerpts, technology mentions and
publication-date claims separately from unknown project dates. An explicit
`Client: NAME` label can populate a source-claimed customer; it is not an
independently verified purchase. Supplier/customer entity resolution, scope
extraction, verified project indexing and cross-company searching remain TODO.
No claim that a historical project implies current buying intent.

Safety: HTTPS only, no query/credentials/IP literals/nonstandard ports; reject
nonpublic DNS results, connect to pinned IP with original TLS hostname and Host,
revalidate every redirect and reject cross-host redirects. Robots fetched first;
a robots retrieval failure (including 404) currently fails closed. At most five
source fetches (four redirect hops per fetch), 300 KB per response, 25s total.
No arbitrary code execution, LLM calls, purchased APIs, payment collection or
persistent company dataset. Inputs/source documents are not logged. Aggregate
business events use a separate action prefix; do not count candidates as verified
results, customers, purchases, or proof of demand.

Release blockers: existing Agent404 deploy/inspect/rollback operation and required
CI issues recorded in the AIBITIOUS 404 workstream. Do not claim the public URL is
live based on this branch. Independent live network/TLS and production verification
are required before release. No production configuration or payment setup changed.

Next product milestone: bounded on-demand corpus with evidence-backed customer,
supplier and scope extraction, source date disambiguation, source-error handling,
searchable records and false-positive benchmark before paid access.
