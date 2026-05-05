"""
Opaque access token store backed by Redis.

Stores user access claims server-side keyed by an opaque UUID. The cookie
sent to the browser carries only that UUID (~36 bytes), so the cookie size
no longer scales with the user's permission breadth — fixes the silent
cookie drop that occurs when JWT-based access tokens exceed the RFC 6265
4096-byte per-cookie limit.

Design notes:
- The store is a thin wrapper over PubSubManager's key/value API
  (set_key / get_key / delete_key); no separate Redis client is opened.
- Keys are namespaced under the ``lys:access_token:`` prefix.
- Values are JSON-serialized claims dicts (the same dict that used to be
  embedded in the JWT payload — sub, is_super_user, webservices, exp,
  xsrf_token, plus whatever subclasses of ``AuthService.generate_access_claims``
  add via ``super()`` chain: organizations, subscriptions, …).
- TTL is set at write time and equal to the access token lifetime
  (``access_token_expire_minutes``), so the store mirrors the previous
  ``exp`` behaviour: a cookie that "expires" simply has no entry in Redis
  any more and the middleware reads ``None``.
"""
import json
import logging
import uuid
from typing import Optional

from lys.core.managers.pubsub import PubSubManager

logger = logging.getLogger(__name__)

ACCESS_TOKEN_KEY_PREFIX = "lys:access_token:"


class AccessTokenStore:
    """
    Server-side store for user access token claims.

    Each instance binds to the PubSubManager from the running AppManager.
    The middleware constructs one per request via
    ``request.app.state.app_manager.pubsub`` (cf. ``UserAuthMiddleware``);
    services construct one via ``cls.app_manager.pubsub``.

    No locking is required — Redis SET/GET/DEL are atomic and we never
    read-modify-write a single entry.
    """

    def __init__(self, pubsub: PubSubManager):
        if pubsub is None:
            raise RuntimeError(
                "AccessTokenStore requires a PubSubManager instance. "
                "Ensure the 'pubsub' plugin is configured in settings.py."
            )
        self._pubsub = pubsub

    @staticmethod
    def _key(token_id: str) -> str:
        return f"{ACCESS_TOKEN_KEY_PREFIX}{token_id}"

    async def create(self, claims: dict, ttl_seconds: int) -> str:
        """
        Store ``claims`` under a new UUID and return that UUID.

        Args:
            claims: Claims dict produced by ``AuthService.generate_access_claims``
                + ``exp`` and ``xsrf_token`` added by ``generate_access_token``.
            ttl_seconds: Time-to-live for the stored entry. Should match
                ``access_token_expire_minutes`` (in seconds) so that the
                store entry disappears at the same moment the previous JWT
                would have expired.

        Returns:
            Opaque token id (UUID v4 string, ~36 chars). This is what the
            ``access_token`` cookie carries to the browser.

        Raises:
            RuntimeError: If the underlying Redis write fails (PubSub
                manager not initialised). Caller should surface this as a
                500 — login cannot succeed without a valid store.
        """
        token_id = str(uuid.uuid4())
        ok = await self._pubsub.set_key(
            self._key(token_id),
            json.dumps(claims),
            ttl_seconds=ttl_seconds,
        )
        if not ok:
            raise RuntimeError(
                "Failed to write access token to Redis (PubSubManager "
                "returned False). Cannot issue an access token."
            )
        return token_id

    async def get(self, token_id: str) -> Optional[dict]:
        """
        Look up claims by token id.

        Args:
            token_id: Opaque UUID extracted from the ``access_token`` cookie
                or from an ``Authorization: Bearer`` header.

        Returns:
            Claims dict, or None if the entry does not exist (expired,
            revoked, or never issued). The middleware treats None as "no
            authenticated user" — same behaviour as a previously expired JWT.
        """
        if not token_id:
            return None
        raw = await self._pubsub.get_key(self._key(token_id))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Corrupted access token entry for id=%s, deleting", token_id)
            await self._pubsub.delete_key(self._key(token_id))
            return None

    async def delete(self, token_id: str) -> bool:
        """
        Revoke a token immediately (logout, refresh-driven rotation).

        Args:
            token_id: Opaque UUID to invalidate.

        Returns:
            True if the entry existed and was deleted; False otherwise.
            The caller should not branch on this — a no-op delete is
            harmless (e.g. logout after the entry already TTL'd out).
        """
        if not token_id:
            return False
        return await self._pubsub.delete_key(self._key(token_id))
