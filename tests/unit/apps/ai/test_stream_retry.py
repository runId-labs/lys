"""
A chat stream refused before its first chunk: retried (a rate limit with growing waits or
the provider's Retry-After, a server error), then the endpoint's fallback. Once a chunk was
yielded nothing is retried: the caller has shown it.
"""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from lys.apps.ai.modules.core.services import AIService
from lys.apps.ai.utils.providers.abstracts import AIStreamChunk
from lys.apps.ai.utils.providers.config import AIEndpointConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
    retry_after_seconds,
)


class _Provider:
    """A provider whose streams play the given scripts: an exception, or chunks then maybe an exception."""

    def __init__(self, *scripts):
        self.scripts = list(scripts)
        self.calls = 0

    async def chat_stream(self, messages, config, tools=None, tool_calls_allowed=True):
        self.calls += 1
        script = self.scripts.pop(0)
        if isinstance(script, Exception):
            raise script
        for item in script:
            if isinstance(item, Exception):
                raise item
            yield AIStreamChunk(content=item)


async def _stream(primary, fallback=None):
    endpoint = AIEndpointConfig(provider="primary", model="m", fallback=(
        AIEndpointConfig(provider="fallback", model="f") if fallback else None
    ))
    providers = {"primary": primary, "fallback": fallback}
    sleep = AsyncMock()
    with patch.object(AIService, "get_endpoint", return_value=endpoint), \
            patch.object(AIService, "get_provider", side_effect=lambda name: providers[name]), \
            patch("lys.apps.ai.modules.core.services.asyncio.sleep", sleep):
        chunks = [chunk.content async for chunk in AIService.chat_stream_with_purpose([], "chatbot")]
    return chunks, sleep


class TestStreamRetry:

    @pytest.mark.asyncio
    async def test_a_rate_limit_is_retried_with_growing_waits(self):
        primary = _Provider(AIRateLimitError("429"), AIRateLimitError("429"), ["ok"])

        chunks, sleep = await _stream(primary)

        assert chunks == ["ok"]
        assert [call.args[0] for call in sleep.await_args_list] == [2.0, 8.0]

    @pytest.mark.asyncio
    async def test_the_provider_s_retry_after_is_honoured_up_to_a_cap(self):
        primary = _Provider(AIRateLimitError("429", retry_after=5), AIRateLimitError("429", retry_after=600), ["ok"])

        _, sleep = await _stream(primary)

        assert [call.args[0] for call in sleep.await_args_list] == [5, AIService.RATE_LIMIT_MAX_WAIT]

    @pytest.mark.asyncio
    async def test_a_server_error_is_retried(self):
        chunks, _ = await _stream(_Provider(AIProviderError("500"), ["ok"]))

        assert chunks == ["ok"]

    @pytest.mark.asyncio
    async def test_after_the_retries_the_fallback_answers(self):
        primary = _Provider(*(AIRateLimitError("429") for _ in range(AIService.MAX_RETRIES)))
        fallback = _Provider(["from the fallback"])

        chunks, _ = await _stream(primary, fallback)

        assert chunks == ["from the fallback"]
        assert primary.calls == AIService.MAX_RETRIES

    @pytest.mark.asyncio
    async def test_a_timeout_goes_to_the_fallback_without_retry(self):
        primary = _Provider(AITimeoutError("60 s"))

        chunks, sleep = await _stream(primary, _Provider(["ok"]))

        assert chunks == ["ok"] and primary.calls == 1 and sleep.await_count == 0

    @pytest.mark.asyncio
    async def test_a_stream_that_started_is_never_retried(self):
        primary = _Provider(["shown", AIProviderError("500")], ["never"])

        with pytest.raises(AIProviderError):
            await _stream(primary, _Provider(["never"]))
        assert primary.calls == 1

    @pytest.mark.asyncio
    async def test_without_fallback_the_last_error_is_raised(self):
        primary = _Provider(*(AIRateLimitError("429") for _ in range(AIService.MAX_RETRIES)))

        with pytest.raises(AIError, match="429"):
            await _stream(primary)

    @pytest.mark.asyncio
    async def test_a_connection_error_goes_to_the_fallback(self):
        chunks, _ = await _stream(_Provider(httpx.ConnectError("refused")), _Provider(["ok"]))

        assert chunks == ["ok"]


class TestRetryAfter:

    @pytest.mark.parametrize("value, seconds", [("12", 12.0), ("0.5", 0.5), (None, None), ("", None),
                                                ("Wed, 21 Oct 2026 07:28:00 GMT", None), ("-3", None)])
    def test_seconds_are_read_a_date_is_not(self, value, seconds):
        assert retry_after_seconds(value) == seconds

    def test_mistral_carries_it_on_the_rate_limit_error(self):
        from lys.apps.ai.utils.providers.mistral import MistralProvider

        response = httpx.Response(429, headers={"Retry-After": "7"})
        with pytest.raises(AIRateLimitError) as raised:
            MistralProvider()._handle_error_status(response)
        assert raised.value.retry_after == 7.0
