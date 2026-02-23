"""
AI Service with multi-provider support.

This module provides the main AIService class for interacting with
AI providers using purpose-based configuration, and AIToolService
for managing AI tool definitions.
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, List, Dict, Any, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel

from lys.apps.ai.utils.providers.abstracts import AIProvider, AIResponse, AIStreamChunk
from lys.apps.ai.utils.providers.config import AIEndpointConfig, parse_plugin_config, AIConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIError,
    AIRateLimitError,
    AIProviderError,
)
from lys.apps.ai.utils.providers.mistral import MistralProvider
from lys.core.consts.ai import ToolRiskLevel
from lys.core.graphql.client import GraphQLClient
from lys.core.registries import register_service
from lys.core.services import Service

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Plugin name for AI configuration
AI_PLUGIN_NAME = "ai"


@register_service()
class AIService(Service):
    """
    Service for AI/LLM integration with multi-provider support.

    This service provides:
    - Purpose-based endpoint configuration via plugin
    - Automatic retry on provider errors
    - Optional fallback to secondary providers
    - Both async and sync methods for Celery workers
    - Structured JSON responses with Pydantic validation
    - Provider registry that can be overridden via inheritance

    Configuration via plugin:
        settings.configure_plugin("ai",
            _keys={"mistral": "sk-..."},
            chatbot={
                "provider": "mistral",
                "model": "mistral-large-latest",
                "timeout": 30,
            },
        )

    Usage:
        ai_service = app_manager.get_service("ai")

        # Chat with purpose
        response = await ai_service.chat_with_purpose(messages, "chatbot")

        # Or with explicit config
        config = ai_service.get_endpoint("chatbot")
        response = await ai_service.chat(messages, config)

    Extending with custom providers:
        # Option 1: Override via inheritance
        class MyAIService(AIService):
            _providers = {
                **AIService._providers,
                "custom": MyCustomProvider,
            }

        # Option 2: Register at runtime
        AIService.register_provider("custom", MyCustomProvider)
    """

    service_name = "ai"

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds

    # Cached config
    _config_cache: Optional[AIConfig] = None

    # Provider registry - can be overridden via inheritance
    _providers: Dict[str, Type[AIProvider]] = {
        "mistral": MistralProvider,
    }

    # ========== Provider Registry ==========

    @classmethod
    def get_provider(cls, name: str) -> AIProvider:
        """
        Get provider instance by name.

        Args:
            name: Provider name (e.g., "mistral", "openai")

        Returns:
            AIProvider instance

        Raises:
            ValueError: If provider is not registered
        """
        if name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(f"Unknown AI provider: {name}. Available: {available}")
        return cls._providers[name]()

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[AIProvider]):
        """
        Register or replace a provider.

        Args:
            name: Provider name
            provider_class: Provider class (must inherit from AIProvider)
        """
        cls._providers[name] = provider_class

    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())

    # ========== Configuration ==========

    @classmethod
    def get_config(cls) -> AIConfig:
        """
        Get parsed AI configuration from plugin.

        Returns:
            AIConfig instance with all endpoints
        """
        if cls._config_cache is not None:
            return cls._config_cache

        plugin_config = cls.app_manager.settings.get_plugin_config(AI_PLUGIN_NAME)
        if not plugin_config:
            raise ValueError(
                f"AI plugin not configured. Use settings.configure_plugin('{AI_PLUGIN_NAME}', ...)"
            )

        cls._config_cache = parse_plugin_config(plugin_config)
        return cls._config_cache

    @classmethod
    def get_endpoint(cls, purpose: str) -> AIEndpointConfig:
        """
        Get endpoint configuration for a purpose.

        Args:
            purpose: Purpose name (e.g., "chatbot", "analysis")

        Returns:
            AIEndpointConfig with resolved API key
        """
        return cls.get_config().get_endpoint(purpose)

    @classmethod
    def clear_config_cache(cls):
        """Clear the config cache to force reload."""
        cls._config_cache = None

    # ========== Purpose-based Chat (convenience) ==========

    @classmethod
    async def chat_with_purpose(
        cls,
        messages: List[Dict[str, Any]],
        purpose: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """
        Chat using a configured purpose.

        Args:
            messages: Conversation messages
            purpose: Purpose name (e.g., "chatbot", "analysis")
            tools: Optional tool definitions

        Returns:
            AIResponse
        """
        config = cls.get_endpoint(purpose)
        return await cls.chat(messages, config, tools)

    @classmethod
    def chat_with_purpose_sync(
        cls,
        messages: List[Dict[str, Any]],
        purpose: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Synchronous version for Celery workers."""
        config = cls.get_endpoint(purpose)
        return cls.chat_sync(messages, config, tools)

    @classmethod
    async def chat_stream_with_purpose(
        cls,
        messages: List[Dict[str, Any]],
        purpose: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[AIStreamChunk, None]:
        """
        Stream a chat response using a configured purpose.

        Tries the primary provider, falls back on connection error (no retry mid-stream).

        Args:
            messages: Conversation messages
            purpose: Purpose name (e.g., "chatbot")
            tools: Optional tool definitions

        Yields:
            AIStreamChunk for each piece of the response
        """
        endpoint = cls.get_endpoint(purpose)

        if endpoint.system_prompt:
            messages = [{"role": "system", "content": endpoint.system_prompt}] + messages

        current_endpoint = endpoint
        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)
            try:
                async for chunk in provider.chat_stream(messages, current_endpoint, tools):
                    yield chunk
                return
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                logger.warning(f"Connection error on {current_endpoint.provider}: {e}")
                current_endpoint = current_endpoint.fallback
                if current_endpoint:
                    logger.info(f"Falling back to {current_endpoint.provider}/{current_endpoint.model}")
            except AIError:
                raise

        raise AIError("All providers failed for streaming")

    # ========== Standard Chat ==========

    @classmethod
    async def chat(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """
        Send a chat request using the specified endpoint configuration.

        Args:
            messages: Conversation messages
            config: Endpoint configuration (from settings.ai.get_endpoint)
            tools: Optional tool definitions for function calling

        Returns:
            AIResponse with content, tool_calls, usage, etc.

        Raises:
            AIError: Provider errors after retries/fallback exhausted
        """
        # Add system prompt from config if present
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages

        return await cls._chat_with_fallback(messages, config, tools)

    @classmethod
    def chat_sync(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Synchronous version for Celery workers."""
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages

        return cls._chat_with_fallback_sync(messages, config, tools)

    # ========== Structured JSON Chat ==========

    @classmethod
    async def chat_json(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """
        Chat with structured JSON response validated against a Pydantic schema.

        Args:
            messages: Conversation messages
            config: Endpoint configuration
            schema: Pydantic model class for response validation

        Returns:
            Validated Pydantic model instance

        Raises:
            AIValidationError: Response doesn't match schema
            AIError: Provider errors after retries/fallback exhausted
        """
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages

        return await cls._chat_json_with_fallback(messages, config, schema)

    @classmethod
    def chat_json_sync(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Synchronous version for Celery workers."""
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages

        return cls._chat_json_with_fallback_sync(messages, config, schema)

    # ========== Fallback Logic ==========

    @classmethod
    async def _chat_with_fallback(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Execute chat with retry and fallback logic."""
        current_endpoint = endpoint
        last_error: Optional[Exception] = None

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return await provider.chat(messages, current_endpoint, tools)

                except AIRateLimitError as e:
                    # Rate limit → try fallback immediately
                    logger.warning(
                        f"Rate limit on {current_endpoint.provider}, trying fallback"
                    )
                    last_error = e
                    break

                except AIProviderError as e:
                    # Server error → retry
                    last_error = e
                    if retry < cls.MAX_RETRIES - 1:
                        logger.warning(
                            f"Provider error (attempt {retry + 1}): {e}, retrying..."
                        )
                        await asyncio.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        logger.error(
                            f"Provider error after {cls.MAX_RETRIES} retries: {e}"
                        )
                        break

                except AIError as e:
                    # Other AI errors → don't retry, try fallback
                    last_error = e
                    break

            # Try fallback if configured
            current_endpoint = current_endpoint.fallback
            if current_endpoint:
                logger.info(
                    f"Falling back to {current_endpoint.provider}/{current_endpoint.model}"
                )

        if last_error:
            logger.error(f"All providers failed: {last_error}")
        raise AIError("All providers failed")

    @classmethod
    def _chat_with_fallback_sync(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Synchronous fallback logic."""
        current_endpoint = endpoint
        last_error: Optional[Exception] = None

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return provider.chat_sync(messages, current_endpoint, tools)

                except AIRateLimitError as e:
                    last_error = e
                    break

                except AIProviderError as e:
                    last_error = e
                    if retry < cls.MAX_RETRIES - 1:
                        time.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        break

                except AIError as e:
                    last_error = e
                    break

            current_endpoint = current_endpoint.fallback

        if last_error:
            logger.error(f"All providers failed: {last_error}")
        raise AIError("All providers failed")

    @classmethod
    async def _chat_json_with_fallback(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Execute chat_json with retry and fallback logic."""
        current_endpoint = endpoint
        last_error: Optional[Exception] = None

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return await provider.chat_json(messages, current_endpoint, schema)

                except AIRateLimitError as e:
                    logger.warning(
                        f"Rate limit on {current_endpoint.provider}, trying fallback"
                    )
                    last_error = e
                    break

                except AIProviderError as e:
                    last_error = e
                    if retry < cls.MAX_RETRIES - 1:
                        logger.warning(
                            f"Provider error (attempt {retry + 1}): {e}, retrying..."
                        )
                        await asyncio.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        logger.error(
                            f"Provider error after {cls.MAX_RETRIES} retries: {e}"
                        )
                        break

                except AIError as e:
                    last_error = e
                    break

            current_endpoint = current_endpoint.fallback
            if current_endpoint:
                logger.info(
                    f"Falling back to {current_endpoint.provider}/{current_endpoint.model}"
                )

        if last_error:
            logger.error(f"All providers failed: {last_error}")
        raise AIError("All providers failed")

    @classmethod
    def _chat_json_with_fallback_sync(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Synchronous fallback logic for chat_json."""
        current_endpoint = endpoint
        last_error: Optional[Exception] = None

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return provider.chat_json_sync(messages, current_endpoint, schema)

                except AIRateLimitError as e:
                    last_error = e
                    break

                except AIProviderError as e:
                    last_error = e
                    if retry < cls.MAX_RETRIES - 1:
                        time.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        break

                except AIError as e:
                    last_error = e
                    break

            current_endpoint = current_endpoint.fallback

        if last_error:
            logger.error(f"All providers failed: {last_error}")
        raise AIError("All providers failed")


@register_service()
class AIToolService(Service):
    """
    Service for managing AI tool definitions.

    This service provides:
    - Fetches tools from Apollo Gateway via GraphQL
    - JWT-based filtering for accessible tools
    - Lazy loading with caching

    Configuration via executor config in AI plugin:
        settings.configure_plugin("ai",
            executor={
                "gateway_url": "http://localhost:8000/graphql",
                "service_name": "mimir-api",
            },
        )

    Usage:
        ai_tool_service = app_manager.get_service("ai_tool")
        tools = await ai_tool_service.get_accessible_tools(connected_user)
    """

    service_name = "ai_tool"

    # Cached tools with resolvers and metadata
    _tools: Dict[str, Dict[str, Any]] = {}
    _initialized: bool = False

    @classmethod
    async def get_accessible_tools(cls, connected_user: Dict[str, Any]) -> List[Dict]:
        """
        Get tool definitions filtered by JWT claims.

        For super_users, all tools are returned without filtering because:
        - The permission layer grants super_users access to everything
        - JWT claims don't contain all webservices for super_users (by design)
        - See AuthService.generate_access_claims() for the JWT override chain

        For regular users, tools are filtered based on:
        - "webservices" claim: global webservices (PUBLIC, CONNECTED, OWNER, ROLE)
        - "organizations" claim: per-organization webservices (ORGANIZATION_ROLE)

        Args:
            connected_user: Connected user dict from context, containing:
                            - "webservices": dict of accessible webservice names
                            - "organizations": dict of per-org webservices (client owners, client_user roles)
                            - "is_super_user": boolean

        Returns:
            List of tool definitions for LLM function calling
        """
        if not cls._initialized:
            await cls._load_tools()

        # Super users get all tools - permission layer handles actual access control
        is_super_user = connected_user.get("is_super_user", False) if connected_user else False
        if is_super_user:
            return [
                {
                    "webservice": name,
                    "definition": tool_data["definition"],
                    "operation_type": tool_data.get("operation_type"),
                }
                for name, tool_data in cls._tools.items()
            ]

        # Regular users: collect all accessible webservices from JWT claims
        accessible_ids = set()

        # Add global webservices (PUBLIC, CONNECTED, OWNER, ROLE access levels)
        jwt_webservices = connected_user.get("webservices", {}) if connected_user else {}
        accessible_ids.update(jwt_webservices.keys())

        # Add organization-scoped webservices (ORGANIZATION_ROLE access level)
        # This includes client owners and users with client_user_roles
        organizations = connected_user.get("organizations", {}) if connected_user else {}
        for org_data in organizations.values():
            org_webservices = org_data.get("webservices", [])
            accessible_ids.update(org_webservices)

        return [
            {
                "webservice": name,
                "definition": tool_data["definition"],
                "operation_type": tool_data.get("operation_type"),
            }
            for name, tool_data in cls._tools.items()
            if name in accessible_ids
        ]

    @classmethod
    async def get_tool(cls, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific tool by name.

        Args:
            name: Tool name to lookup

        Returns:
            Tool data dict with definition, resolver, node_type, etc.
            None if tool not found.
        """
        if not cls._initialized:
            await cls._load_tools()

        return cls._tools.get(name)

    @classmethod
    async def _load_tools(cls):
        """Load tools from Apollo Gateway via GraphQL."""
        config = cls.app_manager.settings.get_plugin_config(AI_PLUGIN_NAME)
        if not config:
            logger.warning("AI plugin not configured, no tools loaded")
            cls._initialized = True
            return

        executor_config = config.get("executor", {})
        await cls._load_tools_remote(executor_config)

        cls._initialized = True
        logger.debug(f"AIToolService loaded {len(cls._tools)} tools from gateway: {list(cls._tools.keys())}")

    @classmethod
    async def _load_tools_remote(cls, executor_config: Dict[str, Any]):
        """Fetch tools from GraphQL endpoint."""
        gateway_url = executor_config.get("gateway_url")
        service_name = executor_config.get("service_name")
        secret_key = cls.app_manager.settings.secret_key
        timeout = executor_config.get("timeout", 30)
        verify_ssl = executor_config.get("verify_ssl", True)

        if not gateway_url:
            logger.error("gateway_url not configured for graphql mode")
            return

        client = GraphQLClient(
            url=gateway_url,
            secret_key=secret_key,
            service_name=service_name or "ai-service",
            timeout=timeout,
            verify_ssl=verify_ssl,
        )

        query = """
        query GetAITools {
            allWebservices(isAiTool: true) {
                edges {
                    node {
                        id
                        code
                        operationType
                        aiTool
                    }
                }
            }
        }
        """

        try:
            data = await client.execute(query)

            if "errors" in data:
                logger.error(f"GraphQL errors fetching tools: {data['errors']}")
                return

            edges = data.get("data", {}).get("allWebservices", {}).get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                ai_tool = node.get("aiTool")
                if ai_tool:
                    name = ai_tool.get("function", {}).get("name") or node.get("code")
                    cls._tools[name] = {
                        "definition": ai_tool,
                        "resolver": None,  # No resolver in graphql mode
                        "node_type": None,
                        "operation_type": node.get("operationType") or "mutation",
                        "risk_level": ToolRiskLevel.READ,  # Default, could be fetched
                        "confirmation_fields": [],
                    }

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch tools from gateway: {e}")

    @classmethod
    def reset(cls):
        """Reset the service state. Useful for testing."""
        cls._tools = {}
        cls._initialized = False


@register_service()
class ContextToolService(Service):
    """
    Service for managing context tools used by chatbot page behaviours.

    This service provides a registry for context tools that can be called
    dynamically based on the page's `context_tools` configuration in the
    routes manifest.

    Services register their context tool functions during initialization:

        class ContextualQuestionService(EntityService):
            @classmethod
            async def on_initialize(cls):
                context_tool_service = cls.app_manager.get_service("context_tool")
                context_tool_service.register(
                    "get_contextual_questions",
                    cls.get_for_prompt
                )

    Then AIConversationService can execute tools dynamically:

        results = await context_tool_service.execute_all(
            context_tools={"questions": "get_contextual_questions"},
            company_id=company_id,
            year=year,
            session=session,
        )

    Usage:
        context_tool_service = app_manager.get_service("context_tool")
        context_tool_service.register("get_contextual_questions", my_func)
        result = await context_tool_service.execute("get_contextual_questions", ...)
    """

    service_name = "context_tool"

    # Registry mapping function names to callables
    _registry: Dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, func: Any) -> None:
        """
        Register a context tool function.

        Args:
            name: Function name as referenced in routes manifest context_tools
            func: Async callable that accepts (company_id, year, session) and returns str
        """
        cls._registry[name] = func
        logger.info(f"ContextToolService: registered '{name}'")

    @classmethod
    def get(cls, name: str) -> Optional[Any]:
        """
        Get a registered context tool function.

        Args:
            name: Function name to lookup

        Returns:
            The registered callable or None if not found
        """
        return cls._registry.get(name)

    @classmethod
    async def execute(
        cls,
        name: str,
        session: Any,
        **params,
    ) -> Optional[str]:
        """
        Execute a registered context tool.

        Args:
            name: Function name to execute
            session: Database session
            **params: Parameters to pass to the function

        Returns:
            Result string from the function, or None if function not found
        """
        func = cls._registry.get(name)
        if not func:
            logger.warning(f"ContextToolService: unknown function '{name}'")
            return None

        try:
            return await func(session=session, **params)
        except Exception as e:
            logger.error(f"ContextToolService: error executing '{name}': {e}")
            return None

    @classmethod
    async def execute_all(
        cls,
        context_tools: Dict[str, str],
        session: Any,
        **params,
    ) -> Dict[str, str]:
        """
        Execute all context tools and return results.

        Args:
            context_tools: Dict mapping labels to function names
                e.g., {"contextual_questions": "get_contextual_questions"}
            session: Database session
            **params: Parameters to pass to functions

        Returns:
            Dict mapping labels to result strings (only for successful calls)
        """
        results = {}

        for label, function_name in context_tools.items():
            result = await cls.execute(function_name, session, **params)
            if result:
                results[label] = result

        return results

    @classmethod
    def reset(cls):
        """Reset the registry. Useful for testing."""
        cls._registry = {}