#!/usr/bin/env python3
"""daily_purge.py — purge RGPD des messages WhatsApp > 12 mois.

Usage:
  python3 scripts/daily_purge.py --dry-run
  python3 scripts/daily_purge.py

Comportement:
  - ne supprime que `whatsapp_messages.created_at < now() - 12 months`
  - `--dry-run` affiche le nombre de lignes concernées sans suppression
  - journalise un résumé dans /app/logs/purge.log (ou ./logs/purge.log en local)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

try:
    from dateutil.relativedelta import relativedelta
except ImportError:  # pragma: no cover - optional dependency
    relativedelta = None

ROOT = Path(__file__).resolve().parents[1]
API_SERVER_DIR = ROOT / "api-server"
if str(API_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(API_SERVER_DIR))

from models.database import engine  # noqa: E402

LOGGER = logging.getLogger("daily_purge")
TABLE_NAME = "whatsapp_messages"
RETENTION_MONTHS = 12


def _configure_logging() -> None:
    target_dir = Path("/app/logs") if Path("/app/logs").exists() else (ROOT / "logs")
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = target_dir / "purge.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


async def _table_exists() -> bool:
    async with engine.connect() as conn:
        def _has_table(sync_conn) -> bool:
            from sqlalchemy import inspect

            return inspect(sync_conn).has_table(TABLE_NAME)

        return bool(await conn.run_sync(_has_table))


def _python_threshold() -> datetime:
    now_utc = datetime.now(UTC)
    if relativedelta is not None:
        return now_utc - relativedelta(months=RETENTION_MONTHS)
    return now_utc - timedelta(days=365)


async def purge_old_messages(*, dry_run: bool) -> int:
    if not await _table_exists():
        LOGGER.warning("table %s not found — purge skipped", TABLE_NAME)
        return 0

    dialect = engine.dialect.name
    params: dict[str, object] = {}

    if dialect == "postgresql":
        threshold_clause = "CURRENT_TIMESTAMP - INTERVAL '12 months'"
    elif dialect == "sqlite":
        threshold_clause = "datetime('now', '-12 months')"
    else:
        threshold_clause = ":threshold"
        params["threshold"] = _python_threshold()

    LOGGER.info("daily_purge dialect=%s retention_months=%s", dialect, RETENTION_MONTHS)

    count_sql = text(
        f"""
        SELECT count(*)
        FROM {TABLE_NAME}
        WHERE created_at < ({threshold_clause})
        """
    )
    delete_sql = text(
        f"""
        DELETE FROM {TABLE_NAME}
        WHERE created_at < ({threshold_clause})
        """
    )

    async with engine.begin() as conn:
        count_result = await conn.execute(count_sql, params)
        affected = int(count_result.scalar() or 0)

        if dry_run or affected == 0:
            LOGGER.info(
                "daily_purge dry_run=%s retention_months=%s affected=%s executed_at=%s",
                dry_run,
                RETENTION_MONTHS,
                affected,
                datetime.now(UTC).isoformat(),
            )
            return affected

        delete_result = await conn.execute(delete_sql, params)
        deleted = int(delete_result.rowcount or 0)
        LOGGER.info(
            "daily_purge dry_run=%s retention_months=%s deleted=%s executed_at=%s",
            dry_run,
            RETENTION_MONTHS,
            deleted,
            datetime.now(UTC).isoformat(),
        )
        return deleted


async def _main(dry_run: bool) -> int:
    return await purge_old_messages(dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="RGPD purge for whatsapp_messages older than 12 months")
    parser.add_argument("--dry-run", action="store_true", help="report matching rows without deleting them")
    args = parser.parse_args()

    _configure_logging()
    affected = asyncio.run(_main(dry_run=args.dry_run))
    print(affected)


if __name__ == "__main__":
    main()
