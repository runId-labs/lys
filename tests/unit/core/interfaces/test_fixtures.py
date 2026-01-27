"""
Unit tests for core interfaces fixtures module.

Tests EntityFixtureInterface abstract class.
"""

import pytest
from abc import ABC


class TestEntityFixtureInterface:
    """Tests for EntityFixtureInterface class."""

    def test_class_exists(self):
        """Test EntityFixtureInterface class exists."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        assert EntityFixtureInterface is not None

    def test_inherits_from_abc(self):
        """Test EntityFixtureInterface inherits from ABC."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        assert issubclass(EntityFixtureInterface, ABC)

    def test_has_service_property(self):
        """Test EntityFixtureInterface has service classproperty."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        # service is a classproperty that raises NotImplementedError
        assert "service" in dir(EntityFixtureInterface)

    def test_has_format_attributes_method(self):
        """Test EntityFixtureInterface has _format_attributes method."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        assert hasattr(EntityFixtureInterface, "_format_attributes")

    def test_format_attributes_is_async(self):
        """Test _format_attributes is an async method."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityFixtureInterface._format_attributes)

    def test_has_check_is_allowed_env_method(self):
        """Test EntityFixtureInterface has _check_is_allowed_env method."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        assert hasattr(EntityFixtureInterface, "_check_is_allowed_env")

    def test_has_is_viable_method(self):
        """Test EntityFixtureInterface has is_viable method."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        assert hasattr(EntityFixtureInterface, "is_viable")

    def test_has_do_before_add_method(self):
        """Test EntityFixtureInterface has _do_before_add method."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        assert hasattr(EntityFixtureInterface, "_do_before_add")

    def test_do_before_add_is_async(self):
        """Test _do_before_add is an async method."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityFixtureInterface._do_before_add)

    def test_has_load_method(self):
        """Test EntityFixtureInterface has load method."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        assert hasattr(EntityFixtureInterface, "load")

    def test_load_is_async(self):
        """Test load is an async method."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        import inspect
        assert inspect.iscoroutinefunction(EntityFixtureInterface.load)


class TestEntityFixtureInterfaceMethodSignatures:
    """Tests for EntityFixtureInterface method signatures."""

    def test_format_attributes_signature(self):
        """Test _format_attributes method signature."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        import inspect

        sig = inspect.signature(EntityFixtureInterface._format_attributes)
        params = list(sig.parameters.keys())
        assert "attributes" in params
        assert "session" in params

    def test_is_viable_signature(self):
        """Test is_viable method signature."""
        from lys.core.interfaces.fixtures import EntityFixtureInterface
        import inspect

        sig = inspect.signature(EntityFixtureInterface.is_viable)
        params = list(sig.parameters.keys())
        assert "obj" in params
