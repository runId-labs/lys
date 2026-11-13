"""
Pytest configuration for licensing integration tests.

Provides a session-scoped AppManager with licensing app loaded,
including plans, rules, and versions for testing subscription and checker services.
"""

import os
import tempfile
from uuid import uuid4

import pytest_asyncio

from lys.apps.licensing.registries import register_validator
from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.managers.app import AppManager
from lys.core.models.webservices import WebserviceFixturesModel
from tests.fixtures.database import create_all_tables


# A second quota rule, defined by the tests rather than by the framework: lys
# only ships quotas it can actually count. Its validator mirrors what a business
# application would register for its own countable resource.
DEMO_QUOTA_RULE = "DEMO_QUOTA"


@register_validator(DEMO_QUOTA_RULE)
async def validate_demo_quota(session, client_id, app_id, limit_value):
    """Validator standing in for an application-specific quota."""
    if limit_value is None:
        return (True, 0, -1)
    return (True, 0, limit_value)


@pytest_asyncio.fixture(scope="session")
async def licensing_app_manager():
    """Create AppManager with licensing app loaded.

    The database is a temporary file rather than ":memory:". The manager builds
    one engine per driver from the same setting, and ":memory:" gives each of
    them a database of its own: the Celery tasks, which run on the synchronous
    engine, would then open an empty schema and silently do nothing. A file is
    what makes both engines address the same data, and it is what makes
    `apply_pending_plan_changes` testable at all.
    """
    db_handle, db_path = tempfile.mkstemp(suffix=".sqlite", prefix="lys_licensing_")
    os.close(db_handle)

    settings = LysAppSettings()
    settings.database.configure(
        type="sqlite",
        database=db_path,
        echo=False
    )
    settings.apps = [
        "lys.apps.base",
        "lys.apps.user_auth",
        "lys.apps.user_role",
        "lys.apps.organization",
        "lys.apps.licensing",
    ]

    app_manager = AppManager(settings=settings)
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
    ])
    app_manager.load_all_components()
    await create_all_tables(app_manager.database)

    # Seed base parametric data
    async with app_manager.database.get_session() as session:
        # Languages
        language_service = app_manager.get_service("language")
        await language_service.create(session=session, id="en", enabled=True)
        await language_service.create(session=session, id="fr", enabled=True)

        # Genders
        gender_service = app_manager.get_service("gender")
        await gender_service.create(session=session, id="M", enabled=True)
        await gender_service.create(session=session, id="F", enabled=True)

        # Emailing types
        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE
        emailing_type_service = app_manager.get_service("emailing_type")
        await emailing_type_service.create(
            session=session, id=USER_PASSWORD_RESET_EMAILING_TYPE,
            enabled=True, subject="Password Reset", template="password_reset",
            context_description={}
        )

        # Emailing statuses
        emailing_status_service = app_manager.get_service("emailing_status")
        await emailing_status_service.create(session=session, id="PENDING", enabled=True)
        await emailing_status_service.create(session=session, id="SENT", enabled=True)

        # One-time token types
        from lys.apps.base.modules.one_time_token.consts import (
            PASSWORD_RESET_TOKEN_TYPE, EMAIL_VERIFICATION_TOKEN_TYPE
        )
        one_time_token_type_service = app_manager.get_service("one_time_token_type")
        await one_time_token_type_service.create(
            session=session, id=PASSWORD_RESET_TOKEN_TYPE, enabled=True, duration=30
        )
        await one_time_token_type_service.create(
            session=session, id=EMAIL_VERIFICATION_TOKEN_TYPE, enabled=True, duration=1440
        )

        # One-time token statuses
        from lys.apps.base.modules.one_time_token.consts import (
            PENDING_TOKEN_STATUS, USED_TOKEN_STATUS, REVOKED_TOKEN_STATUS
        )
        one_time_token_status_service = app_manager.get_service("one_time_token_status")
        await one_time_token_status_service.create(session=session, id=PENDING_TOKEN_STATUS, enabled=True)
        await one_time_token_status_service.create(session=session, id=USED_TOKEN_STATUS, enabled=True)
        await one_time_token_status_service.create(session=session, id=REVOKED_TOKEN_STATUS, enabled=True)

        # User statuses
        from lys.apps.user_auth.modules.user.consts import (
            ENABLED_USER_STATUS, DISABLED_USER_STATUS, REVOKED_USER_STATUS, DELETED_USER_STATUS
        )
        user_status_service = app_manager.get_service("user_status")
        await user_status_service.create(session=session, id=ENABLED_USER_STATUS, enabled=True)
        await user_status_service.create(session=session, id=DISABLED_USER_STATUS, enabled=True)
        await user_status_service.create(session=session, id=REVOKED_USER_STATUS, enabled=True)
        await user_status_service.create(session=session, id=DELETED_USER_STATUS, enabled=True)

        # User audit log types
        from lys.apps.user_auth.modules.user.consts import (
            STATUS_CHANGE_LOG_TYPE, ANONYMIZATION_LOG_TYPE, OBSERVATION_LOG_TYPE
        )
        user_audit_log_type_service = app_manager.get_service("user_audit_log_type")
        await user_audit_log_type_service.create(session=session, id=STATUS_CHANGE_LOG_TYPE, enabled=True)
        await user_audit_log_type_service.create(session=session, id=ANONYMIZATION_LOG_TYPE, enabled=True)
        await user_audit_log_type_service.create(session=session, id=OBSERVATION_LOG_TYPE, enabled=True)

        # Login attempt statuses
        from lys.apps.user_auth.modules.auth.consts import (
            FAILED_LOGIN_ATTEMPT_STATUS, SUCCEED_LOGIN_ATTEMPT_STATUS
        )
        login_attempt_status_service = app_manager.get_service("login_attempt_status")
        await login_attempt_status_service.create(session=session, id=FAILED_LOGIN_ATTEMPT_STATUS, enabled=True)
        await login_attempt_status_service.create(session=session, id=SUCCEED_LOGIN_ATTEMPT_STATUS, enabled=True)

        # License Application
        from lys.apps.licensing.consts import DEFAULT_APPLICATION
        license_app_service = app_manager.get_service("license_application")
        await license_app_service.create(
            session=session, id=DEFAULT_APPLICATION, enabled=True
        )

        # License Rules
        from lys.apps.licensing.consts import MAX_USERS
        license_rule_service = app_manager.get_service("license_rule")
        await license_rule_service.create(session=session, id=MAX_USERS, enabled=True)
        await license_rule_service.create(session=session, id=DEMO_QUOTA_RULE, enabled=True)

        # License Plans
        from lys.apps.licensing.consts import FREE_PLAN, STARTER_PLAN, PRO_PLAN
        license_plan_service = app_manager.get_service("license_plan")
        await license_plan_service.create(
            session=session, id=FREE_PLAN, enabled=True, app_id=DEFAULT_APPLICATION
        )
        await license_plan_service.create(
            session=session, id=STARTER_PLAN, enabled=True, app_id=DEFAULT_APPLICATION
        )
        await license_plan_service.create(
            session=session, id=PRO_PLAN, enabled=True, app_id=DEFAULT_APPLICATION
        )

        # Pricing reference data
        from lys.apps.licensing.consts import (
            EUR_CURRENCY,
            MONTHLY_PERIOD,
            NO_COMMITMENT,
            YEARLY_PERIOD,
        )
        from lys.apps.licensing.consts import MANUAL_BILLING, PROVIDER_BILLING
        billing_mode_service = app_manager.get_service("license_billing_mode")
        await billing_mode_service.create(session=session, id=PROVIDER_BILLING, enabled=True)
        await billing_mode_service.create(session=session, id=MANUAL_BILLING, enabled=True)

        currency_service = app_manager.get_service("license_currency")
        await currency_service.create(
            session=session, id=EUR_CURRENCY, enabled=True, minor_unit=2
        )
        commitment_service = app_manager.get_service("license_commitment")
        await commitment_service.create(
            session=session, id=NO_COMMITMENT, enabled=True, duration_months=0
        )
        period_service = app_manager.get_service("license_price_period")
        await period_service.create(
            session=session, id=MONTHLY_PERIOD, enabled=True, interval_months=1
        )
        await period_service.create(
            session=session, id=YEARLY_PERIOD, enabled=True, interval_months=12
        )

        # Plan Versions
        plan_version_service = app_manager.get_service("license_plan_version")

        free_version = await plan_version_service.create(
            session=session, plan_id=FREE_PLAN, version=1, enabled=True
        )
        starter_version = await plan_version_service.create(
            session=session, plan_id=STARTER_PLAN, version=1, enabled=True
        )
        pro_version = await plan_version_service.create(
            session=session, plan_id=PRO_PLAN, version=1, enabled=True
        )

        # Plan Version Prices (FREE has none, which is what makes it free)
        price_service = app_manager.get_service("license_plan_version_price")
        for version, monthly, yearly in (
            (starter_version, 1900, 19000),
            (pro_version, 4900, 49000),
        ):
            await price_service.create(
                session=session, plan_version_id=version.id,
                period_id=MONTHLY_PERIOD, currency_id=EUR_CURRENCY,
                commitment_id=NO_COMMITMENT, amount=monthly
            )
            await price_service.create(
                session=session, plan_version_id=version.id,
                period_id=YEARLY_PERIOD, currency_id=EUR_CURRENCY,
                commitment_id=NO_COMMITMENT, amount=yearly
            )

        # Version Rules
        version_rule_service = app_manager.get_service("license_plan_version_rule")
        # FREE: 5 users, 3 projects/month
        await version_rule_service.create(
            session=session, plan_version_id=free_version.id,
            rule_id=MAX_USERS, limit_value=5
        )
        await version_rule_service.create(
            session=session, plan_version_id=free_version.id,
            rule_id=DEMO_QUOTA_RULE, limit_value=3
        )
        # STARTER: 25 users, 20 projects/month
        await version_rule_service.create(
            session=session, plan_version_id=starter_version.id,
            rule_id=MAX_USERS, limit_value=25
        )
        await version_rule_service.create(
            session=session, plan_version_id=starter_version.id,
            rule_id=DEMO_QUOTA_RULE, limit_value=20
        )
        # PRO: 100 users, unlimited projects (no rule = unlimited)
        await version_rule_service.create(
            session=session, plan_version_id=pro_version.id,
            rule_id=MAX_USERS, limit_value=100
        )

        await session.commit()

    yield app_manager

    # close() disposes both engines through reset_database_connection
    await app_manager.database.close()
    os.unlink(db_path)


