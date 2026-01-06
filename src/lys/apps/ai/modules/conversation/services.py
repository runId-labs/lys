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
from lys.apps.ai.utils.providers.config import parse_plugin_config
from lys.core.registries import register_service
from lys.core.services import EntityService

logger = logging.getLogger(__name__)


@register_service()
class AIConversationService(EntityService[AIConversation]):
    """Service for managing AI conversations."""

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
    async def _get_tool_executor(cls, tools: List[Dict[str, Any]], info: Any):
        """
        Get the appropriate tool executor based on configuration.

        Args:
            tools: Available tool definitions
            info: GraphQL info context

        Returns:
            Configured tool executor instance (GraphQLToolExecutor or LocalToolExecutor)
        """
        app_manager = cls.app_manager
        plugin_config = app_manager.settings.get_plugin_config("ai")
        ai_config = parse_plugin_config(plugin_config)

        if ai_config.executor.mode == "graphql":
            executor = GraphQLToolExecutor(
                gateway_url=ai_config.executor.gateway_url,
                secret_key=app_manager.settings.secret_key,
                service_name=ai_config.executor.service_name or app_manager.settings.service_name,
                timeout=ai_config.executor.timeout,
            )
            await executor.initialize(tools=tools)
            return executor
        else:
            # Local mode
            executor = LocalToolExecutor(app_manager=app_manager)
            await executor.initialize(tools=tools, info=info)
            return executor

    @classmethod
    async def chat_with_tools(
        cls,
        user_id: str,
        content: str,
        session: AsyncSession,
        tools: List[Dict[str, Any]],
        system_prompt: str,
        info: Any,
        conversation_id: Optional[str] = None,
        max_tool_iterations: int = 10,
    ) -> Dict[str, Any]:
        """
        Send a message with tool execution support (agent loop).

        Args:
            user_id: User ID
            content: User message content
            session: Database session
            tools: Available tool definitions
            system_prompt: System prompt with user context
            info: GraphQL info context
            conversation_id: Optional conversation ID to continue
            max_tool_iterations: Maximum number of tool call iterations

        Returns:
            Dict with content, conversation_id, tool_calls_count, tool_results, frontend_actions
        """
        # Get the appropriate executor based on config
        executor = await cls._get_tool_executor(tools, info)

        conversation = await cls.get_or_create(user_id, session, conversation_id)
        message_service = cls.app_manager.get_service("ai_messages")
        ai_service = cls.app_manager.get_service("ai")

        # Extract tool definitions for LLM (tools may contain operation_type metadata)
        llm_tools = []
        if tools:
            for tool in tools:
                if isinstance(tool, dict) and "definition" in tool:
                    llm_tools.append(tool["definition"])
                else:
                    llm_tools.append(tool)

        # Build messages with system prompt and history
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