"""
AI Conversation webservices.

GraphQL mutations for AI conversation interactions.
"""

import strawberry

from lys.apps.ai.modules.conversation.inputs import AIMessageInput, AIToolResult, FrontendAction
from lys.apps.ai.modules.conversation.nodes import AIMessageNode
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_mutation
from lys.core.graphql.types import Mutation


@register_mutation()
@strawberry.type
class AIMutation(Mutation):
    @lys_field(
        ensure_type=AIMessageNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="Send a message to the AI assistant. Returns AI response with optional tool execution results.",
        options={"generate_tool": False}
    )
    async def send_ai_message(
        self,
        inputs: AIMessageInput,
        info: Info
    ) -> AIMessageNode:
        """
        Send a message to the AI assistant and get a response.

        Args:
            inputs: Input containing the user message and optional conversation ID
            info: GraphQL context

        Returns:
            AIMessageNode with the AI response and tool execution details
        """
        input_data = inputs.to_pydantic()

        # Get user ID from context
        user_id = info.context.connected_user.get("sub") if info.context.connected_user else None

        if not user_id:
            return AIMessageNode(
                content="User must be authenticated to use AI chat.",
                conversation_id=input_data.conversation_id,
                tool_calls_count=0,
                tool_results=[]
            )

        # Get conversation service
        conversation_service = info.context.app_manager.get_service("ai_conversations")

        # Initialize frontend_actions in context for collection during tool execution
        info.context.frontend_actions = []

        # Call conversation service (handles tools, system prompt internally)
        result = await conversation_service.chat_with_tools(
            user_id=user_id,
            content=input_data.message,
            session=info.context.session,
            info=info,
            conversation_id=input_data.conversation_id,
            page_context=input_data.context,
        )

        # Convert tool results to Strawberry types
        tool_results = None
        if result.get("tool_results"):
            tool_results = [
                AIToolResult(
                    tool_name=tr["tool_name"],
                    result=tr["result"],
                    success=tr["success"]
                )
                for tr in result["tool_results"]
            ]

        # Convert frontend actions to Strawberry types
        frontend_actions = None
        if result.get("frontend_actions"):
            frontend_actions = [
                FrontendAction(
                    type=fa["type"],
                    path=fa.get("path"),
                    params=fa.get("params"),
                    nodes=fa.get("nodes")
                )
                for fa in result["frontend_actions"]
            ]

        return AIMessageNode(
            content=result["content"],
            conversation_id=result.get("conversation_id"),
            tool_calls_count=result.get("tool_calls_count", 0),
            tool_results=tool_results,
            frontend_actions=frontend_actions
        )