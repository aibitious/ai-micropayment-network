# Privacy notice — prototype (not a published legal policy)

The experimental API is intended only for PUBLIC questions about CVE identifiers.

Data stored: status and timestamp of calls; an HMAC-truncated derivation of the observed network address (the raw address is not stored by application telemetry); resolved public CVE information; when the caller explicitly opts in, the text of a public missing-information topic. The filter rejects obvious emails, URLs, IPv4 addresses and credential prefixes; it is not comprehensive. Do not transmit personal or confidential data.

Event telemetry retention: 30 days. Aggregated gap topics: until 90 days after last appearance. Cached CVE results: up to 7 days past expiration. The reverse proxy/hosting operator must separately configure access log retention; this prototype does not control it.

CVE records are fetched from the US National Vulnerability Database. No advertiser tracking, email marketing, sale of users' private data or production payments are present in the prototype.

Before public launch, the service operator must designate a legal entity, provide full GDPR/consumer disclosures, contact method, lawful basis and actual retention processes appropriate for the deployment.
