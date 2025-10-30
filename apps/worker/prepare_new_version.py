#!/usr/bin/env python3
"""
Prepare database for new version deployment.

This script:
1. Ends the current version and calculates final performance
2. Resets account state (positions, metadata)
3. Preserves all historical data for the leaderboard

Run this BEFORE deploying a new version:
    python prepare_new_version.py
"""

import asyncio
import sys
from db import Database
from config import settings

async def main():
    print("=" * 60)
    print("PREPARE DATABASE FOR NEW VERSION DEPLOYMENT")
    print("=" * 60)
    print()
    print("This will:")
    print("  ✓ End current version and calculate final performance")
    print("  ✓ Clear current positions")
    print("  ✓ Reset account state metadata")
    print("  ✓ Clear exit plans")
    print("  ✓ Keep all historical data for leaderboard")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Aborted.")
        sys.exit(0)

    print()
    print("Connecting to database...")
    db = Database(settings.database_url)
    await db.connect()

    try:
        # Get current version info
        current_version_id = await db.get_current_version_id()
        if current_version_id:
            async with db.pool.acquire() as conn:
                version = await conn.fetchrow(
                    "SELECT version_tag, deployed_at FROM agent_versions WHERE id = $1",
                    current_version_id
                )
                if version:
                    print(f"Current version: {version['version_tag']}")
                    print(f"Deployed at: {version['deployed_at']}")
                    print()
        else:
            print("No active version found.")
            print()

        # Run the preparation
        await db.prepare_for_new_version()

        print()
        print("=" * 60)
        print("✓ DATABASE PREPARED FOR NEW VERSION")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Update AGENT_VERSION in config.py to your new version (e.g., v1.0.2)")
        print("2. Rebuild and redeploy:")
        print("   cd infra")
        print("   docker compose down")
        print("   docker compose build worker api")
        print("   docker compose up -d")
        print()
        print("The new version will:")
        print("  • Start with fresh $10,000 account")
        print("  • Create new version entry in database")
        print("  • Begin tracking performance separately")
        print("  • Show on leaderboard alongside previous versions")
        print()

    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
