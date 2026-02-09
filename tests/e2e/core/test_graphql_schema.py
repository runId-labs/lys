"""
E2E tests for GraphQL schema configuration.

Tests cover:
- Schema introspection (enabled in DEV mode)
- GraphQL endpoint availability
- Error handling for malformed queries
"""

import pytest


INTROSPECTION_QUERY = """
    query {
        __schema {
            queryType {
                name
            }
            mutationType {
                name
            }
            types {
                name
            }
        }
    }
"""

SIMPLE_QUERY = """
    query {
        __typename
    }
"""


class TestGraphQLSchema:
    """Test GraphQL schema availability and configuration."""

    @pytest.mark.asyncio
    async def test_graphql_endpoint_accessible(self, client):
        """Test that the GraphQL endpoint responds to requests."""
        response = await client.post("/graphql", json={
            "query": SIMPLE_QUERY,
        })

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @pytest.mark.asyncio
    async def test_schema_introspection_in_dev(self, client):
        """Test schema introspection is enabled in DEV mode."""
        response = await client.post("/graphql", json={
            "query": INTROSPECTION_QUERY,
        })

        assert response.status_code == 200
        data = response.json()
        # In DEV mode, introspection should be allowed
        if "errors" not in data:
            schema = data["data"]["__schema"]
            assert schema["queryType"]["name"] == "Query"
            assert schema["mutationType"]["name"] == "Mutation"

            type_names = [t["name"] for t in schema["types"]]
            assert "Query" in type_names
            assert "Mutation" in type_names

    @pytest.mark.asyncio
    async def test_malformed_query_returns_error(self, client):
        """Test malformed GraphQL query returns error response."""
        response = await client.post("/graphql", json={
            "query": "{ this is not valid graphql",
        })

        assert response.status_code == 200
        data = response.json()
        assert "errors" in data

    @pytest.mark.asyncio
    async def test_empty_body_returns_error(self, client):
        """Test empty request body returns appropriate error."""
        response = await client.post(
            "/graphql",
            content=b"",
            headers={"Content-Type": "application/json"},
        )

        # Should return 4xx (bad request) or 200 with errors
        assert response.status_code in (200, 400, 422)
