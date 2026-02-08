"""
Integration tests for base LogService.

Tests cover:
- Log CRUD operations
- JSON context round-trip
"""

import pytest


class TestLogServiceCRUD:
    """Test LogService CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_log(self, user_auth_app_manager):
        """Test creating a log entry."""
        log_service = user_auth_app_manager.get_service("log")

        async with user_auth_app_manager.database.get_session() as session:
            log = await log_service.create(
                session,
                message="Test error occurred",
                file_name="test_module.py",
                line=42,
                traceback="Traceback (most recent call last):\n  File ...",
                context=None
            )

            assert log.id is not None
            assert log.message == "Test error occurred"
            assert log.file_name == "test_module.py"
            assert log.line == 42
            assert log.traceback.startswith("Traceback")

    @pytest.mark.asyncio
    async def test_create_log_with_json_context(self, user_auth_app_manager):
        """Test creating a log with JSON context that survives round-trip."""
        log_service = user_auth_app_manager.get_service("log")

        context_data = {
            "user_id": "abc123",
            "request_path": "/api/users",
            "method": "POST",
            "nested": {"key": "value", "list": [1, 2, 3]}
        }

        async with user_auth_app_manager.database.get_session() as session:
            log = await log_service.create(
                session,
                message="Request failed",
                file_name="api/views.py",
                line=100,
                traceback="ValueError: invalid input",
                context=context_data
            )
            log_id = log.id

        # Read back and verify JSON context
        async with user_auth_app_manager.database.get_session() as session:
            retrieved = await log_service.get_by_id(log_id, session)
            assert retrieved.context == context_data
            assert retrieved.context["nested"]["list"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_log_by_id(self, user_auth_app_manager):
        """Test retrieving a log by ID."""
        log_service = user_auth_app_manager.get_service("log")

        async with user_auth_app_manager.database.get_session() as session:
            log = await log_service.create(
                session,
                message="Lookup test",
                file_name="lookup.py",
                line=1,
                traceback="None"
            )
            log_id = log.id

        async with user_auth_app_manager.database.get_session() as session:
            found = await log_service.get_by_id(log_id, session)
            assert found is not None
            assert found.message == "Lookup test"

    @pytest.mark.asyncio
    async def test_log_accessing_methods(self, user_auth_app_manager):
        """Test that Log accessing methods return empty."""
        log_service = user_auth_app_manager.get_service("log")

        async with user_auth_app_manager.database.get_session() as session:
            log = await log_service.create(
                session,
                message="Access test",
                file_name="access.py",
                line=1,
                traceback="None"
            )

            assert log.accessing_users() == []
            assert log.accessing_organizations() == {}
