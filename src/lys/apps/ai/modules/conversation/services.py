"""
AI Conversation services.

Services for managing conversations and feedback.
"""

import json
import logging
import time
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any

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
from lys.apps.ai.modules.core.executors import GraphQLToolExecutor, LocalToolExecutor
from lys.apps.ai.modules.core.services import AIToolService
from lys.apps.ai.utils.guardrails import CONFIRM_ACTION_TOOL
from lys.apps.ai.utils.providers.config import parse_plugin_config
from lys.core.registries import register_service
from lys.core.services import EntityService
from lys.core.utils.routes import filter_routes_by_permissions, build_navigate_tool, load_routes_manifest

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
    ) -> str:
        """
        Build system prompt with user context.

        Args:
            session: Database session
            connected_user: Connected user from JWT
            chatbot_config: Chatbot configuration from plugin
            tools_count: Number of available tools

        Returns:
            System prompt string
        """
        system_prompt_parts = []

        # Add custom application system prompt if configured
        custom_system_prompt = chatbot_config.get("system_prompt") if isinstance(chatbot_config, dict) else None
        if custom_system_prompt:
            system_prompt_parts.append(custom_system_prompt)
            system_prompt_parts.append("")

        if connected_user:
            user_id = connected_user.get("sub", "unknown")
            is_super_user = connected_user.get("is_super_user", False)

            # Load user details from database
            user_details = await cls._get_user_details(session, user_id)

            system_prompt_parts.append("## User Context")
            if user_details:
                if user_details.get("email"):
                    system_prompt_parts.append(f"- Email: {user_details['email']}")
                if user_details.get("first_name") or user_details.get("last_name"):
                    name = f"{user_details.get('first_name', '')} {user_details.get('last_name', '')}".strip()
                    system_prompt_parts.append(f"- Name: {name}")
                if user_details.get("status"):
                    system_prompt_parts.append(f"- Status: {user_details['status']}")
                if user_details.get("language_code"):
                    system_prompt_parts.append(f"- Language: {user_details['language_code']}")
            system_prompt_parts.append(f"- Super User: {'Yes' if is_super_user else 'No'}")
            system_prompt_parts.append(f"- User ID: {user_id}")

            # Add language instruction
            if user_details and user_details.get("language_code"):
                system_prompt_parts.append(
                    f"\n**Important: Always respond in the user's language ({user_details['language_code']}).**"
                )

            # Get user roles if not super user
            if not is_super_user:
                roles_info = await cls._get_user_roles_info(session, user_id)
                if roles_info:
                    system_prompt_parts.append("\n## User Roles")
                    for role in roles_info:
                        role_line = f"- {role['code']}"
                        if role.get("description"):
                            role_line += f": {role['description']}"
                        system_prompt_parts.append(role_line)

            system_prompt_parts.append(f"\n## Available Tools: {tools_count}")
        else:
            system_prompt_parts.append("## User Context")
            system_prompt_parts.append("- Anonymous user (not authenticated)")
            system_prompt_parts.append(f"\n## Available Tools: {tools_count} (public only)")

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
    ):
        """
        Get the appropriate tool executor based on configuration.

        Args:
            tools: Available tool definitions
            info: GraphQL info context
            accessible_routes: List of routes accessible to the user for navigation

        Returns:
            Configured tool executor instance (GraphQLToolExecutor or LocalToolExecutor)
        """
        app_manager = cls.app_manager
        plugin_config = app_manager.settings.get_plugin_config("ai")
        ai_config = parse_plugin_config(plugin_config)

        if ai_config.executor.mode == "graphql":
            # Use Bearer token from user's JWT if available (user-authenticated calls)
            # Otherwise fall back to Service auth (inter-service calls)
            bearer_token = info.context.access_token if info.context else None

            if bearer_token:
                executor = GraphQLToolExecutor(
                    gateway_url=ai_config.executor.gateway_url,
                    bearer_token=bearer_token,
                    timeout=ai_config.executor.timeout,
                )
            else:
                executor = GraphQLToolExecutor(
                    gateway_url=ai_config.executor.gateway_url,
                    secret_key=app_manager.settings.secret_key,
                    service_name=ai_config.executor.service_name or app_manager.settings.service_name,
                    timeout=ai_config.executor.timeout,
                )
            await executor.initialize(tools=tools, accessible_routes=accessible_routes)
            return executor
        else:
            # Local mode
            executor = LocalToolExecutor(app_manager=app_manager)
            await executor.initialize(tools=tools, info=info, accessible_routes=accessible_routes)
            return executor

    @classmethod
    async def chat_with_tools(
        cls,
        user_id: str,
        content: str,
        session: AsyncSession,
        info: Any,
        conversation_id: Optional[str] = None,
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
            max_tool_iterations: Maximum number of tool call iterations

        Returns:
            Dict with content, conversation_id, tool_calls_count, tool_results, frontend_actions
        """
        app_manager = cls.app_manager
        connected_user = info.context.connected_user

        # Get tools via AIToolService filtered by JWT claims
        # Note: Tools are lazy-loaded once and cached at class level, only filtering is done here
        # For super_users, all tools are returned (see AIToolService.get_accessible_tools)
        tools = await AIToolService.get_accessible_tools(connected_user)

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

        # Build system prompt
        # TODO: Optimize - consider caching system prompt per conversation_id to avoid
        # 2 DB queries (user details + roles) on every message
        system_prompt = await cls._build_system_prompt(
            session, connected_user, chatbot_config, len(tools)
        )

        # Get the appropriate executor based on config
        executor = await cls._get_tool_executor(tools, info, accessible_routes)

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

                frontend_actions = getattr(info.context, "frontend_actions", [])

                return {
                    "content": response.content,
                    "conversation_id": conversation.id,
                    "tool_calls_count": tool_calls_count,
                    "tool_results": tool_results,
                    "frontend_actions": frontend_actions if frontend_actions else None,
                }

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
                    error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                    logger.error(error_msg)
                    tool_results.append({
                        "tool_name": tool_name,
                        "result": error_msg,
                        "success": False,
                    })

                    # Add error to messages
                    error_tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"error": error_msg}),
                    }
                    messages.append(error_tool_msg)

                    # Save error to DB
                    await message_service.add_tool_result(
                        conversation.id,
                        tool_call_id,
                        {"error": error_msg},
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