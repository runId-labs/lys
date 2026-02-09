"""
Unit tests for LicenseCheckerService logic.

Tests both DB-based and JWT-based checking methods.

Isolation: All tests use inline imports + patch.object. No global state modified.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch


class TestCheckSubscriptionFromClaims:
    """Tests for LicenseCheckerService.check_subscription_from_claims() — pure logic."""

    def test_returns_subscription_for_client(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-1": {"plan_id": "PRO", "status": "active", "rules": {"MAX_USERS": 50}}
            }
        }
        result = LicenseCheckerService.check_subscription_from_claims(claims, "client-1")
        assert result["plan_id"] == "PRO"

    def test_returns_empty_for_missing_client(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"client-1": {"plan_id": "PRO"}}}
        result = LicenseCheckerService.check_subscription_from_claims(claims, "client-999")
        assert result == {}

    def test_returns_empty_when_no_subscriptions(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        result = LicenseCheckerService.check_subscription_from_claims({}, "client-1")
        assert result == {}


class TestCheckQuotaFromClaims:
    """Tests for LicenseCheckerService.check_quota_from_claims() — pure logic."""

    def test_within_quota(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"c1": {"rules": {"MAX_USERS": 50}}}}
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "c1", "MAX_USERS", 30
        )
        assert is_valid is True
        assert current == 30
        assert limit == 50

    def test_exceeded_quota(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"c1": {"rules": {"MAX_USERS": 50}}}}
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "c1", "MAX_USERS", 50
        )
        assert is_valid is False
        assert limit == 50

    def test_no_subscription_returns_invalid(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            {}, "c1", "MAX_USERS", 10
        )
        assert is_valid is False
        assert limit == 0

    def test_rule_not_in_plan_returns_unlimited(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"c1": {"rules": {}}}}
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "c1", "MAX_USERS", 999
        )
        assert is_valid is True
        assert limit == -1

    def test_boolean_rule_treated_as_unlimited(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"c1": {"rules": {"EXPORT_PDF": True}}}}
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "c1", "EXPORT_PDF", 10
        )
        assert is_valid is True
        assert limit == -1


class TestEnforceQuotaFromClaims:
    """Tests for LicenseCheckerService.enforce_quota_from_claims()."""

    def test_no_subscription_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        with pytest.raises(LysError, match="NO_ACTIVE_SUBSCRIPTION"):
            LicenseCheckerService.enforce_quota_from_claims({}, "c1", "MAX_USERS", 10)

    def test_inactive_subscription_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        claims = {"subscriptions": {"c1": {"status": "canceled", "rules": {"MAX_USERS": 50}}}}
        with pytest.raises(LysError, match="SUBSCRIPTION_INACTIVE"):
            LicenseCheckerService.enforce_quota_from_claims(claims, "c1", "MAX_USERS", 10)

    def test_exceeded_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        claims = {"subscriptions": {"c1": {"status": "active", "rules": {"MAX_USERS": 5}}}}
        with pytest.raises(LysError, match="QUOTA_EXCEEDED"):
            LicenseCheckerService.enforce_quota_from_claims(claims, "c1", "MAX_USERS", 5)

    def test_within_quota_does_not_raise(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"c1": {"status": "active", "rules": {"MAX_USERS": 50}}}}
        # Should not raise
        LicenseCheckerService.enforce_quota_from_claims(claims, "c1", "MAX_USERS", 10)


class TestCheckFeatureFromClaims:
    """Tests for LicenseCheckerService.check_feature_from_claims() — pure logic."""

    def test_feature_present(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"c1": {"rules": {"EXPORT_PDF": True}}}}
        assert LicenseCheckerService.check_feature_from_claims(claims, "c1", "EXPORT_PDF") is True

    def test_feature_absent(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"c1": {"rules": {}}}}
        assert LicenseCheckerService.check_feature_from_claims(claims, "c1", "EXPORT_PDF") is False

    def test_no_subscription_returns_false(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        assert LicenseCheckerService.check_feature_from_claims({}, "c1", "EXPORT_PDF") is False


class TestEnforceFeatureFromClaims:
    """Tests for LicenseCheckerService.enforce_feature_from_claims()."""

    def test_no_subscription_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        with pytest.raises(LysError, match="NO_ACTIVE_SUBSCRIPTION"):
            LicenseCheckerService.enforce_feature_from_claims({}, "c1", "EXPORT_PDF")

    def test_inactive_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        claims = {"subscriptions": {"c1": {"status": "suspended", "rules": {"EXPORT_PDF": True}}}}
        with pytest.raises(LysError, match="SUBSCRIPTION_INACTIVE"):
            LicenseCheckerService.enforce_feature_from_claims(claims, "c1", "EXPORT_PDF")

    def test_missing_feature_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        claims = {"subscriptions": {"c1": {"status": "active", "rules": {}}}}
        with pytest.raises(LysError, match="FEATURE_NOT_AVAILABLE"):
            LicenseCheckerService.enforce_feature_from_claims(claims, "c1", "EXPORT_PDF")

    def test_available_feature_does_not_raise(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"c1": {"status": "active", "rules": {"EXPORT_PDF": True}}}}
        # Should not raise
        LicenseCheckerService.enforce_feature_from_claims(claims, "c1", "EXPORT_PDF")


class TestGetLimitsFromClaims:
    """Tests for LicenseCheckerService.get_limits_from_claims() — pure logic."""

    def test_empty_when_no_subscription(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        result = LicenseCheckerService.get_limits_from_claims({}, "c1")
        assert result == {}

    def test_parses_quota_and_feature_rules(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {"c1": {"rules": {
            "MAX_USERS": 50,
            "EXPORT_PDF": True
        }}}}
        result = LicenseCheckerService.get_limits_from_claims(claims, "c1")
        assert result["MAX_USERS"] == {"limit": 50, "type": "quota"}
        assert result["EXPORT_PDF"] == {"enabled": True, "type": "feature"}


class TestCheckQuotaDB:
    """Tests for LicenseCheckerService.check_quota() (DB-based)."""

    @pytest.mark.asyncio
    async def test_no_subscription_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_sub_service = AsyncMock()
        mock_sub_service.get_client_subscription = AsyncMock(return_value=None)

        with patch.object(LicenseCheckerService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_sub_service
            with pytest.raises(LysError, match="NO_ACTIVE_SUBSCRIPTION"):
                await LicenseCheckerService.check_quota("c1", "MAX_USERS", mock_session)

    @pytest.mark.asyncio
    async def test_rule_not_configured_returns_valid(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        mock_session = AsyncMock()
        mock_sub = Mock()
        mock_sub.plan_version_id = "pv-1"

        mock_sub_service = AsyncMock()
        mock_sub_service.get_client_subscription = AsyncMock(return_value=mock_sub)

        mock_vr_service = AsyncMock()
        mock_vr_service.get_rules_for_version = AsyncMock(return_value=[])

        with patch.object(LicenseCheckerService, "app_manager", create=True) as mock_am:
            mock_am.get_service.side_effect = lambda name: {
                "subscription": mock_sub_service,
                "license_plan_version_rule": mock_vr_service,
            }.get(name)
            is_valid, current, limit = await LicenseCheckerService.check_quota(
                "c1", "MAX_USERS", mock_session
            )

        assert is_valid is True
        assert limit == -1


class TestEnforceQuotaDB:
    """Tests for LicenseCheckerService.enforce_quota() (DB-based)."""

    @pytest.mark.asyncio
    async def test_exceeded_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        with patch.object(
            LicenseCheckerService, "check_quota",
            new_callable=AsyncMock, return_value=(False, 60, 50)
        ):
            with pytest.raises(LysError, match="QUOTA_EXCEEDED"):
                await LicenseCheckerService.enforce_quota("c1", "MAX_USERS", AsyncMock())

    @pytest.mark.asyncio
    async def test_within_quota_does_not_raise(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        with patch.object(
            LicenseCheckerService, "check_quota",
            new_callable=AsyncMock, return_value=(True, 30, 50)
        ):
            # Should not raise
            await LicenseCheckerService.enforce_quota("c1", "MAX_USERS", AsyncMock())


class TestCheckFeatureDB:
    """Tests for LicenseCheckerService.check_feature() (DB-based)."""

    @pytest.mark.asyncio
    async def test_no_subscription_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_sub_service = AsyncMock()
        mock_sub_service.get_client_subscription = AsyncMock(return_value=None)

        with patch.object(LicenseCheckerService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = mock_sub_service
            with pytest.raises(LysError, match="NO_ACTIVE_SUBSCRIPTION"):
                await LicenseCheckerService.check_feature("c1", "EXPORT_PDF", mock_session)

    @pytest.mark.asyncio
    async def test_feature_present_returns_true(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        mock_session = AsyncMock()
        mock_sub = Mock()
        mock_sub.plan_version_id = "pv-1"

        mock_sub_service = AsyncMock()
        mock_sub_service.get_client_subscription = AsyncMock(return_value=mock_sub)

        mock_rule = Mock()
        mock_rule.rule_id = "EXPORT_PDF"
        mock_vr_service = AsyncMock()
        mock_vr_service.get_rules_for_version = AsyncMock(return_value=[mock_rule])

        with patch.object(LicenseCheckerService, "app_manager", create=True) as mock_am:
            mock_am.get_service.side_effect = lambda name: {
                "subscription": mock_sub_service,
                "license_plan_version_rule": mock_vr_service,
            }.get(name)
            result = await LicenseCheckerService.check_feature("c1", "EXPORT_PDF", mock_session)

        assert result is True

    @pytest.mark.asyncio
    async def test_feature_absent_returns_false(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        mock_session = AsyncMock()
        mock_sub = Mock()
        mock_sub.plan_version_id = "pv-1"

        mock_sub_service = AsyncMock()
        mock_sub_service.get_client_subscription = AsyncMock(return_value=mock_sub)

        mock_vr_service = AsyncMock()
        mock_vr_service.get_rules_for_version = AsyncMock(return_value=[])

        with patch.object(LicenseCheckerService, "app_manager", create=True) as mock_am:
            mock_am.get_service.side_effect = lambda name: {
                "subscription": mock_sub_service,
                "license_plan_version_rule": mock_vr_service,
            }.get(name)
            result = await LicenseCheckerService.check_feature("c1", "EXPORT_PDF", mock_session)

        assert result is False


class TestEnforceFeatureDB:
    """Tests for LicenseCheckerService.enforce_feature() (DB-based)."""

    @pytest.mark.asyncio
    async def test_missing_feature_raises(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.errors import LysError

        with patch.object(
            LicenseCheckerService, "check_feature",
            new_callable=AsyncMock, return_value=False
        ):
            with pytest.raises(LysError, match="FEATURE_NOT_AVAILABLE"):
                await LicenseCheckerService.enforce_feature("c1", "EXPORT_PDF", AsyncMock())

    @pytest.mark.asyncio
    async def test_available_does_not_raise(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        with patch.object(
            LicenseCheckerService, "check_feature",
            new_callable=AsyncMock, return_value=True
        ):
            # Should not raise
            await LicenseCheckerService.enforce_feature("c1", "EXPORT_PDF", AsyncMock())
