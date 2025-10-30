#!/usr/bin/env python3
"""
Completely wipe all data for a specific version.

This script:
1. Deletes ALL data associated with the specified version
2. Removes the version entry itself
3. This is irreversible - the version will be completely removed from history

Run this to completely delete a version:
    python wipe_version.py
"""

import asyncio
import sys
from db import Database
from config import settings

async def main():
    print("=" * 60)
    print("COMPLETELY WIPE VERSION DATA")
    print("=" * 60)
    print()
    print("⚠️  WARNING: This will PERMANENTLY delete ALL data for a version!")
    print()

    db = Database(settings.database_url)
    await db.connect()

    try:
        # List all versions
        async with db.pool.acquire() as conn:
            versions = await conn.fetch(
                """
                SELECT id, version_tag, deployed_at, retired_at, version_description
                FROM agent_versions
                ORDER BY deployed_at DESC
                """
            )

            if not versions:
                print("No versions found in database.")
                sys.exit(0)

            print("Available versions:")
            print()
            for v in versions:
                status = "ACTIVE" if not v['retired_at'] else "RETIRED"
                print(f"  [{v['id']}] {v['version_tag']} - {status}")
                print(f"      Deployed: {v['deployed_at']}")
                if v['retired_at']:
                    print(f"      Retired: {v['retired_at']}")
                if v['version_description']:
                    print(f"      Description: {v['version_description']}")
                print()

            # Get version to delete
            version_input = input("Enter version ID to DELETE (or 'cancel' to abort): ").strip()

            if version_input.lower() == 'cancel':
                print("Aborted.")
                sys.exit(0)

            try:
                version_id = int(version_input)
            except ValueError:
                print("Invalid version ID.")
                sys.exit(1)

            # Get version details
            version = await conn.fetchrow(
                "SELECT version_tag, deployed_at FROM agent_versions WHERE id = $1",
                version_id
            )

            if not version:
                print(f"Version ID {version_id} not found.")
                sys.exit(1)

            print()
            print("=" * 60)
            print(f"ABOUT TO DELETE: {version['version_tag']} (ID: {version_id})")
            print("=" * 60)
            print()
            print("This will DELETE:")
            print(f"  • All trades for {version['version_tag']}")
            print(f"  • All equity snapshots for {version['version_tag']}")
            print(f"  • All chat messages for {version['version_tag']}")
            print(f"  • All version activity records for {version['version_tag']}")
            print(f"  • The version entry itself")
            print()
            print("⚠️  THIS CANNOT BE UNDONE!")
            print()

            confirm = input(f"Type '{version['version_tag']}' to confirm deletion: ").strip()

            if confirm != version['version_tag']:
                print("Confirmation failed. Aborted.")
                sys.exit(0)

            print()
            print("Deleting all data...")

            # Delete all data for this version
            trades_deleted = await conn.execute(
                "DELETE FROM trades WHERE version_id = $1",
                version_id
            )
            print(f"  ✓ Deleted trades: {trades_deleted}")

            equity_deleted = await conn.execute(
                "DELETE FROM equity_snapshots WHERE version_id = $1",
                version_id
            )
            print(f"  ✓ Deleted equity snapshots: {equity_deleted}")

            chat_deleted = await conn.execute(
                "DELETE FROM model_chat WHERE version_id = $1",
                version_id
            )
            print(f"  ✓ Deleted chat messages: {chat_deleted}")

            activity_deleted = await conn.execute(
                "DELETE FROM version_activity WHERE version_id = $1",
                version_id
            )
            print(f"  ✓ Deleted version activity records: {activity_deleted}")

            version_deleted = await conn.execute(
                "DELETE FROM agent_versions WHERE id = $1",
                version_id
            )
            print(f"  ✓ Deleted version entry: {version_deleted}")

            print()
            print("=" * 60)
            print(f"✓ VERSION {version['version_tag']} COMPLETELY DELETED")
            print("=" * 60)
            print()

    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
