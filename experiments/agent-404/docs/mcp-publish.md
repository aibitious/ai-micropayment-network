# MCP Registry — deployment gate, not a ready-made listing

**Do not publish this service until a live HTTPS `/mcp/` endpoint passes Inspector tests.**

1. Deploy API on a domain you own and configure `MCP_ALLOWED_HOSTS` to allow only that hostname (+ `localhost:*` for local-only checks). Ensure the TLS reverse proxy sets `Host` correctly and overwrites, rather than trusts, `X-Forwarded-For`.
2. Test MCP initialization, `tools/list`, `tools/call`, response shapes and rate-limit behavior with the **official SDK v2 client or Inspector**. Test from a different network, not only localhost.
3. Prepare `server.json` from the official current schema, with an `io.github.<owner>/<server>` namespace or domain namespace for which you can prove ownership. Use `mcp-publisher init` and check all generated fields before publishing. Never substitute a placeholder URL.
4. Verify namespace authentication (GitHub or DNS) and run `mcp-publisher publish ./server.json`. Confirm returned listing using registry's API.
5. Document that the MCP API is free and has shared quotas; it does not support paid operations.

Source: https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/cli/commands.md
