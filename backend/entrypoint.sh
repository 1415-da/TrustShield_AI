#!/bin/sh
set -e
echo "[trustshield] applying migrations"
alembic upgrade head
if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "[trustshield] seeding synthetic demo data (skipped if already present)"
  python /srv/scripts/seed_demo_data.py --if-empty
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
