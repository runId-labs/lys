"""
Unit tests for LicensingAuthService logic (generate_access_claims, _drop_unlicensed_owner_claims,
_verify_subscription_status, _verify_mollie_subscription).

Isolation: All tests use inline imports + patch.object. No global state modified.
"""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import declarative_base


_Base = declarative_base()


class _StandInWebservice(_Base):
    """The columns the claim filter reads: the registry entity only exists at app boot."""
    __tablename__ = "webservice"
    id = Column(String, primary_key=True)
    is_licenced = Column(Boolean)


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


class TestDropUnlicensedOwnerClaims:
    """LicensingAuthService._drop_unlicensed_owner_claims()."""

    @staticmethod
    def _app_manager(has_license: bool):
        webservice_service = Mock()
        webservice_service.user_is_licensed = AsyncMock(return_value=has_license)
        app_manager = MagicMock()
        app_manager.get_service = Mock(return_value=webservice_service)
        app_manager.get_entity = Mock(return_value=_StandInWebservice)
        return app_manager

    @pytest.mark.asyncio
    async def test_unlicensed_user_loses_owner_claims_on_licensed_webservices_only(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = [("all_actions",)]
        session.execute = AsyncMock(return_value=result)
        claims = {"all_actions": "owner", "my_profile": "owner", "all_users": "full"}

        with patch.object(LicensingAuthService, "app_manager", self._app_manager(False), create=True):
            kept = await LicensingAuthService._drop_unlicensed_owner_claims("user-1", claims, session)

        assert kept == {"my_profile": "owner", "all_users": "full"}

    @pytest.mark.asyncio
    async def test_licensed_user_keeps_every_claim(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        session = AsyncMock()
        claims = {"all_actions": "owner", "all_users": "full"}

        with patch.object(LicensingAuthService, "app_manager", self._app_manager(True), create=True):
            kept = await LicensingAuthService._drop_unlicensed_owner_claims("user-1", claims, session)

        assert kept == claims
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_owner_claim_needs_no_license_check(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService

        app_manager = self._app_manager(False)
        claims = {"all_users": "full"}

        with patch.object(LicensingAuthService, "app_manager", app_manager, create=True):
            kept = await LicensingAuthService._drop_unlicensed_owner_claims("user-1", claims, AsyncMock())

        assert kept == claims
        app_manager.get_service.assert_not_called()
