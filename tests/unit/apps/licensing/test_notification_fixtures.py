"""
Unit tests for licensing notification module fixtures and models.
"""
from lys.apps.licensing.modules.notification.fixtures import NotificationTypeFixtures
from lys.apps.licensing.modules.notification.models import NotificationTypeFixturesModel
from lys.apps.user_auth.modules.notification.consts import (
    NOTIFICATION_SEVERITY_INFO,
    NOTIFICATION_SEVERITY_SUCCESS,
    NOTIFICATION_SEVERITY_WARNING,
    NOTIFICATION_SEVERITY_ERROR,
)
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel


_VALID_SEVERITIES = {
    NOTIFICATION_SEVERITY_INFO,
    NOTIFICATION_SEVERITY_SUCCESS,
    NOTIFICATION_SEVERITY_WARNING,
    NOTIFICATION_SEVERITY_ERROR,
}


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

    def test_depends_on_role_and_severity_fixtures(self):
        # `depends_on` is consumed by the @register_fixture decorator and not
        # stored on the class — verify it via the source so we still guard
        # against an accidental removal of the dependency declaration.
        import inspect
        from lys.apps.licensing.modules.notification import fixtures as _fixmod
        src = inspect.getsource(_fixmod)
        assert "depends_on" in src
        assert "RoleFixtures" in src
        assert "NotificationSeverityFixtures" in src

    def test_every_data_entry_has_severity_id(self):
        for entry in NotificationTypeFixtures.data_list:
            assert "severity_id" in entry["attributes"], f"missing severity_id in {entry['id']}"

    def test_every_severity_id_is_a_known_code(self):
        for entry in NotificationTypeFixtures.data_list:
            assert entry["attributes"]["severity_id"] in _VALID_SEVERITIES, (
                f"unknown severity for {entry['id']}: {entry['attributes']['severity_id']}"
            )

    def test_payment_failed_uses_error_severity(self):
        from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_PAYMENT_FAILED
        entry = next(e for e in NotificationTypeFixtures.data_list
                     if e["id"] == SUBSCRIPTION_PAYMENT_FAILED)
        assert entry["attributes"]["severity_id"] == NOTIFICATION_SEVERITY_ERROR

    def test_license_granted_uses_success_severity(self):
        from lys.apps.licensing.modules.event.consts import LICENSE_GRANTED
        entry = next(e for e in NotificationTypeFixtures.data_list
                     if e["id"] == LICENSE_GRANTED)
        assert entry["attributes"]["severity_id"] == NOTIFICATION_SEVERITY_SUCCESS

    def test_revoked_and_canceled_use_warning_severity(self):
        from lys.apps.licensing.modules.event.consts import (
            LICENSE_REVOKED,
            SUBSCRIPTION_CANCELED,
        )
        for code in (LICENSE_REVOKED, SUBSCRIPTION_CANCELED):
            entry = next(e for e in NotificationTypeFixtures.data_list if e["id"] == code)
            assert entry["attributes"]["severity_id"] == NOTIFICATION_SEVERITY_WARNING


class TestNotificationTypeFixturesModel:
    def test_exists(self):
        assert NotificationTypeFixturesModel is not None

    def test_inherits_from_parametric_model(self):
        assert issubclass(NotificationTypeFixturesModel, ParametricEntityFixturesModel)

    def test_has_attributes_model(self):
        assert hasattr(NotificationTypeFixturesModel, "AttributesModel")

    def test_attributes_model_has_roles_field(self):
        assert "roles" in NotificationTypeFixturesModel.AttributesModel.model_fields

    def test_attributes_model_has_severity_id_field(self):
        assert "severity_id" in NotificationTypeFixturesModel.AttributesModel.model_fields

    def test_attributes_model_severity_id_is_required(self):
        from pydantic import ValidationError
        import pytest as _pytest
        with _pytest.raises(ValidationError):
            NotificationTypeFixturesModel.AttributesModel(
                enabled=True, description="x", roles=[]
            )
