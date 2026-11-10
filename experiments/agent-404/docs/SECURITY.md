# Security boundary and pre-launch checklist

Threat model: anonymous internet clients, prompt-injected text submitted as gap topics, abusive automation, NVD outage, compromised source data, SSRF, database amplification, repeated payments, compromised MCP clients, traffic spikes.

Implemented:
- Only exact CVE IDs can trigger network access; upstream hostname is fixed in code, redirects disabled, 8s timeout, 1MB response cap.
- No shell execution, no arbitrary crawling, no database queries supplied by a user, no user-provided upstream URLs.
- Bounded daily/minute and upstream call budgets persist in SQLite. Single Uvicorn worker required, plus reverse-proxy traffic limits.
- HMAC anonymization of client network identifiers; opt-in recording of public gap topics; coarse input rejection.
- Admin metrics disabled without an `ADMIN_TOKEN` and guarded by constant-time comparison.
- Docker read-only root, non-root UID, removed Linux capabilities, CPU/ram/process bounds, loopback-only host port.
- No x402 facilitator or wallet configuration: real payment acceptance is impossible in this build.

Required before public exposure:
- Validate exact NVD API attribution and NVD usage/rate rules; impose lower global upstream quota if necessary.
- Run latest MCP v2 integration tests against a real server and validate Host/Origin. The SDK is a protocol server, not authorization for sensitive tools.
- Configure HTTPS with an approved domain, monitor certificate renewal, configure reverse-proxy request-body and rate limits.
- Correctly determine client IP ONLY from an authenticated proxy chain. With Docker NAT the actual proxy peer may be a Docker bridge gateway rather than `127.0.0.1`. Do not configure blanket `--forwarded-allow-ips='*'`. Set the verified gateway/host IP and overwrite X-Forwarded-For at nginx. Without this, different users may share one quota bucket, distorting metrics.
- Validate data retention, privacy notice, abuse reporting, logs/redaction, backup and restore, incident response.
- Add load tests, dependency scans, alerting, monitoring, health checks and a rollback procedure.
- Keep NVD responses as external evidence, not an unqualified claim that something is safe or exploited.

Reporting: security findings can be filed as private GitHub security advisories after the project has a standalone repository. No bug bounty or payout is offered by this experiment.
