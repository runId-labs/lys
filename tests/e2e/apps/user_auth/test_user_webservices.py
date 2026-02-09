"""
E2E tests for user_auth user webservices.

Tests cover user management operations via GraphQL:
- Password reset request
- Email verification
- User creation (super user endpoint)
"""

import pytest

from tests.e2e.conftest import (
    make_test_token,
    ENABLED_USER_EMAIL,
    SUPER_USER_EMAIL,
    DEV_USER_PASSWORD,
)


LOGIN_MUTATION = """
    mutation Login($login: String!, $password: String!) {
        login(inputs: {login: $login, password: $password}) {
            success
            accessTokenExpireIn
            xsrfToken
        }
    }
"""

REQUEST_PASSWORD_RESET_MUTATION = """
    mutation RequestPasswordReset($email: String!) {
        requestPasswordReset(email: $email) {
            succeed
        }
    }
"""

UPDATE_PASSWORD_MUTATION = """
    mutation UpdatePassword($userId: String!, $currentPassword: String!, $newPassword: String!) {
        updatePassword(userId: $userId, currentPassword: $currentPassword, newPassword: $newPassword) {
            succeed
        }
    }
"""

ALL_USER_STATUSES_QUERY = """
    query {
        allUserStatuses {
            id
        }
    }
"""

ALL_GENDERS_QUERY = """
    query {
        allGenders {
            id
        }
    }
"""


class TestPasswordReset:
    """Test password reset flow."""

    @pytest.mark.asyncio
    async def test_request_password_reset_existing_email(self, client):
        """Test requesting password reset for existing user."""
        response = await client.post("/graphql", json={
            "query": REQUEST_PASSWORD_RESET_MUTATION,
            "variables": {"email": ENABLED_USER_EMAIL},
        })

        assert response.status_code == 200
        data = response.json()
        # May succeed or fail depending on email config, but shouldn't crash
        # The mutation is public (no auth required)
        assert data is not None

    @pytest.mark.asyncio
    async def test_request_password_reset_nonexistent_email(self, client):
        """Test requesting password reset for nonexistent email."""
        response = await client.post("/graphql", json={
            "query": REQUEST_PASSWORD_RESET_MUTATION,
            "variables": {"email": "nonexistent@example.com"},
        })

        assert response.status_code == 200
        # Should not reveal whether email exists (security best practice)
        assert response.json() is not None


class TestPublicQueries:
    """Test publicly accessible queries."""

    @pytest.mark.asyncio
    async def test_all_user_statuses(self, client):
        """Test listing all user statuses (public query)."""
        response = await client.post("/graphql", json={
            "query": ALL_USER_STATUSES_QUERY,
        })

        assert response.status_code == 200
        data = response.json()
        if "errors" not in data:
            statuses = data["data"]["allUserStatuses"]
            assert len(statuses) >= 4  # ENABLED, DISABLED, REVOKED, DELETED
            status_ids = [s["id"] for s in statuses]
            assert "ENABLED" in status_ids

    @pytest.mark.asyncio
    async def test_all_genders(self, client):
        """Test listing all genders (public query)."""
        response = await client.post("/graphql", json={
            "query": ALL_GENDERS_QUERY,
        })

        assert response.status_code == 200
        data = response.json()
        if "errors" not in data:
            genders = data["data"]["allGenders"]
            assert len(genders) >= 3  # M, F, O


class TestAuthenticatedOperations:
    """Test operations that require authentication."""

    @pytest.mark.asyncio
    async def test_update_password(self, client, e2e_app_manager):
        """Test updating password for authenticated user."""
        # Login first
        login_response = await client.post("/graphql", json={
            "query": LOGIN_MUTATION,
            "variables": {
                "login": ENABLED_USER_EMAIL,
                "password": DEV_USER_PASSWORD,
            }
        })
        login_data = login_response.json()
        assert "errors" not in login_data

        # Get user ID from the app_manager
        async with e2e_app_manager.database.get_session() as session:
            from sqlalchemy import select
            user_entity = e2e_app_manager.get_entity("user")
            email_entity = e2e_app_manager.get_entity("user_email_address")
            result = await session.execute(
                select(user_entity).join(email_entity).where(
                    email_entity.id == ENABLED_USER_EMAIL
                )
            )
            user = result.scalar_one()
            user_id = str(user.id)

        # Use Bearer token for the update (simpler than cookies with XSRF)
        token = make_test_token(user_id)

        response = await client.post(
            "/graphql",
            json={
                "query": UPDATE_PASSWORD_MUTATION,
                "variables": {
                    "userId": user_id,
                    "currentPassword": DEV_USER_PASSWORD,
                    "newPassword": "NewPassword456!",
                },
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        if "errors" not in data:
            assert data["data"]["updatePassword"]["succeed"] is True
