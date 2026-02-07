"""
Unit tests for licensing error definitions.
"""


class TestSubscriptionErrors:
    """Tests for subscription error tuples."""

    def test_no_active_subscription(self):
        from lys.apps.licensing.errors import NO_ACTIVE_SUBSCRIPTION
        assert NO_ACTIVE_SUBSCRIPTION == (403, "NO_ACTIVE_SUBSCRIPTION")

    def test_subscription_expired(self):
        from lys.apps.licensing.errors import SUBSCRIPTION_EXPIRED
        assert SUBSCRIPTION_EXPIRED == (403, "SUBSCRIPTION_EXPIRED")

    def test_subscription_inactive(self):
        from lys.apps.licensing.errors import SUBSCRIPTION_INACTIVE
        assert SUBSCRIPTION_INACTIVE == (403, "SUBSCRIPTION_INACTIVE")

    def test_subscription_already_exists(self):
        from lys.apps.licensing.errors import SUBSCRIPTION_ALREADY_EXISTS
        assert SUBSCRIPTION_ALREADY_EXISTS == (400, "SUBSCRIPTION_ALREADY_EXISTS")


class TestRuleErrors:
    """Tests for rule enforcement error tuples."""

    def test_quota_exceeded(self):
        from lys.apps.licensing.errors import QUOTA_EXCEEDED
        assert QUOTA_EXCEEDED == (429, "QUOTA_EXCEEDED")

    def test_feature_not_available(self):
        from lys.apps.licensing.errors import FEATURE_NOT_AVAILABLE
        assert FEATURE_NOT_AVAILABLE == (403, "FEATURE_NOT_AVAILABLE")

    def test_unknown_rule(self):
        from lys.apps.licensing.errors import UNKNOWN_RULE
        assert UNKNOWN_RULE == (500, "UNKNOWN_RULE")


class TestPlanErrors:
    """Tests for plan error tuples."""

    def test_plan_not_available(self):
        from lys.apps.licensing.errors import PLAN_NOT_AVAILABLE
        assert PLAN_NOT_AVAILABLE == (400, "PLAN_NOT_AVAILABLE")

    def test_plan_version_not_found(self):
        from lys.apps.licensing.errors import PLAN_VERSION_NOT_FOUND
        assert PLAN_VERSION_NOT_FOUND == (404, "PLAN_VERSION_NOT_FOUND")


class TestUserErrors:
    """Tests for user association error tuples."""

    def test_user_already_licensed(self):
        from lys.apps.licensing.errors import USER_ALREADY_LICENSED
        assert USER_ALREADY_LICENSED == (400, "USER_ALREADY_LICENSED")

    def test_user_not_licensed(self):
        from lys.apps.licensing.errors import USER_NOT_LICENSED
        assert USER_NOT_LICENSED == (404, "USER_NOT_LICENSED")

    def test_max_licensed_users_reached(self):
        from lys.apps.licensing.errors import MAX_LICENSED_USERS_REACHED
        assert MAX_LICENSED_USERS_REACHED == (429, "MAX_LICENSED_USERS_REACHED")


class TestDowngradeErrors:
    """Tests for downgrade error tuples."""

    def test_downgrade_rule_not_found(self):
        from lys.apps.licensing.errors import DOWNGRADE_RULE_NOT_FOUND
        assert DOWNGRADE_RULE_NOT_FOUND == (500, "DOWNGRADE_RULE_NOT_FOUND")


class TestAllErrorsAreTuples:
    """Tests that all errors follow the (status_code, error_code) format."""

    def test_all_errors_are_two_tuples(self):
        from lys.apps.licensing import errors
        error_names = [
            "NO_ACTIVE_SUBSCRIPTION", "SUBSCRIPTION_EXPIRED", "SUBSCRIPTION_INACTIVE",
            "SUBSCRIPTION_ALREADY_EXISTS", "QUOTA_EXCEEDED", "FEATURE_NOT_AVAILABLE",
            "UNKNOWN_RULE", "PLAN_NOT_AVAILABLE", "PLAN_VERSION_NOT_FOUND",
            "USER_ALREADY_LICENSED", "USER_NOT_LICENSED", "MAX_LICENSED_USERS_REACHED",
            "DOWNGRADE_RULE_NOT_FOUND",
        ]
        for name in error_names:
            error = getattr(errors, name)
            assert isinstance(error, tuple), f"{name} is not a tuple"
            assert len(error) == 2, f"{name} does not have 2 elements"
            assert isinstance(error[0], int), f"{name} status code is not int"
            assert isinstance(error[1], str), f"{name} error code is not str"
