"""
Unit tests for AI text improvement services logic.

Tests TextImprovementService.improve() method.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


class TestTextImprovementServiceImprove:
    """Tests for TextImprovementService.improve()."""

    def test_basic_improve_calls_ai_service(self):
        from lys.apps.ai.modules.text_improvement.services import TextImprovementService

        mock_ai_service = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "  Improved text  "
        mock_ai_service.chat_with_purpose = AsyncMock(return_value=mock_response)

        mock_app_manager = MagicMock()
        mock_app_manager.get_service.return_value = mock_ai_service

        with patch.object(TextImprovementService, "app_manager", mock_app_manager):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    TextImprovementService.improve("bad text")
                )
            finally:
                loop.close()

        assert result == "Improved text"
        mock_ai_service.chat_with_purpose.assert_called_once()
        call_args = mock_ai_service.chat_with_purpose.call_args
        messages = call_args.args[0]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "bad text" in messages[1]["content"]

    def test_improve_with_max_length(self):
        from lys.apps.ai.modules.text_improvement.services import TextImprovementService

        mock_ai_service = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Short text"
        mock_ai_service.chat_with_purpose = AsyncMock(return_value=mock_response)

        mock_app_manager = MagicMock()
        mock_app_manager.get_service.return_value = mock_ai_service

        with patch.object(TextImprovementService, "app_manager", mock_app_manager):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    TextImprovementService.improve("text", max_length=100)
                )
            finally:
                loop.close()

        messages = mock_ai_service.chat_with_purpose.call_args.args[0]
        system_prompt = messages[0]["content"]
        # 90% of 100 = 90
        assert "90" in system_prompt

    def test_improve_with_context(self):
        from lys.apps.ai.modules.text_improvement.services import TextImprovementService

        mock_ai_service = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Better text"
        mock_ai_service.chat_with_purpose = AsyncMock(return_value=mock_response)

        mock_app_manager = MagicMock()
        mock_app_manager.get_service.return_value = mock_ai_service

        with patch.object(TextImprovementService, "app_manager", mock_app_manager):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    TextImprovementService.improve("text", context="email subject")
                )
            finally:
                loop.close()

        messages = mock_ai_service.chat_with_purpose.call_args.args[0]
        user_msg = messages[1]["content"]
        assert "Context: email subject" in user_msg

    def test_improve_without_context(self):
        from lys.apps.ai.modules.text_improvement.services import TextImprovementService

        mock_ai_service = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Better text"
        mock_ai_service.chat_with_purpose = AsyncMock(return_value=mock_response)

        mock_app_manager = MagicMock()
        mock_app_manager.get_service.return_value = mock_ai_service

        with patch.object(TextImprovementService, "app_manager", mock_app_manager):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    TextImprovementService.improve("text")
                )
            finally:
                loop.close()

        messages = mock_ai_service.chat_with_purpose.call_args.args[0]
        user_msg = messages[1]["content"]
        assert "Context:" not in user_msg

    def test_improve_with_language(self):
        from lys.apps.ai.modules.text_improvement.services import TextImprovementService

        mock_ai_service = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Meilleur texte"
        mock_ai_service.chat_with_purpose = AsyncMock(return_value=mock_response)

        mock_app_manager = MagicMock()
        mock_app_manager.get_service.return_value = mock_ai_service

        with patch.object(TextImprovementService, "app_manager", mock_app_manager):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    TextImprovementService.improve("texte", language="fr")
                )
            finally:
                loop.close()

        messages = mock_ai_service.chat_with_purpose.call_args.args[0]
        user_msg = messages[1]["content"]
        assert "language: fr" in user_msg