async def register_owner_webservices(app_manager) -> tuple[str, str]:
    """Register one licensed and one non-licensed webservice declaring OWNER; return their ids."""
    access_level_service = app_manager.get_service("access_level")
    webservice_service = app_manager.get_service("webservice")
    licensed_id = f"licensed_owner_ws_{uuid4().hex[:8]}"
    free_id = f"free_owner_ws_{uuid4().hex[:8]}"

    async with app_manager.database.get_session() as session:
        if await access_level_service.get_by_id(OWNER_ACCESS_LEVEL, session) is None:
            await access_level_service.create(session=session, id=OWNER_ACCESS_LEVEL, enabled=True)
        await webservice_service.register_webservices(
            [
                WebserviceFixturesModel(
                    id=ws_id,
                    attributes=WebserviceFixturesModel.AttributesModel(
                        public_type=None,
                        is_licenced=is_licenced,
                        enabled=True,
                        access_levels=[OWNER_ACCESS_LEVEL],
                        operation_type="query",
                        ai_tool=None,
                    ),
                )
                for ws_id, is_licenced in ((licensed_id, True), (free_id, False))
            ],
            "test_app",
            session,
        )
        await session.commit()

    return licensed_id, free_id


async def create_license_profile_users(app_manager) -> dict[str, str]:
    """
    Create the user profiles licensing distinguishes; return their ids.

    - owner: owns a client, which gets the FREE subscription on creation
    - licensed_member: client user holding a seat (subscription_user)
    - unlicensed_member: client user without a seat
    - outsider: user outside any client
    """
    client_service = app_manager.get_service("client")
    user_service = app_manager.get_service("user")
    subscription_service = app_manager.get_service("subscription")
    suffix = uuid4().hex[:8]

    async with app_manager.database.get_session() as session:
        client = await client_service.create_client_with_owner(
            session=session,
            client_name=f"OwnerLic-Corp-{suffix}",
            email=f"ownerlic-owner-{suffix}@example.com",
            password="Password123!",
            language_id="en",
            send_verification_email=False,
        )
        licensed_member = await user_service.create_client_user(
            session=session, client_id=client.id, email=f"ownerlic-lic-{suffix}@example.com", language_id="en"
        )
        unlicensed_member = await user_service.create_client_user(
            session=session, client_id=client.id, email=f"ownerlic-unlic-{suffix}@example.com", language_id="en"
        )
        outsider = await user_service.create_user(
            session=session,
            email=f"ownerlic-out-{suffix}@example.com",
            password="Password123!",
            language_id="en",
            send_verification_email=False,
        )
        subscription = await subscription_service.get_client_subscription(client.id, session)
        await subscription_service.add_user_to_subscription(subscription.id, licensed_member.id, session)
        await session.commit()

        return {
            "client": client.id,
            "owner": client.owner_id,
            "licensed_member": licensed_member.id,
            "unlicensed_member": unlicensed_member.id,
            "outsider": outsider.id,
        }


# Profiles created by create_license_profile_users, with whether each holds a license
LICENSED_PROFILES = {"owner": True, "licensed_member": True, "unlicensed_member": False, "outsider": False}
