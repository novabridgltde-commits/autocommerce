#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="${ROOT_DIR}/api-server"
FRONTEND_DIR="${ROOT_DIR}/autocommerce-app"
METRICS_URL="${METRICS_URL:-http://127.0.0.1:8000/metrics}"
INTERNAL_TOKEN="${INTERNAL_HEALTH_TOKEN:-test-health-token-001}"
ACK_MANUAL_ROUNDTRIP="${ACK_MANUAL_ROUNDTRIP:-0}"

usage() {
  cat <<'USAGE'
Usage: bash scripts/preflight_go_v25.sh [--ack-manual-roundtrip]

Runs the V25 release preflight.
The final round-trip validation remains a manual enterprise gate documented in
`docs/deployment-strategy.md`.

When the manual checklist has been executed and signed off, re-run with:
  ACK_MANUAL_ROUNDTRIP=1 bash scripts/preflight_go_v25.sh
or:
  bash scripts/preflight_go_v25.sh --ack-manual-roundtrip
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --ack-manual-roundtrip)
      ACK_MANUAL_ROUNDTRIP=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 64
      ;;
  esac
done

require_file() {
  local rel="$1"
  if [[ ! -f "${ROOT_DIR}/${rel}" ]]; then
    echo "Required release file missing: ${rel}" >&2
    exit 1
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Required command missing: ${cmd}" >&2
    exit 1
  fi
}

cd "${ROOT_DIR}"

REQUIRED_DOCS=(
  "README.md"
  "ONBOARDING.md"
  "CHANGES_HARDENING.md"
  "AUTOCOMMERCE_E_README.md"
  "docs/deployment-strategy.md"
  "docs/go-nogo-v25.md"
  "docs/go-nogo-v25-final.md"
  "docs/admin-guide-monitoring.md"
  "docs/api-b2b-portal.md"
  "docs/architecture-plan-fg.md"
  "docs/developer-guide-plan-fg.md"
  "docs/merchant-guide-b2b.md"
)

for file in "${REQUIRED_DOCS[@]}"; do
  require_file "$file"
done

for cmd in python3 curl npm docker pytest pip-audit; do
  require_cmd "$cmd"
done

echo "[1/13] Release documentation bundle"
echo "Documentation set present."

echo "[2/13] Packaging audit"
bash scripts/audit_package.sh --check

echo "[3/13] Seed idempotent"
python3 api-server/seed_production.py
python3 api-server/seed_production.py

echo "[4/13] Alembic 1 head"
pushd "${API_DIR}" >/dev/null
[ "$(python3 -m alembic heads 2>&1 | grep -c '(head)')" -eq 1 ]
popd >/dev/null

echo "[5/13] FastAPI import"
pushd "${API_DIR}" >/dev/null
python3 -c "from main import app"
popd >/dev/null

echo "[6/13] Secrets generator"
bash scripts/generate_secrets.sh --dry-run

echo "[7/13] Security targeted tests"
pushd "${API_DIR}" >/dev/null
pytest -c pytest.ini tests/test_security_headers.py tests/test_security_guard.py tests/test_security_multitenant.py -q
popd >/dev/null

echo "[8/13] Webhook HMAC reliability"
pushd "${API_DIR}" >/dev/null
pytest -c pytest.ini tests/test_webhook_reliability.py -q
popd >/dev/null

echo "[9/13] Dependency audit"
pip-audit -r api-server/requirements.txt --strict

echo "[10/13] Metrics endpoint protection"
WITHOUT_TOKEN_STATUS="$(curl -s -o /dev/null -w '%{http_code}' "${METRICS_URL}")"
WITH_TOKEN_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -H "X-Internal-Token: ${INTERNAL_TOKEN}" "${METRICS_URL}")"
[ "${WITHOUT_TOKEN_STATUS}" = "403" ]
[ "${WITH_TOKEN_STATUS}" = "200" ]

echo "[11/13] GDPR purge dry-run"
python3 scripts/daily_purge.py --dry-run

echo "[12/13] Frontend build and image"
pushd "${FRONTEND_DIR}" >/dev/null
npm ci --legacy-peer-deps
npm run build
popd >/dev/null
docker build -q -t ac-frontend-test autocommerce-app/

echo "[13/13] Enterprise round-trip gate"
if [[ "${ACK_MANUAL_ROUNDTRIP}" != "1" ]]; then
  cat <<'MSG'
MANUAL ACTION REQUIRED — release not auto-approved.
Execute the enterprise round-trip checklist described in docs/deployment-strategy.md,
collect the sign-off evidence, then re-run:
  ACK_MANUAL_ROUNDTRIP=1 bash scripts/preflight_go_v25.sh
or:
  bash scripts/preflight_go_v25.sh --ack-manual-roundtrip
MSG
  exit 2
fi

echo "Manual round-trip acknowledged."
echo "✅ GO v25 preflight passed"
