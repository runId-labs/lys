"""
Unit tests for core interfaces entities module.

Tests EntityInterface abstract class.
"""

import pytest
from abc import ABC


class TestEntityInterface:
    """Tests for EntityInterface class."""

    def test_class_exists(self):
        """Test EntityInterface class exists."""
        from lys.core.interfaces.entities import EntityInterface
        assert EntityInterface is not None

    def test_has_get_tablename_method(self):
        """Test EntityInterface has get_tablename abstract method."""
        from lys.core.interfaces.entities import EntityInterface
        assert hasattr(EntityInterface, "get_tablename")

    def test_has_accessing_users_method(self):
        """Test EntityInterface has accessing_users abstract method."""
        from lys.core.interfaces.entities import EntityInterface
        assert hasattr(EntityInterface, "accessing_users")

    def test_has_accessing_organizations_method(self):
        """Test EntityInterface has accessing_organizations abstract method."""
        from lys.core.interfaces.entities import EntityInterface
        assert hasattr(EntityInterface, "accessing_organizations")

    def test_has_user_accessing_filters_method(self):
        """Test EntityInterface has user_accessing_filters abstract method."""
        from lys.core.interfaces.entities import EntityInterface
        assert hasattr(EntityInterface, "user_accessing_filters")

    def test_has_organization_accessing_filters_method(self):
        """Test EntityInterface has organization_accessing_filters abstract method."""
        from lys.core.interfaces.entities import EntityInterface
        assert hasattr(EntityInterface, "organization_accessing_filters")

    def test_has_check_permission_method(self):
        """Test EntityInterface has check_permission abstract method."""
        from lys.core.interfaces.entities import EntityInterface
        assert hasattr(EntityInterface, "check_permission")

    def test_get_tablename_raises_not_implemented(self):
        """Test get_tablename raises NotImplementedError when called directly."""
        from lys.core.interfaces.entities import EntityInterface
        with pytest.raises(NotImplementedError):
            EntityInterface.get_tablename()

    def test_accessing_users_raises_not_implemented(self):
        """Test accessing_users raises NotImplementedError when called directly."""
        from lys.core.interfaces.entities import EntityInterface

        class TestImpl(EntityInterface):
            @classmethod
            def get_tablename(cls):
                return "test"

            def accessing_organizations(self):
                return {}

            @classmethod
            def user_accessing_filters(cls, stmt, user_id):
                return stmt, []

            @classmethod
            def organization_accessing_filters(cls, stmt, accessing_organization_id_dict):
                return stmt, []

            def check_permission(self, user_id, access_type):
                return True

        instance = object.__new__(TestImpl)
        with pytest.raises(NotImplementedError):
            EntityInterface.accessing_users(instance)

    def test_check_permission_raises_not_implemented(self):
        """Test check_permission raises NotImplementedError when called directly."""
        from lys.core.interfaces.entities import EntityInterface
        with pytest.raises(NotImplementedError):
            EntityInterface.check_permission(None, None, None)


class TestEntityInterfaceMethodSignatures:
    """Tests for EntityInterface method signatures."""

    def test_user_accessing_filters_accepts_stmt_and_user_id(self):
        """Test user_accessing_filters accepts stmt and user_id parameters."""
        from lys.core.interfaces.entities import EntityInterface
        import inspect

        sig = inspect.signature(EntityInterface.user_accessing_filters)
        params = list(sig.parameters.keys())
        assert "stmt" in params
        assert "user_id" in params

    def test_organization_accessing_filters_accepts_stmt_and_dict(self):
        """Test organization_accessing_filters accepts stmt and dict parameters."""
        from lys.core.interfaces.entities import EntityInterface
        import inspect

        sig = inspect.signature(EntityInterface.organization_accessing_filters)
        params = list(sig.parameters.keys())
        assert "stmt" in params
        assert "accessing_organization_id_dict" in params

    def test_check_permission_accepts_user_id_and_access_type(self):
        """Test check_permission accepts user_id and access_type parameters."""
        from lys.core.interfaces.entities import EntityInterface
        import inspect

        sig = inspect.signature(EntityInterface.check_permission)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "access_type" in params
