#!/usr/bin/env bash
# =============================================================================
# AUTOCOMMERCE V25 — Script de test déploiement
# Usage : bash scripts/test_deployment.sh [--url http://your-staging-url:8000]
# =============================================================================
set -euo pipefail

# ─── Couleurs ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

pass() { echo -e "${GREEN}✅ PASS${RESET} — $1"; }
fail() { echo -e "${RED}❌ FAIL${RESET} — $1"; FAILURES=$((FAILURES + 1)); }
warn() { echo -e "${YELLOW}⚠️  WARN${RESET} — $1"; WARNINGS=$((WARNINGS + 1)); }
info() { echo -e "${BLUE}ℹ️  INFO${RESET} — $1"; }
section() { echo -e "\n${BOLD}━━━ $1 ━━━${RESET}"; }

FAILURES=0
WARNINGS=0

# ─── Config ───────────────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="${ROOT_DIR}/api-server"
BASE_URL="${BASE_URL:-http://localhost:8000}"
INTERNAL_TOKEN="${INTERNAL_HEALTH_TOKEN:-test-health-token-001}"
TEST_EMAIL="deploy-test-$(date +%s)@autocommerce-test.invalid"
TEST_PASSWORD="TestDeploy2026!!"
TIMEOUT=10

# Parse args
for arg in "$@"; do
  case "$arg" in
    --url=*) BASE_URL="${arg#--url=}" ;;
    --url)   shift; BASE_URL="$1" ;;
  esac
done

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     AUTOCOMMERCE V25 — TEST DÉPLOIEMENT                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"
echo "  Target   : $BASE_URL"
echo "  Démarré  : $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ─── SECTION 1 : MIGRATIONS ───────────────────────────────────────────────────
section "1/5 — MIGRATIONS ALEMBIC"

cd "$API_DIR"

info "Vérification du nombre de têtes Alembic..."
HEADS=$(python3 -m alembic heads 2>&1 | grep -c '(head)' || true)
if [ "$HEADS" -eq 1 ]; then
  pass "1 seule tête Alembic — chaîne linéaire"
elif [ "$HEADS" -eq 0 ]; then
  fail "Aucune tête — alembic non initialisé ou DB vierge non migrée"
else
  fail "Plusieurs têtes ($HEADS) — conflit de migration"
fi

info "Application upgrade head..."
if python3 -m alembic upgrade head 2>&1 | tail -5; then
  pass "upgrade head terminé sans erreur"
else
  fail "upgrade head a échoué"
fi

info "Vérification idempotence (2ème run)..."
BEFORE=$(python3 -m alembic current 2>&1)
python3 -m alembic upgrade head 2>/dev/null
AFTER=$(python3 -m alembic current 2>&1)
if [ "$BEFORE" = "$AFTER" ]; then
  pass "Migrations idempotentes"
else
  fail "Migrations non idempotentes (état a changé au 2ème run)"
fi

cd "$ROOT_DIR"

# ─── SECTION 2 : TESTS UNITAIRES & RÉGRESSION ─────────────────────────────────
section "2/5 — TESTS UNITAIRES & RÉGRESSION"

cd "$API_DIR"

info "Tests sécurité..."
if pytest -c pytest.ini tests/test_security_headers.py tests/test_security_guard.py \
    tests/test_security_multitenant.py -q --tb=short 2>&1 | tail -5; then
  pass "Tests sécurité"
else
  fail "Tests sécurité"
fi

info "Tests webhook reliability..."
if pytest -c pytest.ini tests/test_webhook_reliability.py -q --tb=short 2>&1 | tail -3; then
  pass "Tests webhook"
else
  fail "Tests webhook"
fi

info "Tests régressions health/super_admin..."
if pytest -c pytest.ini \
    tests/integration/test_health_super_admin_regressions.py \
    -q --tb=short 2>&1 | tail -3; then
  pass "Tests régressions health/super_admin"
else
  fail "Tests régressions health/super_admin"
fi

