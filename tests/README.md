# Lys Framework Testing Guide

This guide explains how to write tests for the lys framework.

## Quick Start

```python
# Unit test example
from tests.mocks import MockAppManager
from lys.apps.base.modules.language.services import LanguageService
from lys.apps.base.modules.language.entities import Language

def test_my_service():
    # Setup mock
    mock_app = MockAppManager()
    mock_app.register_entity("language", Language)

    # Configure service
    LanguageService.configure_app_manager_for_testing(mock_app)

    # Test
    assert LanguageService.entity_class == Language
```

## Test Types

### Unit Tests (`tests/unit/`)

**Purpose**: Test business logic in isolation without database.

**Use for**:
- Business logic that doesn't use database
- Service interactions (with mocked dependencies)
- Entity class access via `entity_class` property
- Custom methods in services/fixtures/nodes

**Cannot test**:
- CRUD operations (get_by_id, create, update, delete)
- Database queries
- Entity relationships

**Setup**:
```python
from tests.mocks import MockAppManager

mock_app = MockAppManager()
mock_app.register_entity("language", Language)
mock_app.register_service("language", LanguageService)

LanguageService.configure_app_manager_for_testing(mock_app)
```

### Integration Tests (`tests/integration/`)

**Purpose**: Test with real database (SQLite in-memory).

**Use for**:
- CRUD operations
- Database queries and filters
- Entity relationships
- Full service workflows

**Setup**: Three fixtures are available from `tests/fixtures/database.py`:

```python
@pytest.mark.asyncio
async def test_create_user(db_session):
    """Use db_session for tests with automatic rollback"""
    user = await UserService.create(
        db_session,
        email="test@test.com"
    )
    assert user.id is not None
    # Automatic rollback ensures isolation


@pytest.mark.asyncio
async def test_user_workflow(db_session_commit):
    """Use db_session_commit when you need to commit"""
    user = await UserService.create(
        db_session_commit,
        email="test@test.com"
    )
    await db_session_commit.commit()

    # User persists for next query
    found = await UserService.get_by_id(user.id, db_session_commit)
    assert found is not None
```

### When to Use Which

| Feature to Test | Unit Test | Integration Test |
|----------------|-----------|------------------|
| Custom business logic | ✅ | ✅ |
| `entity_class` property | ✅ | ✅ |
| Service delegation | ✅ | ✅ |
| CRUD operations | ❌ | ✅ Required |
| Database queries | ❌ | ✅ Required |
| Entity relationships | ❌ | ✅ Required |

## Available Fixtures

### Unit Test Fixtures

#### `mock_app_manager`

Basic mock for unit tests.

```python
def test_example(mock_app_manager):
    mock_app_manager.register_entity("language", Language)
    LanguageService.configure_app_manager_for_testing(mock_app_manager)
```

#### `mock_db_session`

Mock database session for unit tests.

```python
async def test_example(mock_db_session):
    # Configure mock behavior
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = user
```

### Integration Test Fixtures

#### `test_app_manager`

Real AppManager configured with SQLite in-memory database.

```python
@pytest.mark.asyncio
async def test_with_real_app_manager(test_app_manager):
    # Full AppManager with all components loaded
    # Database initialized and ready
    assert test_app_manager.database.has_database_configured()
```

#### `db_session`

Database session with automatic rollback for test isolation.

```python
@pytest.mark.asyncio
async def test_create_language(db_session):
    language = await LanguageService.create(
        db_session,
        id="en",
        enabled=True
    )
    assert language.id == "en"
    # Automatic rollback - changes don't persist
```

#### `db_session_commit`

Database session that commits changes (for multi-operation tests).

```python
@pytest.mark.asyncio
async def test_get_by_id(db_session_commit):
    # Create and commit
    created = await LanguageService.create(
        db_session_commit,
        id="fr",
        enabled=True
    )
    await db_session_commit.commit()

    # Retrieve in same test
    found = await LanguageService.get_by_id("fr", db_session_commit)
    assert found is not None
```

## Utilities

### `configure_classes_for_testing`

Configure multiple classes at once.

```python
from tests.mocks import configure_classes_for_testing

configure_classes_for_testing(
    mock_app,
    UserService,
    EmailService,
    UserNode
)
```

### `reset_class_app_managers`

Clean up after tests.

```python
from tests.mocks.utils import reset_class_app_managers

def teardown():
    reset_class_app_managers(UserService, EmailService)
```

## Examples

### Unit Test Examples

#### Example 1: Test Entity Class Access

```python
def test_service_entity_class(mock_app_manager):
    mock_app_manager.register_entity("language", Language)
    LanguageService.configure_app_manager_for_testing(mock_app_manager)

    assert LanguageService.entity_class == Language
```

#### Example 2: Test Service Interaction

```python
def test_service_gets_another_service(mock_app_manager):
    mock_app_manager.register_service("language", LanguageService)
    MyService.configure_app_manager_for_testing(mock_app_manager)

    # MyService internally calls app_manager.get_service("language")
    result = MyService.get_language_service()
    assert result == LanguageService
```

