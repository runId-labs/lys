"""
Integration tests for UserSSOLinkService.

Tests cover:
- create_link: successful creation, duplicate user-provider, duplicate external ID
- find_by_provider_and_external_id: found and not found
- find_by_user_and_provider: found and not found
- find_all_by_user: multiple links, empty result
- delete_link: successful deletion, not found

Test approach: Integration (SQLite in-memory, forked subprocess)
Dependencies: user_auth app (for User entity), sso app (for UserSSOLink)
"""

import pytest
import pytest_asyncio
import uuid

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.errors import LysError
from lys.core.managers.app import AppManager


@pytest_asyncio.fixture(scope="session")
async def sso_app_manager():
    """Create AppManager with user_auth + sso apps loaded."""
    settings = LysAppSettings()
    settings.database.configure(
        type="sqlite",
        database=":memory:",
        echo=False
    )
    settings.apps = ["lys.apps.base", "lys.apps.user_auth", "lys.apps.sso"]

    app_manager = AppManager(settings=settings)
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
    ])
    app_manager.load_all_components()
    await app_manager.database.initialize_database()

    # Create base parametric data
    language_service = app_manager.get_service("language")
    gender_service = app_manager.get_service("gender")
    user_status_service = app_manager.get_service("user_status")
    emailing_status_service = app_manager.get_service("emailing_status")
    emailing_type_service = app_manager.get_service("emailing_type")

    async with app_manager.database.get_session() as session:
        await language_service.create(session=session, id="en", enabled=True)
        await gender_service.create(session=session, id="M", enabled=True)

        from lys.apps.user_auth.modules.user.consts import (
            ENABLED_USER_STATUS, DISABLED_USER_STATUS, REVOKED_USER_STATUS, DELETED_USER_STATUS
        )
        for status_id in [ENABLED_USER_STATUS, DISABLED_USER_STATUS, REVOKED_USER_STATUS, DELETED_USER_STATUS]:
            await user_status_service.create(session=session, id=status_id, enabled=True)

        await emailing_status_service.create(session=session, id="PENDING", enabled=True)
        await emailing_status_service.create(session=session, id="SENT", enabled=True)

        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE
        await emailing_type_service.create(
            session=session, id=USER_PASSWORD_RESET_EMAILING_TYPE, enabled=True,
            subject="Password Reset", template="password_reset", context_description={}
        )

        await session.commit()

    yield app_manager
    await app_manager.database.close()


async def _create_test_user(app_manager, session, email=None, password="Password123!"):
    """Helper to create a test user and return it."""
    user_service = app_manager.get_service("user")
    if email is None:
        email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    user = await user_service.create_user(
        session=session,
        email=email,
        password=password,
        language_id="en",
        send_verification_email=False
    )
    await session.flush()
    return user


