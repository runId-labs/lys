"""
Unit tests for licensing notification module fixtures and models.
"""
from lys.apps.licensing.modules.notification.fixtures import NotificationTypeFixtures
from lys.apps.licensing.modules.notification.models import NotificationTypeFixturesModel
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel


class TestNotificationTypeFixtures:
    def test_exists(self):
        assert NotificationTypeFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        assert issubclass(NotificationTypeFixtures, EntityFixtures)

    def test_has_data_list(self):
        assert NotificationTypeFixtures.data_list is not None
        assert len(NotificationTypeFixtures.data_list) == 5

    def test_has_model(self):
        assert NotificationTypeFixtures.model is not None

    def test_delete_previous_data_is_false(self):
        assert NotificationTypeFixtures.delete_previous_data is False

    def test_has_format_roles_method(self):
        assert hasattr(NotificationTypeFixtures, "format_roles")


class TestNotificationTypeFixturesModel:
    def test_exists(self):
        assert NotificationTypeFixturesModel is not None

    def test_inherits_from_parametric_model(self):
        assert issubclass(NotificationTypeFixturesModel, ParametricEntityFixturesModel)

    def test_has_attributes_model(self):
        assert hasattr(NotificationTypeFixturesModel, "AttributesModel")

    def test_attributes_model_has_roles_field(self):
        assert "roles" in NotificationTypeFixturesModel.AttributesModel.model_fields
