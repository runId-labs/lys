"""
Unit tests for language constants.

Tests that all language constants are properly defined.
"""

import pytest


class TestLanguageConstants:
    """Tests for language ID constants."""

    def test_french_language(self):
        """Test FRENCH_LANGUAGE is defined."""
        from lys.apps.base.modules.language.consts import FRENCH_LANGUAGE

        assert FRENCH_LANGUAGE == "fr"

    def test_english_language(self):
        """Test ENGLISH_LANGUAGE is defined."""
        from lys.apps.base.modules.language.consts import ENGLISH_LANGUAGE

        assert ENGLISH_LANGUAGE == "en"


class TestLanguageConstantsConsistency:
    """Tests for language constants consistency."""

    def test_all_languages_are_strings(self):
        """Test that all language IDs are strings."""
        from lys.apps.base.modules.language.consts import (
            FRENCH_LANGUAGE,
            ENGLISH_LANGUAGE,
        )

        assert isinstance(FRENCH_LANGUAGE, str)
        assert isinstance(ENGLISH_LANGUAGE, str)

    def test_language_ids_are_iso_639_1(self):
        """Test that language IDs follow ISO 639-1 format (2 lowercase letters)."""
        from lys.apps.base.modules.language.consts import (
            FRENCH_LANGUAGE,
            ENGLISH_LANGUAGE,
        )

        for lang in [FRENCH_LANGUAGE, ENGLISH_LANGUAGE]:
            assert len(lang) == 2, f"Language ID '{lang}' should be 2 characters"
            assert lang.islower(), f"Language ID '{lang}' should be lowercase"
            assert lang.isalpha(), f"Language ID '{lang}' should be alphabetic"

    def test_all_languages_are_unique(self):
        """Test that all language IDs have unique values."""
        from lys.apps.base.modules.language.consts import (
            FRENCH_LANGUAGE,
            ENGLISH_LANGUAGE,
        )

        languages = [FRENCH_LANGUAGE, ENGLISH_LANGUAGE]
        assert len(languages) == len(set(languages))
