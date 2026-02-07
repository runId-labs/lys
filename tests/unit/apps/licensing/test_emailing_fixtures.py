"""
Unit tests for licensing emailing fixtures.
"""


class TestEmailingTypeFixtures:
    """Tests for licensing EmailingTypeFixtures."""

    def test_fixture_class_exists(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        assert EmailingTypeFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(EmailingTypeFixtures, EntityFixtures)

    def test_delete_previous_data_is_false(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        assert EmailingTypeFixtures.delete_previous_data is False

    def test_data_list_has_five_entries(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        assert len(EmailingTypeFixtures.data_list) == 5

    def test_data_list_ids(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        ids = [entry["id"] for entry in EmailingTypeFixtures.data_list]
        assert "LICENSE_GRANTED" in ids
        assert "LICENSE_REVOKED" in ids
        assert "SUBSCRIPTION_PAYMENT_SUCCESS" in ids
        assert "SUBSCRIPTION_PAYMENT_FAILED" in ids
        assert "SUBSCRIPTION_CANCELED" in ids

    def test_all_entries_have_enabled_true(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        for entry in EmailingTypeFixtures.data_list:
            assert entry["attributes"]["enabled"] is True

    def test_all_entries_have_subject(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        for entry in EmailingTypeFixtures.data_list:
            assert "subject" in entry["attributes"]
            assert isinstance(entry["attributes"]["subject"], str)
            assert len(entry["attributes"]["subject"]) > 0

    def test_all_entries_have_template(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        for entry in EmailingTypeFixtures.data_list:
            assert "template" in entry["attributes"]
            assert isinstance(entry["attributes"]["template"], str)

    def test_all_entries_have_context_description(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        for entry in EmailingTypeFixtures.data_list:
            assert "context_description" in entry["attributes"]
            assert isinstance(entry["attributes"]["context_description"], dict)

    def test_license_granted_template(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        entry = next(e for e in EmailingTypeFixtures.data_list if e["id"] == "LICENSE_GRANTED")
        assert entry["attributes"]["template"] == "license_granted"

    def test_license_revoked_template(self):
        from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures
        entry = next(e for e in EmailingTypeFixtures.data_list if e["id"] == "LICENSE_REVOKED")
        assert entry["attributes"]["template"] == "license_revoked"
