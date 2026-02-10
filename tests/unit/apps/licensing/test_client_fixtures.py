"""
Unit tests for licensing client fixtures.
"""
import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestClientDevFixtures:
    """Tests for ClientDevFixtures."""

    def test_fixture_class_exists(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        assert ClientDevFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(ClientDevFixtures, EntityFixtures)

    def test_data_list_exists(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        assert hasattr(ClientDevFixtures, "data_list")
        assert isinstance(ClientDevFixtures.data_list, list)

    def test_data_list_has_clients(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        assert len(ClientDevFixtures.data_list) >= 3

    def test_all_entries_have_attributes(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        for entry in ClientDevFixtures.data_list:
            assert "attributes" in entry

    def test_all_entries_have_name(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        for entry in ClientDevFixtures.data_list:
            assert "name" in entry["attributes"]
            assert isinstance(entry["attributes"]["name"], str)


class TestClientDevFixturesRandomPassword:
    """Tests for ClientDevFixtures random password generation (H6 security fix)."""

    @pytest.mark.asyncio
    async def test_create_from_service_uses_random_password(self):
        """create_from_service must NOT use the hardcoded password from attributes."""
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_session = AsyncMock()
        mock_client = MagicMock()

        with patch.object(ClientDevFixtures, "service", create=True) as mock_service:
            mock_service.create_client_with_owner = AsyncMock(return_value=mock_client)

            attributes = {
                "name": "Test Corp",
                "owner_email": "owner@test.fr",
                "password": "password",
                "language_id": "fr",
            }
            await ClientDevFixtures.create_from_service(attributes, mock_session)

            call_kwargs = mock_service.create_client_with_owner.call_args[1]
            assert call_kwargs["password"] != "password"
            assert len(call_kwargs["password"]) > 10

    @pytest.mark.asyncio
    async def test_create_from_service_logs_email(self):
        """create_from_service must log the owner email with the generated password."""
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_session = AsyncMock()

        with patch.object(ClientDevFixtures, "service", create=True) as mock_service, \
             patch("lys.apps.licensing.modules.client.fixtures.logging") as mock_logging:
            mock_service.create_client_with_owner = AsyncMock(return_value=MagicMock())

            attributes = {
                "name": "Test Corp",
                "owner_email": "owner@test.fr",
                "password": "password",
                "language_id": "fr",
            }
            await ClientDevFixtures.create_from_service(attributes, mock_session)

            mock_logging.info.assert_called_once()
            log_msg = mock_logging.info.call_args[0][0]
            assert "owner@test.fr" in log_msg
