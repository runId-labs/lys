"""
Unit tests for licensing entity definitions.
"""
import inspect

from sqlalchemy import String
from sqlalchemy.orm.properties import MappedColumn


def _get_mapped_column(cls, name):
    """Get a MappedColumn from an unmapped declarative class."""
    attr = inspect.getattr_static(cls, name)
    assert isinstance(attr, MappedColumn), f"{name} is not a MappedColumn"
    return attr.column


class TestLicenseApplicationEntity:
    """Tests for LicenseApplication entity."""

    def test_entity_exists(self):
        from lys.apps.licensing.modules.application.entities import LicenseApplication
        assert LicenseApplication is not None

    def test_tablename(self):
        from lys.apps.licensing.modules.application.entities import LicenseApplication
        assert LicenseApplication.__tablename__ == "license_application"

    def test_inherits_from_parametric_entity(self):
        from lys.apps.licensing.modules.application.entities import LicenseApplication
        from lys.core.entities import ParametricEntity
        assert issubclass(LicenseApplication, ParametricEntity)


class TestClientEntity:
    """Tests for licensing Client entity extension."""

    def test_entity_exists(self):
        from lys.apps.licensing.modules.client.entities import Client
        assert Client is not None

    def test_extends_base_client(self):
        from lys.apps.licensing.modules.client.entities import Client
        from lys.apps.organization.modules.client.entities import Client as BaseClient
        assert issubclass(Client, BaseClient)

    def test_tablename(self):
        from lys.apps.licensing.modules.client.entities import Client
        assert Client.__tablename__ == "client"

    def test_has_provider_customer_id_column(self):
        from lys.apps.licensing.modules.client.entities import Client
        attr = inspect.getattr_static(Client, "provider_customer_id")
        assert isinstance(attr, MappedColumn)

    def test_provider_customer_id_is_nullable(self):
        from lys.apps.licensing.modules.client.entities import Client
        col = _get_mapped_column(Client, "provider_customer_id")
        assert col.nullable is True

    def test_provider_customer_id_is_unique(self):
        from lys.apps.licensing.modules.client.entities import Client
        col = _get_mapped_column(Client, "provider_customer_id")
        assert col.unique is True

    def test_provider_customer_id_is_string_type(self):
        from lys.apps.licensing.modules.client.entities import Client
        col = _get_mapped_column(Client, "provider_customer_id")
        assert isinstance(col.type, String)

    def test_extend_existing_table_args(self):
        from lys.apps.licensing.modules.client.entities import Client
        assert Client.__table_args__.get("extend_existing") is True


