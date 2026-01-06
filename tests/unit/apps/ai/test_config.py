"""
Unit tests for AI configuration.

Tests AIConfig, AIEndpointConfig, and parse_plugin_config.
"""

import pytest

from lys.apps.ai.utils.providers.config import (
    AIConfig,
    AIEndpointConfig,
    parse_plugin_config,
)
from lys.apps.ai.utils.providers.exceptions import AIPurposeNotFoundError


class TestAIEndpointConfig:
    """Tests for AIEndpointConfig dataclass."""

    def test_minimal_config(self):
        """Test creating config with minimal required fields."""
        config = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
        )

        assert config.provider == "mistral"
        assert config.model == "mistral-large-latest"
        assert config.api_key is None
        assert config.base_url is None
        assert config.timeout == 30
        assert config.system_prompt is None
        assert config.options == {}
        assert config.fallback is None

    def test_full_config(self):
        """Test creating config with all fields."""
        fallback = AIEndpointConfig(
            provider="openai",
            model="gpt-4o",
            api_key="openai-key",
        )

        config = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="mistral-key",
            base_url="https://custom.api.com",
            timeout=60,
            system_prompt="You are helpful.",
            options={"temperature": 0.7},
            fallback=fallback,
        )

        assert config.provider == "mistral"
        assert config.api_key == "mistral-key"
        assert config.base_url == "https://custom.api.com"
        assert config.timeout == 60
        assert config.system_prompt == "You are helpful."
        assert config.options == {"temperature": 0.7}
        assert config.fallback == fallback
        assert config.fallback.provider == "openai"


class TestAIConfig:
    """Tests for AIConfig dataclass."""

    def test_get_endpoint_success(self):
        """Test getting an existing endpoint."""
        endpoint = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
        )
        config = AIConfig(
            endpoints={"chatbot": endpoint},
            _keys={"mistral": "test-key"},
        )

        result = config.get_endpoint("chatbot")

        assert result.provider == "mistral"
        assert result.api_key == "test-key"

    def test_get_endpoint_not_found(self):
        """Test that missing endpoint raises AIPurposeNotFoundError."""
        config = AIConfig(endpoints={}, _keys={})

        with pytest.raises(AIPurposeNotFoundError) as exc_info:
            config.get_endpoint("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "not configured" in str(exc_info.value)

    def test_api_key_resolution_from_keys(self):
        """Test that API key is resolved from _keys."""
        endpoint = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key=None,  # Not set explicitly
        )
        config = AIConfig(
            endpoints={"chatbot": endpoint},
            _keys={"mistral": "resolved-key"},
        )

        result = config.get_endpoint("chatbot")

        assert result.api_key == "resolved-key"

    def test_api_key_explicit_override(self):
        """Test that explicit api_key overrides _keys."""
        endpoint = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="explicit-key",
        )
        config = AIConfig(
            endpoints={"chatbot": endpoint},
            _keys={"mistral": "keys-value"},
        )

        result = config.get_endpoint("chatbot")

        assert result.api_key == "explicit-key"

    def test_api_key_missing_raises_error(self):
        """Test that missing API key raises ValueError."""
        endpoint = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key=None,
        )
        config = AIConfig(
            endpoints={"chatbot": endpoint},
            _keys={},  # No key for mistral
        )

        with pytest.raises(ValueError) as exc_info:
            config.get_endpoint("chatbot")

        assert "No API key" in str(exc_info.value)
        assert "mistral" in str(exc_info.value)

    def test_fallback_resolution(self):
        """Test that fallback endpoint API keys are resolved."""
        fallback = AIEndpointConfig(
            provider="openai",
            model="gpt-4o",
            api_key=None,
        )
        endpoint = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            fallback=fallback,
        )
        config = AIConfig(
            endpoints={"chatbot": endpoint},
            _keys={"mistral": "mistral-key", "openai": "openai-key"},
        )

        result = config.get_endpoint("chatbot")

        assert result.api_key == "mistral-key"
        assert result.fallback is not None
        assert result.fallback.api_key == "openai-key"


