#!/bin/bash
# Test runner script for Travel Roboto AI Backend
#
# Usage:
#   ./run_tests.sh              # Run all tests
#   ./run_tests.sh sync         # Run only sync endpoint tests
#   ./run_tests.sh database     # Run only database tests
#   ./run_tests.sh --coverage   # Run with coverage report

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Travel Roboto AI Backend - Test Runner${NC}"
echo -e "${YELLOW}========================================${NC}\n"

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Activating virtual environment..."
    source venv/bin/activate
else
    echo -e "${RED}✗${NC} Virtual environment not found. Run: python -m venv venv && pip install -e '.[dev]'"
    exit 1
fi

# Check if test database exists
echo -e "${GREEN}✓${NC} Checking database connection..."
if ! psql -U postgres -lqt | cut -d \| -f 1 | grep -qw travelroboto_test 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC}  Test database 'travelroboto_test' not found. Creating it..."
    createdb -U postgres travelroboto_test 2>/dev/null || echo -e "${YELLOW}⚠${NC}  Database may already exist or you may not have permissions"
fi

# Parse arguments
TEST_PATH="tests/"
PYTEST_ARGS=""

if [ "$1" == "sync" ]; then
    TEST_PATH="tests/test_api_sync.py"
    echo -e "${GREEN}✓${NC} Running sync endpoint tests only...\n"
elif [ "$1" == "database" ]; then
    TEST_PATH="tests/test_database.py"
    echo -e "${GREEN}✓${NC} Running database tests only...\n"
elif [ "$1" == "--coverage" ] || [ "$2" == "--coverage" ]; then
    PYTEST_ARGS="--cov=. --cov-report=term-missing --cov-report=html"
    echo -e "${GREEN}✓${NC} Running tests with coverage report...\n"
elif [ -n "$1" ]; then
    TEST_PATH="$1"
    echo -e "${GREEN}✓${NC} Running tests from: $TEST_PATH\n"
else
    echo -e "${GREEN}✓${NC} Running all tests...\n"
fi

# Run pytest
pytest $TEST_PATH -v $PYTEST_ARGS

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}\n"
else
    echo -e "\n${RED}========================================${NC}"
    echo -e "${RED}✗ Some tests failed${NC}"
    echo -e "${RED}========================================${NC}\n"
    exit 1
fi
