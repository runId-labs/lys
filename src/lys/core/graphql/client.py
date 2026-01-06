"""
GraphQL client for service-to-service communication.
"""

import logging
from typing import Dict, Any, Optional

import httpx

from lys.core.utils.auth import AuthUtils

logger = logging.getLogger(__name__)


async def fetch_graphql(
    url: str,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    secret_key: str = None,
    service_name: str = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Execute a GraphQL query/mutation with automatic service authentication.

    Generates a service JWT token automatically for inter-service calls.

    Args:
        url: GraphQL endpoint URL
        query: GraphQL query or mutation string
        variables: Optional variables for the query
        secret_key: Secret key for JWT generation
        service_name: Name of the calling service
        timeout: Request timeout in seconds

    Returns:
        Dict with 'data' and optionally 'errors' keys

    Raises:
        httpx.HTTPError: On network/HTTP errors
        ValueError: If authentication params are missing
    """
    if not secret_key or not service_name:
        raise ValueError("secret_key and service_name are required for inter-service calls")

    # Generate service JWT token
    auth_utils = AuthUtils(secret_key)
    token = auth_utils.generate_token(service_name)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Service {token}",
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


class GraphQLClient:
    """
    GraphQL client for inter-service communication.

    Automatically handles service JWT authentication.
    """

    def __init__(
        self,
        url: str,
        secret_key: str,
        service_name: str,
        timeout: int = 30,
    ):
        """
        Initialize GraphQL client.

        Args:
            url: GraphQL endpoint URL
            secret_key: Secret key for JWT generation
            service_name: Name of the calling service
            timeout: Request timeout in seconds
        """
        self.url = url
        self.secret_key = secret_key
        self.service_name = service_name
        self.timeout = timeout
        self._auth_utils = AuthUtils(secret_key)

    def _get_headers(self) -> Dict[str, str]:
        """Generate headers with fresh JWT token."""
        token = self._auth_utils.generate_token(self.service_name)
        return {
            "Content-Type": "application/json",
            "Authorization": f"Service {token}",
        }

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query/mutation.

        Args:
            query: GraphQL query or mutation string
            variables: Optional variables for the query

        Returns:
            Dict with 'data' and optionally 'errors' keys

        Raises:
            httpx.HTTPError: On network/HTTP errors
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()

    async def query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a query and return data directly.

        Args:
            query: GraphQL query string
            variables: Optional variables

        Returns:
            Data from the response (raises on errors)

        Raises:
            ValueError: If GraphQL returned errors
        """
        result = await self.execute(query, variables)

        if "errors" in result:
            errors = result["errors"]
            messages = [e.get("message", str(e)) for e in errors]
            raise ValueError(f"GraphQL errors: {'; '.join(messages)}")

        return result.get("data")

    async def mutate(
        self,
        mutation: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a mutation and return data directly.

        Alias for query() for semantic clarity.

        Args:
            mutation: GraphQL mutation string
            variables: Optional variables

        Returns:
            Data from the response
        """
        return await self.query(mutation, variables)