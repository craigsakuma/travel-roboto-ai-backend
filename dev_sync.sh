#!/bin/bash
# Development sync script - pulls data from Supabase frontend and syncs to backend
#
# Prerequisites:
#   - SUPABASE_URL and SUPABASE_KEY must be set in .env
#   - Backend server must be running on http://localhost:8000
#
# Usage:
#   ./dev_sync.sh              # Sync all data from Supabase to backend
#   ./dev_sync.sh --dry-run    # Show what would be synced without making changes

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Run the Python sync script
python3 scripts/dev_sync_from_supabase.py "$@"
