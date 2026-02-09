"""
Unit tests for fixture loading strategies logic.

Tests ParametricFixtureLoadingStrategy, BusinessFixtureLoadingStrategy,
and FixtureLoadingStrategyFactory with mocked dependencies.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from sqlalchemy import UniqueConstraint

from lys.core.entities import Entity, ParametricEntity
from lys.core.strategies.fixture_loading import (
    FixtureLoadingStrategy,
    ParametricFixtureLoadingStrategy,
    BusinessFixtureLoadingStrategy,
    FixtureLoadingStrategyFactory,
)

MODULE_PATH = "lys.core.strategies.fixture_loading"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.new = set()
    session.dirty = set()
    session.deleted = set()
    return session


def _make_fixture_class(data_list=None, delete_previous_data=True):
    """Create a mock fixture class with common defaults."""
    fixture_class = MagicMock()
    fixture_class.data_list = data_list or []
    fixture_class.delete_previous_data = delete_previous_data
    fixture_class._format_attributes = AsyncMock(side_effect=lambda attrs, session=None, extra_data=None: attrs)
    fixture_class._do_before_add = AsyncMock()
    fixture_class.create_from_service = AsyncMock(return_value=None)
    return fixture_class


def _make_entity_class():
    """Create a mock entity class."""
    entity_class = MagicMock()
    entity_class.__tablename__ = "test_table"

    # id column mock for .notin_() and == comparisons
    id_col = MagicMock()
    entity_class.id = id_col

    # Make entity_class callable (constructor)
    mock_instance = MagicMock()
    mock_instance.id = "new-uuid"
    entity_class.return_value = mock_instance

    return entity_class


def _make_service():
    """Create a mock service."""
    service = MagicMock()
    service.check_and_update = AsyncMock(return_value=(MagicMock(), True))
    return service


def _make_select_result(obj=None):
    """Create a mock select result that returns obj from scalars().one_or_none()."""
    scalars_mock = MagicMock()
    scalars_mock.one_or_none.return_value = obj
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


def _make_rowcount_result(count):
    """Create a mock result with rowcount."""
    result = MagicMock()
    result.rowcount = count
    return result


# ---------------------------------------------------------------------------
# FixtureLoadingStrategyFactory
# ---------------------------------------------------------------------------

class TestFixtureLoadingStrategyFactory:
    """Tests for FixtureLoadingStrategyFactory.create_strategy."""

    def test_returns_parametric_strategy_for_parametric_entity(self):
        """Test factory returns ParametricFixtureLoadingStrategy for ParametricEntity subclass."""
        with patch(f"{MODULE_PATH}.issubclass", return_value=True):
            strategy = FixtureLoadingStrategyFactory.create_strategy(MagicMock())
        assert isinstance(strategy, ParametricFixtureLoadingStrategy)

    def test_returns_business_strategy_for_regular_entity(self):
        """Test factory returns BusinessFixtureLoadingStrategy for regular Entity subclass."""
        with patch(f"{MODULE_PATH}.issubclass", return_value=False):
            strategy = FixtureLoadingStrategyFactory.create_strategy(MagicMock())
        assert isinstance(strategy, BusinessFixtureLoadingStrategy)


# ---------------------------------------------------------------------------
# ParametricFixtureLoadingStrategy
# ---------------------------------------------------------------------------

class TestParametricFixtureLoadingStrategy:
    """Tests for ParametricFixtureLoadingStrategy.load."""

    def _run_parametric_load(self, fixture_class, session, entity_class, service):
        """Run parametric load with patched SQLAlchemy functions."""
        strategy = ParametricFixtureLoadingStrategy()
        with patch(f"{MODULE_PATH}.update") as mock_update, \
             patch(f"{MODULE_PATH}.select") as mock_select:
            # Chain: update(entity_class).where(...).values(...)
            mock_update.return_value.where.return_value.values.return_value = MagicMock()
            # Chain: select(entity_class).where(...).limit(...)
            mock_select.return_value.where.return_value.limit.return_value = MagicMock()
            return _run(strategy.load(fixture_class, session, entity_class, service))

    def test_disable_entities_not_in_data_list(self):
        """Test that entities not in data_list are disabled when delete_previous_data is True."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()

        fixture_class = _make_fixture_class(
            data_list=[{"id": "A", "attributes": {}}],
            delete_previous_data=True,
        )

        # First call: update (rowcount=3), second call: select (no existing obj)
        session.execute = AsyncMock(side_effect=[
            _make_rowcount_result(3),
            _make_select_result(None),
        ])

        deleted, added, updated, unchanged = self._run_parametric_load(
            fixture_class, session, entity_class, service
        )

        assert deleted == 3
        assert added == 1

    def test_no_disable_when_delete_previous_data_is_false(self):
        """Test that no entities are disabled when delete_previous_data is False."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()

        fixture_class = _make_fixture_class(
            data_list=[{"id": "X", "attributes": {"code": "XX"}}],
            delete_previous_data=False,
        )

        session.execute = AsyncMock(return_value=_make_select_result(None))

        deleted, added, updated, unchanged = self._run_parametric_load(
            fixture_class, session, entity_class, service
        )

        assert deleted == 0
        assert added == 1

    def test_update_existing_entity_with_attributes(self):
        """Test updating an existing entity that has attributes (lines 97-106)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        service.check_and_update = AsyncMock(return_value=(MagicMock(), True))

        existing_obj = MagicMock()
        session.execute = AsyncMock(return_value=_make_select_result(existing_obj))

        fixture_class = _make_fixture_class(
            data_list=[{"id": "A", "attributes": {"code": "NEW_CODE", "description": "desc"}}],
            delete_previous_data=False,
        )

        deleted, added, updated, unchanged = self._run_parametric_load(
            fixture_class, session, entity_class, service
        )

        assert updated == 1
        assert added == 0
        assert unchanged == 0
        service.check_and_update.assert_awaited_once()

    def test_existing_entity_with_attributes_not_changed(self):
        """Test existing entity with attributes that did not change (lines 107-108)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        service.check_and_update = AsyncMock(return_value=(MagicMock(), False))

        existing_obj = MagicMock()
        session.execute = AsyncMock(return_value=_make_select_result(existing_obj))

        fixture_class = _make_fixture_class(
            data_list=[{"id": "A", "attributes": {"code": "SAME"}}],
            delete_previous_data=False,
        )

        deleted, added, updated, unchanged = self._run_parametric_load(
            fixture_class, session, entity_class, service
        )

        assert unchanged == 1
        assert updated == 0

    def test_existing_entity_with_empty_attributes(self):
        """Test existing entity with no attributes increments unchanged (lines 109-110)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()

        existing_obj = MagicMock()
        session.execute = AsyncMock(return_value=_make_select_result(existing_obj))

        fixture_class = _make_fixture_class(
            data_list=[{"id": "A", "attributes": {}}],
            delete_previous_data=False,
        )

        deleted, added, updated, unchanged = self._run_parametric_load(
            fixture_class, session, entity_class, service
        )

        assert unchanged == 1
        assert updated == 0
        assert added == 0

    def test_existing_entity_with_no_attributes_key(self):
        """Test existing entity where data has no 'attributes' key defaults to empty dict."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()

        existing_obj = MagicMock()
        session.execute = AsyncMock(return_value=_make_select_result(existing_obj))

        fixture_class = _make_fixture_class(
            data_list=[{"id": "A"}],
            delete_previous_data=False,
        )

        deleted, added, updated, unchanged = self._run_parametric_load(
            fixture_class, session, entity_class, service
        )

        assert unchanged == 1

    def test_create_new_entity(self):
        """Test creating a new entity when not found in the database."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()

        session.execute = AsyncMock(return_value=_make_select_result(None))

        fixture_class = _make_fixture_class(
            data_list=[{"id": "NEW_ID", "attributes": {"code": "NEW"}}],
            delete_previous_data=False,
        )

        deleted, added, updated, unchanged = self._run_parametric_load(
            fixture_class, session, entity_class, service
        )

        assert added == 1
        session.add.assert_called_once()
        fixture_class._do_before_add.assert_awaited_once()

    def test_multiple_data_items_mixed(self):
        """Test processing multiple data items with mixed outcomes."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        service.check_and_update = AsyncMock(return_value=(MagicMock(), True))

        existing_obj = MagicMock()

        # First item: exists (updated), Second item: not found (added)
        session.execute = AsyncMock(side_effect=[
            _make_select_result(existing_obj),
            _make_select_result(None),
        ])

        fixture_class = _make_fixture_class(
            data_list=[
                {"id": "EXIST", "attributes": {"code": "X"}},
                {"id": "NEW", "attributes": {"code": "Y"}},
            ],
            delete_previous_data=False,
        )

        deleted, added, updated, unchanged = self._run_parametric_load(
            fixture_class, session, entity_class, service
        )

        assert updated == 1
        assert added == 1


# ---------------------------------------------------------------------------
# BusinessFixtureLoadingStrategy._get_unique_key_fields
# ---------------------------------------------------------------------------

class TestGetUniqueKeyFields:
    """Tests for BusinessFixtureLoadingStrategy._get_unique_key_fields."""

    def test_no_table_args_returns_none(self):
        """Test returns None when entity has no __table_args__ (line 148)."""
        strategy = BusinessFixtureLoadingStrategy()
        entity_class = MagicMock(spec=[])  # empty spec, no __table_args__
        assert strategy._get_unique_key_fields(entity_class) is None

    def test_table_args_is_dict_returns_none(self):
        """Test returns None when __table_args__ is a dict."""
        strategy = BusinessFixtureLoadingStrategy()
        entity_class = MagicMock()
        entity_class.__table_args__ = {"schema": "public"}
        assert strategy._get_unique_key_fields(entity_class) is None

    def test_table_args_with_unique_constraint(self):
        """Test extracts column names from UniqueConstraint (lines 154-157)."""
        strategy = BusinessFixtureLoadingStrategy()
        entity_class = MagicMock()

        col1 = MagicMock()
        col1.name = "client_id"
        col2 = MagicMock()
        col2.name = "code"

        uc = MagicMock(spec=UniqueConstraint)
        uc.columns = [col1, col2]

        entity_class.__table_args__ = (uc,)

        result = strategy._get_unique_key_fields(entity_class)
        assert result == ["client_id", "code"]

    def test_table_args_tuple_without_unique_constraint(self):
        """Test returns None when tuple has no UniqueConstraint (lines 154-159)."""
        strategy = BusinessFixtureLoadingStrategy()
        entity_class = MagicMock()
        entity_class.__table_args__ = ("not_a_constraint",)

        result = strategy._get_unique_key_fields(entity_class)
        assert result is None

    def test_table_args_column_without_name_attribute(self):
        """Test columns without .name attribute fall back to str()."""
        strategy = BusinessFixtureLoadingStrategy()
        entity_class = MagicMock()

        # Create a simple object without .name
        class ColProxy:
            def __str__(self):
                return "fallback_col"

        col1 = ColProxy()

        uc = MagicMock(spec=UniqueConstraint)
        uc.columns = [col1]

        entity_class.__table_args__ = (uc,)

        result = strategy._get_unique_key_fields(entity_class)
        assert result == ["fallback_col"]

    def test_table_args_none_value(self):
        """Test __table_args__ set to None returns None (line 147-148)."""
        strategy = BusinessFixtureLoadingStrategy()
        entity_class = MagicMock()
        entity_class.__table_args__ = None
        assert strategy._get_unique_key_fields(entity_class) is None


# ---------------------------------------------------------------------------
# BusinessFixtureLoadingStrategy.load
# ---------------------------------------------------------------------------

class TestBusinessFixtureLoadingStrategyLoad:
    """Tests for BusinessFixtureLoadingStrategy.load."""

    def _run_business_load(self, fixture_class, session, entity_class, service,
                           unique_key_fields_return=None):
        """Run business load with patched SQLAlchemy functions and _get_unique_key_fields."""
        strategy = BusinessFixtureLoadingStrategy()
        with patch(f"{MODULE_PATH}.delete") as mock_delete, \
             patch(f"{MODULE_PATH}.select") as mock_select, \
             patch.object(strategy, "_get_unique_key_fields", return_value=unique_key_fields_return):
            # Chain: select(entity_class).where(...).limit(...)
            mock_select.return_value.where.return_value.limit.return_value = MagicMock()
            return _run(strategy.load(fixture_class, session, entity_class, service))

    def test_delete_previous_data_deletes_all(self):
        """Test that delete_previous_data=True deletes all rows (line 181)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        session.execute = AsyncMock(return_value=_make_rowcount_result(5))

        fixture_class = _make_fixture_class(data_list=[], delete_previous_data=True)

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service
        )

        assert deleted == 5
        assert added == 0

    def test_no_delete_when_delete_previous_data_is_false(self):
        """Test no rows are deleted when delete_previous_data is False."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        fixture_class = _make_fixture_class(data_list=[], delete_previous_data=False)

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service
        )

        assert deleted == 0

    def test_standard_creation_when_no_upsert(self):
        """Test standard entity creation path (create_from_service returns None, lines 234-242)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"name": "Test"}}],
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(return_value=None)

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service
        )

        entity_class.assert_called_once()
        fixture_class._do_before_add.assert_awaited_once()
        session.add.assert_called_once()

    def test_creation_via_create_from_service(self):
        """Test entity creation via service when create_from_service returns an object."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        service_created_obj = MagicMock()
        service_created_obj.id = "service-created-id"

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"name": "Test"}}],
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(return_value=service_created_obj)

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service
        )

        # Entity was NOT created via constructor, but via service
        entity_class.assert_not_called()
        session.add.assert_called_once_with(service_created_obj)

    def test_upsert_updates_existing_entity(self):
        """Test upsert logic when entity already exists (lines 201-229)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        service.check_and_update = AsyncMock(return_value=(MagicMock(), True))

        entity_class.client_id = MagicMock()
        entity_class.code = MagicMock()

        existing_obj = MagicMock()
        existing_obj.id = "existing-id"

        session.execute = AsyncMock(return_value=_make_select_result(existing_obj))

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"client_id": "c1", "code": "CODE1"}}],
            delete_previous_data=False,
        )

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service,
            unique_key_fields_return=["client_id", "code"],
        )

        assert updated == 1
        assert added == 0
        service.check_and_update.assert_awaited_once()

    def test_upsert_unchanged_existing_entity(self):
        """Test upsert logic when entity exists but is unchanged (lines 227-228)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        service.check_and_update = AsyncMock(return_value=(MagicMock(), False))

        entity_class.code = MagicMock()

        existing_obj = MagicMock()
        existing_obj.id = "existing-id"

        session.execute = AsyncMock(return_value=_make_select_result(existing_obj))

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"code": "SAME"}}],
            delete_previous_data=False,
        )

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service,
            unique_key_fields_return=["code"],
        )

        assert unchanged == 1
        assert updated == 0

    def test_upsert_creates_new_when_not_found(self):
        """Test upsert logic when entity does not exist creates new entity."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        entity_class.code = MagicMock()

        session.execute = AsyncMock(return_value=_make_select_result(None))

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"code": "NEW"}}],
            delete_previous_data=False,
        )
        fixture_class.create_from_service = AsyncMock(return_value=None)

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service,
            unique_key_fields_return=["code"],
        )

        entity_class.assert_called_once()
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    def test_exception_during_creation_is_logged_and_raised(self):
        """Test exception during object creation is logged and re-raised (lines 244-250)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"bad_field": "value"}}],
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(side_effect=ValueError("creation error"))

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        with pytest.raises(ValueError, match="creation error"):
            self._run_business_load(fixture_class, session, entity_class, service)

    def test_exception_during_creation_logs_error(self):
        """Test that exception during creation logs error messages (lines 245-249)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"name": "broken"}}],
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(side_effect=RuntimeError("db error"))

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        with patch("logging.error") as mock_log_error:
            with pytest.raises(RuntimeError, match="db error"):
                self._run_business_load(fixture_class, session, entity_class, service)

            assert mock_log_error.call_count == 2
            assert "Failed to create/update object" in mock_log_error.call_args_list[0][0][0]
            assert "Problematic attributes" in mock_log_error.call_args_list[1][0][0]

    def test_flush_called_when_objects_created(self):
        """Test flush is called after objects are created (lines 253-265)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        fixture_class = _make_fixture_class(
            data_list=[
                {"attributes": {"name": "obj1"}},
                {"attributes": {"name": "obj2"}},
            ],
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(return_value=None)

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service
        )

        session.flush.assert_awaited_once()
        assert added == 2

    def test_flush_not_called_when_no_objects_created(self):
        """Test flush is NOT called when no objects are created (line 253)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        fixture_class = _make_fixture_class(data_list=[], delete_previous_data=True)

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service
        )

        session.flush.assert_not_awaited()
        assert added == 0

    def test_flush_exception_is_logged_and_raised(self):
        """Test exception during flush is logged and re-raised (lines 256-262)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock(side_effect=RuntimeError("flush error"))

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"name": "obj"}}],
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(return_value=None)

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        with patch("logging.error") as mock_log_error:
            with pytest.raises(RuntimeError, match="flush error"):
                self._run_business_load(fixture_class, session, entity_class, service)

            assert mock_log_error.call_count == 2
            assert "Failed to flush fixtures" in mock_log_error.call_args_list[0][0][0]
            assert "Session state" in mock_log_error.call_args_list[1][0][0]

    def test_warning_for_objects_without_id(self):
        """Test warning is logged for objects that failed to persist (line 270)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        # Create entity instances where one has no id (failed to persist)
        obj_with_id = MagicMock()
        obj_with_id.id = "uuid-1"

        obj_without_id = MagicMock()
        obj_without_id.id = None

        call_count = [0]

        def entity_constructor(**kwargs):
            result = [obj_with_id, obj_without_id][call_count[0]]
            call_count[0] += 1
            return result

        entity_class.side_effect = entity_constructor

        fixture_class = _make_fixture_class(
            data_list=[
                {"attributes": {"name": "good"}},
                {"attributes": {"name": "bad"}},
            ],
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(return_value=None)

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        with patch("logging.warning") as mock_log_warning:
            deleted, added, updated, unchanged = self._run_business_load(
                fixture_class, session, entity_class, service
            )

            assert added == 1  # only the one with id
            mock_log_warning.assert_called_once()
            assert "failed to persist" in mock_log_warning.call_args[0][0]

    def test_upsert_format_attributes_called_with_extra_data(self):
        """Test that _format_attributes is called with extra_data containing parent_id (line 216-218)."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        service.check_and_update = AsyncMock(return_value=(MagicMock(), True))

        entity_class.code = MagicMock()

        existing_obj = MagicMock()
        existing_obj.id = "parent-uuid"

        session.execute = AsyncMock(return_value=_make_select_result(existing_obj))

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"code": "X"}}],
            delete_previous_data=False,
        )

        self._run_business_load(
            fixture_class, session, entity_class, service,
            unique_key_fields_return=["code"],
        )

        # _format_attributes should be called twice for upsert:
        # 1st: temp_attributes without extra_data
        # 2nd: with extra_data={"parent_id": "parent-uuid"}
        calls = fixture_class._format_attributes.call_args_list
        assert len(calls) == 2
        # First call: no extra_data
        assert calls[0].kwargs.get("extra_data") is None
        # Second call: extra_data with parent_id
        assert calls[1].kwargs.get("extra_data") == {"parent_id": "parent-uuid"}

    def test_delete_previous_data_with_items(self):
        """Test delete + create in single load call."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"name": "item1"}}],
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(return_value=None)

        session.execute = AsyncMock(return_value=_make_rowcount_result(10))

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service
        )

        assert deleted == 10
        assert added == 1

    def test_all_objects_persisted_no_warning(self):
        """Test no warning when all objects have valid IDs after flush."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        obj = MagicMock()
        obj.id = "valid-uuid"
        entity_class.return_value = obj

        fixture_class = _make_fixture_class(
            data_list=[{"attributes": {"name": "good"}}],
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(return_value=None)

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        with patch("logging.warning") as mock_log_warning:
            deleted, added, updated, unchanged = self._run_business_load(
                fixture_class, session, entity_class, service
            )

            assert added == 1
            mock_log_warning.assert_not_called()

    def test_empty_data_list_returns_zeros(self):
        """Test empty data_list returns all zero counts."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        fixture_class = _make_fixture_class(data_list=[], delete_previous_data=False)

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service
        )

        assert (deleted, added, updated, unchanged) == (0, 0, 0, 0)

    def test_data_without_attributes_key_defaults_to_empty_dict(self):
        """Test data entries without 'attributes' key default to empty dict."""
        session = _make_session()
        entity_class = _make_entity_class()
        service = _make_service()
        session.flush = AsyncMock()

        fixture_class = _make_fixture_class(
            data_list=[{"id": "1"}],  # no "attributes" key
            delete_previous_data=True,
        )
        fixture_class.create_from_service = AsyncMock(return_value=None)

        session.execute = AsyncMock(return_value=_make_rowcount_result(0))

        deleted, added, updated, unchanged = self._run_business_load(
            fixture_class, session, entity_class, service
        )

        # Should still create entity with empty attributes
        assert added == 1


# ---------------------------------------------------------------------------
# FixtureLoadingStrategy (abstract base class)
# ---------------------------------------------------------------------------

class TestFixtureLoadingStrategyABC:
    """Tests for the abstract FixtureLoadingStrategy base class."""

    def test_cannot_instantiate_directly(self):
        """Test that FixtureLoadingStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            FixtureLoadingStrategy()

    def test_concrete_subclass_must_implement_load(self):
        """Test that a concrete subclass without load raises TypeError."""

        class IncompleteStrategy(FixtureLoadingStrategy):
            pass

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_concrete_subclass_with_load_can_be_instantiated(self):
        """Test that a concrete subclass with load can be instantiated (covers line 46)."""

        class ConcreteStrategy(FixtureLoadingStrategy):
            async def load(self, fixture_class, session, entity_class, service):
                return (0, 0, 0, 0)

        strategy = ConcreteStrategy()
        result = _run(strategy.load(None, None, None, None))
        assert result == (0, 0, 0, 0)