info "Tests nouveaux modules (loyalty_ia, visual_builder, restocking)..."
if pytest -c pytest.ini \
    tests/test_loyalty_ia_service.py \
    tests/test_visual_builder_service.py \
    tests/test_restocking_service.py \
    -q --tb=short 2>&1 | tail -3; then
  pass "Tests nouveaux modules"
else
  fail "Tests nouveaux modules"
fi

info "Suite complète avec gate coverage (55%)..."
if pytest -c pytest_full.ini -q --tb=short 2>&1 | tail -5; then
  pass "Suite complète — coverage ≥ 55%"
else
  fail "Suite complète — coverage insuffisant ou tests cassés"
fi

cd "$ROOT_DIR"

# ─── SECTION 3 : SMOKE TESTS HTTP ─────────────────────────────────────────────
section "3/5 — SMOKE TESTS HTTP"

http_check() {
  local label="$1" method="$2" url="$3"
  shift 3
  local expected_status="${1:-200}"; shift || true
  local extra_args=("$@")

  local response
  response=$(curl -s -o /tmp/ac_response -w "%{http_code}" \
    -X "$method" \
    -H "Content-Type: application/json" \
    --max-time "$TIMEOUT" \
    "${extra_args[@]}" \
    "${BASE_URL}${url}" 2>/dev/null || echo "000")

  if [ "$response" = "$expected_status" ]; then
    pass "$label → HTTP $response"
    return 0
  else
    fail "$label → attendu $expected_status, reçu $response"
    return 1
  fi
}

# Health endpoints
http_check "GET /api/health" GET "/api/health"
http_check "GET /api/health/detailed sans token → 401" GET "/api/health/detailed" 401
http_check "GET /api/health/detailed avec token → 200" GET "/api/health/detailed" 200 \
  -H "X-Internal-Token: $INTERNAL_TOKEN"
http_check "GET /metrics sans token → 403" GET "/metrics" 403
http_check "GET /metrics avec token → 200" GET "/metrics" 200 \
  -H "X-Internal-Token: $INTERNAL_TOKEN"

# Auth flow
info "Inscription d'un compte test..."
REG_RESPONSE=$(curl -s -o /tmp/ac_reg -w "%{http_code}" \
  -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"store_name\":\"DeployTest\"}" \
  --max-time "$TIMEOUT" 2>/dev/null || echo "000")

if [ "$REG_RESPONSE" = "200" ] || [ "$REG_RESPONSE" = "201" ]; then
  pass "POST /api/v1/auth/register → $REG_RESPONSE"
  JWT=$(python3 -c "import json,sys; d=json.load(open('/tmp/ac_reg')); print(d.get('access_token',''))" 2>/dev/null || true)
else
  fail "POST /api/v1/auth/register → $REG_RESPONSE"
  JWT=""
fi

info "Connexion avec le compte test..."
LOGIN_RESPONSE=$(curl -s -o /tmp/ac_login -w "%{http_code}" \
  -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}" \
  --max-time "$TIMEOUT" 2>/dev/null || echo "000")

if [ "$LOGIN_RESPONSE" = "200" ]; then
  pass "POST /api/v1/auth/login → 200"
  JWT=$(python3 -c "import json,sys; d=json.load(open('/tmp/ac_login')); print(d.get('access_token',''))" 2>/dev/null || true)
else
  fail "POST /api/v1/auth/login → $LOGIN_RESPONSE"
fi

# Sécurité: accès sans JWT
http_check "GET /api/v1/auth/me sans JWT → 401" GET "/api/v1/auth/me" 401

# Avec JWT valide
if [ -n "${JWT:-}" ]; then
  http_check "GET /api/v1/auth/me avec JWT → 200" GET "/api/v1/auth/me" 200 \
    -H "Authorization: Bearer $JWT"

  # Route B2B sans rôle suffisant (viewer = défaut register) → 403
  http_check "GET /api/v1/b2b/accounts avec viewer JWT → 403" \
    GET "/api/v1/b2b/accounts" 403 \
    -H "Authorization: Bearer $JWT"

  # Route /ai avec JWT viewer → 200 (require_role viewer)
  http_check "GET /api/v1/ai/search avec JWT viewer → non-401" \
    GET "/api/v1/ai/search?q=test" 200 \
    -H "Authorization: Bearer $JWT" || \
  http_check "GET /api/v1/ai/search avec JWT viewer → 422 (params)" \
    GET "/api/v1/ai/search" 422 \
    -H "Authorization: Bearer $JWT"
