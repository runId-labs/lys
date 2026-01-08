"""
GraphQL client for service-to-service communication.
"""

import base64
import logging
from typing import Dict, Any, Optional

import httpx

from lys.core.utils.auth import AuthUtils

logger = logging.getLogger(__name__)


def build_global_id(type_name: str, node_id: str) -> str:
    """
    Build a Relay GlobalID string.

    Args:
        type_name: The GraphQL node type name (e.g., "CompanyNode", "UserNode")
        node_id: The actual UUID/ID string

    Returns:
        Base64-encoded GlobalID string (format: "TypeName:uuid" encoded)
    """
    raw = f"{type_name}:{node_id}"
    return base64.b64encode(raw.encode()).decode()


def extract_id_from_global_id(global_id: str) -> str:
    """
    Extract the actual ID from a Relay GlobalID.

    Args:
        global_id: Base64-encoded GlobalID string

    Returns:
        The actual UUID/ID string
    """
    decoded = base64.b64decode(global_id).decode()
    parts = decoded.split(":", 1)
    return parts[1] if len(parts) > 1 else decoded


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

    Supports two authentication modes:
    - Service JWT: For inter-service calls (requires secret_key and service_name)
    - Bearer JWT: For user-authenticated calls (requires bearer_token)
    """

    def __init__(
        self,
        url: str,
        secret_key: Optional[str] = None,
        service_name: Optional[str] = None,
        bearer_token: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize GraphQL client.

        Either provide (secret_key + service_name) for Service auth,
        or bearer_token for Bearer auth.

        Args:
            url: GraphQL endpoint URL
            secret_key: Secret key for JWT generation (Service auth)
            service_name: Name of the calling service (Service auth)
            bearer_token: User JWT token (Bearer auth)
            timeout: Request timeout in seconds

        Raises:
            ValueError: If neither Service auth params nor bearer_token are provided
        """
        self.url = url
        self.timeout = timeout
        self._bearer_token = bearer_token

        # Validate auth configuration
        has_service_auth = secret_key is not None and service_name is not None
        has_bearer_auth = bearer_token is not None

        if not has_service_auth and not has_bearer_auth:
            raise ValueError(
                "Either (secret_key + service_name) for Service auth "
                "or bearer_token for Bearer auth must be provided"
            )

        # Store service auth params if provided
        self._service_name = service_name
        self._auth_utils = AuthUtils(secret_key) if secret_key else None

    def _get_headers(self) -> Dict[str, str]:
        """Generate headers with appropriate authentication."""
        headers = {"Content-Type": "application/json"}

        if self._bearer_token:
            # Use Bearer auth (user JWT)
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        elif self._auth_utils and self._service_name:
            # Use Service auth (inter-service JWT)
            token = self._auth_utils.generate_token(self._service_name)
            headers["Authorization"] = f"Service {token}"
        else:
            logger.warning("[GraphQLClient] No authentication configured!")

        return headers

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

        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.url,
                json=payload,
                headers=headers,
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

    # -------------------------------------------------------------------------
    # Synchronous methods (for Celery workers)
    # -------------------------------------------------------------------------

    def execute_sync(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query/mutation synchronously.

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

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()

    def query_sync(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a query synchronously and return data directly.

        Args:
            query: GraphQL query string
            variables: Optional variables

        Returns:
            Data from the response (raises on errors)

        Raises:
            ValueError: If GraphQL returned errors
        """
        result = self.execute_sync(query, variables)

        if "errors" in result:
            errors = result["errors"]
            messages = [e.get("message", str(e)) for e in errors]
            raise ValueError(f"GraphQL errors: {'; '.join(messages)}")

        return result.get("data")

    def mutate_sync(
        self,
        mutation: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a mutation synchronously and return data directly.

        Args:
            mutation: GraphQL mutation string
            variables: Optional variables

        Returns:
            Data from the response
        """
        return self.query_sync(mutation, variables)