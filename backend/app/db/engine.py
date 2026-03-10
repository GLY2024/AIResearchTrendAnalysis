"""SQLAlchemy async engine and session management."""

import json
import logging

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.db_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _cleanup_legacy_data():
    """Remove deprecated citation-expansion data and fields from the live database."""
    try:
        async with engine.begin() as conn:
            result = await conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in result.fetchall()}

            if "papers" in tables:
                delete_result = await conn.exec_driver_sql(
                    "DELETE FROM papers WHERE discovery_method IS NOT NULL AND discovery_method != 'search'"
                )
                if delete_result.rowcount and delete_result.rowcount > 0:
                    logger.info("Removed %s legacy non-search papers", delete_result.rowcount)

            if "search_plans" in tables:
                plan_rows = await conn.exec_driver_sql("SELECT id, plan_data FROM search_plans")
                updated_plans = 0
                for plan_id, raw_plan_data in plan_rows.fetchall():
                    try:
                        plan_data = raw_plan_data if isinstance(raw_plan_data, dict) else json.loads(raw_plan_data or "{}")
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(plan_data, dict) or "snowball_config" not in plan_data:
                        continue

                    plan_data.pop("snowball_config", None)
                    await conn.exec_driver_sql(
                        "UPDATE search_plans SET plan_data = ? WHERE id = ?",
                        (json.dumps(plan_data, ensure_ascii=False), plan_id),
                    )
                    updated_plans += 1

                if updated_plans > 0:
                    logger.info("Removed legacy citation-expansion config from %s search plans", updated_plans)

            await conn.exec_driver_sql("DROP TABLE IF EXISTS snowball_candidates")
            await conn.exec_driver_sql("DROP TABLE IF EXISTS snowball_runs")
    except OperationalError as exc:
        logger.warning("Skipping legacy cleanup because the database is locked: %s", exc)


async def init_db():
    """Create all tables."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _cleanup_legacy_data()


async def get_session() -> AsyncSession:
    """Dependency for FastAPI routes."""
    async with async_session() as session:
        yield session
