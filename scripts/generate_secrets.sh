#!/usr/bin/env bash
# generate_secrets.sh — Génère un .env complet avec secrets sécurisés
# Usage: bash scripts/generate_secrets.sh > api-server/.env
# Ou pour ajouter aux secrets existants: bash scripts/generate_secrets.sh >> api-server/.env
set -euo pipefail

ADMIN_PASS=$(openssl rand -hex 8)
SUPERADMIN_PASS=$(openssl rand -hex 8)
DB_PASS=$(openssl rand -hex 16)
JWT_KEY=$(openssl rand -hex 32)
CSRF_KEY=$(openssl rand -hex 32)
HEALTH_TOKEN=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
WA_APP_SECRET=$(openssl rand -hex 16)
WA_VERIFY_TOKEN=$(openssl rand -hex 24)
IG_VERIFY_TOKEN=$(openssl rand -hex 24)
FB_VERIFY_TOKEN=$(openssl rand -hex 24)
TIKTOK_VERIFY_TOKEN=$(openssl rand -hex 24)

cat << ENV
# ══════════════════════════════════════════════════════════════════════════════
# AutoCommerce V25 — Environnement généré le $(date +%Y-%m-%d\ %H:%M:%S)
# ⚠️  NE COMMITEZ JAMAIS CE FICHIER — Ajoutez .env à .gitignore
# ══════════════════════════════════════════════════════════════════════════════

# ── App (ENV=development pour bypass validateurs production si pas de vraies clés API)
ENV=development
DEBUG=False
SERVER_DOMAIN=http://localhost:8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# ── Database
# POSTGRES_PASSWORD est utilisé par Docker Compose pour initialiser la DB
POSTGRES_PASSWORD=${DB_PASS}
DATABASE_URL=postgresql+asyncpg://autocommerce:${DB_PASS}@localhost:5432/autocommerce

# ── Redis
REDIS_URL=redis://localhost:6379/0
REDIS_RATELIMIT_URL=redis://localhost:6379/1
REDIS_CACHE_URL=redis://localhost:6379/2
REDIS_PASSWORD=
REDIS_SENTINEL_MASTER=mymaster
REDIS_SENTINEL_PASSWORD=
REDIS_MAX_CONNECTIONS=10
REDIS_SOCKET_TIMEOUT=5.0
REDIS_SOCKET_CONNECT_TIMEOUT=3.0

# ── Secrets (GÉNÉRÉS — NE PAS CHANGER APRÈS LE PREMIER DÉMARRAGE)
JWT_SECRET_KEY=${JWT_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
FERNET_KEYS_JSON=
CSRF_SECRET=${CSRF_KEY}
INTERNAL_HEALTH_TOKEN=${HEALTH_TOKEN}

# ── Passwords initiaux (à changer après première connexion)
ADMIN_INITIAL_PASSWORD=${ADMIN_PASS}
SUPERADMIN_INITIAL_PASSWORD=${SUPERADMIN_PASS}

# ── WhatsApp (laisser vide en développement)
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_APP_SECRET=${WA_APP_SECRET}
WHATSAPP_VERIFY_TOKEN=${WA_VERIFY_TOKEN}
WHATSAPP_PHONE_NUMBER_ID=

# ── Instagram
INSTAGRAM_VERIFY_TOKEN=${IG_VERIFY_TOKEN}
INSTAGRAM_APP_SECRET=

# ── Facebook
FACEBOOK_VERIFY_TOKEN=${FB_VERIFY_TOKEN}
FACEBOOK_APP_SECRET=

# ── TikTok
TIKTOK_APP_SECRET=
TIKTOK_VERIFY_TOKEN=${TIKTOK_VERIFY_TOKEN}
TIKTOK_ENABLED=False
TIKTOK_ALLOW_REAL_CALLS=False

# ── Alertes
SLACK_ALERT_WEBHOOK=
EMOTION_ESCALATION_THRESHOLD=2

# ── OmniCall V9
OMNICALL_V9_SHADOW_MODE=0
OMNICALL_V9_ENABLED=0
OMNICALL_V9_ROLLOUT_PCT=0
OMNICALL_V9_BETA_STORES=

# ── Providers IA (remplir avec vos vraies clés)
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
FEATURE_FLAG_DEEPSEEK=True
FEATURE_FLAG_OPENAI_FALLBACK=True
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_VISION_MODEL=gpt-4o
OPENAI_LOW_COST_MODEL=gpt-4o-mini

# ── SaaS / FinOps
AI_BUDGET_HARD_LIMIT_USD=250.0
AI_MAX_MONTHLY_CALLS=10000
AI_MAX_MONTHLY_TOKENS=2000000
AI_WARNING_THRESHOLD_PCT=80
AI_DEGRADED_THRESHOLD_PCT=100
AI_CONTROLLED_FALLBACK_MESSAGE="Service IA momentanément limité. Réessayez plus tard."
SAAS_BILLING_WEBHOOK_SECRET=

# ── Sécurité
MAX_INPUT_LENGTH=2000
RESET_TOKEN_TTL=900
SKIP_LIMITER=0

# ── Runtime
PORT=8000
UVICORN_WORKERS=4
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=3
DB_STATEMENT_TIMEOUT_MS=30000

# ── Sentry
SENTRY_DSN=

# ── Celery
CELERY_SOFT_TIME_LIMIT=120
CELERY_TIME_LIMIT=300
CELERY_MAX_TASKS_PER_CHILD=200
CELERY_MAX_MEMORY_KB=400000
CELERY_BROKER_POOL_LIMIT=10

# ── Rate limits
RL_LOGIN_LIMIT=10
RL_LOGIN_WINDOW=60
RL_REGISTER_LIMIT=5
RL_REGISTER_WINDOW=60
RL_FORGOT_LIMIT=5
RL_FORGOT_WINDOW=3600
RL_AI_LIMIT=60
RL_AI_WINDOW=60
RL_UPLOAD_LIMIT=30
RL_UPLOAD_WINDOW=60
RL_WEBHOOK_LIMIT=600
RL_WEBHOOK_WINDOW=60

# ── Circuit breakers
CB_OPENAI_THRESHOLD=6
CB_OPENAI_COOLDOWN=45
CB_STRIPE_THRESHOLD=5
CB_STRIPE_COOLDOWN=30

# ── Uploads
UPLOAD_MAX_BYTES_IMAGE=5242880
UPLOAD_MAX_BYTES_DOCUMENT=10485760
UPLOAD_STORAGE_ROOT=uploads

# ── S3 / MinIO (laisser vide pour dev — stockage local)
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET=autocommerce-uploads
S3_REGION=us-east-1
S3_USE_PRESIGNED_URLS=True
S3_PRESIGNED_EXPIRY=3600
S3_PUBLIC_URL=

# ── PostgreSQL HA
POSTGRES_REPLICATION_PASSWORD=

# ── Observability
LOG_LEVEL=INFO
LOG_FORMAT=json
METRICS_ENABLED=True

# ══════════════════════════════════════════════════════════════════════════════
# RÉSUMÉ DES CREDENTIALS GÉNÉRÉS — SAUVEGARDEZ-LES !
# ══════════════════════════════════════════════════════════════════════════════
# DB Password:          ${DB_PASS}
# Admin Password:       ${ADMIN_PASS}
# SuperAdmin Password:  ${SUPERADMIN_PASS}
# ══════════════════════════════════════════════════════════════════════════════
ENV