class TestParsePluginConfig:
    """Tests for parse_plugin_config function."""

    def test_parse_minimal_config(self):
        """Test parsing minimal plugin config."""
        plugin_config = {
            "_keys": {"mistral": "test-key"},
            "chatbot": {
                "provider": "mistral",
                "model": "mistral-large-latest",
            },
        }

        config = parse_plugin_config(plugin_config)

        assert "chatbot" in config.endpoints
        assert config.endpoints["chatbot"].provider == "mistral"
        assert config.endpoints["chatbot"].model == "mistral-large-latest"
        assert config._keys == {"mistral": "test-key"}

    def test_parse_full_config(self):
        """Test parsing full plugin config with all options."""
        plugin_config = {
            "_keys": {"mistral": "mistral-key", "openai": "openai-key"},
            "chatbot": {
                "provider": "mistral",
                "model": "mistral-large-latest",
                "base_url": "https://custom.api.com",
                "timeout": 60,
                "system_prompt": "You are helpful.",
                "options": {"temperature": 0.7},
            },
            "analysis": {
                "provider": "openai",
                "model": "gpt-4o",
                "timeout": 120,
            },
        }

        config = parse_plugin_config(plugin_config)

        assert len(config.endpoints) == 2
        assert config.endpoints["chatbot"].timeout == 60
        assert config.endpoints["chatbot"].system_prompt == "You are helpful."
        assert config.endpoints["chatbot"].options == {"temperature": 0.7}
        assert config.endpoints["analysis"].provider == "openai"
        assert config.endpoints["analysis"].timeout == 120

    def test_parse_config_with_fallback(self):
        """Test parsing config with fallback endpoint."""
        plugin_config = {
            "_keys": {"mistral": "mistral-key", "openai": "openai-key"},
            "chatbot": {
                "provider": "mistral",
                "model": "mistral-large-latest",
                "fallback": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "timeout": 60,
                },
            },
        }

        config = parse_plugin_config(plugin_config)

        chatbot = config.endpoints["chatbot"]
        assert chatbot.fallback is not None
        assert chatbot.fallback.provider == "openai"
        assert chatbot.fallback.model == "gpt-4o"
        assert chatbot.fallback.timeout == 60

    def test_parse_config_with_nested_fallback(self):
        """Test parsing config with nested fallback chain."""
        plugin_config = {
            "_keys": {
                "mistral": "mistral-key",
                "openai": "openai-key",
                "anthropic": "anthropic-key",
            },
            "chatbot": {
                "provider": "mistral",
                "model": "mistral-large-latest",
                "fallback": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "fallback": {
                        "provider": "anthropic",
                        "model": "claude-3-opus",
                    },
                },
            },
        }

        config = parse_plugin_config(plugin_config)

        chatbot = config.endpoints["chatbot"]
        assert chatbot.fallback.provider == "openai"
        assert chatbot.fallback.fallback.provider == "anthropic"

    def test_parse_ignores_special_keys(self):
        """Test that keys starting with _ are ignored as endpoints."""
        plugin_config = {
            "_keys": {"mistral": "key"},
            "_internal": {"some": "value"},
            "chatbot": {
                "provider": "mistral",
                "model": "mistral-large-latest",
            },
        }

        config = parse_plugin_config(plugin_config)

        assert "_internal" not in config.endpoints
        assert "chatbot" in config.endpoints

    def test_parse_ignores_non_dict_values(self):
        """Test that non-dict values are ignored as endpoints."""
        plugin_config = {
            "_keys": {"mistral": "key"},
            "enabled": True,  # Not a dict
            "max_retries": 3,  # Not a dict
            "chatbot": {
                "provider": "mistral",
                "model": "mistral-large-latest",
            },
        }

        config = parse_plugin_config(plugin_config)

        assert "enabled" not in config.endpoints
        assert "max_retries" not in config.endpoints
        assert "chatbot" in config.endpoints

    def test_parse_empty_config(self):
        """Test parsing empty plugin config."""
        config = parse_plugin_config({})

        assert config.endpoints == {}
        assert config._keys == {}

    def test_parse_default_timeout(self):
        """Test that default timeout is 30 seconds."""
        plugin_config = {
            "_keys": {"mistral": "key"},
            "chatbot": {
                "provider": "mistral",
                "model": "mistral-large-latest",
                # No timeout specified
            },
        }

        config = parse_plugin_config(plugin_config)

        assert config.endpoints["chatbot"].timeout == 30
