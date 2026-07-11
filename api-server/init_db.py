"""init_db.py — Initialise la base de données SQLite pour le mode demo/dev"""
import asyncio
import os
import sys

# Assure que le répertoire courant est dans le path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import create_async_engine

from models.database import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./autocommerce_demo.db")

async def init():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print(f"[init_db] Tables créées dans: {DATABASE_URL}")

if __name__ == "__main__":
    asyncio.run(init())
