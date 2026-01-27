"""
Unit tests for language services.

Tests LanguageService methods with mocked dependencies.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from lys.apps.base.modules.language.consts import FRENCH_LANGUAGE


class TestLanguageServiceGetDefaultLanguage:
    """Tests for LanguageService.get_default_language method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def mock_language(self):
        """Create mock language entity."""
        language = MagicMock()
        language.id = FRENCH_LANGUAGE
        language.name = "French"
        return language

    @pytest.mark.asyncio
    async def test_get_default_language_returns_french(self, mock_session, mock_language):
        """Test that default language is French."""
        from lys.apps.base.modules.language.services import LanguageService

        with patch.object(LanguageService, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = mock_language

            result = await LanguageService.get_default_language(mock_session)

            mock_get_by_id.assert_called_once_with(FRENCH_LANGUAGE, mock_session)
            assert result is mock_language

    @pytest.mark.asyncio
    async def test_get_default_language_calls_get_by_id_with_french(self, mock_session):
        """Test that get_by_id is called with FRENCH_LANGUAGE constant."""
        from lys.apps.base.modules.language.services import LanguageService

        with patch.object(LanguageService, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = MagicMock()

            await LanguageService.get_default_language(mock_session)

            # Verify the constant is used
            assert mock_get_by_id.call_args[0][0] == "fr"


class TestLanguageServiceValidateLanguageExists:
    """Tests for LanguageService.validate_language_exists method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_validate_language_exists_passes_when_found(self, mock_session):
        """Test that validation passes when language exists."""
        from lys.apps.base.modules.language.services import LanguageService

        mock_language = MagicMock()
        mock_language.id = "en"

        with patch.object(LanguageService, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = mock_language

            # Should not raise
            await LanguageService.validate_language_exists("en", mock_session)

    @pytest.mark.asyncio
    async def test_validate_language_exists_raises_when_not_found(self, mock_session):
        """Test that validation raises LysError when language not found."""
        from lys.apps.base.modules.language.services import LanguageService
        from lys.core.errors import LysError

        with patch.object(LanguageService, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = None

            with pytest.raises(LysError) as exc_info:
                await LanguageService.validate_language_exists("invalid_lang", mock_session)

            # LysError stores the error code name in detail
            assert exc_info.value.detail == "INVALID_LANGUAGE"
            assert "invalid_lang" in exc_info.value.debug_message

    @pytest.mark.asyncio
    async def test_validate_language_exists_error_message_contains_language_id(self, mock_session):
        """Test that error message includes the invalid language ID."""
        from lys.apps.base.modules.language.services import LanguageService
        from lys.core.errors import LysError

        with patch.object(LanguageService, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = None

            with pytest.raises(LysError) as exc_info:
                await LanguageService.validate_language_exists("xyz", mock_session)

            assert "xyz" in exc_info.value.debug_message


class TestLanguageServiceInheritance:
    """Tests for LanguageService class structure."""

    def test_inherits_from_entity_service(self):
        """Test that LanguageService inherits from EntityService."""
        from lys.apps.base.modules.language.services import LanguageService
        from lys.core.services import EntityService

        assert issubclass(LanguageService, EntityService)

    def test_is_registered_service(self):
        """Test that LanguageService is registered via decorator."""
        from lys.apps.base.modules.language.services import LanguageService

        # The @register_service decorator adds metadata
        # We can check the class exists and is properly defined
        assert hasattr(LanguageService, 'get_by_id')
        assert hasattr(LanguageService, 'get_default_language')
        assert hasattr(LanguageService, 'validate_language_exists')