class TestLicensePlanEntity:
    """Tests for LicensePlan entity."""

    def test_entity_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        assert LicensePlan is not None

    def test_tablename(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        assert LicensePlan.__tablename__ == "license_plan"

    def test_inherits_from_parametric_entity(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        from lys.core.entities import ParametricEntity
        assert issubclass(LicensePlan, ParametricEntity)

    def test_has_app_id_annotation(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        all_annotations = {}
        for cls in LicensePlan.__mro__:
            if hasattr(cls, "__annotations__"):
                all_annotations.update(cls.__annotations__)
        assert "app_id" in all_annotations

    def test_has_client_id_annotation(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        all_annotations = {}
        for cls in LicensePlan.__mro__:
            if hasattr(cls, "__annotations__"):
                all_annotations.update(cls.__annotations__)
        assert "client_id" in all_annotations

    def test_client_id_is_nullable(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        col = _get_mapped_column(LicensePlan, "client_id")
        assert col.nullable is True

    def test_is_custom_property_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        assert isinstance(inspect.getattr_static(LicensePlan, "is_custom"), property)

    def test_current_version_property_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        assert isinstance(inspect.getattr_static(LicensePlan, "current_version"), property)


class TestLicensePlanVersionEntity:
    """Tests for LicensePlanVersion entity."""

    def test_entity_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        assert LicensePlanVersion is not None

    def test_tablename(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        assert LicensePlanVersion.__tablename__ == "license_plan_version"

    def test_inherits_from_entity(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        from lys.core.entities import Entity
        assert issubclass(LicensePlanVersion, Entity)

    def test_has_plan_id_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        attr = inspect.getattr_static(LicensePlanVersion, "plan_id")
        assert isinstance(attr, MappedColumn)

    def test_has_version_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        attr = inspect.getattr_static(LicensePlanVersion, "version")
        assert isinstance(attr, MappedColumn)

    def test_has_enabled_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        attr = inspect.getattr_static(LicensePlanVersion, "enabled")
        assert isinstance(attr, MappedColumn)

    def test_has_price_monthly_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        attr = inspect.getattr_static(LicensePlanVersion, "price_monthly")
        assert isinstance(attr, MappedColumn)

    def test_has_price_yearly_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        attr = inspect.getattr_static(LicensePlanVersion, "price_yearly")
        assert isinstance(attr, MappedColumn)

    def test_has_currency_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        attr = inspect.getattr_static(LicensePlanVersion, "currency")
        assert isinstance(attr, MappedColumn)

    def test_has_provider_product_id_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        attr = inspect.getattr_static(LicensePlanVersion, "provider_product_id")
        assert isinstance(attr, MappedColumn)

    def test_is_free_property_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        assert isinstance(inspect.getattr_static(LicensePlanVersion, "is_free"), property)


class TestLicensePlanVersionRuleEntity:
    """Tests for LicensePlanVersionRule entity."""

    def test_entity_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        assert LicensePlanVersionRule is not None

    def test_tablename(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        assert LicensePlanVersionRule.__tablename__ == "license_plan_version_rule"

    def test_inherits_from_entity(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        from lys.core.entities import Entity
        assert issubclass(LicensePlanVersionRule, Entity)

    def test_has_plan_version_id_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        attr = inspect.getattr_static(LicensePlanVersionRule, "plan_version_id")
        assert isinstance(attr, MappedColumn)

    def test_has_rule_id_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        attr = inspect.getattr_static(LicensePlanVersionRule, "rule_id")
        assert isinstance(attr, MappedColumn)

    def test_has_limit_value_column(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        attr = inspect.getattr_static(LicensePlanVersionRule, "limit_value")
        assert isinstance(attr, MappedColumn)

    def test_limit_value_is_nullable(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        col = _get_mapped_column(LicensePlanVersionRule, "limit_value")
        assert col.nullable is True


class TestSubscriptionEntity:
    """Tests for Subscription entity."""

    def test_entity_exists(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        assert Subscription is not None

    def test_tablename(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        assert Subscription.__tablename__ == "subscription"

    def test_inherits_from_entity(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        from lys.core.entities import Entity
        assert issubclass(Subscription, Entity)

    def test_has_client_id_column(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        attr = inspect.getattr_static(Subscription, "client_id")
        assert isinstance(attr, MappedColumn)

    def test_client_id_is_unique(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        col = _get_mapped_column(Subscription, "client_id")
        assert col.unique is True

    def test_has_plan_version_id_column(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        attr = inspect.getattr_static(Subscription, "plan_version_id")
        assert isinstance(attr, MappedColumn)

    def test_has_provider_subscription_id_column(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        attr = inspect.getattr_static(Subscription, "provider_subscription_id")
        assert isinstance(attr, MappedColumn)

    def test_has_pending_plan_version_id_column(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        attr = inspect.getattr_static(Subscription, "pending_plan_version_id")
        assert isinstance(attr, MappedColumn)

    def test_has_billing_period_column(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        attr = inspect.getattr_static(Subscription, "billing_period")
        assert isinstance(attr, MappedColumn)

    def test_has_current_period_start_column(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        attr = inspect.getattr_static(Subscription, "current_period_start")
        assert isinstance(attr, MappedColumn)

    def test_has_current_period_end_column(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        attr = inspect.getattr_static(Subscription, "current_period_end")
        assert isinstance(attr, MappedColumn)

    def test_has_canceled_at_column(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        attr = inspect.getattr_static(Subscription, "canceled_at")
        assert isinstance(attr, MappedColumn)

    def test_has_pending_downgrade_property(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        assert isinstance(inspect.getattr_static(Subscription, "has_pending_downgrade"), property)

    def test_has_is_canceled_property(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        assert isinstance(inspect.getattr_static(Subscription, "is_canceled"), property)

    def test_has_is_free_property(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        assert isinstance(inspect.getattr_static(Subscription, "is_free"), property)


class TestLicensePlanVersionEntityRelationships:
    """Tests for LicensePlanVersion relationships and constraints."""

    def test_has_plan_relationship(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        from tests.mocks.utils import has_relationship
        assert has_relationship(LicensePlanVersion, "plan")

    def test_has_rules_relationship(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        from tests.mocks.utils import has_relationship
        assert has_relationship(LicensePlanVersion, "rules")

    def test_has_unique_constraint(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        # Check __table_args__ for unique constraint
        assert hasattr(LicensePlanVersion, "__table_args__")
        args = LicensePlanVersion.__table_args__
        # Should be a tuple containing a UniqueConstraint
        has_unique = any(
            hasattr(arg, "name") and "uq_license_plan_version" in str(getattr(arg, "name", ""))
            for arg in args if not isinstance(arg, dict)
        )
        assert has_unique

    def test_accessing_users_method_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        assert hasattr(LicensePlanVersion, "accessing_users")

    def test_accessing_organizations_method_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
        assert hasattr(LicensePlanVersion, "accessing_organizations")


class TestLicensePlanVersionRuleRelationships:
    """Tests for LicensePlanVersionRule relationships and constraints."""

    def test_has_plan_version_relationship(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        from tests.mocks.utils import has_relationship
        assert has_relationship(LicensePlanVersionRule, "plan_version")

    def test_has_rule_relationship(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        from tests.mocks.utils import has_relationship
        assert has_relationship(LicensePlanVersionRule, "rule")

    def test_has_unique_constraint(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        args = LicensePlanVersionRule.__table_args__
        has_unique = any(
            hasattr(arg, "name") and "uq_license_plan_version_rule" in str(getattr(arg, "name", ""))
            for arg in args if not isinstance(arg, dict)
        )
        assert has_unique

    def test_accessing_users_method_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        assert hasattr(LicensePlanVersionRule, "accessing_users")

    def test_accessing_organizations_method_exists(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlanVersionRule
        assert hasattr(LicensePlanVersionRule, "accessing_organizations")


class TestSubscriptionEntityRelationships:
    """Tests for Subscription relationships and properties."""

    def test_has_client_relationship(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        from tests.mocks.utils import has_relationship
        assert has_relationship(Subscription, "client")

    def test_has_plan_version_relationship(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        from tests.mocks.utils import has_relationship
        assert has_relationship(Subscription, "plan_version")

    def test_has_pending_plan_version_relationship(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        from tests.mocks.utils import has_relationship
        assert has_relationship(Subscription, "pending_plan_version")

    def test_has_users_relationship(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        from tests.mocks.utils import has_relationship
        assert has_relationship(Subscription, "users")

    def test_has_plan_property(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        assert isinstance(inspect.getattr_static(Subscription, "plan"), property)

    def test_accessing_users_method_exists(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        assert hasattr(Subscription, "accessing_users")

    def test_accessing_organizations_method_exists(self):
        from lys.apps.licensing.modules.subscription.entities import Subscription
        assert hasattr(Subscription, "accessing_organizations")


class TestLicensePlanRelationships:
    """Tests for LicensePlan relationships."""

    def test_has_application_relationship(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        from tests.mocks.utils import has_relationship
        assert has_relationship(LicensePlan, "application")

    def test_has_client_relationship(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        from tests.mocks.utils import has_relationship
        assert has_relationship(LicensePlan, "client")

    def test_has_versions_relationship(self):
        from lys.apps.licensing.modules.plan.entities import LicensePlan
        from tests.mocks.utils import has_relationship
        assert has_relationship(LicensePlan, "versions")


class TestSubscriptionUserTable:
    """Tests for subscription_user association table."""

    def test_subscription_user_table_exists(self):
        from lys.apps.licensing.modules.subscription.entities import subscription_user
        assert subscription_user is not None

    def test_table_name(self):
        from lys.apps.licensing.modules.subscription.entities import subscription_user
        assert subscription_user.name == "subscription_user"

    def test_has_subscription_id_column(self):
        from lys.apps.licensing.modules.subscription.entities import subscription_user
        assert "subscription_id" in subscription_user.columns

    def test_has_user_id_column(self):
        from lys.apps.licensing.modules.subscription.entities import subscription_user
        assert "user_id" in subscription_user.columns

    def test_has_created_at_column(self):
        from lys.apps.licensing.modules.subscription.entities import subscription_user
        assert "created_at" in subscription_user.columns
