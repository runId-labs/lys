"""
Unit tests for user_auth notification severity consts and fixtures.
"""
from lys.apps.user_auth.modules.notification.consts import (
    NOTIFICATION_SEVERITY_INFO,
    NOTIFICATION_SEVERITY_SUCCESS,
    NOTIFICATION_SEVERITY_WARNING,
    NOTIFICATION_SEVERITY_ERROR,
)
from lys.apps.user_auth.modules.notification.fixtures import NotificationSeverityFixtures
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel


class TestNotificationSeverityConsts:
    def test_info_value(self):
        assert NOTIFICATION_SEVERITY_INFO == "INFO"

    def test_success_value(self):
        assert NOTIFICATION_SEVERITY_SUCCESS == "SUCCESS"

    def test_warning_value(self):
        assert NOTIFICATION_SEVERITY_WARNING == "WARNING"

    def test_error_value(self):
        assert NOTIFICATION_SEVERITY_ERROR == "ERROR"

    def test_all_values_are_unique(self):
        values = {
            NOTIFICATION_SEVERITY_INFO,
            NOTIFICATION_SEVERITY_SUCCESS,
            NOTIFICATION_SEVERITY_WARNING,
            NOTIFICATION_SEVERITY_ERROR,
        }
        assert len(values) == 4


class TestNotificationSeverityFixtures:
    def test_exists(self):
        assert NotificationSeverityFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        assert issubclass(NotificationSeverityFixtures, EntityFixtures)

    def test_uses_parametric_model(self):
        assert NotificationSeverityFixtures.model is ParametricEntityFixturesModel

    def test_delete_previous_data_is_false(self):
        # Reference data — must never wipe rows that other apps FK against.
        assert NotificationSeverityFixtures.delete_previous_data is False

    def test_data_list_has_four_severities(self):
        assert len(NotificationSeverityFixtures.data_list) == 4

    def test_data_list_ids_match_consts(self):
        ids = {entry["id"] for entry in NotificationSeverityFixtures.data_list}
        assert ids == {
            NOTIFICATION_SEVERITY_INFO,
            NOTIFICATION_SEVERITY_SUCCESS,
            NOTIFICATION_SEVERITY_WARNING,
            NOTIFICATION_SEVERITY_ERROR,
        }

    def test_every_entry_has_description(self):
        for entry in NotificationSeverityFixtures.data_list:
            assert entry["attributes"]["description"], f"empty description for {entry['id']}"

    def test_every_entry_is_enabled(self):
        for entry in NotificationSeverityFixtures.data_list:
            assert entry["attributes"]["enabled"] is True
