"""
Authentication utilities for service-to-service communication.
"""
from datetime import timedelta
from typing import Dict, Any
from uuid import uuid4

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from lys.core.utils.datetime import now_utc


class ServiceAuthUtils:
    """Utility class for service-to-service JWT operations."""

    ALGORITHM = "HS256"
    TOKEN_TYPE = "service"
    INTERNAL_AUDIENCE = "lys-internal"

    def __init__(self, secret_key: str, instance_id: str = None):
        """
        Initialize AuthUtils with a secret key.

        Args:
            secret_key: Secret key for JWT encoding/decoding
            instance_id: Unique identifier for this service instance.
                Auto-generated if not provided. Included in tokens
                for tracing which instance made each call.
        """
        self.secret_key = secret_key
        self.instance_id = instance_id or str(uuid4())[:8]

    def generate_token(self, service_name: str, expiration_minutes: int = 1) -> str:
        """
        Generate a JWT token for service-to-service communication.

        Args:
            service_name: Name of the calling service
            expiration_minutes: Token expiration time in minutes (default: 1)

        Returns:
            Encoded JWT token string
        """
        now = now_utc()
        payload = {
            "type": self.TOKEN_TYPE,
            "service_name": service_name,
            "instance_id": self.instance_id,
            "iat": now,
            "exp": now + timedelta(minutes=expiration_minutes),
            "iss": service_name,
            "aud": self.INTERNAL_AUDIENCE,
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.ALGORITHM)

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate a service JWT token.

        Args:
            token: JWT token string to decode

        Returns:
            Dict containing decoded JWT claims

        Raises:
            ExpiredSignatureError: Token has expired
            InvalidTokenError: Token is invalid or not a service token
        """
        payload = jwt.decode(
            token,
            self.secret_key,
            algorithms=[self.ALGORITHM],
            audience=self.INTERNAL_AUDIENCE,
            options={"verify_aud": True},
        )

        if payload.get("type") != self.TOKEN_TYPE:
            raise InvalidTokenError("Not a service token")

        return payload