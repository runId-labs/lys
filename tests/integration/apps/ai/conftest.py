"""
Pytest configuration for AI app integration tests.

Provides a session-scoped AppManager with AI app loaded,
configured for database-only tests (no LLM calls).
"""

import pytest_asyncio

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager
from tests.fixtures.database import create_all_tables


@pytest_asyncio.fixture(scope="session")
async def ai_app_manager():
    """Create AppManager with AI app loaded."""
    settings = LysAppSettings()
    settings.database.configure(
        type="sqlite",
        database=":memory:",
        echo=False
    )
    settings.apps = [
        "lys.apps.base",
        "lys.apps.user_auth",
        "lys.apps.ai",
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

        await session.commit()

    yield app_manager
    await app_manager.database.close()
