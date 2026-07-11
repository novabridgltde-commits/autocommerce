#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/4] Backend targeted tests"
cd "$ROOT_DIR/api-server"
pytest tests/test_b2b_portal_service.py tests/test_b2b_portal_routes.py tests/security/test_b2b_access_control.py tests/test_llm_stub.py tests/test_plan_e_routes.py -q

echo "[2/4] Playwright targeted suite"
cd "$ROOT_DIR/e2e"
if [ ! -d node_modules ]; then
  npm install
fi
npx playwright install --with-deps chromium
E2E_BASE_URL="${E2E_BASE_URL:-http://localhost:3000}" \
  npx playwright test tests/01-inscription.spec.ts --reporter=list
E2E_BASE_URL="${E2E_BASE_URL:-http://localhost:3000}" \
  npx playwright test tests/02-checkout.spec.ts --reporter=list
E2E_BASE_URL="${E2E_BASE_URL:-http://localhost:3000}" \
  npx playwright test tests/03-whatsapp-webhook.spec.ts --reporter=list
E2E_BASE_URL="${E2E_BASE_URL:-http://localhost:3000}" \
  npx playwright test tests/b2b-portal.spec.ts --reporter=list

echo "[3/4] Load profile"
cd "$ROOT_DIR/api-server"
if command -v k6 >/dev/null 2>&1; then
  k6 run tests/load/k6_b2b_portal.js
else
  echo "k6 non installé — exécuter manuellement: k6 run tests/load/k6_b2b_portal.js"
fi

echo "[4/4] Packaging audit"
cd "$ROOT_DIR"
bash scripts/audit_package.sh --check

echo "Plan F/G quality suite completed."
