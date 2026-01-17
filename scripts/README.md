# Development Scripts

This directory contains utility scripts for development and testing.

## dev_sync_from_supabase.py

Syncs data from the Supabase frontend to the backend PostgreSQL database. Useful during development to ensure the backend has the same data as the frontend.

### Setup

1. Add Supabase credentials to `.env`:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
BACKEND_URL=http://localhost:8000  # Optional, defaults to localhost:8000
```

2. Install httpx dependency (if not already installed):

```bash
pip install -e '.[dev]'
```

### Usage

From the repository root:

```bash
# Dry run - shows what would be synced without making changes
./dev_sync.sh --dry-run

# Actually sync the data
./dev_sync.sh
```

Or run the Python script directly:

```bash
python scripts/dev_sync_from_supabase.py --dry-run
python scripts/dev_sync_from_supabase.py
```

### What it syncs

The script fetches and syncs the following tables in order:

1. **users** - All user records from Supabase
2. **trips** - All trip records from Supabase
3. **trip_members** - All trip member relationships from Supabase

The script uses the backend's idempotent sync endpoints, so it's safe to run multiple times. Existing records will be updated, and new records will be created.

### Output

```
============================================================
Travel Roboto - Development Sync from Supabase
============================================================
Checking backend health at http://localhost:8000...
✓ Backend is healthy

📥 Fetching users from Supabase...
✓ Found 3 records in users

📥 Fetching trips from Supabase...
✓ Found 2 records in trips

📥 Fetching trip_members from Supabase...
✓ Found 4 records in trip_members

Syncing 3 users...
  ✓ Synced user: test@example.com
  ✓ Synced user: user2@example.com
  ✓ Synced user: user3@example.com

Syncing 2 trips...
  ✓ Synced trip: Kiran's Bday Trip
  ✓ Synced trip: Summer Vacation

Syncing 4 trip members...
  ✓ Synced trip member: user-id-1 to trip trip-id-1
  ✓ Synced trip member: user-id-2 to trip trip-id-1
  ✓ Synced trip member: user-id-3 to trip trip-id-2
  ✓ Synced trip member: user-id-4 to trip trip-id-2

============================================================
✓ Sync complete!
============================================================
```

### When to use

- After making changes in the frontend that you want reflected in the backend
- When setting up a fresh backend database for testing
- When the backend gets out of sync with the frontend
- Before running backend tests that depend on specific data

### Requirements

- Backend server must be running on `http://localhost:8000` (or configured `BACKEND_URL`)
- Supabase credentials must be configured in `.env`
- httpx package must be installed (included in dev dependencies)
