"""
Unit tests for organization abstract base classes.

Tests AbstractOrganizationEntity and AbstractUserOrganizationRoleEntity.
"""

import pytest
from unittest.mock import MagicMock


class TestAbstractOrganizationEntity:
    """Tests for AbstractOrganizationEntity abstract class."""

    def test_class_is_abstract(self):
        """Test that AbstractOrganizationEntity is abstract."""
        from lys.apps.organization.abstracts import AbstractOrganizationEntity

        assert AbstractOrganizationEntity.__abstract__ is True

    def test_has_name_column(self):
        """Test that AbstractOrganizationEntity has name column."""
        from lys.apps.organization.abstracts import AbstractOrganizationEntity

        assert "name" in AbstractOrganizationEntity.__annotations__

    def test_parent_organization_is_abstract_property(self):
        """Test that parent_organization is an abstract property."""
        from lys.apps.organization.abstracts import AbstractOrganizationEntity

        assert hasattr(AbstractOrganizationEntity, "parent_organization")

    def test_owner_is_abstract_property(self):
        """Test that owner is an abstract property."""
        from lys.apps.organization.abstracts import AbstractOrganizationEntity

        assert hasattr(AbstractOrganizationEntity, "owner")

    def test_accessing_users_returns_empty_list_by_default(self):
        """Test accessing_users returns empty list by default."""
        from lys.apps.organization.abstracts import AbstractOrganizationEntity

        # Create a concrete subclass for testing
        class ConcreteOrg(AbstractOrganizationEntity):
            __tablename__ = "test_org"
            __abstract__ = False

            @property
            def parent_organization(self):
                return None

            @property
            def owner(self):
                return None

        org = object.__new__(ConcreteOrg)
        assert org.accessing_users() == []

    def test_accessing_organizations_returns_self(self):
        """Test accessing_organizations returns dict with self."""
        from lys.apps.organization.abstracts import AbstractOrganizationEntity

        # Create a concrete mock
        org = MagicMock()
        org.__tablename__ = "client"
        org.id = "client-123"
        org.parent_organization = None

        result = AbstractOrganizationEntity.accessing_organizations(org)

        assert "client" in result
        assert "client-123" in result["client"]

    def test_accessing_organizations_includes_parent(self):
        """Test accessing_organizations includes parent organization."""
        from lys.apps.organization.abstracts import AbstractOrganizationEntity

        # Create parent mock
        parent = MagicMock(spec=AbstractOrganizationEntity)
        parent.__tablename__ = "parent_org"
        parent.id = "parent-123"
        parent.parent_organization = None
        parent.accessing_organizations.return_value = {"parent_org": ["parent-123"]}

        # Create child mock
        child = MagicMock()
        child.__tablename__ = "child_org"
        child.id = "child-456"
        child.parent_organization = parent

        result = AbstractOrganizationEntity.accessing_organizations(child)

        assert "child_org" in result
        assert "child-456" in result["child_org"]
        assert "parent_org" in result
        assert "parent-123" in result["parent_org"]


class TestAbstractUserOrganizationRoleEntity:
    """Tests for AbstractUserOrganizationRoleEntity abstract class."""

    def test_class_is_abstract(self):
        """Test that AbstractUserOrganizationRoleEntity is abstract."""
        from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity

        assert AbstractUserOrganizationRoleEntity.__abstract__ is True

    def test_has_user_id_column(self):
        """Test that class has user_id column."""
        from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity

        assert "user_id" in AbstractUserOrganizationRoleEntity.__annotations__

    def test_has_role_id_column(self):
        """Test that class has role_id column."""
        from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity

        assert "role_id" in AbstractUserOrganizationRoleEntity.__annotations__

    def test_organization_is_abstract_property(self):
        """Test that organization is an abstract property."""
        from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity

        assert hasattr(AbstractUserOrganizationRoleEntity, "organization")

    def test_user_is_abstract_property(self):
        """Test that user is an abstract property."""
        from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity

        assert hasattr(AbstractUserOrganizationRoleEntity, "user")

    def test_level_is_abstract_property(self):
        """Test that level is an abstract property."""
        from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity

        assert hasattr(AbstractUserOrganizationRoleEntity, "level")

    def test_accessing_users_returns_empty_list(self):
        """Test accessing_users returns empty list."""
        from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity

        role = MagicMock()
        result = AbstractUserOrganizationRoleEntity.accessing_users(role)

        assert result == []

    def test_accessing_organizations_returns_org_dict(self):
        """Test accessing_organizations returns organization dict."""
        from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity, AbstractOrganizationEntity

        # Create mock organization
        org = MagicMock(spec=AbstractOrganizationEntity)
        org.__tablename__ = "client"
        org.id = "client-123"
        org.parent_organization = None

        # Create mock user org role
        user_role = MagicMock()
        user_role.organization = org

        result = AbstractUserOrganizationRoleEntity.accessing_organizations(user_role)

        assert "client" in result
        assert "client-123" in result["client"]
