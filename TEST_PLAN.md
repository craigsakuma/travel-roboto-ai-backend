# Test Plan: API Sync Endpoints

## Overview

Comprehensive testing strategy for Travel Roboto AI Backend sync endpoints, following industry best practices for FastAPI applications.

## Test Strategy

### Testing Pyramid

```
         /\
        /  \  E2E Tests (Manual/Smoke)
       /----\
      / Inte-\  Integration Tests (API + DB)
     / gration\
    /----------\
   /   Unit      \ Unit Tests (Logic/Models)
  /--------------\
```

### Test Types

1. **Unit Tests** (`tests/test_api_sync.py`)
   - Individual endpoint testing
   - Mocked dependencies where appropriate
   - Fast execution (<1s per test)

2. **Integration Tests** (`tests/test_api_sync.py`)
   - Full database integration
   - Real PostgreSQL test database
   - Comprehensive error scenarios

3. **Manual Testing** (`manual_test_sync.sh`)
   - Quick smoke tests against running server
   - Useful for debugging and validation

## Test Coverage

### 1. User Sync Endpoint: `POST /api/users/sync`

**Success Scenarios:**
- ✅ Create new user
- ✅ Update existing user (upsert)
- ✅ Idempotent operation (same data twice)

**Error Scenarios:**
- ✅ Invalid UUID format
- ✅ Invalid email format
- ✅ Missing required fields

### 2. Trip Sync Endpoint: `POST /api/trips/sync`

**Success Scenarios:**
- ✅ Create new trip
- ✅ Update existing trip (upsert)
- ✅ Idempotent operation
- ✅ Parse ISO 8601 datetime format

**Error Scenarios:**
- ✅ Non-existent user (foreign key violation)
- ✅ Invalid date format
- ✅ Invalid UUID format

### 3. Trip Delete Endpoint: `DELETE /api/trips/{trip_id}`

**Success Scenarios:**
- ✅ Delete existing trip
- ✅ Idempotent deletion (delete twice)
- ✅ Delete non-existent trip (returns success)

**Error Scenarios:**
- ✅ Invalid UUID format

### 4. Trip Member Sync Endpoint: `POST /api/trips/{trip_id}/members/sync`

**Success Scenarios:**
- ✅ Add new member to trip
- ✅ Update member role (upsert)
- ✅ Idempotent operation

**Error Scenarios:**
- ✅ Non-existent user
- ✅ Non-existent trip
- ✅ Invalid UUID format

### 5. Trip Member Remove Endpoint: `DELETE /api/trips/{trip_id}/members/{user_id}`

**Success Scenarios:**
- ✅ Remove existing member
- ✅ Idempotent removal (remove twice)
- ✅ Remove non-existent member (returns success)

**Error Scenarios:**
- ✅ Invalid UUID format

### 6. Message Feedback Endpoint: `PATCH /api/messages/{message_id}/feedback`

**Success Scenarios:**
- ✅ Update feedback to "up"
- ✅ Update feedback to "down"
- ✅ Toggle feedback (up -> down -> up)

**Error Scenarios:**
- ✅ Non-existent message
- ✅ Invalid feedback value
- ✅ Invalid UUID format

## Test Fixtures & Factories

### Database Fixtures
- `async_engine` - PostgreSQL test database engine
- `db_session` - Isolated database session per test
- `test_client` - FastAPI TestClient with DB overrides

### Data Factories
- `sample_user_data` - Realistic user test data
- `sample_trip_data` - Realistic trip test data
- `sample_trip_member_data` - Trip member relationship
- `sample_message_feedback_data` - Feedback data

### Pre-created Records
- `created_user` - User already in database
- `created_trip` - Trip already in database
- `created_message` - Message already in database

## Running Tests

### Quick Start

```bash
# Run all tests
./run_tests.sh

# Run only sync endpoint tests
./run_tests.sh sync

# Run only database tests
./run_tests.sh database

# Run with coverage report
./run_tests.sh --coverage
```

### Using pytest directly

```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_api_sync.py

# Specific test class
pytest tests/test_api_sync.py::TestUserSync

# Specific test method
pytest tests/test_api_sync.py::TestUserSync::test_sync_user_create_success

# With verbose output
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

### Manual Testing

```bash
# Ensure server is running on port 8000
python main.py

# In another terminal, run manual tests
./manual_test_sync.sh
```

## Test Database Setup

### Initial Setup

```bash
# Create test database
createdb -U postgres travelroboto_test

# Database will be automatically migrated by test fixtures
```

### Test Isolation

- Each test run drops and recreates all tables
- Each test gets a fresh database session
- Transactions are rolled back after each test
- No test data pollution between runs

## Best Practices Followed

### 1. AAA Pattern (Arrange-Act-Assert)
```python
def test_sync_user_create_success(self, test_client, sample_user_data):
    # Arrange - setup test data
    data = sample_user_data

    # Act - perform the operation
    response = test_client.post("/api/users/sync", json=data)

    # Assert - verify results
    assert response.status_code == 200
    assert response.json()["success"] is True
```

### 2. Descriptive Test Names
- Test names clearly describe what is being tested
- Format: `test_{action}_{scenario}`
- Examples: `test_sync_user_create_success`, `test_delete_trip_invalid_uuid`

### 3. Comprehensive Error Coverage
- Every endpoint has error scenario tests
- Foreign key violations tested
- Invalid input formats tested
- Edge cases (null, empty, malformed) tested

### 4. Idempotency Testing
- All sync/delete operations tested for idempotency
- Ensures frontend can safely retry operations
- Critical for distributed systems reliability

### 5. Database State Verification
- Tests verify database state changes
- Not just API response, but actual DB records
- Ensures data integrity

### 6. Isolation & Independence
- Tests don't depend on each other
- Can run in any order
- Can run in parallel (with proper DB setup)

### 7. Fast Feedback
- Tests run quickly (<5s for all sync tests)
- Immediate feedback on code changes
- Suitable for TDD workflow

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e '.[dev]'

      - name: Create test database
        run: |
          PGPASSWORD=postgres createdb -U postgres -h localhost travelroboto_test

      - name: Run tests
        run: |
          pytest tests/ --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
pg_isready

# Check if test database exists
psql -U postgres -l | grep travelroboto_test

# Recreate test database
dropdb -U postgres travelroboto_test
createdb -U postgres travelroboto_test
```

### Import Errors

```bash
# Reinstall dependencies
pip install -e '.[dev]'

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

### Test Failures

```bash
# Run tests with verbose output
pytest tests/test_api_sync.py -v -s

# Run specific failing test
pytest tests/test_api_sync.py::TestUserSync::test_sync_user_create_success -v -s

# Check database state
psql -U postgres travelroboto_test -c "SELECT * FROM users;"
```

## Next Steps

1. **Add Performance Tests** - Load testing for concurrent operations
2. **Add Security Tests** - SQL injection, XSS, authentication bypass
3. **Add Contract Tests** - Pact tests for frontend-backend integration
4. **Add Chaos Tests** - Database failures, network issues
5. **Increase Coverage** - Aim for >90% code coverage

## References

- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
