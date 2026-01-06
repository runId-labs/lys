"""
AI configuration models.

This module defines configuration dataclasses for AI endpoints,
supporting purpose-based configuration with API key resolution.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from lys.apps.ai.utils.providers.exceptions import AIPurposeNotFoundError


@dataclass
class AIEndpointConfig:
    """Configuration for a single AI endpoint."""

    provider: str
    model: str
    api_key: Optional[str] = None  # Resolved from _keys[provider] if not set
    base_url: Optional[str] = None
    timeout: int = 30
    system_prompt: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    fallback: Optional["AIEndpointConfig"] = None


@dataclass
class ExecutorConfig:
    """Configuration for tool executor."""

    mode: str = "local"  # "local" or "graphql"
    gateway_url: Optional[str] = None  # Required for graphql mode
    service_name: Optional[str] = None  # Service name for JWT auth
    timeout: int = 30


@dataclass
class AIConfig:
    """Root AI configuration with all purposes."""

    endpoints: Dict[str, AIEndpointConfig] = field(default_factory=dict)
    _keys: Dict[str, str] = field(default_factory=dict)
    executor: ExecutorConfig = field(default_factory=ExecutorConfig)

    def get_endpoint(self, purpose: str) -> AIEndpointConfig:
        """Get endpoint config for a purpose with resolved API key."""
        if purpose not in self.endpoints:
            raise AIPurposeNotFoundError(f"AI purpose '{purpose}' not configured")

        endpoint = self.endpoints[purpose]
        return self._resolve_endpoint(endpoint)

    def _resolve_endpoint(self, endpoint: AIEndpointConfig) -> AIEndpointConfig:
        """Resolve API key for an endpoint."""
        resolved_key = self._resolve_api_key(endpoint)

        # Resolve fallback recursively
        resolved_fallback = None
        if endpoint.fallback:
            resolved_fallback = self._resolve_endpoint(endpoint.fallback)

        return AIEndpointConfig(
            provider=endpoint.provider,
            model=endpoint.model,
            api_key=resolved_key,
            base_url=endpoint.base_url,
            timeout=endpoint.timeout,
            system_prompt=endpoint.system_prompt,
            options=endpoint.options,
            fallback=resolved_fallback,
        )

    def _resolve_api_key(self, endpoint: AIEndpointConfig) -> str:
        """
        Resolve API key in order:
        1. Explicit api_key in endpoint config
        2. _keys[provider] lookup
        3. Error if neither available
        """
        # 1. Explicit override
        if endpoint.api_key:
            return endpoint.api_key

        # 2. Lookup from _keys using provider name
        if endpoint.provider in self._keys:
            return self._keys[endpoint.provider]

        # 3. Error
        raise ValueError(
            f"No API key for provider '{endpoint.provider}'. "
            f"Set api_key explicitly or add to _keys."
        )


def parse_plugin_config(plugin_config: Dict[str, Any]) -> AIConfig:
    """
    Parse plugin configuration dict into AIConfig.

    Expected format:
        {
            "_keys": {"mistral": "sk-...", "openai": "sk-..."},
            "executor": {
                "mode": "graphql",  # or "local"
                "gateway_url": "https://gateway:8000/graphql",
                "service_name": "mimir-api",
                "timeout": 30
            },
            "chatbot": {
                "provider": "mistral",
                "model": "mistral-large-latest",
                "timeout": 30,
                "system_prompt": "You are helpful.",
                "options": {"temperature": 0.7},
                "fallback": {...}
            },
            "analysis": {
                "provider": "mistral",
                "model": "mistral-medium-latest",
            }
        }

    Args:
        plugin_config: Dict from settings.get_plugin_config("ai")

    Returns:
        AIConfig instance with parsed endpoints
    """
    keys = plugin_config.get("_keys", {})
    endpoints = {}

    # Parse executor config
    executor_cfg = plugin_config.get("executor", {})
    executor = ExecutorConfig(
        mode=executor_cfg.get("mode", "local"),
        gateway_url=executor_cfg.get("gateway_url"),
        service_name=executor_cfg.get("service_name"),
        timeout=executor_cfg.get("timeout", 30),
    )

    for purpose, cfg in plugin_config.items():
        # Skip special keys
        if purpose.startswith("_") or purpose == "executor":
            continue

        # Skip non-dict values
        if not isinstance(cfg, dict):
            continue

        # Skip if no provider (not an endpoint config)
        if "provider" not in cfg:
            continue

        # Parse fallback recursively
        fallback = None
        if cfg.get("fallback"):
            fallback = _parse_endpoint_config(cfg["fallback"])

        endpoints[purpose] = AIEndpointConfig(
            provider=cfg["provider"],
            model=cfg["model"],
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url"),
            timeout=cfg.get("timeout", 30),
            system_prompt=cfg.get("system_prompt"),
            options=cfg.get("options", {}),
            fallback=fallback,
        )

    return AIConfig(endpoints=endpoints, _keys=keys, executor=executor)


def _parse_endpoint_config(cfg: Dict[str, Any]) -> AIEndpointConfig:
    """Parse a single endpoint config dict."""
    fallback = None
    if cfg.get("fallback"):
        fallback = _parse_endpoint_config(cfg["fallback"])

    return AIEndpointConfig(
        provider=cfg["provider"],
        model=cfg["model"],
        api_key=cfg.get("api_key"),
        base_url=cfg.get("base_url"),
        timeout=cfg.get("timeout", 30),
        system_prompt=cfg.get("system_prompt"),
        options=cfg.get("options", {}),
        fallback=fallback,
    )