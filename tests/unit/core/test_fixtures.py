"""
Unit tests for core fixtures module.

Tests EntityFixtures base class and helper classes.
"""

import pytest
import inspect


class TestFixtureValidator:
    """Tests for _FixtureValidator helper class."""

    def test_class_exists(self):
        """Test _FixtureValidator class exists."""
        from lys.core.fixtures import _FixtureValidator
        assert _FixtureValidator is not None

    def test_has_is_valid_fixture_class_method(self):
        """Test _FixtureValidator has is_valid_fixture_class method."""
        from lys.core.fixtures import _FixtureValidator
        assert hasattr(_FixtureValidator, "is_valid_fixture_class")

    def test_has_has_required_attributes_method(self):
        """Test _FixtureValidator has has_required_attributes method."""
        from lys.core.fixtures import _FixtureValidator
        assert hasattr(_FixtureValidator, "has_required_attributes")


class TestFixtureLogger:
    """Tests for _FixtureLogger helper class."""

    def test_class_exists(self):
        """Test _FixtureLogger class exists."""
        from lys.core.fixtures import _FixtureLogger
        assert _FixtureLogger is not None

    def test_has_log_messages_dict(self):
        """Test _FixtureLogger has LOG_MESSAGES dict."""
        from lys.core.fixtures import _FixtureLogger
        assert hasattr(_FixtureLogger, "LOG_MESSAGES")
        assert isinstance(_FixtureLogger.LOG_MESSAGES, dict)

    def test_log_messages_has_start_key(self):
        """Test LOG_MESSAGES has START key."""
        from lys.core.fixtures import _FixtureLogger
        assert "START" in _FixtureLogger.LOG_MESSAGES

    def test_log_messages_has_report_header_key(self):
        """Test LOG_MESSAGES has REPORT_HEADER key."""
        from lys.core.fixtures import _FixtureLogger
        assert "REPORT_HEADER" in _FixtureLogger.LOG_MESSAGES

    def test_log_messages_has_deleted_key(self):
        """Test LOG_MESSAGES has DELETED key."""
        from lys.core.fixtures import _FixtureLogger
        assert "DELETED" in _FixtureLogger.LOG_MESSAGES

    def test_log_messages_has_added_key(self):
        """Test LOG_MESSAGES has ADDED key."""
        from lys.core.fixtures import _FixtureLogger
        assert "ADDED" in _FixtureLogger.LOG_MESSAGES

    def test_log_messages_has_updated_key(self):
        """Test LOG_MESSAGES has UPDATED key."""
        from lys.core.fixtures import _FixtureLogger
        assert "UPDATED" in _FixtureLogger.LOG_MESSAGES

    def test_log_messages_has_unchanged_key(self):
        """Test LOG_MESSAGES has UNCHANGED key."""
        from lys.core.fixtures import _FixtureLogger
        assert "UNCHANGED" in _FixtureLogger.LOG_MESSAGES

    def test_has_log_start_method(self):
        """Test _FixtureLogger has log_start method."""
        from lys.core.fixtures import _FixtureLogger
        assert hasattr(_FixtureLogger, "log_start")
        assert callable(_FixtureLogger.log_start)

    def test_has_log_results_method(self):
        """Test _FixtureLogger has log_results method."""
        from lys.core.fixtures import _FixtureLogger
        assert hasattr(_FixtureLogger, "log_results")
        assert callable(_FixtureLogger.log_results)


