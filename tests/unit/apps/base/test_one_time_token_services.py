"""
Unit tests for one-time token services.

Tests OneTimeTokenService methods with mocked dependencies.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

from lys.apps.base.modules.one_time_token.consts import USED_TOKEN_STATUS, REVOKED_TOKEN_STATUS


class TestOneTimeTokenServiceGetValidToken:
    """Tests for OneTimeTokenService.get_valid_token method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def valid_token(self):
        """Create a valid token mock."""
        token = MagicMock()
        token.is_valid = True
        token.id = "token-123"
        return token

    @pytest.fixture
    def invalid_token(self):
        """Create an invalid token mock."""
        token = MagicMock()
        token.is_valid = False
        token.id = "token-456"
        return token

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_token_when_valid(self, mock_session, valid_token):
        """Test that valid token is returned."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        # Create concrete implementation for testing
        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                return valid_token

        result = await TestTokenService.get_valid_token("token-123", mock_session)

        assert result is valid_token

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none_when_not_found(self, mock_session):
        """Test that None is returned when token not found."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                return None

        result = await TestTokenService.get_valid_token("nonexistent", mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none_when_invalid(self, mock_session, invalid_token):
        """Test that None is returned when token is invalid."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                return invalid_token

        result = await TestTokenService.get_valid_token("token-456", mock_session)

        assert result is None


class TestOneTimeTokenServiceMarkAsUsed:
    """Tests for OneTimeTokenService.mark_as_used method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def token(self):
        """Create a token mock."""
        token = MagicMock()
        token.status_id = "pending"
        token.used_at = None
        return token

    @pytest.mark.asyncio
    async def test_mark_as_used_sets_status(self, mock_session, token):
        """Test that status is set to USED."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                raise NotImplementedError

        await TestTokenService.mark_as_used(token, mock_session)

        assert token.status_id == USED_TOKEN_STATUS

    @pytest.mark.asyncio
    async def test_mark_as_used_sets_used_at(self, mock_session, token):
        """Test that used_at timestamp is set."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                raise NotImplementedError

        await TestTokenService.mark_as_used(token, mock_session)

        assert token.used_at is not None

    @pytest.mark.asyncio
    async def test_mark_as_used_flushes_session(self, mock_session, token):
        """Test that session is flushed."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                raise NotImplementedError

        await TestTokenService.mark_as_used(token, mock_session)

        mock_session.flush.assert_called_once()


class TestOneTimeTokenServiceRevokeToken:
    """Tests for OneTimeTokenService.revoke_token method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def token(self):
        """Create a token mock."""
        token = MagicMock()
        token.status_id = "pending"
        return token

    @pytest.mark.asyncio
    async def test_revoke_token_sets_status(self, mock_session, token):
        """Test that status is set to REVOKED."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                raise NotImplementedError

        await TestTokenService.revoke_token(token, mock_session)

        assert token.status_id == REVOKED_TOKEN_STATUS

    @pytest.mark.asyncio
    async def test_revoke_token_flushes_session(self, mock_session, token):
        """Test that session is flushed."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                raise NotImplementedError

        await TestTokenService.revoke_token(token, mock_session)

        mock_session.flush.assert_called_once()


class TestOneTimeTokenServiceUseToken:
    """Tests for OneTimeTokenService.use_token method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def valid_token(self):
        """Create a valid token mock."""
        token = MagicMock()
        token.is_valid = True
        token.id = "token-123"
        token.status_id = "pending"
        token.used_at = None
        return token

    @pytest.mark.asyncio
    async def test_use_token_returns_token_and_marks_used(self, mock_session, valid_token):
        """Test that valid token is returned and marked as used."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                return valid_token

        result = await TestTokenService.use_token("token-123", mock_session)

        assert result is valid_token
        assert result.status_id == USED_TOKEN_STATUS
        assert result.used_at is not None

    @pytest.mark.asyncio
    async def test_use_token_returns_none_when_invalid(self, mock_session):
        """Test that None is returned when token is invalid."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        invalid_token = MagicMock()
        invalid_token.is_valid = False

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                return invalid_token

        result = await TestTokenService.use_token("token-456", mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_use_token_returns_none_when_not_found(self, mock_session):
        """Test that None is returned when token not found."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenService

        class TestTokenService(OneTimeTokenService):
            @classmethod
            async def get_by_id(cls, entity_id, session):
                return None

        result = await TestTokenService.use_token("nonexistent", mock_session)

        assert result is None


class TestOneTimeTokenStatusService:
    """Tests for OneTimeTokenStatusService."""

    def test_service_is_entity_service(self):
        """Test that service inherits from EntityService."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenStatusService
        from lys.core.services import EntityService

        assert issubclass(OneTimeTokenStatusService, EntityService)


class TestOneTimeTokenTypeService:
    """Tests for OneTimeTokenTypeService."""

    def test_service_is_entity_service(self):
        """Test that service inherits from EntityService."""
        from lys.apps.base.modules.one_time_token.services import OneTimeTokenTypeService
        from lys.core.services import EntityService

        assert issubclass(OneTimeTokenTypeService, EntityService)
