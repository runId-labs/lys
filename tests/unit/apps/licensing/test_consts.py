"""
Unit tests for licensing constants.
"""


class TestBillingPeriodEnum:
    """Tests for BillingPeriod enum."""

    def test_billing_period_exists(self):
        from lys.apps.licensing.consts import BillingPeriod
        assert BillingPeriod is not None

    def test_monthly_value(self):
        from lys.apps.licensing.consts import BillingPeriod
        assert BillingPeriod.MONTHLY == "monthly"

    def test_yearly_value(self):
        from lys.apps.licensing.consts import BillingPeriod
        assert BillingPeriod.YEARLY == "yearly"

    def test_is_string_enum(self):
        from lys.apps.licensing.consts import BillingPeriod
        assert isinstance(BillingPeriod.MONTHLY, str)
        assert isinstance(BillingPeriod.YEARLY, str)

    def test_enum_members_count(self):
        from lys.apps.licensing.consts import BillingPeriod
        assert len(BillingPeriod) == 2


class TestApplicationConstants:
    """Tests for application constants."""

    def test_default_application(self):
        from lys.apps.licensing.consts import DEFAULT_APPLICATION
        assert DEFAULT_APPLICATION == "DEFAULT"


class TestPlanConstants:
    """Tests for plan ID constants."""

    def test_free_plan(self):
        from lys.apps.licensing.consts import FREE_PLAN
        assert FREE_PLAN == "FREE"

    def test_starter_plan(self):
        from lys.apps.licensing.consts import STARTER_PLAN
        assert STARTER_PLAN == "STARTER"

    def test_pro_plan(self):
        from lys.apps.licensing.consts import PRO_PLAN
        assert PRO_PLAN == "PRO"


class TestRuleConstants:
    """Tests for rule ID constants."""

    def test_max_users(self):
        from lys.apps.licensing.consts import MAX_USERS
        assert MAX_USERS == "MAX_USERS"

    def test_max_projects_per_month(self):
        from lys.apps.licensing.consts import MAX_PROJECTS_PER_MONTH
        assert MAX_PROJECTS_PER_MONTH == "MAX_PROJECTS_PER_MONTH"


class TestRoleConstants:
    """Tests for role constants."""

    def test_license_admin_role(self):
        from lys.apps.licensing.consts import LICENSE_ADMIN_ROLE
        assert LICENSE_ADMIN_ROLE == "LICENSE_ADMIN_ROLE"


class TestErrorMessageConstants:
    """Tests for error message constants."""

    def test_authentication_required_error(self):
        from lys.apps.licensing.consts import AUTHENTICATION_REQUIRED_ERROR
        assert AUTHENTICATION_REQUIRED_ERROR == "AUTHENTICATION_REQUIRED_ERROR"

    def test_not_client_associated_user_error(self):
        from lys.apps.licensing.consts import NOT_CLIENT_ASSOCIATED_USER_ERROR
        assert NOT_CLIENT_ASSOCIATED_USER_ERROR == "NOT_CLIENT_ASSOCIATED_USER_ERROR"

    def test_no_payment_customer_error(self):
        from lys.apps.licensing.consts import NO_PAYMENT_CUSTOMER_ERROR
        assert NO_PAYMENT_CUSTOMER_ERROR == "NO_PAYMENT_CUSTOMER_ERROR"

    def test_checkout_session_failed_error(self):
        from lys.apps.licensing.consts import CHECKOUT_SESSION_FAILED_ERROR
        assert CHECKOUT_SESSION_FAILED_ERROR == "CHECKOUT_SESSION_FAILED_ERROR"

    def test_no_active_subscription_error(self):
        from lys.apps.licensing.consts import NO_ACTIVE_SUBSCRIPTION_ERROR
        assert NO_ACTIVE_SUBSCRIPTION_ERROR == "NO_ACTIVE_SUBSCRIPTION_ERROR"

    def test_same_plan_error(self):
        from lys.apps.licensing.consts import SAME_PLAN_ERROR
        assert SAME_PLAN_ERROR == "SAME_PLAN_ERROR"

    def test_plan_not_found_error(self):
        from lys.apps.licensing.consts import PLAN_NOT_FOUND_ERROR
        assert PLAN_NOT_FOUND_ERROR == "PLAN_NOT_FOUND_ERROR"

    def test_cancel_subscription_failed_error(self):
        from lys.apps.licensing.consts import CANCEL_SUBSCRIPTION_FAILED_ERROR
        assert CANCEL_SUBSCRIPTION_FAILED_ERROR == "CANCEL_SUBSCRIPTION_FAILED_ERROR"

    def test_no_provider_subscription_error(self):
        from lys.apps.licensing.consts import NO_PROVIDER_SUBSCRIPTION_ERROR
        assert NO_PROVIDER_SUBSCRIPTION_ERROR == "NO_PROVIDER_SUBSCRIPTION_ERROR"