else
  warn "JWT absent — skip des tests auth avancés"
fi

# Route /ai sans JWT → 401
http_check "GET /api/v1/ai/search sans JWT → 401" GET "/api/v1/ai/search" 401

cd "$ROOT_DIR"

# ─── SECTION 4 : SÉCURITÉ HEADERS ─────────────────────────────────────────────
section "4/5 — HEADERS DE SÉCURITÉ"

HEADERS=$(curl -s -I --max-time "$TIMEOUT" "$BASE_URL/api/health" 2>/dev/null || true)

check_header() {
  local name="$1"
  if echo "$HEADERS" | grep -qi "$name"; then
    pass "Header présent : $name"
  else
    warn "Header absent : $name"
  fi
}

check_header "X-Content-Type-Options"
check_header "X-Frame-Options"
check_header "Strict-Transport-Security"
check_header "Content-Security-Policy"
check_header "X-Request-ID"

# ─── SECTION 5 : ARTEFACTS & INTÉGRITÉ ────────────────────────────────────────
section "5/5 — INTÉGRITÉ DU DÉPLOIEMENT"

info "Vérification imports Python critiques..."
cd "$API_DIR"
if python3 -c "from main import app; print('FastAPI app OK')" 2>&1; then
  pass "Import FastAPI app"
else
  fail "Import FastAPI app échoué"
fi

if python3 -c "from middleware.tenant import TenantMiddleware; import inspect; src=inspect.getsource(TenantMiddleware.dispatch); assert 'jwt_payload' in src" 2>/dev/null; then
  pass "BUG#1 jwt_payload présent dans TenantMiddleware"
else
  fail "BUG#1 jwt_payload ABSENT — régression critique!"
fi

if python3 -c "
from api.v1.ai import router
deps = getattr(router, 'dependencies', [])
assert len(deps) > 0, 'Aucune dépendance sur le router /ai'
" 2>/dev/null; then
  pass "BUG#3 require_role actif sur router /ai"
else
  fail "BUG#3 require_role ABSENT sur router /ai — régression critique!"
fi

info "Vérification absence de credentials hardcodés..."
if grep -r "postgres:postgres" "$ROOT_DIR/api-server/" --include="*.yml" --include="*.yaml" -q 2>/dev/null; then
  fail "BUG#2 credentials hardcodés toujours présents!"
else
  pass "BUG#2 aucun credential hardcodé"
fi

info "pip-audit — CVE connues..."
if command -v pip-audit &>/dev/null; then
  if pip-audit -r requirements.txt --strict -q 2>&1 | tail -3; then
    pass "pip-audit : 0 CVE"
  else
    fail "pip-audit : vulnérabilités détectées"
  fi
else
  warn "pip-audit non installé — skip (pip install pip-audit pour activer)"
fi

cd "$ROOT_DIR"

# ─── RÉSUMÉ ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ RÉSUMÉ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo "  Terminé : $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

if [ "$FAILURES" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}  ✅ GO — Tous les checks passent (0 échec, 0 warning)${RESET}"
  exit 0
elif [ "$FAILURES" -eq 0 ]; then
  echo -e "${YELLOW}${BOLD}  ⚠️  GO CONDITIONNEL — 0 échec, $WARNINGS warning(s)${RESET}"
  echo "  → Vérifier les warnings avant déploiement prod"
  exit 0
else
  echo -e "${RED}${BOLD}  ❌ NO-GO — $FAILURES échec(s), $WARNINGS warning(s)${RESET}"
  echo "  → Corriger les échecs avant tout déploiement"
  exit 1
fi
