"""tests/integration/conftest.py — Fixtures partagées pour les tests d'intégration.

Utilise SQLite in-memory (aiosqlite) pour l'isolation complète.
Chaque test reçoit une DB vierge via les fixtures async_client / db_session.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Forcer SQLite in-memory avant tout import applicatif ──────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-32chars-minimum!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test-app-secret")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("INSTAGRAM_APP_SECRET", "")
os.environ.setdefault("FACEBOOK_APP_SECRET", "")
os.environ.setdefault("TIKTOK_APP_SECRET", "")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test-ig-token")
os.environ.setdefault("FACEBOOK_VERIFY_TOKEN", "test-fb-token")
os.environ.setdefault("TIKTOK_VERIFY_TOKEN", "test-tt-token")
os.environ.setdefault("TIKTOK_ENABLED", "false")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmNoYXJz")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-000000000000000000000000000000000000000000000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-0000")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32chars-minimum!!")
os.environ.setdefault("SENDGRID_API_KEY", "SG.test.test")
os.environ.setdefault("FROM_EMAIL", "test@example.com")
os.environ.setdefault("SUPER_ADMIN_SECRET", "super-secret-test")
os.environ.setdefault("INTERNAL_HEALTH_TOKEN", "test-health-token-001")
os.environ.setdefault("FLOUCI_APP_TOKEN", "test-flouci-token")
os.environ.setdefault("FLOUCI_APP_SECRET", "test-flouci-secret")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
os.environ.setdefault("AWS_REGION", "eu-west-1")

# ── Imports applicatifs APRÈS la configuration des env vars ───────────────────
from models.database import Base  # noqa: E402

# ── Moteur SQLite in-memory ────────────────────────────────────────────────────
from models.database import engine

TestingSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
)


@pytest_asyncio.fixture(autouse=True)
async def create_tables():
    """Crée le schéma pour toute la session de test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        # Pour PostgreSQL, on utilise CASCADE pour gérer les dépendances FK
        if engine.dialect.name == "postgresql":
            await conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        else:
            # Pour SQLite (utilisé en tests locaux parfois), drop_all suffit généralement
            await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Session DB isolée pour chaque test — rollback automatique après."""
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Client HTTP async branché sur l'app FastAPI avec la DB de test."""
    from main import app
    from models.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, db_session: AsyncSession):
    """Factory de headers auth JWT pour différents rôles."""
    _cache: dict[str, dict[str, str]] = {}

    async def _get(role: str = "admin") -> dict[str, str]:
        if role in _cache:
            return _cache[role]
        suffix = uuid.uuid4().hex[:6]
        email = f"test_{role}_{suffix}@example.com"
        store_name = f"Store {role} {suffix}"
        payload = {
            "email": email,
            "password": "Password123!",
            "store_name": store_name,
        }
        if role == "super_admin":
            # super_admin créé via register puis forcé en DB
            from sqlalchemy import select

            from models.database import User
            resp = await async_client.post("/api/v1/auth/register", json=payload)
            assert resp.status_code in [200, 201], f"register failed: {resp.text}"
            token = resp.json()["access_token"]
            # Forcer le rôle super_admin en DB
            result = await db_session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                user.role = "super_admin"
                await db_session.commit()
            # Ré-émettre un token avec le bon rôle
            from api.v1.auth import create_token
            token = create_token(user.store_id, "super_admin", user_id=user.id)
        else:
            resp = await async_client.post("/api/v1/auth/register", json=payload)
            assert resp.status_code in [200, 201], f"register failed: {resp.text}"
            token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        _cache[role] = headers
        return headers

    return _get
