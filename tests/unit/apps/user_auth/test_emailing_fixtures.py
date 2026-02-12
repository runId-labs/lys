"""
Unit tests for user_auth emailing module fixtures.
"""
from lys.apps.user_auth.modules.emailing.fixtures import EmailingTypeFixtures
from lys.core.fixtures import EntityFixtures


class TestEmailingTypeFixtures:
    def test_exists(self):
        assert EmailingTypeFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        assert issubclass(EmailingTypeFixtures, EntityFixtures)

    def test_has_data_list(self):
        assert EmailingTypeFixtures.data_list is not None
        assert len(EmailingTypeFixtures.data_list) == 3

    def test_has_model(self):
        assert EmailingTypeFixtures.model is not None

    def test_data_list_contains_password_reset(self):
        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE
        ids = [d["id"] for d in EmailingTypeFixtures.data_list]
        assert USER_PASSWORD_RESET_EMAILING_TYPE in ids

    def test_data_list_contains_email_verification(self):
        from lys.apps.user_auth.modules.emailing.consts import USER_EMAIL_VERIFICATION_EMAILING_TYPE
        ids = [d["id"] for d in EmailingTypeFixtures.data_list]
        assert USER_EMAIL_VERIFICATION_EMAILING_TYPE in ids

    def test_data_list_contains_invitation(self):
        from lys.apps.user_auth.modules.emailing.consts import USER_INVITATION_EMAILING_TYPE
        ids = [d["id"] for d in EmailingTypeFixtures.data_list]
        assert USER_INVITATION_EMAILING_TYPE in ids
