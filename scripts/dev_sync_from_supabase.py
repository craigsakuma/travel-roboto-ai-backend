#!/usr/bin/env python3
"""
Development sync script to pull data from Supabase frontend and sync to backend.

Usage:
    python scripts/dev_sync_from_supabase.py [--dry-run]

Environment variables required:
    SUPABASE_URL - Supabase project URL
    SUPABASE_KEY - Supabase anon/service key
    BACKEND_URL - Backend API URL (default: http://localhost:8000)
"""

import argparse
import asyncio
import os
import sys
from typing import Any

import httpx
from dotenv import load_dotenv

# Add parent directory to path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Color codes for output
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color


def print_colored(color: str, message: str) -> None:
    """Print colored message."""
    print(f"{color}{message}{NC}")


async def fetch_supabase_table(
    client: httpx.AsyncClient, table_name: str
) -> list[dict[str, Any]]:
    """Fetch all records from a Supabase table."""
    url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

    print_colored(YELLOW, f"📥 Fetching {table_name} from Supabase...")
    response = await client.get(url, headers=headers, timeout=30.0)
    response.raise_for_status()

    data = response.json()
    print_colored(GREEN, f"✓ Found {len(data)} records in {table_name}")
    return data


async def sync_users(
    client: httpx.AsyncClient, users: list[dict[str, Any]], dry_run: bool = False
) -> None:
    """Sync users to backend."""
    print_colored(BLUE, f"\n{'[DRY RUN] ' if dry_run else ''}Syncing {len(users)} users...")

    for user in users:
        # Map Supabase fields to backend fields
        # Note: Supabase user_profiles doesn't have email (it's in auth.users)
        # and uses phone_number instead of phone
        user_data = {
            "id": user.get("id"),
            "email": user.get("email") or f"{user.get('id')}@placeholder.com",  # Email not in user_profiles
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "phone": user.get("phone_number") or user.get("phone"),
            "home_city": user.get("home_city"),
        }

        if dry_run:
            print(f"  [DRY RUN] Would sync user: {user_data['email']} ({user_data['id']})")
            continue

        response = await client.post(
            f"{BACKEND_URL}/api/users/sync", json=user_data, timeout=10.0
        )

        if response.status_code == 200:
            print_colored(GREEN, f"  ✓ Synced user: {user_data['email']}")
        else:
            print_colored(
                RED,
                f"  ✗ Failed to sync user {user_data['email']}: {response.status_code} - {response.text}",
            )


async def sync_trips(
    client: httpx.AsyncClient, trips: list[dict[str, Any]], dry_run: bool = False
) -> None:
    """Sync trips to backend."""
    print_colored(BLUE, f"\n{'[DRY RUN] ' if dry_run else ''}Syncing {len(trips)} trips...")

    for trip in trips:
        # Map Supabase fields to backend fields
        # Note: Supabase uses 'created_by' instead of 'created_by_user_id'
        trip_data = {
            "id": trip.get("id"),
            "name": trip.get("name"),
            "destination": trip.get("destination"),
            "start_date": trip.get("start_date"),
            "end_date": trip.get("end_date"),
            "created_by_user_id": trip.get("created_by") or trip.get("created_by_user_id"),
        }

        if dry_run:
            print(f"  [DRY RUN] Would sync trip: {trip_data['name']} ({trip_data['id']})")
            continue

        response = await client.post(
            f"{BACKEND_URL}/api/trips/sync", json=trip_data, timeout=10.0
        )

        if response.status_code == 200:
            print_colored(GREEN, f"  ✓ Synced trip: {trip_data['name']}")
        else:
            print_colored(
                RED,
                f"  ✗ Failed to sync trip {trip_data['name']}: {response.status_code} - {response.text}",
            )


async def sync_trip_members(
    client: httpx.AsyncClient, trip_members: list[dict[str, Any]], dry_run: bool = False
) -> None:
    """Sync trip members to backend."""
    print_colored(
        BLUE, f"\n{'[DRY RUN] ' if dry_run else ''}Syncing {len(trip_members)} trip members..."
    )

    for member in trip_members:
        trip_id = member["trip_id"]
        member_data = {
            "user_id": member["user_id"],
            "role": member.get("role", "traveler"),
        }

        if dry_run:
            print(
                f"  [DRY RUN] Would sync trip member: {member_data['user_id']} to trip {trip_id}"
            )
            continue

        response = await client.post(
            f"{BACKEND_URL}/api/trips/{trip_id}/members/sync",
            json=member_data,
            timeout=10.0,
        )

        if response.status_code == 200:
            print_colored(
                GREEN, f"  ✓ Synced trip member: {member_data['user_id']} to trip {trip_id}"
            )
        else:
            print_colored(
                RED,
                f"  ✗ Failed to sync trip member: {response.status_code} - {response.text}",
            )


async def main(dry_run: bool = False) -> None:
    """Main sync process."""
    # Validate configuration
    if not SUPABASE_URL or not SUPABASE_KEY:
        print_colored(RED, "✗ SUPABASE_URL and SUPABASE_KEY must be set in .env")
        print_colored(
            YELLOW,
            "  Add these to your .env file:\n  SUPABASE_URL=https://your-project.supabase.co\n  SUPABASE_KEY=your-anon-key",
        )
        sys.exit(1)

    print_colored(BLUE, "=" * 60)
    print_colored(BLUE, "Travel Roboto - Development Sync from Supabase")
    print_colored(BLUE, "=" * 60)
    if dry_run:
        print_colored(YELLOW, "\n⚠️  DRY RUN MODE - No changes will be made\n")

    async with httpx.AsyncClient() as client:
        # Check backend health
        try:
            print_colored(YELLOW, f"Checking backend health at {BACKEND_URL}...")
            response = await client.get(f"{BACKEND_URL}/health", timeout=5.0)
            response.raise_for_status()
            print_colored(GREEN, "✓ Backend is healthy\n")
        except Exception as e:
            print_colored(RED, f"✗ Backend not available at {BACKEND_URL}: {e}")
            print_colored(YELLOW, "  Make sure the backend server is running: python main.py")
            sys.exit(1)

        try:
            # Fetch data from Supabase (using actual table names)
            users = await fetch_supabase_table(client, "user_profiles")
            trips = await fetch_supabase_table(client, "trips")
            trip_members = await fetch_supabase_table(client, "trip_members")

            # Sync in order (users first, then trips, then trip members)
            await sync_users(client, users, dry_run)
            await sync_trips(client, trips, dry_run)
            await sync_trip_members(client, trip_members, dry_run)

            print_colored(GREEN, "\n" + "=" * 60)
            if dry_run:
                print_colored(
                    GREEN, "✓ Dry run complete! Run without --dry-run to apply changes"
                )
            else:
                print_colored(GREEN, "✓ Sync complete!")
            print_colored(GREEN, "=" * 60)

        except httpx.HTTPStatusError as e:
            print_colored(RED, f"\n✗ HTTP error: {e.response.status_code}")
            print_colored(RED, f"  Response: {e.response.text}")
            sys.exit(1)
        except Exception as e:
            print_colored(RED, f"\n✗ Error: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Supabase data to backend")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without making changes",
    )
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run))
