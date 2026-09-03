"""
AI Conversation webservices.

GraphQL queries and mutations for AI conversation interactions.
"""

from datetime import datetime, UTC
from typing import Optional

import strawberry
from sqlalchemy import Select, select
from sqlalchemy.orm import noload
from strawberry import relay

from lys.apps.ai.modules.conversation.consts import AIMessageRole
from lys.apps.ai.modules.conversation.entities import AIConversation
from lys.apps.ai.modules.conversation.inputs import (
    AIMessageInput,
    AIToolResult,
    FrontendAction,
    UpdateAIConversationTitleInput,
)
from lys.apps.ai.modules.conversation.nodes import (
    AIConversationMessageNode,
    AIConversationNode,
    AIMessageNode,
)
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_mutation, register_query
from lys.core.graphql.types import Mutation, Query


@strawberry.type
@register_query()
class AIConversationQuery(Query):
    """GraphQL queries for AI conversations."""

    @lys_connection(
        AIConversationNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="List AI conversations, newest first - active ones by default, the archive "
                    "alone with archived=true, both with archived=null. Restricted to the "
                    "connected user's own conversations unless a role grants full access.",
        options={"generate_tool": False},
    )
    async def all_ai_conversations(
        self,
        info: Info,
        user_id: Optional[relay.GlobalID] = None,
        purpose: Optional[str] = None,
        archived: Optional[bool] = False,
    ) -> Select:
        """
        List AI conversations.

        Scoping is declarative and combines with OR: OWNER access applies
        AIConversation.user_accessing_filters (own conversations only), while ROLE
        access returns every conversation. The user_id argument narrows a
        full-access listing to one user; it cannot widen an owner-scoped one.

        Args:
            info: GraphQL context
            user_id: If set, restrict to this user's conversations. Only meaningful
                with full access - an owner-scoped caller is already limited to itself.
            purpose: If set, restrict to conversations opened for this purpose
                (e.g. "chatbot"). Null → every purpose.
            archived: False (default) lists the active conversations, True lists only the
                archived ones, null lists both. Archiving exists to set a conversation
                aside, so browsing the archive shows the archive alone - mixing the active
                ones back in would scatter what was filed away among what was not.
        """
        entity = info.context.app_manager.get_entity("ai_conversation")

        # The messages relation is selectin-loaded for the chat flow; a listing must not
        # drag every message of every conversation along with it.
        stmt = (
            select(entity)
            .options(noload(entity.messages))
            .order_by(entity.created_at.desc(), entity.id.desc())
        )

        if user_id is not None:
            stmt = stmt.where(entity.user_id == user_id.node_id)

        if purpose is not None:
            stmt = stmt.where(entity.purpose == purpose)

        if archived is not None:
            stmt = stmt.where(
                entity.archived_at.isnot(None) if archived else entity.archived_at.is_(None)
            )

        return stmt


@strawberry.type
@register_query()
class AIConversationMessageQuery(Query):
    """GraphQL queries for the stored messages of a conversation."""

    @lys_connection(
        AIConversationMessageNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Replay the messages of a conversation, oldest first.",
        options={"generate_tool": False},
    )
    async def all_ai_conversation_messages(
        self,
        info: Info,
        conversation_id: relay.GlobalID,
    ) -> Select:
        """
        Replay one conversation's messages, in the order they were exchanged.

        Ownership is enforced declaratively: OWNER access applies
        AIMessage.user_accessing_filters, which resolves ownership through the parent
        conversation, so passing another user's conversation_id yields nothing.

        Only the exchanged turns are returned. Tool rows and the tool-call-only
        assistant rows carry the machinery of an answer, not the answer itself: they
        are never shown to the user and would render as blank bubbles.

        Args:
            info: GraphQL context
            conversation_id: Conversation whose messages are replayed.
        """
        entity = info.context.app_manager.get_entity("ai_message")

        return (
            select(entity)
            .where(
                entity.conversation_id == conversation_id.node_id,
                entity.role.in_([AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value]),
                entity.content.isnot(None),
                entity.content != "",
            )
            .order_by(entity.created_at, entity.id)
        )


@register_mutation()
@strawberry.type
class AIConversationMutation(Mutation):
    """GraphQL mutations for AI conversations."""

    @lys_edition(
        ensure_type=AIConversationNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Rename a conversation. Required: id (conversation ID), inputs.title (new title).",
        options={"generate_tool": False},
    )
    async def update_ai_conversation_title(
        self,
        obj: AIConversation,
        inputs: UpdateAIConversationTitleInput,
        info: Info,
    ):
        """
        Rename a conversation.

        Ownership is enforced by lys_edition, which resolves the conversation and runs
        the OWNER check before this body: a user renames only their own conversations.

        Args:
            obj: AIConversation entity (fetched and validated by lys_edition)
            inputs: Input containing the new title
            info: GraphQL context

        Returns:
            AIConversation: the renamed conversation
        """
        obj.title = inputs.to_pydantic().title

        return obj

    @lys_edition(
        ensure_type=AIConversationNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Archive a conversation, hiding it from the default listing. Required: id.",
        options={"generate_tool": False},
    )
    async def archive_ai_conversation(self, obj: AIConversation, info: Info):
        """
        Archive a conversation.

        Archiving is reversible and keeps the messages: the conversation drops out of
        the default listing, and unarchive_ai_conversation brings it back.

        Idempotent: archiving an already-archived conversation leaves the original date
        untouched, because that date records when it was archived. Overwriting it on a
        second call - a double click, a retry - would lose that fact silently, and
        raising instead would turn a harmless repeat into an error the client must handle.

        Args:
            obj: AIConversation entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            AIConversation: the archived conversation
        """
        if obj.archived_at is None:
            obj.archived_at = datetime.now(UTC)

        return obj

    @lys_edition(
        ensure_type=AIConversationNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Restore an archived conversation to the default listing. Required: id.",
        options={"generate_tool": False},
    )
    async def unarchive_ai_conversation(self, obj: AIConversation, info: Info):
        """
        Restore an archived conversation.

        Args:
            obj: AIConversation entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            AIConversation: the restored conversation
        """
        obj.archived_at = None

        return obj


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
        conversation_service = info.context.app_manager.get_service("ai_conversation")

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