import logging
import os
from typing import Dict

import bcrypt
import jwt

from lys.apps.user_auth.consts import AUTH_PLUGIN_KEY
from lys.core.utils.manager import AppManagerCallerMixin


class AuthUtils(AppManagerCallerMixin):
    ALLOWED_ALGORITHMS = ["HS256", "HS384", "HS512"]
    def __init__(self):
        app_settings = self.app_manager.settings
        self.secret_key = app_settings.secret_key
        self.config = app_settings.get_plugin_config(AUTH_PLUGIN_KEY)
        self._validate_auth_config(self.config)

    def _validate_auth_config(self, auth_config):
        """Validate authentication configuration at startup."""
        if not auth_config:
            logging.warning("No auth configuration found, using defaults")
            return

        algorithm = auth_config.get("encryption_algorithm", "HS256")
        if algorithm not in self.ALLOWED_ALGORITHMS:
            raise ValueError(f"Unsupported JWT algorithm: {algorithm}. Allowed: {self.ALLOWED_ALGORITHMS}")

        if not self.secret_key:
            raise ValueError("JWT secret_key is required for authentication")

        logging.info(f"Auth middleware initialized with algorithm: {algorithm}")

    @staticmethod
    def hash_password(plain_text_password: str):
        bytes_ = plain_text_password.encode('utf-8')
        salt = bcrypt.gensalt()
        return str(bcrypt.hashpw(bytes_, salt), encoding='utf-8')

    @staticmethod
    async def generate_xsrf_token():
        return os.urandom(64).hex().encode("ascii")


    async def encode(self, claims: Dict) -> str:
        """
        Encode user information to token
        """
        return jwt.encode(
            claims,
            self.secret_key,
            algorithm=self.config.get("encryption_algorithm", "HS256")
        )

    async def decode(self, access_token: str) -> Dict:
        """
        Decode JWT token with proper error handling

        Args:
            access_token: JWT token string to decode

        Returns:
            Dict: Decoded JWT claims

        Raises:
            ExpiredSignatureError: Token has expired
            InvalidTokenError: Token is invalid
            DecodeError: Token cannot be decoded
        """
        algorithm = self.config.get("encryption_algorithm", "HS256")

        return jwt.decode(
            access_token,
            self.secret_key,
            algorithms=[algorithm]  # Use list for security (explicit algorithm)
        )
