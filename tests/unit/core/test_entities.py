"""
Unit tests for core entities module.

Tests Entity and ParametricEntity base classes.
"""

import pytest
from uuid import UUID


class TestEntityClass:
    """Tests for Entity base class."""

    def test_class_exists(self):
        """Test Entity class exists."""
        from lys.core.entities import Entity
        assert Entity is not None

    def test_has_tablename_attribute(self):
        """Test Entity has __tablename__ annotation."""
        from lys.core.entities import Entity
        assert "__tablename__" in Entity.__annotations__

    def test_has_abstract_attribute(self):
        """Test Entity has __abstract__ attribute."""
        from lys.core.entities import Entity
        assert hasattr(Entity, "__abstract__")
        assert Entity.__abstract__ is True

    def test_has_id_column(self):
        """Test Entity has id column."""
        from lys.core.entities import Entity
        assert "id" in Entity.__annotations__

    def test_has_created_at_column(self):
        """Test Entity has created_at column."""
        from lys.core.entities import Entity
        assert "created_at" in Entity.__annotations__

    def test_has_updated_at_column(self):
        """Test Entity has updated_at column."""
        from lys.core.entities import Entity
        assert "updated_at" in Entity.__annotations__

    def test_has_get_tablename_method(self):
        """Test Entity has get_tablename classmethod."""
        from lys.core.entities import Entity
        assert hasattr(Entity, "get_tablename")
        assert callable(Entity.get_tablename)

    def test_has_user_accessing_filters_method(self):
        """Test Entity has user_accessing_filters classmethod."""
        from lys.core.entities import Entity
        assert hasattr(Entity, "user_accessing_filters")
        assert callable(Entity.user_accessing_filters)

    def test_has_organization_accessing_filters_method(self):
        """Test Entity has organization_accessing_filters classmethod."""
        from lys.core.entities import Entity
        assert hasattr(Entity, "organization_accessing_filters")
        assert callable(Entity.organization_accessing_filters)

    def test_has_check_permission_method(self):
        """Test Entity has check_permission method."""
        from lys.core.entities import Entity
        assert hasattr(Entity, "check_permission")
        assert callable(Entity.check_permission)

    def test_implements_entity_interface(self):
        """Test Entity implements EntityInterface."""
        from lys.core.entities import Entity
        from lys.core.interfaces.entities import EntityInterface
        assert issubclass(Entity, EntityInterface)


class TestParametricEntityClass:
    """Tests for ParametricEntity class."""

    def test_class_exists(self):
        """Test ParametricEntity class exists."""
        from lys.core.entities import ParametricEntity
        assert ParametricEntity is not None

    def test_inherits_from_entity(self):
        """Test ParametricEntity inherits from Entity."""
        from lys.core.entities import Entity, ParametricEntity
        assert issubclass(ParametricEntity, Entity)

    def test_has_id_column_as_string(self):
        """Test ParametricEntity has string id column."""
        from lys.core.entities import ParametricEntity
        assert "id" in ParametricEntity.__annotations__

    def test_has_enabled_column(self):
        """Test ParametricEntity has enabled column."""
        from lys.core.entities import ParametricEntity
        assert "enabled" in ParametricEntity.__annotations__

    def test_has_description_column(self):
        """Test ParametricEntity has description column."""
        from lys.core.entities import ParametricEntity
        assert "description" in ParametricEntity.__annotations__

    def test_has_code_property(self):
        """Test ParametricEntity has code property."""
        from lys.core.entities import ParametricEntity
        assert hasattr(ParametricEntity, "code")

    def test_has_accessing_users_method(self):
        """Test ParametricEntity has accessing_users method."""
        from lys.core.entities import ParametricEntity
        assert hasattr(ParametricEntity, "accessing_users")
        assert callable(ParametricEntity.accessing_users)

    def test_has_accessing_organizations_method(self):
        """Test ParametricEntity has accessing_organizations method."""
        from lys.core.entities import ParametricEntity
        assert hasattr(ParametricEntity, "accessing_organizations")
        assert callable(ParametricEntity.accessing_organizations)


class TestEntityCheckPermission:
    """Tests for Entity check_permission method logic."""

    def test_check_permission_with_boolean_true(self):
        """Test check_permission returns True when access_type is True."""
        from lys.core.entities import Entity

        class TestEntity(Entity):
            __tablename__ = "test"
            __abstract__ = False

            def accessing_users(self):
                return []

            def accessing_organizations(self):
                return {}

        entity = object.__new__(TestEntity)
        result = entity.check_permission("user_123", True)
        assert result is True

    def test_check_permission_with_boolean_false(self):
        """Test check_permission returns False when access_type is False."""
        from lys.core.entities import Entity

        class TestEntity(Entity):
            __tablename__ = "test"
            __abstract__ = False

            def accessing_users(self):
                return []

            def accessing_organizations(self):
                return {}

        entity = object.__new__(TestEntity)
        result = entity.check_permission("user_123", False)
        assert result is False

    def test_check_permission_with_role_access(self):
        """Test check_permission with role access grants permission."""
        from lys.core.entities import Entity
        from lys.core.consts.permissions import ROLE_ACCESS_KEY

        class TestEntity(Entity):
            __tablename__ = "test"
            __abstract__ = False

            def accessing_users(self):
                return []

            def accessing_organizations(self):
                return {}

        entity = object.__new__(TestEntity)
        access_type = {ROLE_ACCESS_KEY: True}
        result = entity.check_permission("user_123", access_type)
        assert result is True

    def test_check_permission_with_owner_access_granted(self):
        """Test check_permission with owner access when user is owner."""
        from lys.core.entities import Entity
        from lys.core.consts.permissions import OWNER_ACCESS_KEY

        class TestEntity(Entity):
            __tablename__ = "test"
            __abstract__ = False

            def accessing_users(self):
                return ["user_123", "user_456"]

            def accessing_organizations(self):
                return {}

        entity = object.__new__(TestEntity)
        access_type = {OWNER_ACCESS_KEY: True}
        result = entity.check_permission("user_123", access_type)
        assert result is True

    def test_check_permission_with_owner_access_denied(self):
        """Test check_permission with owner access when user is not owner."""
        from lys.core.entities import Entity
        from lys.core.consts.permissions import OWNER_ACCESS_KEY

        class TestEntity(Entity):
            __tablename__ = "test"
            __abstract__ = False

            def accessing_users(self):
                return ["user_456"]

            def accessing_organizations(self):
                return {}

        entity = object.__new__(TestEntity)
        access_type = {OWNER_ACCESS_KEY: True}
        result = entity.check_permission("user_123", access_type)
        assert result is False


class TestParametricEntityDefaults:
    """Tests for ParametricEntity default method behaviors."""

    def test_accessing_users_returns_empty_list(self):
        """Test ParametricEntity accessing_users returns empty list by default."""
        from lys.core.entities import ParametricEntity

        class TestParametric(ParametricEntity):
            __tablename__ = "test_parametric"
            __abstract__ = False

        entity = object.__new__(TestParametric)
        result = entity.accessing_users()
        assert result == []

    def test_accessing_organizations_returns_empty_dict(self):
        """Test ParametricEntity accessing_organizations returns empty dict by default."""
        from lys.core.entities import ParametricEntity

        class TestParametric(ParametricEntity):
            __tablename__ = "test_parametric"
            __abstract__ = False

        entity = object.__new__(TestParametric)
        result = entity.accessing_organizations()
        assert result == {}
