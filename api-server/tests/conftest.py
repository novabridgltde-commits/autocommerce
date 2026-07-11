"""Shared pytest bootstrap for AutoCommerce V25 merged delivery.

Ensures required environment variables are present before importing app modules.
"""
from __future__ import annotations

import os
import sys

API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

# Core app
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-32chars-minimum!!")
os.environ.setdefault("ENCRYPTION_KEY", "mQ76Y4LQdjfKjD42QikIYjneih_7xToYtL6vhfVqlh0=")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32chars-minimum!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CSRF_SECRET", "test-csrf-secret-32-chars-minimum-ok!")
os.environ.setdefault("SKIP_LIMITER", "1")

# Integrations / webhooks
os.environ.setdefault("WHATSAPP_APP_SECRET", "test-app-secret")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("INSTAGRAM_APP_SECRET", "")
os.environ.setdefault("FACEBOOK_APP_SECRET", "")
os.environ.setdefault("TIKTOK_APP_SECRET", "")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test-ig-token")
os.environ.setdefault("FACEBOOK_VERIFY_TOKEN", "test-fb-token")
os.environ.setdefault("TIKTOK_VERIFY_TOKEN", "test-tt-token")
os.environ.setdefault("TIKTOK_ENABLED", "false")

# AI / LLM
os.environ.setdefault("OPENAI_API_KEY", "sk-test-000000000000000000000000000000000000000000000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-0000")
os.environ.setdefault("DEEPSEEK_API_KEY", "ds-test-000000000000000000000000")
os.environ.setdefault("LLM_PROVIDER", "stub")
os.environ.setdefault("VISION_PROVIDER", "stub")
os.environ.setdefault("LOYALTY_IA_ENABLED", "true")
os.environ.setdefault("PREDICTIVE_RESTOCKING_ENABLED", "true")

# Misc
os.environ.setdefault("SUPER_ADMIN_SECRET", "super-secret-test")
os.environ.setdefault("SENDGRID_API_KEY", "SG.test.test")
os.environ.setdefault("FROM_EMAIL", "test@example.com")
os.environ.setdefault("FLOUCI_APP_TOKEN", "test-flouci-token")
os.environ.setdefault("FLOUCI_APP_SECRET", "test-flouci-secret")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
os.environ.setdefault("AWS_REGION", "eu-west-1")
os.environ.setdefault("INTERNAL_HEALTH_TOKEN", "test-health-token-001")
os.environ.setdefault("SERVER_DOMAIN", "https://test.example.com")
