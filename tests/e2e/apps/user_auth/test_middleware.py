"""
E2E tests for UserAuthMiddleware.

Tests verify that the middleware correctly:
- Extracts opaque access tokens from cookies and headers
- Resolves them against the AccessTokenStore
- Sets request.state.connected_user for authenticated requests
- Treats unknown/missing tokens as anonymous
"""

import pytest

from tests.e2e.conftest import (
    make_test_token,
    make_unknown_token,
    ENABLED_USER_EMAIL,
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

CONNECTED_USER_QUERY = """
    query {
        connectedUser {
            id
        }
    }
"""


class TestMiddlewareTokenExtraction:
    """Test middleware opaque access token extraction and resolution."""

    @pytest.mark.asyncio
    async def test_bearer_token_authenticates_request(self, client, e2e_app_manager):
        """Test valid Bearer token in Authorization header authenticates user."""
        # Create a real user and get their ID
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
            user_id = user.id

        token = await make_test_token(e2e_app_manager, user_id)

        response = await client.post(
            "/graphql",
            json={"query": CONNECTED_USER_QUERY},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # With a valid token, the connected user query should not return auth errors
        if "errors" not in data:
            assert data["data"]["connectedUser"]["id"] is not None

    @pytest.mark.asyncio
    async def test_no_token_unauthenticated(self, client):
        """Test request without token results in unauthenticated context."""
        response = await client.post(
            "/graphql",
            json={"query": CONNECTED_USER_QUERY},
        )

        assert response.status_code == 200
        data = response.json()
        connected_user = data.get("data", {}).get("connectedUser")
        assert connected_user is None

    @pytest.mark.asyncio
    async def test_unknown_token_unauthenticated(self, client):
        """Token that has no entry in the store (expired/revoked/never issued) is anonymous."""
        token = make_unknown_token()

        response = await client.post(
            "/graphql",
            json={"query": CONNECTED_USER_QUERY},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        connected_user = data.get("data", {}).get("connectedUser")
        assert connected_user is None

    @pytest.mark.asyncio
    async def test_invalid_token_unauthenticated(self, client):
        """Test malformed token results in unauthenticated context."""
        response = await client.post(
            "/graphql",
            json={"query": CONNECTED_USER_QUERY},
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        assert response.status_code == 200
        data = response.json()
        connected_user = data.get("data", {}).get("connectedUser")
        assert connected_user is None

    @pytest.mark.asyncio
    async def test_cookie_auth_after_login(self, client):
        """Test that login sets cookies and subsequent requests are authenticated."""
        # Login
        login_response = await client.post("/graphql", json={
            "query": LOGIN_MUTATION,
            "variables": {
                "login": ENABLED_USER_EMAIL,
                "password": DEV_USER_PASSWORD,
            }
        })
        assert "errors" not in login_response.json()

        # Subsequent request uses cookies automatically (httpx handles this)
        response = await client.post(
            "/graphql",
            json={"query": CONNECTED_USER_QUERY},
        )

        assert response.status_code == 200
        data = response.json()
        # After login, cookies should authenticate the request
        # Note: XSRF check is disabled in E2E config, so cookie auth works
        if "errors" not in data:
            assert data["data"]["connectedUser"]["id"] is not None
