import strawberry

from lys.apps.base.modules.ai.inputs import AIMessageInput
from lys.apps.base.modules.ai.nodes import AIMessageNode
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registers import register_mutation
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
        options={"generate_tool": False}  # Don't generate tool for this meta-endpoint
    )
    async def send_ai_message(
        self,
        inputs: AIMessageInput,
        info: Info
    ) -> AIMessageNode:
        """
        Send a message to the AI assistant and get a response.

        This endpoint:
        1. Gets the user's available tools from context
        2. Builds the system prompt with user context
        3. Sends the message to the configured LLM
        4. Executes any tool calls requested by the LLM
        5. Returns the final response

        Args:
            inputs: Input containing the user message and optional conversation ID
            info: GraphQL context with AI tools and system prompt

        Returns:
            AIMessageNode with the AI response and tool execution details
        """
        input_data = inputs.to_pydantic()

        # Get AI context set by AIContextExtension
        ai_tools = getattr(info.context, "ai_tools", [])
        ai_system_prompt = getattr(info.context, "ai_system_prompt", "")

        if not ai_tools and not ai_system_prompt:
            return AIMessageNode(
                content="AI is not configured or you don't have access to any tools.",
                conversation_id=input_data.conversation_id,
                tool_calls_count=0,
                tool_results=[]
            )

        # Get AI service
        ai_service = info.context.app_manager.get_service("ai")

        # Call AI service
        result = await ai_service.chat(
            message=input_data.message,
            tools=ai_tools,
            system_prompt=ai_system_prompt,
            session=info.context.session,
            info=info,
            conversation_id=input_data.conversation_id
        )

        # Convert tool results to Strawberry types
        tool_results = None
        if result.get("tool_results"):
            from lys.apps.base.modules.ai.inputs import AIToolResult
            tool_results = [
                AIToolResult(
                    tool_name=tr["tool_name"],
                    result=tr["result"],
                    success=tr["success"]
                )
                for tr in result["tool_results"]
            ]

        return AIMessageNode(
            content=result["content"],
            conversation_id=result.get("conversation_id"),
            tool_calls_count=result["tool_calls_count"],
            tool_results=tool_results
        )
