#!/bin/bash
# Manual testing script for sync endpoints
#
# Prerequisites:
#   - Server must be running on http://localhost:8000
#   - Run: python main.py
#
# Usage:
#   ./manual_test_sync.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

BASE_URL="http://localhost:8000"

# Generate UUIDs for testing
USER_ID=$(uuidgen)
TRIP_ID=$(uuidgen)
USER_ID_2=$(uuidgen)

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Manual Sync Endpoint Tests${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if server is running
echo -e "${YELLOW}Checking if server is running...${NC}"
if ! curl -s "${BASE_URL}/health" > /dev/null; then
    echo -e "${RED}✗ Server is not running on ${BASE_URL}${NC}"
    echo -e "${YELLOW}Please start the server with: python main.py${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Server is running${NC}\n"

# Test 1: Sync User (Create)
echo -e "${YELLOW}Test 1: POST /api/users/sync (create)${NC}"
RESPONSE=$(curl -s -X POST "${BASE_URL}/api/users/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'"${USER_ID}"'",
    "email": "test@example.com",
    "first_name": "Test",
    "last_name": "User",
    "phone": "+1-555-0100",
    "home_city": "San Francisco, CA"
  }')

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ User created successfully${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed to create user${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Test 2: Sync User (Update - Idempotent)
echo -e "${YELLOW}Test 2: POST /api/users/sync (update/idempotent)${NC}"
RESPONSE=$(curl -s -X POST "${BASE_URL}/api/users/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'"${USER_ID}"'",
    "email": "test@example.com",
    "first_name": "Updated",
    "last_name": "Name",
    "phone": "+1-555-0100",
    "home_city": "Los Angeles, CA"
  }')

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ User updated successfully${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed to update user${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Test 3: Sync Trip (Create)
echo -e "${YELLOW}Test 3: POST /api/trips/sync (create)${NC}"
RESPONSE=$(curl -s -X POST "${BASE_URL}/api/trips/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'"${TRIP_ID}"'",
    "name": "SF Fall Trip",
    "destination": "San Francisco, CA",
    "start_date": "2026-09-04",
    "end_date": "2026-10-05",
    "created_by_user_id": "'"${USER_ID}"'"
  }')

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ Trip created successfully${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed to create trip${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Test 4: Sync Trip (Update - Idempotent)
echo -e "${YELLOW}Test 4: POST /api/trips/sync (update/idempotent)${NC}"
RESPONSE=$(curl -s -X POST "${BASE_URL}/api/trips/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'"${TRIP_ID}"'",
    "name": "Updated Trip Name",
    "destination": "New York, NY",
    "start_date": "2026-09-04",
    "end_date": "2026-10-05",
    "created_by_user_id": "'"${USER_ID}"'"
  }')

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ Trip updated successfully${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed to update trip${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Test 5: Sync Trip Member (Add)
echo -e "${YELLOW}Test 5: POST /api/trips/{trip_id}/members/sync (add)${NC}"
# First create a second user
curl -s -X POST "${BASE_URL}/api/users/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'"${USER_ID_2}"'",
    "email": "user2@example.com",
    "first_name": "Second",
    "last_name": "User"
  }' > /dev/null

RESPONSE=$(curl -s -X POST "${BASE_URL}/api/trips/${TRIP_ID}/members/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "'"${USER_ID_2}"'",
    "role": "traveler"
  }')

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ Trip member added successfully${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed to add trip member${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Test 6: Sync Trip Member (Update Role)
echo -e "${YELLOW}Test 6: POST /api/trips/{trip_id}/members/sync (update role)${NC}"
RESPONSE=$(curl -s -X POST "${BASE_URL}/api/trips/${TRIP_ID}/members/sync" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "'"${USER_ID_2}"'",
    "role": "organizer"
  }')

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ Trip member role updated successfully${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed to update trip member role${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Test 7: Message Feedback
echo -e "${YELLOW}Test 7: PATCH /api/messages/{message_id}/feedback${NC}"
echo -e "${YELLOW}Note: Skipping - requires a message to exist${NC}\n"

# Test 8: Remove Trip Member
echo -e "${YELLOW}Test 8: DELETE /api/trips/{trip_id}/members/{user_id}${NC}"
RESPONSE=$(curl -s -X DELETE "${BASE_URL}/api/trips/${TRIP_ID}/members/${USER_ID_2}")

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ Trip member removed successfully${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed to remove trip member${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Test 9: Remove Trip Member (Idempotent)
echo -e "${YELLOW}Test 9: DELETE /api/trips/{trip_id}/members/{user_id} (idempotent)${NC}"
RESPONSE=$(curl -s -X DELETE "${BASE_URL}/api/trips/${TRIP_ID}/members/${USER_ID_2}")

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ Idempotent removal successful${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed idempotent removal${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Test 10: Delete Trip
echo -e "${YELLOW}Test 10: DELETE /api/trips/{trip_id}${NC}"
RESPONSE=$(curl -s -X DELETE "${BASE_URL}/api/trips/${TRIP_ID}")

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ Trip deleted successfully${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed to delete trip${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Test 11: Delete Trip (Idempotent)
echo -e "${YELLOW}Test 11: DELETE /api/trips/{trip_id} (idempotent)${NC}"
RESPONSE=$(curl -s -X DELETE "${BASE_URL}/api/trips/${TRIP_ID}")

if echo "$RESPONSE" | jq -e '.success == true' > /dev/null; then
    echo -e "${GREEN}✓ Idempotent deletion successful${NC}"
    echo "$RESPONSE" | jq '.'
else
    echo -e "${RED}✗ Failed idempotent deletion${NC}"
    echo "$RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All manual tests passed!${NC}"
echo -e "${GREEN}========================================${NC}\n"
echo -e "Test IDs used:"
echo -e "  User 1: ${USER_ID}"
echo -e "  User 2: ${USER_ID_2}"
echo -e "  Trip:   ${TRIP_ID}"
echo ""
echo -e "${YELLOW}Note: Test data remains in database for inspection${NC}"
echo -e "${YELLOW}To clean up, restart the server or truncate tables${NC}"
