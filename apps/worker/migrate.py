"""Run database migrations on startup"""
import asyncpg
import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS = [
    "db/schema.sql",
    "db/seed.sql",
    "db/migrations/2025_10_25_add_sim_tables.sql",
    "db/migrations/2025_10_26_add_multi_agent_support.sql",
    "db/migrations/2025_10_26_add_market_prices.sql",
    "db/migrations/2025_10_26_add_exit_plan_to_positions.sql",
    "db/migrations/2025_10_26_add_leverage_to_positions.sql",
    "db/migrations/2025_10_27_add_position_entry_time.sql",
    "db/migrations/2025_10_27_add_observation_action_to_chat.sql",
]


async def run_migrations(database_url: str):
    """Run all migrations in order"""
    logger.info("Starting database migrations...")

    conn = await asyncpg.connect(database_url)

    try:
        # Create migrations tracking table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Get list of already applied migrations
        applied = await conn.fetch("SELECT filename FROM _migrations")
        applied_files = {row['filename'] for row in applied}

        # Run each migration if not already applied
        base_path = Path(__file__).parent
        for migration_file in MIGRATIONS:
            if migration_file in applied_files:
                logger.info(f"Skipping already applied: {migration_file}")
                continue

            migration_path = base_path / migration_file
            if not migration_path.exists():
                logger.warning(f"Migration file not found: {migration_path}")
                continue

            logger.info(f"Applying migration: {migration_file}")
            sql = migration_path.read_text()

            try:
                # Run migration in a transaction
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO _migrations (filename) VALUES ($1)",
                        migration_file
                    )
                logger.info(f"✓ Applied: {migration_file}")
            except Exception as e:
                logger.error(f"✗ Failed to apply {migration_file}: {e}")
                # For idempotent migrations (CREATE IF NOT EXISTS, etc),
                # we can mark as applied even if it errors
                if "already exists" in str(e).lower():
                    logger.info(f"Migration {migration_file} already applied (objects exist)")
                    await conn.execute(
                        "INSERT INTO _migrations (filename) VALUES ($1) ON CONFLICT DO NOTHING",
                        migration_file
                    )
                else:
                    raise

        logger.info("✓ All migrations completed successfully")

    finally:
        await conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    asyncio.run(run_migrations(database_url))
