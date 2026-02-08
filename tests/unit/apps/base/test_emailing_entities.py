"""
Unit tests for base emailing module entities.

Tests entity structure.
"""

import pytest


class TestEmailingStatusEntity:
    """Tests for EmailingStatus entity."""

    def test_entity_exists(self):
        """Test EmailingStatus entity exists."""
        from lys.apps.base.modules.emailing.entities import EmailingStatus
        assert EmailingStatus is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test EmailingStatus inherits from ParametricEntity."""
        from lys.apps.base.modules.emailing.entities import EmailingStatus
        from lys.core.entities import ParametricEntity
        assert issubclass(EmailingStatus, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test EmailingStatus has correct __tablename__."""
        from lys.apps.base.modules.emailing.entities import EmailingStatus
        assert EmailingStatus.__tablename__ == "emailing_status"


class TestEmailingTypeEntity:
    """Tests for EmailingType entity."""

    def test_entity_exists(self):
        """Test EmailingType entity exists."""
        from lys.apps.base.modules.emailing.entities import EmailingType
        assert EmailingType is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test EmailingType inherits from ParametricEntity."""
        from lys.apps.base.modules.emailing.entities import EmailingType
        from lys.core.entities import ParametricEntity
        assert issubclass(EmailingType, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test EmailingType has correct __tablename__."""
        from lys.apps.base.modules.emailing.entities import EmailingType
        assert EmailingType.__tablename__ == "emailing_type"

    def test_entity_has_subject_column(self):
        """Test EmailingType has subject column."""
        from lys.apps.base.modules.emailing.entities import EmailingType
        assert "subject" in EmailingType.__annotations__

    def test_entity_has_template_column(self):
        """Test EmailingType has template column."""
        from lys.apps.base.modules.emailing.entities import EmailingType
        assert "template" in EmailingType.__annotations__

    def test_entity_has_context_description_column(self):
        """Test EmailingType has context_description column."""
        from lys.apps.base.modules.emailing.entities import EmailingType
        assert "context_description" in EmailingType.__annotations__


class TestEmailingEntity:
    """Tests for Emailing entity."""

    def test_entity_exists(self):
        """Test Emailing entity exists."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert Emailing is not None

    def test_entity_inherits_from_entity(self):
        """Test Emailing inherits from Entity."""
        from lys.apps.base.modules.emailing.entities import Emailing
        from lys.core.entities import Entity
        assert issubclass(Emailing, Entity)

    def test_entity_has_tablename(self):
        """Test Emailing has correct __tablename__."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert Emailing.__tablename__ == "emailing"

    def test_entity_has_email_address_column(self):
        """Test Emailing has email_address column."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert "email_address" in Emailing.__annotations__

    def test_entity_has_context_column(self):
        """Test Emailing has context column."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert "context" in Emailing.__annotations__

    def test_entity_has_error_column(self):
        """Test Emailing has error column."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert "error" in Emailing.__annotations__

    def test_entity_has_status_id_column(self):
        """Test Emailing has status_id column."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert "status_id" in Emailing.__annotations__

    def test_entity_has_type_id_column(self):
        """Test Emailing has type_id column."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert "type_id" in Emailing.__annotations__

    def test_entity_has_language_id_column(self):
        """Test Emailing has language_id column."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert "language_id" in Emailing.__annotations__

    def test_entity_has_status_relationship(self):
        """Test Emailing has status relationship."""
        from lys.apps.base.modules.emailing.entities import Emailing
        from tests.mocks.utils import has_relationship
        assert has_relationship(Emailing, "status")

    def test_entity_has_type_relationship(self):
        """Test Emailing has type relationship."""
        from lys.apps.base.modules.emailing.entities import Emailing
        from tests.mocks.utils import has_relationship
        assert has_relationship(Emailing, "type")

    def test_entity_has_language_relationship(self):
        """Test Emailing has language relationship."""
        from lys.apps.base.modules.emailing.entities import Emailing
        from tests.mocks.utils import has_relationship
        assert has_relationship(Emailing, "language")

    def test_entity_has_accessing_users_method(self):
        """Test Emailing has accessing_users method."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert hasattr(Emailing, "accessing_users")
        assert callable(Emailing.accessing_users)

    def test_entity_has_accessing_organizations_method(self):
        """Test Emailing has accessing_organizations method."""
        from lys.apps.base.modules.emailing.entities import Emailing
        assert hasattr(Emailing, "accessing_organizations")
        assert callable(Emailing.accessing_organizations)
