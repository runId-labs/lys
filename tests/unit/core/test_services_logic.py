"""
Unit tests for core services module logic.

Tests Service base class and EntityService value comparison methods.
"""

import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock, patch

from lys.core.entities import Entity
from lys.core.services import EntityService, Service


class TestServiceOnInitializeOnShutdown:

    def test_on_initialize_is_noop(self):
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(Service.on_initialize())
            assert result is None
        finally:
            loop.close()

    def test_on_shutdown_is_noop(self):
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(Service.on_shutdown())
            assert result is None
        finally:
            loop.close()


class TestValuesDiffer:

    def test_different_strings(self):
        assert EntityService._values_differ("a", "b") is True

    def test_same_strings(self):
        assert EntityService._values_differ("a", "a") is False

    def test_none_old_entity_new(self):
        mock_entity = MagicMock(spec=Entity)
        mock_entity.id = "id1"
        assert EntityService._values_differ(None, mock_entity) is True

    def test_entity_different_ids(self):
        old_entity = MagicMock(spec=Entity)
        old_entity.id = "id1"
        new_entity = MagicMock(spec=Entity)
        new_entity.id = "id2"
        assert EntityService._values_differ(old_entity, new_entity) is True

    def test_entity_same_ids(self):
        old_entity = MagicMock(spec=Entity)
        old_entity.id = "id1"
        new_entity = MagicMock(spec=Entity)
        new_entity.id = "id1"
        assert EntityService._values_differ(old_entity, new_entity) is False

    def test_list_different_lengths(self):
        assert EntityService._values_differ([1, 2], [1, 2, 3]) is True

    def test_string_old_list_new(self):
        assert EntityService._values_differ("old", [1, 2]) is True


class TestListValuesDiffer:

    def test_old_not_list(self):
        assert EntityService._list_values_differ("not_a_list", [1, 2]) is True

    def test_different_lengths(self):
        assert EntityService._list_values_differ([1], [1, 2]) is True

    def test_same_entity_lists(self):
        e1 = MagicMock(spec=Entity)
        e1.id = "id1"
        e2 = MagicMock(spec=Entity)
        e2.id = "id2"
        old_list = [e1, e2]

        e3 = MagicMock(spec=Entity)
        e3.id = "id1"
        e4 = MagicMock(spec=Entity)
        e4.id = "id2"
        new_list = [e3, e4]

        assert EntityService._list_values_differ(old_list, new_list) is False

    def test_different_entity_lists(self):
        e1 = MagicMock(spec=Entity)
        e1.id = "id1"
        old_list = [e1]

        e2 = MagicMock(spec=Entity)
        e2.id = "id2"
        new_list = [e2]

        assert EntityService._list_values_differ(old_list, new_list) is True

    def test_same_primitive_lists(self):
        assert EntityService._list_values_differ([1, 2, 3], [3, 2, 1]) is False

    def test_different_primitive_lists(self):
        assert EntityService._list_values_differ([1, 2], [3, 4]) is True


class TestExecuteParallel:
    """Tests for Service.execute_parallel."""

    def test_execute_parallel_delegates_to_database_manager(self):
        """Test execute_parallel delegates to app_manager.database.execute_parallel."""
        import asyncio

        mock_db = MagicMock()
        mock_db.execute_parallel = AsyncMock(return_value=["result1", "result2"])
        mock_app_manager = MagicMock()
        mock_app_manager.database = mock_db

        with patch.object(Service, "app_manager", mock_app_manager):
            loop = asyncio.new_event_loop()
            try:
                fn1 = lambda s: s.execute("q1")
                fn2 = lambda s: s.execute("q2")
                result = loop.run_until_complete(Service.execute_parallel(fn1, fn2))
            finally:
                loop.close()

        mock_db.execute_parallel.assert_awaited_once_with(fn1, fn2)
        assert result == ["result1", "result2"]


class TestCheckAndUpdate:
    """Tests for EntityService.check_and_update."""

    def test_updates_changed_attribute(self):
        """Test check_and_update detects and applies changes."""
        import asyncio

        entity = MagicMock()
        entity.name = "old"
        entity.email = "same@test.com"

        loop = asyncio.new_event_loop()
        try:
            updated_entity, is_updated = loop.run_until_complete(
                EntityService.check_and_update(entity, name="new", email="same@test.com")
            )
        finally:
            loop.close()

        assert is_updated is True
        assert updated_entity.name == "new"

    def test_no_update_when_values_same(self):
        """Test check_and_update returns False when no changes."""
        import asyncio

        entity = MagicMock()
        entity.name = "same"

        loop = asyncio.new_event_loop()
        try:
            updated_entity, is_updated = loop.run_until_complete(
                EntityService.check_and_update(entity, name="same")
            )
        finally:
            loop.close()

        assert is_updated is False


class TestFilterAllowedFields:

    def _make_service(self, column_names):
        """Create a mock EntityService subclass with given column names."""
        mock_columns = []
        for name in column_names:
            col = MagicMock()
            col.name = name
            mock_columns.append(col)

        mock_table = MagicMock()
        mock_table.columns = mock_columns

        mock_entity = MagicMock()
        mock_entity.__table__ = mock_table

        service = type("TestService", (EntityService,), {})
        service.service_name = "test"

        mock_app_manager = MagicMock()
        mock_app_manager.get_entity.return_value = mock_entity

        return service, mock_app_manager

    def test_all_fields_valid(self):
        service, mock_am = self._make_service(["id", "name", "email"])
        with patch.object(service, "app_manager", mock_am):
            result = service._filter_allowed_fields({"name": "John", "email": "j@x.com"})
        assert result == {"name": "John", "email": "j@x.com"}

    def test_filters_out_unknown_fields(self):
        service, mock_am = self._make_service(["id", "name"])
        with patch.object(service, "app_manager", mock_am):
            result = service._filter_allowed_fields({"name": "John", "is_super_user": True})
        assert result == {"name": "John"}
        assert "is_super_user" not in result

    def test_filters_out_relationship_attribute(self):
        service, mock_am = self._make_service(["id", "client_id"])
        with patch.object(service, "app_manager", mock_am):
            result = service._filter_allowed_fields({"client_id": "uuid", "client": MagicMock()})
        assert result == {"client_id": "uuid"}
        assert "client" not in result

    def test_logs_warning_on_unexpected_fields(self, caplog):
        service, mock_am = self._make_service(["id", "name"])
        with patch.object(service, "app_manager", mock_am):
            with caplog.at_level(logging.WARNING):
                service._filter_allowed_fields({"name": "John", "hacked": "yes"})
        assert "Unexpected fields" in caplog.text
        assert "hacked" in caplog.text

    def test_no_warning_when_all_valid(self, caplog):
        service, mock_am = self._make_service(["id", "name"])
        with patch.object(service, "app_manager", mock_am):
            with caplog.at_level(logging.WARNING):
                service._filter_allowed_fields({"name": "John"})
        assert "Unexpected fields" not in caplog.text

    def test_empty_kwargs(self):
        service, mock_am = self._make_service(["id", "name"])
        with patch.object(service, "app_manager", mock_am):
            result = service._filter_allowed_fields({})
        assert result == {}

    def test_all_fields_unexpected(self):
        service, mock_am = self._make_service(["id"])
        with patch.object(service, "app_manager", mock_am):
            result = service._filter_allowed_fields({"roles": [], "client": MagicMock()})
        assert result == {}
