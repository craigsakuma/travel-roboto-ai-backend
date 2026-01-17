# Testing Quick Start Guide

## TL;DR - Run Tests Now

```bash
# Option 1: Automated pytest tests (recommended)
./run_tests.sh sync

# Option 2: Manual curl-based tests (for debugging)
./manual_test_sync.sh
```

## Prerequisites

### 0. Development Sync (Optional)

If you're working with the frontend and want to sync data from Supabase to the backend:

```bash
# Add Supabase credentials to .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Run sync (dry-run first to see what would happen)
./dev_sync.sh --dry-run

# Actually sync the data
./dev_sync.sh
```

This will pull all users, trips, and trip_members from your Supabase frontend and sync them to the backend database. Run this whenever you need to refresh backend data during development.

### 1. Install Test Dependencies

```bash
pip install -e '.[dev]'
```

This installs:
- pytest - Test framework
- pytest-asyncio - Async test support
- pytest-cov - Coverage reporting
- aiosqlite - In-memory database for tests
- pytest-mock - Mocking support

### 2. Create Test Database

```bash
createdb -U postgres travelroboto_test
```

Or let the test runner create it automatically.

### 3. Ensure Server is Running (for manual tests only)

```bash
python main.py
```

Server should be running on `http://localhost:8000`

## Three Ways to Test

### 1. Automated Tests (Best for CI/CD)

```bash
# Run all sync endpoint tests
./run_tests.sh sync

# Run all tests
./run_tests.sh

# Run with coverage report
./run_tests.sh --coverage

# Using pytest directly
pytest tests/test_api_sync.py -v
```

**Pros:**
- ✅ Comprehensive coverage (40+ test cases)
- ✅ Fast (<5 seconds)
- ✅ Isolated (fresh DB per test)
- ✅ Great for TDD workflow

**Cons:**
- ❌ Requires test database setup
- ❌ Less visibility into actual HTTP requests

### 2. Manual Tests (Best for Debugging)

```bash
# Start server first
python main.py

# In another terminal
./manual_test_sync.sh
```

**Pros:**
- ✅ See actual HTTP requests/responses
- ✅ Tests against running server
- ✅ Easy to modify and debug
- ✅ No test database required

**Cons:**
- ❌ Pollutes development database
- ❌ Less comprehensive than automated tests
- ❌ Slower

### 3. Interactive cURL (Best for Ad-hoc Testing)

```bash
# Generate a UUID
UUID=$(uuidgen)

# Create a user
curl -X POST http://localhost:8000/api/users/sync \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'$UUID'",
    "email": "test@example.com",
    "first_name": "Test",
    "last_name": "User"
  }'

# Create a trip
TRIP_ID=$(uuidgen)
curl -X POST http://localhost:8000/api/trips/sync \
  -H "Content-Type: application/json" \
  -d '{
    "id": "'$TRIP_ID'",
    "name": "Test Trip",
    "destination": "San Francisco",
    "start_date": "2026-09-01",
    "end_date": "2026-09-10",
    "created_by_user_id": "'$UUID'"
  }'
```

**Pros:**
- ✅ Maximum flexibility
- ✅ Perfect for exploration
- ✅ Can test edge cases easily

**Cons:**
- ❌ Manual and tedious
- ❌ Not repeatable
- ❌ No automated verification

## Test Coverage Summary

| Endpoint | Success Cases | Error Cases | Total |
|----------|---------------|-------------|-------|
| POST /api/users/sync | 3 | 3 | 6 |
| POST /api/trips/sync | 4 | 3 | 7 |
| DELETE /api/trips/{id} | 3 | 1 | 4 |
| POST /api/trips/{id}/members/sync | 3 | 3 | 6 |
| DELETE /api/trips/{id}/members/{uid} | 3 | 1 | 4 |
| PATCH /api/messages/{id}/feedback | 3 | 3 | 6 |
| **TOTAL** | **19** | **14** | **33** |

## Common Issues & Solutions

### Issue: "Test database not found"

```bash
# Solution: Create the test database
createdb -U postgres travelroboto_test
```

### Issue: "Server not running" (manual tests)

```bash
# Solution: Start the server
python main.py
```

### Issue: "Import errors"

```bash
# Solution: Reinstall dev dependencies
pip install -e '.[dev]'
```

### Issue: "Tests fail with database errors"

```bash
# Solution: Reset the test database
dropdb -U postgres travelroboto_test
createdb -U postgres travelroboto_test
```

### Issue: "jq: command not found" (manual tests)

```bash
# Solution: Install jq (JSON processor)
brew install jq  # macOS
# or
sudo apt-get install jq  # Linux
```

## Test Output Examples

### Successful Test Run

```
========================================
Travel Roboto AI Backend - Test Runner
========================================

✓ Activating virtual environment...
✓ Checking database connection...
✓ Running sync endpoint tests only...

tests/test_api_sync.py::TestUserSync::test_sync_user_create_success PASSED
tests/test_api_sync.py::TestUserSync::test_sync_user_update_success PASSED
tests/test_api_sync.py::TestUserSync::test_sync_user_idempotent PASSED
...
tests/test_api_sync.py::TestMessageFeedback::test_update_feedback_invalid_uuid PASSED

========================================
✓ All tests passed!
========================================
```

### Failed Test Example

```
FAILED tests/test_api_sync.py::TestUserSync::test_sync_user_create_success

E   AssertionError: assert 500 == 200
E    +  where 500 = <Response [500]>.status_code

tests/test_api_sync.py:25: AssertionError
```

## Next Steps After Running Tests

1. **All tests pass?** ✅
   - Great! Your API is working correctly
   - Check coverage report: `./run_tests.sh --coverage`
   - Review `htmlcov/index.html` for detailed coverage

2. **Some tests fail?** ❌
   - Run failing test with verbose output: `pytest tests/test_api_sync.py::TestName::test_method -v -s`
   - Check server logs for errors
   - Verify database state: `psql -U postgres travelroboto_test`
   - Check API documentation: http://localhost:8000/docs

3. **Want to add more tests?**
   - Follow the AAA pattern in `tests/test_api_sync.py`
   - Add new test methods to existing test classes
   - Use existing fixtures from `tests/conftest.py`
   - Run `pytest tests/ -v` to verify

## Integration with Your Workflow

### During Development

```bash
# Watch mode (re-run tests on file changes)
pytest tests/test_api_sync.py --looponfail

# Quick smoke test
./manual_test_sync.sh
```

### Before Committing

```bash
# Run all tests with coverage
./run_tests.sh --coverage

# Ensure >80% coverage
```

### In CI/CD

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: pytest tests/ --cov=. --cov-report=xml
```

## Questions?

- See `TEST_PLAN.md` for comprehensive testing strategy
- Check `tests/test_api_sync.py` for test examples
- Review `tests/conftest.py` for available fixtures
- FastAPI testing docs: https://fastapi.tianglio.com/tutorial/testing/
