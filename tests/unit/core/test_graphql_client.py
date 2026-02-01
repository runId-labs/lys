"""
Unit tests for GraphQL client.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import httpx

from lys.core.graphql.client import GraphQLClient, fetch_graphql


class TestFetchGraphQL:
    """Tests for fetch_graphql function."""

    @pytest.mark.asyncio
    async def test_fetch_graphql_success(self):
        """Test successful GraphQL fetch."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"data": {"users": [{"id": "1"}]}}

        with patch("lys.core.graphql.client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            with patch("lys.core.graphql.client.AuthUtils") as MockAuth:
                mock_auth = MagicMock()
                mock_auth.generate_token.return_value = "test-token"
                MockAuth.return_value = mock_auth

                result = await fetch_graphql(
                    url="http://gateway/graphql",
                    query="query { users { id } }",
                    secret_key="secret",
                    service_name="test-service",
                )

        assert result == {"data": {"users": [{"id": "1"}]}}
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_graphql_with_variables(self):
        """Test GraphQL fetch with variables."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"data": {"user": {"id": "1"}}}

        with patch("lys.core.graphql.client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            with patch("lys.core.graphql.client.AuthUtils") as MockAuth:
                mock_auth = MagicMock()
                mock_auth.generate_token.return_value = "test-token"
                MockAuth.return_value = mock_auth

                result = await fetch_graphql(
                    url="http://gateway/graphql",
                    query="query GetUser($id: ID!) { user(id: $id) { id } }",
                    variables={"id": "123"},
                    secret_key="secret",
                    service_name="test-service",
                )

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["variables"] == {"id": "123"}

    @pytest.mark.asyncio
    async def test_fetch_graphql_missing_secret_key(self):
        """Test that missing secret_key raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await fetch_graphql(
                url="http://gateway/graphql",
                query="query { users { id } }",
                secret_key=None,
                service_name="test-service",
            )

        assert "secret_key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_graphql_missing_service_name(self):
        """Test that missing service_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await fetch_graphql(
                url="http://gateway/graphql",
                query="query { users { id } }",
                secret_key="secret",
                service_name=None,
            )

        assert "service_name" in str(exc_info.value)


class TestGraphQLClient:
    """Tests for GraphQLClient class."""

    @pytest.fixture
    def client(self):
        """Create a GraphQLClient instance for testing."""
        with patch("lys.core.graphql.client.AuthUtils") as MockAuth:
            mock_auth = MagicMock()
            mock_auth.generate_token.return_value = "test-token"
            MockAuth.return_value = mock_auth

            client = GraphQLClient(
                url="http://gateway/graphql",
                secret_key="secret",
                service_name="test-service",
                timeout=30,
            )
            client._auth_utils = mock_auth
            return client

    def test_init_stores_config(self, client):
        """Test that initialization stores configuration."""
        assert client.url == "http://gateway/graphql"
        assert client.timeout == 30
        # Internal attributes (not public API)
        assert client._service_name == "test-service"
        assert client._auth_utils is not None

    def test_get_headers_includes_token(self, client):
        """Test that headers include service JWT token."""
        headers = client._get_headers()

        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Service test-token"

    @pytest.mark.asyncio
    async def test_execute_success(self, client):
        """Test successful execute."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"data": {"users": []}}

        with patch("lys.core.graphql.client.httpx.AsyncClient") as MockClient:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_http_client

            result = await client.execute("query { users { id } }")

        assert result == {"data": {"users": []}}

    @pytest.mark.asyncio
    async def test_execute_with_variables(self, client):
        """Test execute with variables."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"data": {"user": {"id": "1"}}}

        with patch("lys.core.graphql.client.httpx.AsyncClient") as MockClient:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_http_client

            result = await client.execute(
                "query GetUser($id: ID!) { user(id: $id) { id } }",
                variables={"id": "123"},
            )

        call_args = mock_http_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["variables"] == {"id": "123"}

    @pytest.mark.asyncio
    async def test_query_returns_data_directly(self, client):
        """Test that query returns data directly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"data": {"users": [{"id": "1"}]}}

        with patch("lys.core.graphql.client.httpx.AsyncClient") as MockClient:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_http_client

            result = await client.query("query { users { id } }")

        assert result == {"users": [{"id": "1"}]}

    @pytest.mark.asyncio
    async def test_query_raises_on_errors(self, client):
        """Test that query raises ValueError on GraphQL errors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {
            "data": None,
            "errors": [{"message": "User not found"}],
        }

        with patch("lys.core.graphql.client.httpx.AsyncClient") as MockClient:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_http_client

            with pytest.raises(ValueError) as exc_info:
                await client.query("query { user(id: 999) { id } }")

        assert "User not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mutate_is_alias_for_query(self, client):
        """Test that mutate works the same as query."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"data": {"createUser": {"id": "1"}}}

        with patch("lys.core.graphql.client.httpx.AsyncClient") as MockClient:
            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_http_client

            result = await client.mutate(
                "mutation CreateUser($email: String!) { createUser(email: $email) { id } }",
                variables={"email": "test@example.com"},
            )

        assert result == {"createUser": {"id": "1"}}

    @pytest.mark.asyncio
    async def test_execute_http_error(self, client):
        """Test that HTTP errors propagate."""
        with patch("lys.core.graphql.client.httpx.AsyncClient") as MockClient:
            mock_http_client = AsyncMock()
            mock_http_client.post.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
            MockClient.return_value.__aenter__.return_value = mock_http_client

            with pytest.raises(httpx.HTTPStatusError):
                await client.execute("query { users { id } }")
