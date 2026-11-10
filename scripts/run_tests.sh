#!/usr/bin/env bash
# Run the TrustShield test suites and write a combined report to reports/.
#
#   scripts/run_tests.sh            # backend (pytest) only — hermetic, no services needed
#   scripts/run_tests.sh --e2e      # also run Playwright against E2E_BASE_URL (default http://localhost:3000)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/reports"

PY="${PYTHON:-$ROOT/backend/.venv/bin/python}"
[ -x "$PY" ] || PY=python3

echo "▸ Backend tests (pytest, SQLite in-memory, mock LLM)"
(cd "$ROOT/backend" && "$PY" -m pytest --junitxml="$ROOT/reports/backend-junit.xml" -q)

if [[ "${1:-}" == "--e2e" ]]; then
  echo "▸ Frontend end-to-end tests (Playwright) against ${E2E_BASE_URL:-http://localhost:3000}"
  (cd "$ROOT/frontend" && npx playwright test)
  cp "$ROOT/frontend/test-results/e2e-results.json" "$ROOT/reports/e2e-results.json" 2>/dev/null || true
fi

echo "▸ Writing report"
"$PY" "$ROOT/scripts/generate_test_report.py"
