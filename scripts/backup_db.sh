#!/usr/bin/env bash
# scripts/backup_db.sh — Sauvegarde PostgreSQL vers S3 (ou local)
#
# Usage:
#   bash scripts/backup_db.sh              # backup vers S3 si AWS_S3_BUCKET défini
#   bash scripts/backup_db.sh --local      # backup local uniquement
#   bash scripts/backup_db.sh --restore backup_20260101_120000.sql.gz  # restaurer
#
# Variables d'environnement requises:
#   DATABASE_URL        postgresql+asyncpg://user:pass@host/dbname
#   AWS_S3_BUCKET       (optionnel) nom du bucket S3
#   AWS_DEFAULT_REGION  (optionnel) région AWS, défaut: eu-west-1
#
# Cron recommandé (crontab -e):
#   0 2 * * * /bin/bash /app/scripts/backup_db.sh >> /var/log/backup.log 2>&1
#   0 */6 * * * /bin/bash /app/scripts/backup_db.sh >> /var/log/backup.log 2>&1

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-/tmp/backups}"
BACKUP_FILE="autocommerce_backup_${TIMESTAMP}.sql.gz"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

mkdir -p "${BACKUP_DIR}"

# ── Parse DATABASE_URL ─────────────────────────────────────────────────────────
# Supports: postgresql+asyncpg://user:pass@host:5432/dbname
DB_URL="${DATABASE_URL:-}"
if [ -z "$DB_URL" ]; then
    echo "❌ DATABASE_URL not set"
    exit 1
fi

# Remove asyncpg prefix if present
DB_URL_CLEAN="${DB_URL/postgresql+asyncpg:\/\//postgresql://}"

# Extract components
DB_USER=$(echo "$DB_URL_CLEAN" | sed 's|.*://\([^:]*\):.*|\1|')
DB_PASS=$(echo "$DB_URL_CLEAN" | sed 's|.*://[^:]*:\([^@]*\)@.*|\1|')
DB_HOST=$(echo "$DB_URL_CLEAN" | sed 's|.*@\([^:/]*\)[:/].*|\1|')
DB_PORT=$(echo "$DB_URL_CLEAN" | sed 's|.*:\([0-9]*\)/.*|\1|')
DB_NAME=$(echo "$DB_URL_CLEAN" | sed 's|.*/\([^?]*\).*|\1|')

DB_PORT="${DB_PORT:-5432}"

# ── Restore mode ───────────────────────────────────────────────────────────────
if [ "${1:-}" = "--restore" ]; then
    RESTORE_FILE="${2:-}"
    if [ -z "$RESTORE_FILE" ]; then
        echo "Usage: $0 --restore <backup_file.sql.gz>"
        exit 1
    fi

    echo "⚠️  RESTORE MODE — This will OVERWRITE the database ${DB_NAME}"
    echo "    File: ${RESTORE_FILE}"
    read -r -p "Confirmer ? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Annulé."
        exit 0
    fi

    echo "🔄 Restoring from ${RESTORE_FILE}..."
    PGPASSWORD="$DB_PASS" gunzip -c "$RESTORE_FILE" | \
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
    echo "✅ Restore complete"
    exit 0
fi

# ── Backup ─────────────────────────────────────────────────────────────────────
echo "🔒 Starting backup at $(date)"
echo "   Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo "   Output:   ${BACKUP_PATH}"

PGPASSWORD="$DB_PASS" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    --format=plain \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    | gzip -9 > "${BACKUP_PATH}"

BACKUP_SIZE=$(du -sh "${BACKUP_PATH}" | cut -f1)
echo "✅ Backup created: ${BACKUP_FILE} (${BACKUP_SIZE})"

# ── Upload to S3 ───────────────────────────────────────────────────────────────
if [ -n "${AWS_S3_BUCKET:-}" ]; then
    S3_KEY="autocommerce/backups/$(date +%Y/%m)/${BACKUP_FILE}"
    echo "☁️  Uploading to s3://${AWS_S3_BUCKET}/${S3_KEY} ..."
    aws s3 cp "${BACKUP_PATH}" "s3://${AWS_S3_BUCKET}/${S3_KEY}" \
        --storage-class STANDARD_IA \
        --region "${AWS_DEFAULT_REGION:-eu-west-1}"
    echo "✅ Uploaded to S3"

    # Local cleanup after S3 upload
    rm -f "${BACKUP_PATH}"
else
    echo "⚠️  AWS_S3_BUCKET not set — backup kept locally only"
    echo "   Set AWS_S3_BUCKET in .env for cloud backup"
fi

# ── Cleanup old local backups ─────────────────────────────────────────────────
if [ "${1:-}" != "--local" ]; then
    find "${BACKUP_DIR}" -name "autocommerce_backup_*.sql.gz" \
        -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
    echo "🗑️  Cleaned backups older than ${RETENTION_DAYS} days"
fi

echo "✅ Backup complete at $(date)"
