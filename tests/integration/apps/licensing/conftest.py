"""
Pytest configuration for licensing integration tests.

Provides a session-scoped AppManager with licensing app loaded,
including plans, rules, and versions for testing subscription and checker services.
"""

import pytest_asyncio

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager


@pytest_asyncio.fixture(scope="session")
async def licensing_app_manager():
    """Create AppManager with licensing app loaded."""
    settings = LysAppSettings()
    settings.database.configure(
        type="sqlite",
        database=":memory:",
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
    await app_manager.database.initialize_database()

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
        from lys.apps.licensing.consts import MAX_USERS, MAX_PROJECTS_PER_MONTH
        license_rule_service = app_manager.get_service("license_rule")
        await license_rule_service.create(session=session, id=MAX_USERS, enabled=True)
        await license_rule_service.create(session=session, id=MAX_PROJECTS_PER_MONTH, enabled=True)

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

        # Plan Versions
        plan_version_service = app_manager.get_service("license_plan_version")

        free_version = await plan_version_service.create(
            session=session, plan_id=FREE_PLAN, version=1, enabled=True,
            price_monthly=None, price_yearly=None, currency="eur"
        )
        starter_version = await plan_version_service.create(
            session=session, plan_id=STARTER_PLAN, version=1, enabled=True,
            price_monthly=1900, price_yearly=19000, currency="eur"
        )
        pro_version = await plan_version_service.create(
            session=session, plan_id=PRO_PLAN, version=1, enabled=True,
            price_monthly=4900, price_yearly=49000, currency="eur"
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
            rule_id=MAX_PROJECTS_PER_MONTH, limit_value=3
        )
        # STARTER: 25 users, 20 projects/month
        await version_rule_service.create(
            session=session, plan_version_id=starter_version.id,
            rule_id=MAX_USERS, limit_value=25
        )
        await version_rule_service.create(
            session=session, plan_version_id=starter_version.id,
            rule_id=MAX_PROJECTS_PER_MONTH, limit_value=20
        )
        # PRO: 100 users, unlimited projects (no rule = unlimited)
        await version_rule_service.create(
            session=session, plan_version_id=pro_version.id,
            rule_id=MAX_USERS, limit_value=100
        )

        await session.commit()

    yield app_manager
    await app_manager.database.close()
