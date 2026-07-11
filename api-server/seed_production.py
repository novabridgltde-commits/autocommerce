import asyncio
import logging
import os
import sys
from pathlib import Path

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.v1.auth import hash_password
from models.database import Store, User


REPORTS_DIR = Path(__file__).resolve().parent / "reports"
SEED_LOG_PATH = REPORTS_DIR / "seed.log"


def _require_env(key: str) -> str:
    """Read a required environment variable. Raises RuntimeError if not set."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"Required environment variable '{key}' is not set. "
            f"Set it before running the seed script."
        )
    return value



def _make_async_url(raw: str) -> str:
    import re

    url = raw
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    url = re.sub(r"[?&]sslmode=[^&]*", "", url)
    url = re.sub(r"[?&]connect_timeout=[^&]*", "", url)
    return url.rstrip("?").rstrip("&")


_raw_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://autocommerce:autocommerce_pass@localhost/autocommerce",
)
DATABASE_URL = _make_async_url(_raw_url)


def _build_seed_logger() -> structlog.stdlib.BoundLogger:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("seed_production")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not any(getattr(handler, "baseFilename", None) == str(SEED_LOG_PATH) for handler in logger.handlers):
        handler = logging.FileHandler(SEED_LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return structlog.wrap_logger(logger)


async def _already_seeded(session: AsyncSession) -> bool:
    result = await session.execute(
        text("SELECT EXISTS(SELECT 1 FROM users WHERE role IN ('admin', 'super_admin'))")
    )
    return bool(result.scalar())


async def seed() -> int:
    logger = _build_seed_logger()
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            if await _already_seeded(session):
                print("Already seeded")
                return 0

            result = await session.execute(select(Store).where(Store.slug == "demo-store"))
            store = result.scalar_one_or_none()

            if not store:
                store = Store(
                    name="Demo Store",
                    slug="demo-store",
                    country="TN",
                    onboarding_completed=True,
                )
                session.add(store)
                await session.flush()
                print("Store created.")
            else:
                print("Store already exists.")

            result = await session.execute(select(User).where(User.email == "admin@autocommerce.tn"))
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    email="admin@autocommerce.tn",
                    hashed_password=hash_password(_require_env("ADMIN_INITIAL_PASSWORD")),
                    role="admin",
                    store_id=store.id,
                    is_active=True,
                )
                session.add(user)
                logger.info(
                    "seed_insert",
                    email=user.email,
                    role=user.role,
                )
                print("Admin user created (admin@autocommerce.tn). Password from ADMIN_INITIAL_PASSWORD env var.")
            else:
                print("Admin user already exists.")

            result = await session.execute(select(User).where(User.email == "superadmin@autocommerce.tn"))
            super_user = result.scalar_one_or_none()
            if not super_user:
                super_user = User(
                    email="superadmin@autocommerce.tn",
                    hashed_password=hash_password(_require_env("SUPERADMIN_INITIAL_PASSWORD")),
                    role="super_admin",
                    store_id=store.id,
                    is_active=True,
                )
                session.add(super_user)
                logger.info(
                    "seed_insert",
                    email=super_user.email,
                    role=super_user.role,
                )
                print("Super Admin user created. Password from SUPERADMIN_INITIAL_PASSWORD env var.")
            else:
                print("Super Admin user already exists.")

            await session.commit()
        print("Seeding completed successfully.")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(seed()))