class TestCreateLink:
    """Tests for UserSSOLinkService.create_link()."""

    @pytest.mark.asyncio
    async def test_create_link_success(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            user = await _create_test_user(sso_app_manager, session)

            link = await sso_link_service.create_link(
                user_id=user.id,
                provider="microsoft",
                external_user_id="ms-ext-001",
                external_email="user@outlook.com",
                session=session,
            )

            assert link.id is not None
            assert link.user_id == user.id
            assert link.provider == "microsoft"
            assert link.external_user_id == "ms-ext-001"
            assert link.external_email == "user@outlook.com"
            assert link.linked_at is not None

    @pytest.mark.asyncio
    async def test_create_link_duplicate_user_provider_raises(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            user = await _create_test_user(sso_app_manager, session)

            await sso_link_service.create_link(
                user_id=user.id,
                provider="microsoft",
                external_user_id="ms-ext-002",
                external_email="user@outlook.com",
                session=session,
            )

            with pytest.raises(LysError) as exc_info:
                await sso_link_service.create_link(
                    user_id=user.id,
                    provider="microsoft",
                    external_user_id="ms-ext-003",
                    external_email="user2@outlook.com",
                    session=session,
                )
            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_create_link_duplicate_external_id_raises(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            user1 = await _create_test_user(sso_app_manager, session)
            user2 = await _create_test_user(sso_app_manager, session)

            await sso_link_service.create_link(
                user_id=user1.id,
                provider="google",
                external_user_id="google-ext-001",
                external_email="user1@gmail.com",
                session=session,
            )

            with pytest.raises(LysError) as exc_info:
                await sso_link_service.create_link(
                    user_id=user2.id,
                    provider="google",
                    external_user_id="google-ext-001",
                    external_email="user2@gmail.com",
                    session=session,
                )
            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_user_can_have_links_to_different_providers(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            user = await _create_test_user(sso_app_manager, session)

            link1 = await sso_link_service.create_link(
                user_id=user.id,
                provider="microsoft",
                external_user_id="ms-ext-multi",
                external_email="user@outlook.com",
                session=session,
            )
            link2 = await sso_link_service.create_link(
                user_id=user.id,
                provider="google",
                external_user_id="google-ext-multi",
                external_email="user@gmail.com",
                session=session,
            )

            assert link1.provider == "microsoft"
            assert link2.provider == "google"


class TestFindMethods:
    """Tests for find methods."""

    @pytest.mark.asyncio
    async def test_find_by_provider_and_external_id_found(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            user = await _create_test_user(sso_app_manager, session)

            await sso_link_service.create_link(
                user_id=user.id,
                provider="microsoft",
                external_user_id="ms-find-001",
                external_email="find@outlook.com",
                session=session,
            )

            found = await sso_link_service.find_by_provider_and_external_id(
                "microsoft", "ms-find-001", session
            )
            assert found is not None
            assert found.user_id == user.id

    @pytest.mark.asyncio
    async def test_find_by_provider_and_external_id_not_found(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            found = await sso_link_service.find_by_provider_and_external_id(
                "microsoft", "nonexistent", session
            )
            assert found is None

    @pytest.mark.asyncio
    async def test_find_by_user_and_provider_found(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            user = await _create_test_user(sso_app_manager, session)

            await sso_link_service.create_link(
                user_id=user.id,
                provider="microsoft",
                external_user_id="ms-userfind-001",
                external_email="ufind@outlook.com",
                session=session,
            )

            found = await sso_link_service.find_by_user_and_provider(user.id, "microsoft", session)
            assert found is not None
            assert found.external_user_id == "ms-userfind-001"

    @pytest.mark.asyncio
    async def test_find_by_user_and_provider_not_found(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            found = await sso_link_service.find_by_user_and_provider(
                "nonexistent-user-id", "microsoft", session
            )
            assert found is None

    @pytest.mark.asyncio
    async def test_find_all_by_user(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            user = await _create_test_user(sso_app_manager, session)

            await sso_link_service.create_link(
                user_id=user.id, provider="microsoft",
                external_user_id="ms-all-001", external_email="all@outlook.com",
                session=session,
            )
            await sso_link_service.create_link(
                user_id=user.id, provider="google",
                external_user_id="google-all-001", external_email="all@gmail.com",
                session=session,
            )

            links = await sso_link_service.find_all_by_user(user.id, session)
            assert len(links) == 2
            providers = {link.provider for link in links}
            assert providers == {"microsoft", "google"}

    @pytest.mark.asyncio
    async def test_find_all_by_user_empty(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            links = await sso_link_service.find_all_by_user("no-links-user", session)
            assert links == []


class TestDeleteLink:
    """Tests for UserSSOLinkService.delete_link()."""

    @pytest.mark.asyncio
    async def test_delete_link_success(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            user = await _create_test_user(sso_app_manager, session)

            await sso_link_service.create_link(
                user_id=user.id, provider="microsoft",
                external_user_id="ms-del-001", external_email="del@outlook.com",
                session=session,
            )

            result = await sso_link_service.delete_link(user.id, "microsoft", session)
            assert result is True

            # Verify it's gone
            found = await sso_link_service.find_by_user_and_provider(user.id, "microsoft", session)
            assert found is None

    @pytest.mark.asyncio
    async def test_delete_link_not_found(self, sso_app_manager):
        sso_link_service = sso_app_manager.get_service("user_sso_link")

        async with sso_app_manager.database.get_session() as session:
            result = await sso_link_service.delete_link("nonexistent", "microsoft", session)
            assert result is False


class TestUserCreationWithSSO:
    """Tests for user creation with password=None (SSO-only users)."""

    @pytest.mark.asyncio
    async def test_create_user_without_password(self, sso_app_manager):
        """SSO-only users are created with password=None."""
        user_service = sso_app_manager.get_service("user")

        async with sso_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=f"sso-{uuid.uuid4().hex[:8]}@test.com",
                password=None,
                language_id="en",
                send_verification_email=False,
            )

            assert user.id is not None
            assert user.password is None

    @pytest.mark.asyncio
    async def test_sso_user_cannot_login_with_password(self, sso_app_manager):
        """SSO-only users should be rejected during password login."""
        user_service = sso_app_manager.get_service("user")
        auth_service = sso_app_manager.get_service("auth")

        email = f"sso-nologin-{uuid.uuid4().hex[:8]}@test.com"

        async with sso_app_manager.database.get_session() as session:
            await user_service.create_user(
                session=session,
                email=email,
                password=None,
                language_id="en",
                send_verification_email=False,
            )
            await session.commit()

        async with sso_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await auth_service.authenticate_user(
                    login=email,
                    password="SomePassword123!",
                    session=session,
                )
            # Should fail with invalid credentials (same as unknown user for security)
            assert exc_info.value.status_code == 401
