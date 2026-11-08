#!/usr/bin/env bash
# Read-only checks; deliberately does not deploy or change production state.
set -euo pipefail
cd "$(dirname "$0")/.."
test -f .env || { echo 'ERROR: .env missing (copy and edit .env.example)' >&2; exit 1; }
if grep -E 'REPLACE_WITH|example\.org' .env >/dev/null; then
  echo 'ERROR: placeholder tokens or hosts remain in .env' >&2; exit 1
fi
python3 - <<'PY'
import os
from pathlib import Path
from urllib.parse import urlparse
config=dict(line.split('=',1) for line in Path('.env').read_text().splitlines()
            if '=' in line and not line.lstrip().startswith('#'))
required=('DB_PATH','ANON_HASH_SECRET','ADMIN_TOKEN','MCP_ALLOWED_HOSTS','UPSTREAM_DAILY_LIMIT')
assert all(config.get(k) for k in required), 'missing required configuration'
assert len(config['ADMIN_TOKEN'])>=32 and len(config['ANON_HASH_SECRET'])>=32, 'weak secrets'
assert config['MCP_ALLOWED_HOSTS'].strip(), 'hostname allowlist missing'
assert all(int(config[k])>=1 for k in ('UPSTREAM_DAILY_LIMIT','CLIENT_MINUTE_LIMIT','CLIENT_DAILY_LIMIT')), 'bad limits'
print('Environment syntax and basic safety gates: OK')
PY
command -v docker >/dev/null || { echo 'ERROR: docker not installed'; exit 1; }
docker compose -f deploy/docker-compose.yml config >/dev/null
echo 'Docker Compose parses: OK; no deployment executed.'