#### Example 3: Test Custom Business Logic

```python
async def test_custom_validation():
    """Test custom business logic that doesn't touch database"""
    mock_app = MockAppManager()
    UserService.configure_app_manager_for_testing(mock_app)

    # Test a custom validation method
    is_valid = UserService.validate_email_format("test@example.com")
    assert is_valid is True
```

### Integration Test Examples

#### Example 4: Test CRUD Create Operation

```python
@pytest.mark.asyncio
async def test_create_language(db_session):
    """Test creating a language entity"""
    language = await LanguageService.create(
        db_session,
        id="en",
        enabled=True
    )

    assert language is not None
    assert language.id == "en"
    assert language.enabled is True
    assert language.created_at is not None
```

#### Example 5: Test CRUD Read Operation

```python
@pytest.mark.asyncio
async def test_get_by_id(db_session_commit):
    """Test retrieving a language by ID"""
    # Create and commit
    created = await LanguageService.create(
        db_session_commit,
        id="fr",
        enabled=True
    )
    await db_session_commit.commit()

    # Retrieve
    found = await LanguageService.get_by_id("fr", db_session_commit)

    assert found is not None
    assert found.id == "fr"
```

#### Example 6: Test CRUD Update Operation

```python
@pytest.mark.asyncio
async def test_update(db_session_commit):
    """Test updating a language"""
    # Create
    await LanguageService.create(db_session_commit, id="de", enabled=True)
    await db_session_commit.commit()

    # Update
    updated = await LanguageService.update(
        "de",
        db_session_commit,
        enabled=False
    )

    assert updated.enabled is False
    assert updated.updated_at is not None
```

#### Example 7: Test CRUD Delete Operation

```python
@pytest.mark.asyncio
async def test_delete(db_session_commit):
    """Test deleting a language"""
    # Create
    await LanguageService.create(db_session_commit, id="it", enabled=True)
    await db_session_commit.commit()

    # Delete
    deleted = await LanguageService.delete("it", db_session_commit)
    assert deleted is True

    # Verify deleted
    found = await LanguageService.get_by_id("it", db_session_commit)
    assert found is None
```

#### Example 8: Test Pagination

```python
@pytest.mark.asyncio
async def test_get_all_with_pagination(db_session_commit):
    """Test get_all with limit and offset"""
    # Create 5 languages
    for i in range(5):
        await LanguageService.create(
            db_session_commit,
            id=f"lang{i}",
            enabled=True
        )
    await db_session_commit.commit()

    # Get first 2
    page1 = await LanguageService.get_all(db_session_commit, limit=2, offset=0)
    assert len(page1) == 2

    # Get next 2
    page2 = await LanguageService.get_all(db_session_commit, limit=2, offset=2)
    assert len(page2) == 2

    # Verify no overlap
    page1_ids = {lang.id for lang in page1}
    page2_ids = {lang.id for lang in page2}
    assert len(page1_ids & page2_ids) == 0
```

## Common Patterns

### Pattern 1: Setup Multiple Services

```python
@pytest.fixture
def configured_services(mock_app_manager):
    mock_app_manager.register_entity("users", User)
    mock_app_manager.register_entity("emails", Email)
    mock_app_manager.register_service("users", UserService)
    mock_app_manager.register_service("emails", EmailService)

    configure_classes_for_testing(
        mock_app_manager,
        UserService,
        EmailService
    )

    yield

    # Cleanup
    reset_class_app_managers(UserService, EmailService)
```

### Pattern 2: Test with Pytest Class

```python
class TestUserService:
    @pytest.fixture(autouse=True)
    def setup(self, mock_app_manager):
        mock_app_manager.register_entity("users", User)
        UserService.configure_app_manager_for_testing(mock_app_manager)

        yield

        reset_class_app_managers(UserService)

    def test_something(self):
        # UserService is already configured
        assert UserService.entity_class == User
```

## Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run specific test file
pytest tests/unit/test_mock_app_manager.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src/lys

# Run tests in parallel (faster)
pytest -n auto
```

## Test Results

Current test status:
- **32 tests passing** (20 unit + 12 integration)
- **2 tests skipped** (documented as requiring integration tests)
- **Zero conflicts** - perfect test isolation

## Troubleshooting

### KeyError: Entity 'xyz' not registered

**Cause**: Forgot to register entity or used wrong name.

**Solution**: Check entity's `__tablename__` and register it:
```python
print(MyEntity.__tablename__)  # Check the actual table name
mock_app.register_entity(MyEntity.__tablename__, MyEntity)
```

### SQLAlchemy ArgumentError in unit tests

**Cause**: Trying to test CRUD operations in unit test.

**Solution**: Move to integration test with real database.

### Service still uses singleton instead of mock

**Cause**: Forgot to call `configure_app_manager_for_testing()`.

**Solution**:
```python
MyService.configure_app_manager_for_testing(mock_app)
```

## Further Reading

- See `docs/todos/testing/STRATEGY.md` for detailed testing strategy
- See `docs/todos/testing/STATUS.md` for current implementation status
- See test examples in `tests/unit/test_service_with_mock.py`