class TestEntityFixturesClass:
    """Tests for EntityFixtures base class."""

    def test_class_exists(self):
        """Test EntityFixtures class exists."""
        from lys.core.fixtures import EntityFixtures
        assert EntityFixtures is not None

    def test_implements_entity_fixture_interface(self):
        """Test EntityFixtures implements EntityFixtureInterface."""
        from lys.core.fixtures import EntityFixtures
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        assert issubclass(EntityFixtures, EntityFixtureInterface)

    def test_has_service_name_annotation(self):
        """Test EntityFixtures has service_name annotation."""
        from lys.core.fixtures import EntityFixtures
        assert "service_name" in EntityFixtures.__annotations__

    def test_has_model_annotation(self):
        """Test EntityFixtures has model annotation."""
        from lys.core.fixtures import EntityFixtures
        assert "model" in EntityFixtures.__annotations__

    def test_has_allowed_envs_attribute(self):
        """Test EntityFixtures has _allowed_envs attribute."""
        from lys.core.fixtures import EntityFixtures
        assert hasattr(EntityFixtures, "_allowed_envs")

    def test_has_data_list_annotation(self):
        """Test EntityFixtures has data_list annotation."""
        from lys.core.fixtures import EntityFixtures
        assert "data_list" in EntityFixtures.__annotations__

    def test_has_delete_previous_data_attribute(self):
        """Test EntityFixtures has delete_previous_data attribute."""
        from lys.core.fixtures import EntityFixtures
        assert hasattr(EntityFixtures, "delete_previous_data")
        assert EntityFixtures.delete_previous_data is True

    def test_has_service_property(self):
        """Test EntityFixtures has service classproperty."""
        from lys.core.fixtures import EntityFixtures
        # service is a classproperty
        assert "service" in dir(EntityFixtures)

    def test_has_create_from_service_method(self):
        """Test EntityFixtures has create_from_service method."""
        from lys.core.fixtures import EntityFixtures
        assert hasattr(EntityFixtures, "create_from_service")

    def test_create_from_service_is_async(self):
        """Test create_from_service is async."""
        from lys.core.fixtures import EntityFixtures
        assert inspect.iscoroutinefunction(EntityFixtures.create_from_service)

    def test_has_format_attributes_method(self):
        """Test EntityFixtures has _format_attributes method."""
        from lys.core.fixtures import EntityFixtures
        assert hasattr(EntityFixtures, "_format_attributes")

    def test_format_attributes_is_async(self):
        """Test _format_attributes is async."""
        from lys.core.fixtures import EntityFixtures
        assert inspect.iscoroutinefunction(EntityFixtures._format_attributes)

    def test_has_check_is_allowed_env_method(self):
        """Test EntityFixtures has _check_is_allowed_env method."""
        from lys.core.fixtures import EntityFixtures
        assert hasattr(EntityFixtures, "_check_is_allowed_env")

    def test_has_do_before_add_method(self):
        """Test EntityFixtures has _do_before_add method."""
        from lys.core.fixtures import EntityFixtures
        assert hasattr(EntityFixtures, "_do_before_add")

    def test_do_before_add_is_async(self):
        """Test _do_before_add is async."""
        from lys.core.fixtures import EntityFixtures
        assert inspect.iscoroutinefunction(EntityFixtures._do_before_add)

    def test_has_inner_load_method(self):
        """Test EntityFixtures has _inner_load method."""
        from lys.core.fixtures import EntityFixtures
        assert hasattr(EntityFixtures, "_inner_load")

    def test_inner_load_is_async(self):
        """Test _inner_load is async."""
        from lys.core.fixtures import EntityFixtures
        assert inspect.iscoroutinefunction(EntityFixtures._inner_load)

    def test_has_is_viable_method(self):
        """Test EntityFixtures has is_viable method."""
        from lys.core.fixtures import EntityFixtures
        assert hasattr(EntityFixtures, "is_viable")

    def test_has_load_method(self):
        """Test EntityFixtures has load method."""
        from lys.core.fixtures import EntityFixtures
        assert hasattr(EntityFixtures, "load")

    def test_load_is_async(self):
        """Test load is async."""
        from lys.core.fixtures import EntityFixtures
        assert inspect.iscoroutinefunction(EntityFixtures.load)


class TestEntityFixturesMethodSignatures:
    """Tests for EntityFixtures method signatures."""

    def test_create_from_service_signature(self):
        """Test create_from_service method signature."""
        from lys.core.fixtures import EntityFixtures

        sig = inspect.signature(EntityFixtures.create_from_service)
        params = list(sig.parameters.keys())
        assert "attributes" in params
        assert "session" in params

    def test_format_attributes_signature(self):
        """Test _format_attributes method signature."""
        from lys.core.fixtures import EntityFixtures

        sig = inspect.signature(EntityFixtures._format_attributes)
        params = list(sig.parameters.keys())
        assert "attributes" in params
        assert "session" in params
        assert "extra_data" in params

    def test_inner_load_signature(self):
        """Test _inner_load method signature."""
        from lys.core.fixtures import EntityFixtures

        sig = inspect.signature(EntityFixtures._inner_load)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "entity_class" in params
        assert "service" in params
