"""
Unit tests for lys.apps.ai.utils.search.

Tests resolve_text_search_config's language-detection thresholds and fallbacks.
"""

from unittest.mock import patch

from lys.apps.ai.utils.search import (
    DEFAULT_TEXT_SEARCH_CONFIG,
    MIN_CHARS_FOR_DETECTION,
    SEARCH_CONVERSATION_TOOL,
    resolve_text_search_config,
)


class TestResolveTextSearchConfig:
    """Tests for resolve_text_search_config."""

    def test_none_content_falls_back_to_default(self):
        assert resolve_text_search_config(None) == DEFAULT_TEXT_SEARCH_CONFIG

    def test_empty_content_falls_back_to_default(self):
        assert resolve_text_search_config("") == DEFAULT_TEXT_SEARCH_CONFIG

    def test_content_below_min_chars_falls_back_to_default(self):
        short = "ok" * (MIN_CHARS_FOR_DETECTION // 2 - 1)
        assert len(short) < MIN_CHARS_FOR_DETECTION
        assert resolve_text_search_config(short) == DEFAULT_TEXT_SEARCH_CONFIG

    def test_detects_french(self):
        text = (
            "Bonjour, pourriez-vous me faire un point complet sur la tresorerie "
            "du dernier trimestre et les echeances a venir ?"
        )
        assert len(text) >= MIN_CHARS_FOR_DETECTION
        assert resolve_text_search_config(text) == "french"

    def test_detects_english(self):
        text = (
            "Hello, could you please give me a complete summary of last quarter's "
            "revenue and the upcoming payment deadlines?"
        )
        assert len(text) >= MIN_CHARS_FOR_DETECTION
        assert resolve_text_search_config(text) == "english"

    def test_unsupported_language_falls_back_to_default(self):
        text = "a" * MIN_CHARS_FOR_DETECTION
        with patch("lys.apps.ai.utils.search.detect", return_value="zz"):
            assert resolve_text_search_config(text) == DEFAULT_TEXT_SEARCH_CONFIG

    def test_regional_code_maps_to_base_language(self):
        text = "a" * MIN_CHARS_FOR_DETECTION
        with patch("lys.apps.ai.utils.search.detect", return_value="pt-br"):
            assert resolve_text_search_config(text) == "portuguese"

    def test_detector_failure_falls_back_to_default(self):
        from langdetect import LangDetectException

        text = "a" * MIN_CHARS_FOR_DETECTION
        with patch(
            "lys.apps.ai.utils.search.detect",
            side_effect=LangDetectException(0, "no features in text"),
        ):
            assert resolve_text_search_config(text) == DEFAULT_TEXT_SEARCH_CONFIG

    def test_never_raises_on_garbage_input(self):
        text = "!@#$%^&*()" * 10
        # Must not raise, whatever the detector makes of it.
        resolve_text_search_config(text)


class TestSearchConversationTool:
    """Tests for the SEARCH_CONVERSATION_TOOL definition."""

    def test_is_a_function_tool_named_search_conversation(self):
        assert SEARCH_CONVERSATION_TOOL["type"] == "function"
        assert SEARCH_CONVERSATION_TOOL["function"]["name"] == "search_conversation"

    def test_requires_a_query_argument(self):
        parameters = SEARCH_CONVERSATION_TOOL["function"]["parameters"]
        assert parameters["required"] == ["query"]
        assert "query" in parameters["properties"]
