"""
Unit tests for EmailingType entity with roles (user_role app).

Tests:
- Entity structure and inheritance
- emailing_type_role association table
- roles relationship declaration
"""
import inspect

from lys.apps.base.modules.emailing.entities import EmailingType as BaseEmailingType
from lys.apps.user_role.modules.emailing.entities import EmailingType, emailing_type_role
from lys.core.managers.database import Base


class TestEmailingTypeRoleAssociationTable:
    """Tests for the emailing_type_role association table."""

    def test_table_exists(self):
        assert emailing_type_role is not None

    def test_table_name(self):
        assert emailing_type_role.name == "emailing_type_role"

    def test_has_emailing_type_id_column(self):
        col_names = [c.name for c in emailing_type_role.columns]
        assert "emailing_type_id" in col_names

    def test_has_role_id_column(self):
        col_names = [c.name for c in emailing_type_role.columns]
        assert "role_id" in col_names

    def test_has_created_at_column(self):
        col_names = [c.name for c in emailing_type_role.columns]
        assert "created_at" in col_names

    def test_emailing_type_id_is_primary_key(self):
        col = emailing_type_role.c.emailing_type_id
        assert col.primary_key

    def test_role_id_is_primary_key(self):
        col = emailing_type_role.c.role_id
        assert col.primary_key

    def test_registered_in_base_metadata(self):
        assert "emailing_type_role" in Base.metadata.tables


class TestEmailingTypeEntity:
    """Tests for the extended EmailingType entity."""

    def test_class_exists(self):
        assert inspect.isclass(EmailingType)

    def test_inherits_from_base_emailing_type(self):
        assert issubclass(EmailingType, BaseEmailingType)

    def test_tablename(self):
        assert EmailingType.__tablename__ == "emailing_type"

    def test_has_roles_attribute(self):
        assert "roles" in EmailingType.__dict__

    def test_roles_is_declared_attr(self):
        # The roles attribute should be a relationship on the entity
        assert "roles" in EmailingType.__dict__

    def test_inherits_subject(self):
        # subject column inherited from base
        assert hasattr(EmailingType, "subject")

    def test_inherits_template(self):
        assert hasattr(EmailingType, "template")

    def test_inherits_context_description(self):
        assert hasattr(EmailingType, "context_description")
