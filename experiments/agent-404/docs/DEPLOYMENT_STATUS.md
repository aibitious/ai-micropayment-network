# AIBITIOUS 404 — public pilot, 9 November 2026

- Live HTTPS: https://404.eostorm.com/
- Code: draft PR #1 https://github.com/aibitious/ai-micropayment-network/pull/1 (not merged).
- Host pilot path: `/srv/agent404-experiment`; Docker Compose project `aibitious404`; one container `agent404_experiment`; local port 127.0.0.1:18044.
- Isolated Caddy route on an existing TLS gateway; Let's Encrypt obtained. Caddy is attached to the `aibitious404_default` Docker network. This join may need to be persisted in gateway Compose if the gateway container is recreated.
- Never commit local secrets: `.env` and local DNS registry private key remain on the VPS with mode 0600.
- DNS `404.eostorm.com` A record is live. A public Ed25519 DNS TXT proof was added to `eostorm.com`. Official mcp-publisher metadata validation passed; authentication/publishing is NOT completed.
- Real NVD CVE lookup, MCP initialization, SDK tools/list and tools/call were tested successfully; metrics is not public.
- 30-day daily read-only monitoring scheduled; distinguish internal smoke traffic from organic integrations.
- x402 payments disabled, no wallet/facilitator, no new paid cloud resources. No claim of audited security.
- Rollback: remove only 404 hostname block after validating Caddy, adjust only 404 A record, and stop only `agent404_experiment`; never use the generic Docker Compose project `deploy` for teardown. Existing sites may be briefly affected by Caddy restart.
