"""
Unit tests for the framework-owned default system prompts.

The argument these defaults rest on is that forgetting them is silent: a purpose lys
drives itself would run with no system prompt at all and answer something plausible.
Nothing reports that, so it is pinned here instead.

The framework currently drives no purpose of its own, so the mechanism is exercised
against a purpose patched into the mapping: what is tested is the plumbing — the
default application at config-parse time, the configured prompt winning over it —
not the content of any prompt.
"""

import pytest

import lys.apps.ai.utils.prompts as prompts_module
from lys.apps.ai.utils.prompts import framework_default_system_prompt
from lys.apps.ai.utils.providers.config import parse_plugin_config

DUMMY_PURPOSE = "dummy_framework_purpose"
DUMMY_PROMPT = "Framework instructions for the dummy purpose."


@pytest.fixture
def framework_purpose(monkeypatch):
    """A purpose the framework drives, for the length of one test."""
    monkeypatch.setattr(
        prompts_module, "FRAMEWORK_DEFAULT_SYSTEM_PROMPTS", {DUMMY_PURPOSE: DUMMY_PROMPT}
    )


class TestFrameworkDefaultSystemPrompt:
    def test_a_framework_driven_purpose_has_a_default(self, framework_purpose):
        assert framework_default_system_prompt(DUMMY_PURPOSE) == DUMMY_PROMPT

    def test_an_application_purpose_has_none(self, framework_purpose):
        """A purpose carrying application content gets no framework instructions."""
        assert framework_default_system_prompt("chatbot") is None
        assert framework_default_system_prompt("unknown_purpose") is None


class TestEndpointPromptResolution:
    """The default is applied where config becomes an endpoint, not at call time.

    on_initialize skips an endpoint carrying no system_prompt, so a default applied
    later would never reach ai_prompt_version and a turn could not be attributed to
    the prompt that produced it.
    """

    @staticmethod
    def _config(endpoint_cfg):
        return parse_plugin_config(
            {"_keys": {"mistral": "k"}, DUMMY_PURPOSE: endpoint_cfg}
        )

    def test_an_endpoint_configuring_no_prompt_gets_the_framework_default(self, framework_purpose):
        config = self._config({"provider": "mistral", "model": "voxtral"})

        assert config.get_endpoint(DUMMY_PURPOSE).system_prompt == DUMMY_PROMPT

    def test_a_configured_prompt_wins(self, framework_purpose):
        config = self._config(
            {"provider": "mistral", "model": "voxtral", "system_prompt": "Speak like a pirate."}
        )

        assert config.get_endpoint(DUMMY_PURPOSE).system_prompt == "Speak like a pirate."

    def test_an_application_purpose_keeps_no_prompt(self):
        """The default must not leak onto purposes the framework does not drive."""
        config = parse_plugin_config(
            {"_keys": {"mistral": "k"}, "chatbot": {"provider": "mistral", "model": "m"}}
        )

        assert config.get_endpoint("chatbot").system_prompt is None

    def test_only_the_primary_endpoint_carries_the_prompt(self, framework_purpose):
        """A fallback declaring no prompt keeps none, and that is correct.

        The chat paths inject the PRIMARY endpoint's system_prompt into the messages
        once, before walking the chain (AIService.chat / chat_stream_with_purpose), so
        a fallback answers with the instructions already in the conversation. Applying
        the default to each link too would double the prompt on a fallback that
        declares one of its own.
        """
        config = self._config({
            "provider": "mistral",
            "model": "voxtral",
            "fallback": {"provider": "mistral", "model": "voxtral-mini"},
        })
        endpoint = config.get_endpoint(DUMMY_PURPOSE)

        assert endpoint.system_prompt == DUMMY_PROMPT
        assert endpoint.fallback is not None
        assert endpoint.fallback.system_prompt is None
