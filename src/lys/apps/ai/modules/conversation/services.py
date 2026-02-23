"""
AI Conversation services.

Services for managing conversations and feedback.
"""

import json
import logging
import time
from datetime import datetime, UTC
from typing import AsyncGenerator, Optional, List, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lys.apps.ai.modules.conversation.consts import (
    AIFeedbackRating,
    AIMessageRole,
    AI_PURPOSE_CHATBOT,
)
from lys.apps.ai.modules.conversation.entities import (
    AIConversation,
    AIMessage,
    AIMessageFeedback,
)
from lys.apps.ai.modules.conversation.models import PageContextModel
from lys.apps.ai.modules.core.executors import GraphQLToolExecutor
from lys.apps.ai.modules.core.services import AIToolService
from lys.apps.ai.utils.guardrails import CONFIRM_ACTION_TOOL
from lys.apps.ai.utils.providers.config import parse_plugin_config
from lys.core.registries import register_service
from lys.core.services import EntityService
from lys.core.utils.routes import filter_routes_by_permissions, build_navigate_tool, load_routes_manifest
from lys.core.utils.strings import to_snake_case

logger = logging.getLogger(__name__)


@register_service()
class AIConversationService(EntityService[AIConversation]):
    """Service for managing AI conversations."""

    _routes_manifest_cache: Optional[Dict[str, Any]] = None

    @classmethod
    def _get_routes_manifest(cls) -> Optional[Dict[str, Any]]:
        """
        Get cached routes manifest, loading once if needed.

        Returns:
            Routes manifest dict or None if not configured
        """
        if cls._routes_manifest_cache is not None:
            return cls._routes_manifest_cache

        ai_plugin_config = cls.app_manager.settings.get_plugin_config("ai") or {}
        chatbot_config = ai_plugin_config.get("chatbot", {})
        routes_manifest_path = None
        if isinstance(chatbot_config, dict):
            routes_manifest_path = chatbot_config.get("options", {}).get("routes_manifest_path")

        if routes_manifest_path:
            cls._routes_manifest_cache = load_routes_manifest(routes_manifest_path)
        else:
            cls._routes_manifest_cache = {}

        return cls._routes_manifest_cache

    @classmethod
    def _get_page_webservices(cls, page_name: str) -> set[str]:
        """
        Get webservices available on a specific page.

        Args:
            page_name: Name of the page (e.g., "FinancialDashboardPage")

        Returns:
            Set of webservice names available on the page (in snake_case)
        """
        manifest = cls._get_routes_manifest()
        if not manifest:
            return set()

        # Include global webservices (always available)
        # Convert from camelCase (manifest) to snake_case (backend)
        global_webservices = {
            to_snake_case(ws) for ws in manifest.get("globalWebservices", [])
        }

        # Find page-specific webservices
        for route in manifest.get("routes", []):
            if route.get("name") == page_name:
                page_webservices = {
                    to_snake_case(ws) for ws in route.get("webservices", [])
                }
                return global_webservices | page_webservices

        # Page not found, return only global webservices
        return global_webservices

    @classmethod
    def _get_page_chatbot_behaviour(cls, page_name: str) -> Optional[Dict[str, Any]]:
        """
        Get chatbot behaviour configuration for a specific page.

        Args:
            page_name: Name of the page (e.g., "FinancialDashboardPage")

        Returns:
            Chatbot behaviour dict with 'prompt' and 'context_tools', or None
        """
        manifest = cls._get_routes_manifest()
        if not manifest:
            return None

        for route in manifest.get("routes", []):
            if route.get("name") == page_name:
                return route.get("chatbot_behaviour")

        return None

    @classmethod
    def _process_response(cls, result: dict) -> None:
        """
        Process the final response before returning.

        Override in subclass to modify result in-place (e.g., parsing special tags).

        Args:
            result: Dict with content, conversation_id, tool_calls_count,
                    tool_results, frontend_actions
        """
        pass

    @classmethod
    async def get_or_create(
        cls,
        user_id: str,
        session: AsyncSession,
        conversation_id: Optional[str] = None,
    ) -> "AIConversation":
        """
        Get existing conversation or create a new one.

        Args:
            user_id: User ID
            session: Database session
            conversation_id: Optional conversation ID to retrieve

        Returns:
            AIConversation instance
        """
        if conversation_id:
            conversation = await cls.get_by_id(conversation_id, session)
            if conversation and conversation.user_id == user_id:
                return conversation

        return await cls.create(
            session,
            user_id=user_id,
            purpose=AI_PURPOSE_CHATBOT,
        )

    @classmethod
    async def chat(
        cls,
        user_id: str,
        content: str,
        session: AsyncSession,
        conversation_id: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> "AIMessage":
        """
        Send a message and get AI response.

        Args:
            user_id: User ID
            content: User message content
            session: Database session
            conversation_id: Optional conversation ID to continue
            tools: Optional tool definitions

        Returns:
            AIMessage with assistant response
        """
        conversation = await cls.get_or_create(user_id, session, conversation_id)

        message_service = cls.app_manager.get_service("ai_messages")
        ai_service = cls.app_manager.get_service("ai")

        # Save user message
        await message_service.create(
            session,
            conversation_id=conversation.id,
            role=AIMessageRole.USER.value,
            content=content,
        )

        # Build messages list from conversation history
        messages = await cls._build_messages(conversation, session)

        # Call AI service
        start_time = time.perf_counter()
        response = await ai_service.chat_with_purpose(messages, AI_PURPOSE_CHATBOT, tools)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Save assistant message with metrics
        assistant_message = await message_service.create(
            session,
            conversation_id=conversation.id,
            role=AIMessageRole.ASSISTANT.value,
            content=response.content,
            tool_calls=response.tool_calls or None,
            provider=response.provider,
            model=response.model,
            tokens_in=response.usage.get("prompt_tokens") if response.usage else None,
            tokens_out=response.usage.get("completion_tokens") if response.usage else None,
            latency_ms=latency_ms,
        )

        return assistant_message

    @classmethod
    async def _build_messages(
        cls,
        conversation: "AIConversation",
        session: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Build messages list from conversation history."""
        message_entity = cls.app_manager.get_entity("ai_messages")
        result = await session.execute(
            select(message_entity)
            .where(message_entity.conversation_id == conversation.id)
            .order_by(message_entity.created_at)
        )
        db_messages = result.scalars().all()

        messages = []
        for msg in db_messages:
            if msg.role == AIMessageRole.TOOL.value:
                messages.append({
                    "role": msg.role,
                    "content": str(msg.tool_result) if msg.tool_result else "",
                    "tool_call_id": msg.tool_call_id,
                })
            elif msg.role == AIMessageRole.ASSISTANT.value and msg.tool_calls:
                # Include tool_calls for assistant messages that made tool calls
                messages.append({
                    "role": msg.role,
                    "content": msg.content or "",
                    "tool_calls": msg.tool_calls,
                })
            else:
                messages.append({
                    "role": msg.role,
                    "content": msg.content or "",
                })

        return messages

    @classmethod
    async def archive(cls, conversation_id: str, session: AsyncSession) -> bool:
        """Archive a conversation."""
        result = await cls.update(conversation_id, session, archived_at=datetime.now(UTC))
        return result is not None

    @classmethod
    async def _build_system_prompt(
        cls,
        session: AsyncSession,
        connected_user: Optional[Dict[str, Any]],
        chatbot_config: Dict[str, Any],
        tools_count: int,
        page_behaviour: Optional[Dict[str, Any]] = None,
        context_data: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Build system prompt with user context.

        Args:
            session: Database session
            connected_user: Connected user from JWT
            chatbot_config: Chatbot configuration from plugin
            tools_count: Number of available tools
            page_behaviour: Optional page-specific chatbot behaviour from manifest
            context_data: Optional context data from executing context_tools

        Returns:
            System prompt string
        """
        system_prompt_parts = []

        # Add custom application system prompt if configured
        custom_system_prompt = chatbot_config.get("system_prompt") if isinstance(chatbot_config, dict) else None
        if custom_system_prompt:
            system_prompt_parts.append(custom_system_prompt)
            system_prompt_parts.append("")

        # Add page-specific prompt if available
        if page_behaviour and page_behaviour.get("prompt"):
            system_prompt_parts.append(page_behaviour["prompt"])
            system_prompt_parts.append("")

        # Add context data from context_tools if available
        if context_data:
            system_prompt_parts.append("## Contexte dynamique")
            for label, data in context_data.items():
                system_prompt_parts.append(f"\n### {label}")
                system_prompt_parts.append(data)

        return "\n".join(system_prompt_parts)

    @classmethod
    async def _get_user_details(cls, session: AsyncSession, user_id: str) -> Dict[str, Any]:
        """Get user details from database."""
        try:
            user_entity = cls.app_manager.get_entity("user")

            stmt = (
                select(user_entity)
                .where(user_entity.id == user_id)
                .options(selectinload(user_entity.private_data))
            )

            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return {}

            details = {
                "email": getattr(user, "email", None),
                "status": getattr(user, "status", None),
            }

            if hasattr(user, "private_data") and user.private_data:
                details["first_name"] = getattr(user.private_data, "first_name", None)
                details["last_name"] = getattr(user.private_data, "last_name", None)
                details["language_code"] = getattr(user.private_data, "language_code", None)

            if details["status"]:
                if hasattr(details["status"], "code"):
                    details["status"] = details["status"].code
                elif hasattr(details["status"], "value"):
                    details["status"] = details["status"].value

            return details
        except Exception:
            return {}

    @classmethod
    async def _get_user_roles_info(cls, session: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
        """Get user roles with descriptions."""
        try:
            role_entity = cls.app_manager.get_entity("role")
            user_entity = cls.app_manager.get_entity("user")

            stmt = (
                select(role_entity)
                .where(role_entity.users.any(user_entity.id == user_id))
                .where(role_entity.enabled == True)
            )

            result = await session.execute(stmt)
            roles = result.scalars().all()

            return [
                {
                    "code": role.code,
                    "description": getattr(role, "description", None)
                }
                for role in roles
            ]
        except Exception:
            return []

    @classmethod
    async def _get_tool_executor(
        cls,
        tools: List[Dict[str, Any]],
        info: Any,
        accessible_routes: List[Dict[str, Any]] = None,
        page_context: Optional[PageContextModel] = None,
    ):
        """
        Get the GraphQL tool executor.

        Args:
            tools: Available tool definitions
            info: GraphQL info context
            accessible_routes: List of routes accessible to the user for navigation
            page_context: Page context for param injection

        Returns:
            Configured GraphQLToolExecutor instance
        """
        app_manager = cls.app_manager
        plugin_config = app_manager.settings.get_plugin_config("ai")
        ai_config = parse_plugin_config(plugin_config)

        # Use Bearer token from user's JWT if available (user-authenticated calls)
        # Otherwise fall back to Service auth (inter-service calls)
        bearer_token = info.context.access_token if info.context else None

        if bearer_token:
            executor = GraphQLToolExecutor(
                gateway_url=ai_config.executor.gateway_url,
                bearer_token=bearer_token,
                timeout=ai_config.executor.timeout,
                verify_ssl=ai_config.executor.verify_ssl,
            )
        else:
            executor = GraphQLToolExecutor(
                gateway_url=ai_config.executor.gateway_url,
                secret_key=app_manager.settings.secret_key,
                service_name=ai_config.executor.service_name or app_manager.settings.service_name,
                timeout=ai_config.executor.timeout,
                verify_ssl=ai_config.executor.verify_ssl,
            )

        await executor.initialize(
            tools=tools,
            accessible_routes=accessible_routes,
            page_context=page_context,
        )
        return executor

    @classmethod
    async def _prepare_chat_context(
        cls,
        user_id: str,
        content: str,
        session: AsyncSession,
        connected_user: Dict[str, Any],
        info: Any,
        conversation_id: Optional[str] = None,
        page_context: Optional[PageContextModel] = None,
    ) -> Dict[str, Any]:
        """
        Prepare the shared context for both streaming and non-streaming chat.

        Handles tool loading, permission filtering, system prompt building,
        executor initialization, conversation retrieval, and message history.

        Args:
            user_id: User ID
            content: User message content
            session: Database session
            connected_user: Connected user dict from JWT
            info: GraphQL info context (or _StreamingInfo shim)
            conversation_id: Optional conversation ID to continue
            page_context: Optional page context for tool filtering and param injection

        Returns:
            Dict with keys: tools, llm_tools, executor, conversation,
            message_service, ai_service, messages, info
        """
        app_manager = cls.app_manager

        # Get tools via AIToolService filtered by JWT claims
        # Note: Tools are lazy-loaded once and cached at class level, only filtering is done here
        # For super_users, all tools are returned (see AIToolService.get_accessible_tools)
        tools = await AIToolService.get_accessible_tools(connected_user)
        initial_tools_count = len(tools)

        # Filter tools by page context if provided
        if page_context and page_context.page_name:
            logger.debug(
                f"[PageContext] Received context: page_name='{page_context.page_name}', "
                f"params={page_context.params}"
            )
            page_webservices = cls._get_page_webservices(page_context.page_name)
            logger.debug(
                f"[PageContext] Page webservices for '{page_context.page_name}': {page_webservices}"
            )
            if page_webservices:
                tools = [
                    tool for tool in tools
                    if tool.get("webservice") in page_webservices
                ]
                tool_names = [tool.get("webservice", "unknown") for tool in tools]
                logger.debug(
                    f"[PageContext] Tool filtering: {initial_tools_count} -> {len(tools)} tools "
                    f"(filtered by page '{page_context.page_name}'): {tool_names}"
                )
        else:
            logger.debug(
                f"[PageContext] No page context provided, all {initial_tools_count} tools available"
            )

        # Add confirm_action special tool
        tools.append(CONFIRM_ACTION_TOOL)

        # Load navigation routes from cache and filter by user permissions
        ai_plugin_config = app_manager.settings.get_plugin_config("ai") or {}
        chatbot_config = ai_plugin_config.get("chatbot", {})

        # Note: Routes manifest is loaded once and cached at class level
        accessible_routes = []
        manifest = cls._get_routes_manifest()
        is_super_user = connected_user.get("is_super_user", False) if connected_user else False

        if manifest and "routes" in manifest:
            if is_super_user:
                # Super users get all routes - permission layer handles actual access control
                accessible_routes = manifest["routes"]
            else:
                # Regular users: collect all accessible webservice IDs from JWT claims
                accessible_webservice_ids = set()

                # Add global webservices (PUBLIC, CONNECTED, OWNER, ROLE access levels)
                jwt_webservices = connected_user.get("webservices", {}) if connected_user else {}
                accessible_webservice_ids.update(jwt_webservices.keys())

                # Add organization-scoped webservices (ORGANIZATION_ROLE access level)
                # This includes client owners and users with client_user_roles
                organizations = connected_user.get("organizations", {}) if connected_user else {}
                for org_data in organizations.values():
                    accessible_webservice_ids.update(org_data.get("webservices", []))

                accessible_routes = filter_routes_by_permissions(
                    manifest["routes"],
                    accessible_webservice_ids
                )

            if accessible_routes:
                navigate_tool = build_navigate_tool(accessible_routes)
                tools.append(navigate_tool)

        # Get page-specific chatbot behaviour if available
        page_behaviour = None
        context_data = {}
        if page_context and page_context.page_name:
            page_behaviour = cls._get_page_chatbot_behaviour(page_context.page_name)
            if page_behaviour:
                logger.debug(
                    f"[ChatbotBehaviour] Found behaviour for page '{page_context.page_name}'"
                )
                # Execute context_tools to fetch dynamic data
                context_tools = page_behaviour.get("context_tools", {})
                if context_tools:
                    context_tool_service = app_manager.get_service("context_tool")
                    context_data = await context_tool_service.execute_all(
                        context_tools,
                        session,
                        **(page_context.params or {}),
                    )
                    logger.debug(
                        f"[ContextTools] Fetched data for {len(context_data)} labels"
                    )

        # Build system prompt
        # TODO: Optimize - consider caching system prompt per conversation_id to avoid
        # 2 DB queries (user details + roles) on every message
        system_prompt = await cls._build_system_prompt(
            session, connected_user, chatbot_config, len(tools),
            page_behaviour=page_behaviour,
            context_data=context_data,
        )
        logger.debug(f"[SystemPrompt] Built prompt:\n{system_prompt}")

        # Get the appropriate executor based on config
        executor = await cls._get_tool_executor(tools, info, accessible_routes, page_context)

        conversation = await cls.get_or_create(user_id, session, conversation_id)
        message_service = app_manager.get_service("ai_messages")
        ai_service = app_manager.get_service("ai")

        # Extract just the definitions for the LLM (tools contain operation_type metadata)
        llm_tools = [
            tool.get("definition", tool) if isinstance(tool, dict) and "definition" in tool else tool
            for tool in tools
        ]

        # Build messages with system prompt and history
        # TODO: Optimize - consider keeping messages in memory during conversation to avoid
        # reloading full history from DB on every message
        history = await cls._build_messages(conversation, session)
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (filter out system messages)
        for msg in history:
            if msg.get("role") != "system":
                messages.append(msg)

        # Add new user message
        messages.append({"role": "user", "content": content})

        # Save user message to DB
        await message_service.create(
            session,
            conversation_id=conversation.id,
            role=AIMessageRole.USER.value,
            content=content,
        )

        return {
            "tools": tools,
            "llm_tools": llm_tools,
            "executor": executor,
            "conversation": conversation,
            "message_service": message_service,
            "ai_service": ai_service,
            "messages": messages,
            "info": info,
        }

    @classmethod
    async def chat_with_tools(
        cls,
        user_id: str,
        content: str,
        session: AsyncSession,
        info: Any,
        conversation_id: Optional[str] = None,
        page_context: Optional[PageContextModel] = None,
        max_tool_iterations: int = 10,
    ) -> Dict[str, Any]:
        """
        Send a message with tool execution support (agent loop).

        Handles tool loading, system prompt building, and tool execution internally.

        Args:
            user_id: User ID
            content: User message content
            session: Database session
            info: GraphQL info context
            conversation_id: Optional conversation ID to continue
            page_context: Optional page context for tool filtering and param injection
            max_tool_iterations: Maximum number of tool call iterations

        Returns:
            Dict with content, conversation_id, tool_calls_count, tool_results, frontend_actions
        """
        connected_user = info.context.connected_user
        ctx = await cls._prepare_chat_context(
            user_id, content, session, connected_user, info,
            conversation_id=conversation_id, page_context=page_context,
        )
        executor = ctx["executor"]
        conversation = ctx["conversation"]
        message_service = ctx["message_service"]
        ai_service = ctx["ai_service"]
        llm_tools = ctx["llm_tools"]
        messages = ctx["messages"]

        tool_results = []
        tool_calls_count = 0

        # Agent loop: call LLM, execute tools, repeat until no more tool calls
        for iteration in range(max_tool_iterations):
            start_time = time.perf_counter()
            response = await ai_service.chat_with_purpose(
                messages,
                AI_PURPOSE_CHATBOT,
                llm_tools if llm_tools else None
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Check if LLM wants to call tools
            tool_calls = response.tool_calls or []

            if not tool_calls:
                # No tool calls, save and return the response
                await message_service.create(
                    session,
                    conversation_id=conversation.id,
                    role=AIMessageRole.ASSISTANT.value,
                    content=response.content,
                    provider=response.provider,
                    model=response.model,
                    tokens_in=response.usage.get("prompt_tokens") if response.usage else None,
                    tokens_out=response.usage.get("completion_tokens") if response.usage else None,
                    latency_ms=latency_ms,
                )

                frontend_actions = list(getattr(info.context, "frontend_actions", []))

                result = {
                    "content": response.content,
                    "conversation_id": conversation.id,
                    "tool_calls_count": tool_calls_count,
                    "tool_results": tool_results,
                    "frontend_actions": frontend_actions if frontend_actions else None,
                }
                cls._process_response(result)
                return result

            # Execute tool calls
            tool_calls_count += len(tool_calls)

            # Add assistant message with tool calls to history
            assistant_msg = {
                "role": "assistant",
                "content": response.content,
                "tool_calls": tool_calls,
            }
            messages.append(assistant_msg)

            # Save assistant message with tool calls
            await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content=response.content,
                tool_calls=tool_calls,
                provider=response.provider,
                model=response.model,
                tokens_in=response.usage.get("prompt_tokens") if response.usage else None,
                tokens_out=response.usage.get("completion_tokens") if response.usage else None,
                latency_ms=latency_ms,
            )

            # Execute each tool and collect results
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                tool_call_id = tool_call.get("id", "")

                try:
                    tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    result = await executor.execute(
                        tool_name=tool_name,
                        arguments=tool_args,
                        context={"session": session, "info": info},
                    )
                    tool_results.append({
                        "tool_name": tool_name,
                        "result": str(result),
                        "success": True,
                    })

                    # Add tool result to messages
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    }
                    messages.append(tool_msg)

                    # Save tool result to DB
                    await message_service.add_tool_result(
                        conversation.id,
                        tool_call_id,
                        result if isinstance(result, dict) else {"result": result},
                        session,
                    )

                except Exception as e:
                    logger.error(f"Tool '{tool_name}' execution failed: {e}")
                    safe_error_msg = f"Tool '{tool_name}' failed to execute."
                    tool_results.append({
                        "tool_name": tool_name,
                        "result": safe_error_msg,
                        "success": False,
                    })

                    # Add error to messages (generic message for LLM)
                    error_tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"error": safe_error_msg}),
                    }
                    messages.append(error_tool_msg)

                    # Save error to DB
                    await message_service.add_tool_result(
                        conversation.id,
                        tool_call_id,
                        {"error": safe_error_msg},
                        session,
                    )

        # Max iterations reached
        frontend_actions = getattr(info.context, "frontend_actions", [])

        return {
            "content": "Maximum tool iterations reached. Please try a simpler request.",
            "conversation_id": conversation.id,
            "tool_calls_count": tool_calls_count,
            "tool_results": tool_results,
            "frontend_actions": frontend_actions if frontend_actions else None,
        }

    # ========== Streaming Agent Loop ==========

    @classmethod
    async def chat_with_tools_streaming(
        cls,
        user_id: str,
        content: str,
        session: "AsyncSession",
        connected_user: Dict[str, Any],
        access_token: str,
        conversation_id: Optional[str] = None,
        page_context: Optional[PageContextModel] = None,
        max_tool_iterations: int = 10,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming version of chat_with_tools. Yields SSE-formatted strings.

        Args:
            user_id: User ID
            content: User message content
            session: Database session
            connected_user: Connected user dict from JWT
            access_token: User's access token for tool execution
            conversation_id: Optional conversation ID to continue
            page_context: Optional page context
            max_tool_iterations: Maximum tool call iterations

        Yields:
            SSE-formatted event strings
        """
        # Defensive guard: these values should already be validated by UserAuthMiddleware,
        # but we verify them here in case this method is called from a non-middleware context.
        if not connected_user or not connected_user.get("sub"):
            raise ValueError("connected_user must contain a valid 'sub' claim")
        if not access_token:
            raise ValueError("access_token is required")

        # Build a shim info object for _get_tool_executor (expects info.context.access_token etc.)
        info = _StreamingInfo(connected_user=connected_user, access_token=access_token)

        ctx = await cls._prepare_chat_context(
            user_id, content, session, connected_user, info,
            conversation_id=conversation_id, page_context=page_context,
        )
        executor = ctx["executor"]
        conversation = ctx["conversation"]
        message_service = ctx["message_service"]
        ai_service = ctx["ai_service"]
        llm_tools = ctx["llm_tools"]
        messages = ctx["messages"]

        tool_results = []
        tool_calls_count = 0

        # Agent loop
        for iteration in range(max_tool_iterations):
            accumulated_content = ""
            tool_calls_accumulator: Dict[int, Dict[str, Any]] = {}
            last_finish_reason = None
            last_usage = None
            last_model = None
            last_provider = None

            try:
                async for chunk in ai_service.chat_stream_with_purpose(
                    messages, AI_PURPOSE_CHATBOT, llm_tools if llm_tools else None
                ):
                    # Yield token events for text content
                    if chunk.content:
                        accumulated_content += chunk.content
                        yield _format_sse("token", {"content": chunk.content})

                    # Accumulate tool calls from partial chunks
                    if chunk.tool_calls:
                        _accumulate_tool_calls(tool_calls_accumulator, chunk.tool_calls)

                    if chunk.finish_reason:
                        last_finish_reason = chunk.finish_reason
                    if chunk.usage:
                        last_usage = chunk.usage
                    if chunk.model:
                        last_model = chunk.model
                    if chunk.provider:
                        last_provider = chunk.provider

            except Exception as e:
                logger.error(f"Streaming provider error: {e}")
                yield _format_sse("error", {
                    "message": "An error occurred while generating the response.",
                    "code": "PROVIDER_ERROR",
                })
                return

            # Build finalized tool_calls list from accumulator
            finalized_tool_calls = _finalize_tool_calls(tool_calls_accumulator)

            if not finalized_tool_calls:
                # No tool calls — final response
                await message_service.create(
                    session,
                    conversation_id=conversation.id,
                    role=AIMessageRole.ASSISTANT.value,
                    content=accumulated_content,
                    provider=last_provider,
                    model=last_model,
                    tokens_in=last_usage.get("prompt_tokens") if last_usage else None,
                    tokens_out=last_usage.get("completion_tokens") if last_usage else None,
                )

                frontend_actions = list(getattr(info.context, "frontend_actions", []))

                result = {
                    "conversationId": conversation.id,
                    "toolCallsCount": tool_calls_count,
                    "frontendActions": frontend_actions if frontend_actions else None,
                }
                cls._process_response({
                    "content": accumulated_content,
                    "conversation_id": conversation.id,
                    "tool_calls_count": tool_calls_count,
                    "tool_results": tool_results,
                    "frontend_actions": frontend_actions if frontend_actions else None,
                })
                yield _format_sse("done", result)
                return

            # Tool calls detected — execute them
            tool_calls_count += len(finalized_tool_calls)

            # Save assistant message with tool calls
            assistant_msg = {
                "role": "assistant",
                "content": accumulated_content,
                "tool_calls": finalized_tool_calls,
            }
            messages.append(assistant_msg)

            await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.ASSISTANT.value,
                content=accumulated_content,
                tool_calls=finalized_tool_calls,
                provider=last_provider,
                model=last_model,
                tokens_in=last_usage.get("prompt_tokens") if last_usage else None,
                tokens_out=last_usage.get("completion_tokens") if last_usage else None,
            )

            # Execute each tool
            for tool_call in finalized_tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                tool_call_id = tool_call.get("id", "")

                yield _format_sse("tool_start", {"name": tool_name, "arguments": tool_args_str})

                try:
                    tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    result = await executor.execute(
                        tool_name=tool_name,
                        arguments=tool_args,
                        context={"session": session, "info": info},
                    )
                    tool_results.append({
                        "tool_name": tool_name,
                        "result": str(result),
                        "success": True,
                    })

                    yield _format_sse("tool_result", {
                        "name": tool_name,
                        "result": result if isinstance(result, dict) else {"result": str(result)},
                        "success": True,
                    })

                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    }
                    messages.append(tool_msg)

                    await message_service.add_tool_result(
                        conversation.id, tool_call_id,
                        result if isinstance(result, dict) else {"result": result},
                        session,
                    )

                except Exception as e:
                    logger.error(f"Tool '{tool_name}' execution failed: {e}")
                    safe_error_msg = f"Tool '{tool_name}' failed to execute."
                    tool_results.append({
                        "tool_name": tool_name,
                        "result": safe_error_msg,
                        "success": False,
                    })

                    yield _format_sse("tool_result", {
                        "name": tool_name,
                        "result": {"error": safe_error_msg},
                        "success": False,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"error": safe_error_msg}),
                    })

                    await message_service.add_tool_result(
                        conversation.id, tool_call_id,
                        {"error": safe_error_msg}, session,
                    )

        # Max iterations reached
        yield _format_sse("error", {
            "message": "Maximum tool iterations reached.",
            "code": "MAX_ITERATIONS",
        })


# ========== Streaming Helpers ==========


class _StreamingContext:
    """Minimal context shim for streaming (replaces GraphQL info.context)."""

    def __init__(self, connected_user: Dict[str, Any], access_token: str):
        self.connected_user = connected_user
        self.access_token = access_token
        self.frontend_actions: List[Dict[str, Any]] = []


class _StreamingInfo:
    """Minimal info shim for streaming (replaces GraphQL info)."""

    def __init__(self, connected_user: Dict[str, Any], access_token: str):
        self.context = _StreamingContext(connected_user, access_token)


def _format_sse(event: str, data: Any) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _accumulate_tool_calls(accumulator: Dict[int, Dict[str, Any]], deltas: List[Dict[str, Any]]) -> None:
    """
    Merge partial tool call chunks into the accumulator.

    Mistral sends tool_calls as partial deltas with an index. Each chunk may contain:
    - id: tool call ID (usually in the first chunk)
    - function.name: tool name (usually in the first chunk)
    - function.arguments: partial argument string (concatenated across chunks)
    """
    for delta in deltas:
        idx = delta.get("index", 0)
        if idx not in accumulator:
            accumulator[idx] = {
                "id": delta.get("id", ""),
                "type": "function",
                "function": {"name": "", "arguments": ""},
            }
        entry = accumulator[idx]
        if delta.get("id"):
            entry["id"] = delta["id"]
        func = delta.get("function", {})
        if func.get("name"):
            entry["function"]["name"] = func["name"]
        if func.get("arguments"):
            entry["function"]["arguments"] += func["arguments"]


def _finalize_tool_calls(accumulator: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert accumulator dict to sorted list of finalized tool calls."""
    if not accumulator:
        return []
    return [accumulator[idx] for idx in sorted(accumulator.keys())]


@register_service()
class AIMessageService(EntityService[AIMessage]):
    """Service for managing AI messages."""

    @classmethod
    async def add_tool_result(
        cls,
        conversation_id: str,
        tool_call_id: str,
        result: Dict[str, Any],
        session: AsyncSession,
    ) -> "AIMessage":
        """
        Add a tool result message.

        Args:
            conversation_id: Conversation ID
            tool_call_id: ID of the tool call being responded to
            result: Tool execution result
            session: Database session

        Returns:
            AIMessage with tool result
        """
        return await cls.create(
            session,
            conversation_id=conversation_id,
            role=AIMessageRole.TOOL.value,
            tool_call_id=tool_call_id,
            tool_result=result,
        )


@register_service()
class AIMessageFeedbackService(EntityService[AIMessageFeedback]):
    """Service for managing AI message feedback."""

    @classmethod
    async def rate_message(
        cls,
        message_id: str,
        user_id: str,
        rating: AIFeedbackRating,
        session: AsyncSession,
        comment: Optional[str] = None,
    ):
        """Add or update a rating on a message."""
        feedback = await cls._get_or_create_feedback(message_id, user_id, session)
        feedback.rating = rating.value
        if comment is not None:
            feedback.comment = comment
        await session.flush()
        return feedback

    @classmethod
    async def add_comment(
        cls,
        message_id: str,
        user_id: str,
        comment: str,
        session: AsyncSession,
    ):
        """Add a comment to feedback."""
        feedback = await cls._get_or_create_feedback(message_id, user_id, session)
        feedback.comment = comment
        await session.flush()
        return feedback

    @classmethod
    async def _get_or_create_feedback(
        cls,
        message_id: str,
        user_id: str,
        session: AsyncSession,
    ):
        """Get existing feedback or create new one."""
        result = await session.execute(
            select(cls.entity_class).where(
                cls.entity_class.message_id == message_id,
                cls.entity_class.user_id == user_id,
            )
        )
        feedback = result.scalar_one_or_none()

        if not feedback:
            feedback = cls.entity_class(
                message_id=message_id,
                user_id=user_id,
            )
            session.add(feedback)

        return feedback