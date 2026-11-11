#!/usr/bin/env bash
# Show which host ports TrustShield will use and whether something else already holds them.
# Run before `docker compose up` if the app, API or database don't answer where you expect.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
FRONTEND_PORT=${FRONTEND_PORT:-3000}; BACKEND_PORT=${BACKEND_PORT:-8000}; DB_PORT=${DB_PORT:-5433}
status=0
for pair in "frontend:$FRONTEND_PORT" "backend:$BACKEND_PORT" "database:$DB_PORT"; do
  name=${pair%%:*}; port=${pair##*:}
  owner=$(docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -E "[:.]${port}->" | awk '{print $1}' | head -1 || true)
  if [ -n "$owner" ] && [[ "$owner" != trustshield-* ]]; then
    echo "✗ $name port $port is used by container '$owner' — change it in .env (FRONTEND_PORT, BACKEND_PORT or DB_PORT)"; status=1
  elif [ -z "$owner" ] && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "✗ $name port $port is used by $(lsof -nP -iTCP:"$port" -sTCP:LISTEN | awk 'NR==2{print $1}') — pick another port in .env"; status=1
  else
    echo "✓ $name → localhost:$port${owner:+ (TrustShield running)}"
  fi
done
exit $status
