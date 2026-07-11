#!/bin/bash
# ════════════════════════════════════════════════════════════════
# AutoCommerce V25 — Script de Setup Local (Dev / Staging)
# ════════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
API_DIR="$ROOT_DIR/api-server"
APP_DIR="$ROOT_DIR/autocommerce-app"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   AutoCommerce V25 — Setup Local                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 1. Vérification des prérequis ─────────────────────────────
echo "▶ Vérification des prérequis..."
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 requis"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ node requis"; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "❌ postgresql-client requis"; exit 1; }
command -v redis-cli >/dev/null 2>&1 || { echo "❌ redis-cli requis"; exit 1; }
echo "✅ Prérequis OK"

# ── 2. Génération du .env ──────────────────────────────────────
if [ ! -f "$API_DIR/.env" ]; then
    echo ""
    echo "▶ Génération du fichier .env..."
    bash "$SCRIPT_DIR/generate_secrets.sh" > "$API_DIR/.env"
    echo "✅ .env généré dans $API_DIR/.env"
    echo "⚠️  Vérifiez et complétez ce fichier avant de continuer."
else
    echo "✅ .env existe déjà ($API_DIR/.env)"
fi

# ── 3. Setup PostgreSQL ────────────────────────────────────────
echo ""
echo "▶ Setup PostgreSQL..."
DB_PASS=$(grep 'DATABASE_URL' "$API_DIR/.env" | sed 's/.*:\(.*\)@.*/\1/' | tr -d '\n')
DB_NAME="autocommerce"
DB_USER="autocommerce"

# Create user and database if not exists
psql -U postgres -c "DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
    CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS';
  END IF;
END \$\$;" 2>/dev/null || true

psql -U postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || true

# Install pgvector extension
psql -U postgres -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || \
  echo "⚠️  pgvector non installé — embedding search désactivé (OK pour dev)"

echo "✅ PostgreSQL configuré"

# ── 4. Installation des dépendances Python ─────────────────────
echo ""
echo "▶ Installation des dépendances Python..."
cd "$API_DIR"
pip install -r requirements.txt --quiet
echo "✅ Dépendances Python installées"

# ── 5. Migrations Alembic ──────────────────────────────────────
echo ""
echo "▶ Exécution des migrations Alembic..."
cd "$API_DIR"
python3 -m alembic upgrade heads
echo "✅ Migrations OK"

# ── 6. Seed de production ──────────────────────────────────────
echo ""
echo "▶ Seeding de la base de données..."
ADMIN_PASS=$(grep 'ADMIN_INITIAL_PASSWORD' "$API_DIR/.env" | cut -d= -f2 | tr -d '\n')
SUPERADMIN_PASS=$(grep 'SUPERADMIN_INITIAL_PASSWORD' "$API_DIR/.env" | cut -d= -f2 | tr -d '\n')

if [ -z "$ADMIN_PASS" ] || [ "$ADMIN_PASS" = "CHANGE_ME_admin_password" ]; then
    echo "⚠️  ADMIN_INITIAL_PASSWORD non configuré dans .env"
    read -sp "  Mot de passe admin (masqué): " ADMIN_PASS
    echo ""
fi

if [ -z "$SUPERADMIN_PASS" ] || [ "$SUPERADMIN_PASS" = "CHANGE_ME_superadmin_password" ]; then
    echo "⚠️  SUPERADMIN_INITIAL_PASSWORD non configuré dans .env"
    read -sp "  Mot de passe superadmin (masqué): " SUPERADMIN_PASS
    echo ""
fi

cd "$API_DIR"
ADMIN_INITIAL_PASSWORD="$ADMIN_PASS" SUPERADMIN_INITIAL_PASSWORD="$SUPERADMIN_PASS" \
    python3 seed_production.py
echo "✅ Seed OK"

# ── 7. Installation Frontend ───────────────────────────────────
echo ""
echo "▶ Installation des dépendances frontend..."
cd "$APP_DIR"
if command -v pnpm >/dev/null 2>&1; then
    pnpm install --no-frozen-lockfile
elif command -v npm >/dev/null 2>&1; then
    npm install
fi
echo "✅ Frontend prêt"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ✅ Setup terminé !                                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Pour démarrer:"
echo "  Backend:  cd api-server && ENV=development DEBUG=True bash start.sh"
echo "  Frontend: cd autocommerce-app && PORT=5173 npm run dev"
echo ""
