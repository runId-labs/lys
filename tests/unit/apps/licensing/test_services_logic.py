"""
Unit tests for licensing service logic (JWT-based methods that don't need DB).
"""
import pytest

from lys.core.errors import LysError


class TestLicenseCheckerCheckSubscriptionFromClaims:
    """Tests for LicenseCheckerService.check_subscription_from_claims."""

    def test_returns_subscription_when_exists(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"plan_id": "PRO", "status": "active", "rules": {"MAX_USERS": 50}}
            }
        }
        result = LicenseCheckerService.check_subscription_from_claims(claims, "client-123")
        assert result["plan_id"] == "PRO"
        assert result["status"] == "active"

    def test_returns_empty_dict_when_no_subscription(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {}}
        result = LicenseCheckerService.check_subscription_from_claims(claims, "client-123")
        assert result == {}

    def test_returns_empty_dict_when_no_subscriptions_key(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {}
        result = LicenseCheckerService.check_subscription_from_claims(claims, "client-123")
        assert result == {}

    def test_returns_empty_dict_for_different_client(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-456": {"plan_id": "PRO"}
            }
        }
        result = LicenseCheckerService.check_subscription_from_claims(claims, "client-123")
        assert result == {}


class TestLicenseCheckerCheckQuotaFromClaims:
    """Tests for LicenseCheckerService.check_quota_from_claims."""

    def test_within_quota_returns_valid(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"MAX_USERS": 50}}
            }
        }
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "client-123", "MAX_USERS", 10
        )
        assert is_valid is True
        assert current == 10
        assert limit == 50

    def test_at_quota_returns_invalid(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"MAX_USERS": 50}}
            }
        }
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "client-123", "MAX_USERS", 50
        )
        assert is_valid is False
        assert current == 50
        assert limit == 50

    def test_over_quota_returns_invalid(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"MAX_USERS": 50}}
            }
        }
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "client-123", "MAX_USERS", 75
        )
        assert is_valid is False

    def test_unknown_rule_returns_unlimited(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"MAX_USERS": 50}}
            }
        }
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "client-123", "UNKNOWN_RULE", 10
        )
        assert is_valid is True
        assert limit == -1

    def test_no_subscription_returns_invalid(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {}}
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "client-123", "MAX_USERS", 10
        )
        assert is_valid is False
        assert limit == 0

    def test_feature_toggle_treated_as_unlimited(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"EXPORT_PDF": True}}
            }
        }
        is_valid, current, limit = LicenseCheckerService.check_quota_from_claims(
            claims, "client-123", "EXPORT_PDF", 10
        )
        assert is_valid is True
        assert limit == -1


class TestLicenseCheckerEnforceQuotaFromClaims:
    """Tests for LicenseCheckerService.enforce_quota_from_claims."""

    def test_within_quota_does_not_raise(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"status": "active", "rules": {"MAX_USERS": 50}}
            }
        }
        # Should not raise
        LicenseCheckerService.enforce_quota_from_claims(
            claims, "client-123", "MAX_USERS", 10
        )

    def test_over_quota_raises_error(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"status": "active", "rules": {"MAX_USERS": 50}}
            }
        }
        with pytest.raises(LysError):
            LicenseCheckerService.enforce_quota_from_claims(
                claims, "client-123", "MAX_USERS", 50
            )

    def test_no_subscription_raises_error(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {}}
        with pytest.raises(LysError):
            LicenseCheckerService.enforce_quota_from_claims(
                claims, "client-123", "MAX_USERS", 10
            )

    def test_inactive_subscription_raises_error(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"status": "canceled", "rules": {"MAX_USERS": 50}}
            }
        }
        with pytest.raises(LysError):
            LicenseCheckerService.enforce_quota_from_claims(
                claims, "client-123", "MAX_USERS", 10
            )

    def test_pending_subscription_does_not_raise(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"status": "pending", "rules": {"MAX_USERS": 50}}
            }
        }
        # Should not raise - pending is allowed
        LicenseCheckerService.enforce_quota_from_claims(
            claims, "client-123", "MAX_USERS", 10
        )

    def test_custom_error_used_when_provided(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"status": "active", "rules": {"MAX_USERS": 5}}
            }
        }
        custom_error = (429, "CUSTOM_ERROR")
        with pytest.raises(LysError) as exc_info:
            LicenseCheckerService.enforce_quota_from_claims(
                claims, "client-123", "MAX_USERS", 10,
                error=custom_error
            )
        assert exc_info.value.status_code == 429
        assert exc_info.value.detail == "CUSTOM_ERROR"


