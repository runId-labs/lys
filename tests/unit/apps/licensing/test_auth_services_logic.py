"""
Unit tests for LicensingAuthService logic (generate_access_claims, _verify_subscription_status,
_verify_mollie_subscription).

Isolation: All tests use inline imports + patch.object. No global state modified.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch


class TestGenerateAccessClaims:
    """Tests for LicensingAuthService.generate_access_claims()."""

    @pytest.mark.asyncio
    async def test_super_user_skips_subscriptions(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        mock_session = AsyncMock()
        mock_user = Mock()
        mock_user.is_super_user = True

        base_claims = {"sub": "user-123", "webservices": {}}

        with patch.object(LicensingAuthService, "app_manager", create=True):
            with patch(
                "lys.apps.licensing.modules.auth.services.OrganizationAuthService.generate_access_claims",
                new_callable=AsyncMock, return_value=base_claims
            ):
                result = await LicensingAuthService.generate_access_claims(mock_user, mock_session)

        assert "subscriptions" not in result
        assert result["sub"] == "user-123"

    @pytest.mark.asyncio
    async def test_regular_user_gets_subscriptions(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        mock_session = AsyncMock()
        mock_user = Mock()
        mock_user.id = "user-123"
        mock_user.is_super_user = False

        base_claims = {"sub": "user-123", "webservices": {}}
        mock_subscriptions = {"client-1": {"plan_id": "PRO", "status": "active", "rules": {}}}

        with patch.object(LicensingAuthService, "app_manager", create=True):
            with patch(
                "lys.apps.licensing.modules.auth.services.OrganizationAuthService.generate_access_claims",
                new_callable=AsyncMock, return_value=base_claims
            ):
                with patch.object(
                    LicensingAuthService, "_get_subscription_claims",
                    new_callable=AsyncMock, return_value=mock_subscriptions
                ):
                    result = await LicensingAuthService.generate_access_claims(
                        mock_user, mock_session
                    )

        assert result["subscriptions"] == mock_subscriptions

    @pytest.mark.asyncio
    async def test_no_subscriptions_not_added(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        mock_session = AsyncMock()
        mock_user = Mock()
        mock_user.id = "user-123"
        mock_user.is_super_user = False

        base_claims = {"sub": "user-123"}

        with patch.object(LicensingAuthService, "app_manager", create=True):
            with patch(
                "lys.apps.licensing.modules.auth.services.OrganizationAuthService.generate_access_claims",
                new_callable=AsyncMock, return_value=base_claims
            ):
                with patch.object(
                    LicensingAuthService, "_get_subscription_claims",
                    new_callable=AsyncMock, return_value={}
                ):
                    result = await LicensingAuthService.generate_access_claims(
                        mock_user, mock_session
                    )

        assert "subscriptions" not in result


class TestVerifySubscriptionStatus:
    """Tests for LicensingAuthService._verify_subscription_status()."""

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_active(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        with patch("lys.apps.licensing.modules.auth.services.get_payment_provider", return_value="stripe"):
            result = await LicensingAuthService._verify_subscription_status("cust-1", "sub-1")

        assert result == "active"

    @pytest.mark.asyncio
    async def test_mollie_provider_delegates(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        with patch(
            "lys.apps.licensing.modules.auth.services.get_payment_provider",
            return_value="mollie"
        ):
            with patch.object(
                LicensingAuthService, "_verify_mollie_subscription",
                new_callable=AsyncMock, return_value="canceled"
            ) as mock_verify:
                result = await LicensingAuthService._verify_subscription_status("cust-1", "sub-1")

        assert result == "canceled"
        mock_verify.assert_called_once_with("cust-1", "sub-1")


class TestVerifyMollieSubscription:
    """Tests for LicensingAuthService._verify_mollie_subscription()."""

    @pytest.mark.asyncio
    async def test_mollie_not_configured_returns_active(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        with patch("lys.apps.licensing.modules.auth.services.get_mollie_client", return_value=None):
            result = await LicensingAuthService._verify_mollie_subscription("cust-1", "sub-1")

        assert result == "active"

    @pytest.mark.asyncio
    async def test_mollie_error_returns_active(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        mock_mollie = Mock()
        mock_mollie.customers.get.side_effect = Exception("API error")

        with patch(
            "lys.apps.licensing.modules.auth.services.get_mollie_client",
            return_value=mock_mollie
        ):
            result = await LicensingAuthService._verify_mollie_subscription("cust-1", "sub-1")

        assert result == "active"

    @pytest.mark.asyncio
    async def test_mollie_success_returns_status(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        mock_subscription = Mock()
        mock_subscription.status = "suspended"
        mock_customer = Mock()
        mock_customer.subscriptions.get.return_value = mock_subscription
        mock_mollie = Mock()
        mock_mollie.customers.get.return_value = mock_customer

        with patch(
            "lys.apps.licensing.modules.auth.services.get_mollie_client",
            return_value=mock_mollie
        ):
            result = await LicensingAuthService._verify_mollie_subscription("cust-1", "sub-1")

        assert result == "suspended"
