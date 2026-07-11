from __future__ import annotations

import asyncio
from datetime import datetime
import os
from pathlib import Path
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
for candidate in (ROOT, SCRIPTS_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-32chars-minimum!!")
os.environ.setdefault("ENCRYPTION_KEY", "mQ76Y4LQdjfKjD42QikIYjneih_7xToYtL6vhfVqlh0=")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32chars-minimum!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CSRF_SECRET", "test-csrf-secret-32-chars-minimum-ok!")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test-app-secret")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test-ig-token")
os.environ.setdefault("FACEBOOK_VERIFY_TOKEN", "test-fb-token")
os.environ.setdefault("TIKTOK_VERIFY_TOKEN", "test-tt-token")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-000000000000000000000000000000000000000000000000")
os.environ.setdefault("INTERNAL_HEALTH_TOKEN", "test-health-token-001")

import daily_purge  # noqa: E402


async def _run_case() -> int:
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE whatsapp_messages (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        await conn.execute(
            text(
                "INSERT INTO whatsapp_messages (id, created_at) VALUES (:id, :created_at)"
            ),
            {"id": 1, "created_at": datetime(2020, 1, 1, 0, 0, 0).isoformat(sep=" ")},
        )

    original_engine = daily_purge.engine
    try:
        daily_purge.engine = test_engine
        return await daily_purge.purge_old_messages(dry_run=True)
    finally:
        daily_purge.engine = original_engine
        await test_engine.dispose()


def test_daily_purge_sqlite_dry_run_returns_one() -> None:
    assert asyncio.run(_run_case()) == 1