class TestLicenseCheckerCheckFeatureFromClaims:
    """Tests for LicenseCheckerService.check_feature_from_claims."""

    def test_feature_present_returns_true(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"EXPORT_PDF": True}}
            }
        }
        result = LicenseCheckerService.check_feature_from_claims(
            claims, "client-123", "EXPORT_PDF"
        )
        assert result is True

    def test_feature_absent_returns_false(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"MAX_USERS": 50}}
            }
        }
        result = LicenseCheckerService.check_feature_from_claims(
            claims, "client-123", "EXPORT_PDF"
        )
        assert result is False

    def test_no_subscription_returns_false(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {}}
        result = LicenseCheckerService.check_feature_from_claims(
            claims, "client-123", "EXPORT_PDF"
        )
        assert result is False

    def test_quota_rule_also_counts_as_present(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"MAX_USERS": 50}}
            }
        }
        result = LicenseCheckerService.check_feature_from_claims(
            claims, "client-123", "MAX_USERS"
        )
        assert result is True


class TestLicenseCheckerEnforceFeatureFromClaims:
    """Tests for LicenseCheckerService.enforce_feature_from_claims."""

    def test_feature_present_does_not_raise(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"status": "active", "rules": {"EXPORT_PDF": True}}
            }
        }
        LicenseCheckerService.enforce_feature_from_claims(
            claims, "client-123", "EXPORT_PDF"
        )

    def test_feature_absent_raises_error(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"status": "active", "rules": {}}
            }
        }
        with pytest.raises(LysError):
            LicenseCheckerService.enforce_feature_from_claims(
                claims, "client-123", "EXPORT_PDF"
            )

    def test_no_subscription_raises_error(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {}}
        with pytest.raises(LysError):
            LicenseCheckerService.enforce_feature_from_claims(
                claims, "client-123", "EXPORT_PDF"
            )

    def test_inactive_subscription_raises_error(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"status": "expired", "rules": {"EXPORT_PDF": True}}
            }
        }
        with pytest.raises(LysError):
            LicenseCheckerService.enforce_feature_from_claims(
                claims, "client-123", "EXPORT_PDF"
            )


class TestLicenseCheckerGetLimitsFromClaims:
    """Tests for LicenseCheckerService.get_limits_from_claims."""

    def test_returns_quota_limits(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"MAX_USERS": 50, "MAX_PROJECTS": 100}}
            }
        }
        limits = LicenseCheckerService.get_limits_from_claims(claims, "client-123")
        assert limits["MAX_USERS"] == {"limit": 50, "type": "quota"}
        assert limits["MAX_PROJECTS"] == {"limit": 100, "type": "quota"}

    def test_returns_feature_toggles(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"EXPORT_PDF": True}}
            }
        }
        limits = LicenseCheckerService.get_limits_from_claims(claims, "client-123")
        assert limits["EXPORT_PDF"] == {"enabled": True, "type": "feature"}

    def test_returns_empty_when_no_subscription(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {"subscriptions": {}}
        limits = LicenseCheckerService.get_limits_from_claims(claims, "client-123")
        assert limits == {}

    def test_mixed_rules(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService

        claims = {
            "subscriptions": {
                "client-123": {"rules": {"MAX_USERS": 50, "EXPORT_PDF": True}}
            }
        }
        limits = LicenseCheckerService.get_limits_from_claims(claims, "client-123")
        assert limits["MAX_USERS"]["type"] == "quota"
        assert limits["EXPORT_PDF"]["type"] == "feature"


class TestValidateMaxProjectsPerMonthPlaceholder:
    """Tests for placeholder validator."""

    @pytest.mark.asyncio
    async def test_returns_valid_with_limit(self):
        from lys.apps.licensing.modules.rule.validators import validate_max_projects_per_month
        result = await validate_max_projects_per_month(None, "client-1", "app-1", 100)
        assert result == (True, 0, 100)

    @pytest.mark.asyncio
    async def test_returns_unlimited_when_none(self):
        from lys.apps.licensing.modules.rule.validators import validate_max_projects_per_month
        result = await validate_max_projects_per_month(None, "client-1", "app-1", None)
        assert result == (True, 0, -1)
