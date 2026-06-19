"""
AI Conversation services.

Services for managing conversations and feedback.
"""

import json
import logging
import time
from datetime import datetime, timedelta, UTC
from typing import AsyncGenerator, Optional, List, Dict, Any

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.ai.modules.conversation.consts import (
    AIFeedbackRating,
    AIMessageRole,
    AI_PURPOSE_CHATBOT,
    AI_PURPOSE_CONVERSATION_SUMMARY,
    DEFAULT_COMPACTION_PENDING_TTL_SECONDS,
    DEFAULT_COMPACTION_TOKEN_THRESHOLD,
    DEFAULT_COMPACTION_WINDOW_MESSAGES,
    DEFAULT_DYNAMIC_CONTEXT_HEADER,
    DEFAULT_SUMMARY_HEADER,
)
from lys.apps.ai.modules.conversation.entities import (
    AIConversation,
    AIMessage,
    AIMessageFeedback,
)
from lys.apps.ai.modules.conversation.models import PageContextModel
from lys.apps.ai.modules.core.executors import GraphQLToolExecutor
from lys.apps.ai.modules.core.services import AIToolService
from lys.apps.ai.tasks import summarize_conversation
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

    @staticmethod
    def _usage_fields(usage: Optional[Dict[str, Any]]) -> Dict[str, Optional[int]]:
        """Map a provider-normalized usage dict to AIMessage token columns."""
        usage = usage or {}
        return {
            "tokens_in": usage.get("prompt_tokens"),
            "tokens_out": usage.get("completion_tokens"),
            "cache_read_tokens": usage.get("cache_read_tokens"),
            "cache_write_tokens": usage.get("cache_write_tokens"),
        }

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

        message_service = cls.app_manager.get_service("ai_message")
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
            latency_ms=latency_ms,
            **cls._usage_fields(response.usage),
        )

        return assistant_message

    @classmethod
    async def _load_current_summary(
        cls,
        conversation_id: str,
        session: AsyncSession,
    ) -> Optional[Any]:
        """
        Return the latest completed compaction summary for a conversation, or None.

        The current summary is the most recent row with ``completed=True`` (an
        uncompleted row is an in-flight background task, not yet usable). Ordered
        by ``(created_at, id)`` descending — the id tie-break keeps ordering
        deterministic when two rows share a created_at.
        """
        summary_entity = cls.app_manager.get_entity("ai_conversation_summary")
        result = await session.execute(
            select(summary_entity)
            .where(
                summary_entity.conversation_id == conversation_id,
                summary_entity.completed.is_(True),
            )
            .order_by(summary_entity.created_at.desc(), summary_entity.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _render_summary_input(prev_summary: Optional[str], messages: List[Any]) -> str:
        """
        Render the previous summary + the new message slice into one prompt input.

        Labels are English scaffolding; the model is instructed (by the endpoint's system
        prompt) to write the summary in the conversation's own language. Tool results are
        omitted (often large); the assistant's textual answers carry the conclusions.
        """
        lines: List[str] = []
        if prev_summary:
            lines.append("# Existing summary")
            lines.append(prev_summary)
            lines.append("")
        lines.append("# New messages to fold in")
        for m in messages:
            if m.role == AIMessageRole.USER.value:
                lines.append(f"User: {m.content or ''}")
            elif m.role == AIMessageRole.ASSISTANT.value:
                if m.content:
                    lines.append(f"Assistant: {m.content}")
                if m.tool_calls:
                    names = ", ".join(
                        tc.get("function", {}).get("name") or tc.get("name", "")
                        for tc in m.tool_calls
                    )
                    if names:
                        lines.append(f"Assistant [used tools: {names}]")
        return "\n".join(lines)

    @classmethod
    def fill_summary(cls, session: Session, ai_service: Any, summary_id: str) -> None:
        """
        Fill a pending compaction summary row (background task body).

        SYNCHRONOUS — runs in the Celery worker on a sync session
        (``app_manager.database.get_sync_session``), the pattern used by the proven
        worker tasks; an async-session-in-asyncio.run path is avoided for reliability.

        Summarizes the messages from the previous summary boundary up to this row's
        boundary, merged with the previous summary (incremental), and marks the row
        completed. Does not commit — the caller owns the transaction.
        """
        summary_entity = cls.app_manager.get_entity("ai_conversation_summary")
        message_entity = cls.app_manager.get_entity("ai_message")

        row = session.get(summary_entity, summary_id)
        if row is None or row.completed:
            return

        # Previous completed summary (incremental merge) and its boundary.
        prev = session.execute(
            select(summary_entity)
            .where(
                summary_entity.conversation_id == row.conversation_id,
                summary_entity.completed.is_(True),
            )
            .order_by(summary_entity.created_at.desc(), summary_entity.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        prev_summary = prev.summary if prev else None
        prev_boundary = session.get(message_entity, prev.through_message_id) if prev else None
        boundary = session.get(message_entity, row.through_message_id)

        # Slice: messages after the previous boundary, up to and including this one.
        stmt = select(message_entity).where(message_entity.conversation_id == row.conversation_id)
        if prev_boundary is not None:
            stmt = stmt.where(
                tuple_(message_entity.created_at, message_entity.id)
                > (prev_boundary.created_at, prev_boundary.id)
            )
        if boundary is not None:
            stmt = stmt.where(
                tuple_(message_entity.created_at, message_entity.id)
                <= (boundary.created_at, boundary.id)
            )
        slice_messages = session.execute(
            stmt.order_by(message_entity.created_at, message_entity.id)
        ).scalars().all()

        if not slice_messages:
            # Nothing new to fold in (should not happen) — keep the prior text, complete.
            row.summary = prev_summary or ""
            row.completed = True
            session.add(row)
            return

        response = ai_service.chat_with_purpose_sync(
            [{"role": "user", "content": cls._render_summary_input(prev_summary, slice_messages)}],
            AI_PURPOSE_CONVERSATION_SUMMARY,
        )

        row.summary = response.content
        row.model = response.model
        row.completed = True
        for field, value in cls._usage_fields(response.usage).items():
            setattr(row, field, value)
        session.add(row)

    @classmethod
    async def discard_pending_summary(cls, session: AsyncSession, summary_id: str) -> None:
        """Delete an uncompleted summary row (async, request path) so a later turn re-enqueues."""
        summary_entity = cls.app_manager.get_entity("ai_conversation_summary")
        row = await session.get(summary_entity, summary_id)
        if row is not None and not row.completed:
            await session.delete(row)

    @classmethod
    def discard_pending_summary_sync(cls, session: Session, summary_id: str) -> None:
        """Sync variant of :meth:`discard_pending_summary` for the Celery worker error path."""
        summary_entity = cls.app_manager.get_entity("ai_conversation_summary")
        row = session.get(summary_entity, summary_id)
        if row is not None and not row.completed:
            session.delete(row)

    @staticmethod
    def _compute_compaction_boundary(messages: List[Any], window: int) -> Optional[Any]:
        """
        Pick the boundary message (last message to summarize) so that about `window` recent
        messages stay verbatim, snapped forward so the verbatim window begins on a user turn
        (never splitting a user -> assistant -> tool sequence). Returns None when there is
        nothing to compact (history within the window, or no clean frontier to snap to).
        """
        if len(messages) <= window:
            return None
        ideal_start = len(messages) - window
        # Snap forward to the next user message so the window starts on a turn frontier.
        for i in range(ideal_start, len(messages)):
            if messages[i].role == AIMessageRole.USER.value:
                return messages[i - 1] if i > 0 else None
        return None

    @classmethod
    async def maybe_enqueue_compaction(cls, conversation: "AIConversation", session: AsyncSession, usage: Any) -> None:
        """
        Best-effort: enqueue a background compaction when the last turn's prompt has grown
        past the configured token threshold and none is already pending. Never raises — a
        failure here must not break the turn.

        The trigger metric is the turn's real billed prompt size (input + cache read + cache
        write tokens), not a message count which a single large tool output would defeat.
        """
        try:
            fields = cls._usage_fields(usage)
            prompt_tokens = (
                (fields.get("tokens_in") or 0)
                + (fields.get("cache_read_tokens") or 0)
                + (fields.get("cache_write_tokens") or 0)
            )

            chatbot_config = (cls.app_manager.settings.get_plugin_config("ai") or {}).get("chatbot", {})
            compaction = chatbot_config.get("compaction", {})
            threshold = compaction.get("token_threshold", DEFAULT_COMPACTION_TOKEN_THRESHOLD)
            if prompt_tokens <= threshold:
                return

            summary_entity = cls.app_manager.get_entity("ai_conversation_summary")
            message_entity = cls.app_manager.get_entity("ai_message")

            # Concurrency guard: a recent pending summary blocks a second enqueue. A pending
            # row older than the TTL is treated as stale (worker died) and ignored.
            stale_before = datetime.now(UTC) - timedelta(seconds=DEFAULT_COMPACTION_PENDING_TTL_SECONDS)
            pending = (await session.execute(
                select(summary_entity).where(
                    summary_entity.conversation_id == conversation.id,
                    summary_entity.completed.is_(False),
                    summary_entity.created_at >= stale_before,
                ).limit(1)
            )).scalar_one_or_none()
            if pending is not None:
                return

            window = compaction.get("window_messages", DEFAULT_COMPACTION_WINDOW_MESSAGES)
            messages = (await session.execute(
                select(message_entity)
                .where(message_entity.conversation_id == conversation.id)
                .order_by(message_entity.created_at, message_entity.id)
            )).scalars().all()
            boundary = cls._compute_compaction_boundary(messages, window)
            if boundary is None:
                return

            # Skip if the boundary would not advance past the previous summary.
            prev = await cls._load_current_summary(conversation.id, session)
            if prev is not None:
                prev_boundary = await session.get(message_entity, prev.through_message_id)
                if prev_boundary is not None and (
                    (boundary.created_at, boundary.id) <= (prev_boundary.created_at, prev_boundary.id)
                ):
                    return

            row = summary_entity(
                conversation_id=conversation.id,
                through_message_id=boundary.id,
                completed=False,
            )
            session.add(row)
            # The worker runs in a separate session: the pending row must be committed before
            # it is enqueued. A later request-end commit is then a harmless no-op.
            await session.commit()

            try:
                summarize_conversation.delay(row.id)
            except Exception:
                # Broker enqueue failed: drop the lock so a later turn retries.
                await cls.discard_pending_summary(session, row.id)
                await session.commit()
                raise
        except Exception as e:
            logger.warning(f"Compaction enqueue skipped for conversation {conversation.id}: {e}")

    @classmethod
    async def _build_messages(
        cls,
        conversation: "AIConversation",
        session: AsyncSession,
        current_summary: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build messages list from conversation history.

        When a compaction summary exists, only the messages after its boundary
        (``through_message_id``) are returned verbatim — the older messages are
        represented by the summary, injected separately as a system segment by the
        caller. A window edge that splits a tool_call/tool_result pair is harmless:
        the sanitizer drops orphan tool results and pairs any unmatched tool_calls.
        """
        message_entity = cls.app_manager.get_entity("ai_message")
        stmt = select(message_entity).where(message_entity.conversation_id == conversation.id)

        if current_summary is not None:
            boundary = await session.get(message_entity, current_summary.through_message_id)
            if boundary is not None:
                # Strictly after the boundary, matching the (created_at, id) ordering.
                stmt = stmt.where(
                    tuple_(message_entity.created_at, message_entity.id)
                    > (boundary.created_at, boundary.id)
                )

        result = await session.execute(
            stmt.order_by(message_entity.created_at, message_entity.id)
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
        page_behaviour: Optional[Dict[str, Any]] = None,
        context_data: Optional[Dict[str, str]] = None,
        conversation_summary: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build the system prompt as ordered cacheable / volatile segments.

        Args:
            page_behaviour: Optional page-specific chatbot behaviour from manifest
            context_data: Optional context data from executing context_tools

        Returns:
            Ordered list of {"content", "cache"} segments. The base prompt is injected
            separately by the AIService entry point (endpoint.system_prompt). The page
            prompt is stable per page (cacheable); the compaction summary and the per-turn
            context are volatile and marked uncached, so a provider can place the cache
            breakpoint between the stable prefix and the volatile tail and stop the tail
            from busting the stable prefix. Segment headers default to English and are
            overridable via the ai plugin config (chatbot.summary_header /
            chatbot.dynamic_context_header).
        """
        chatbot_config = (cls.app_manager.settings.get_plugin_config("ai") or {}).get("chatbot", {})
        summary_header = chatbot_config.get("summary_header", DEFAULT_SUMMARY_HEADER)
        dynamic_context_header = chatbot_config.get(
            "dynamic_context_header", DEFAULT_DYNAMIC_CONTEXT_HEADER
        )

        segments: List[Dict[str, Any]] = []

        # Page-specific prompt — stable per page → cacheable.
        if page_behaviour and page_behaviour.get("prompt"):
            segments.append({"content": page_behaviour["prompt"], "cache": True})

        # Compaction summary of older turns — volatile (changes on each re-summary) →
        # not cached. Placed after the cacheable page prefix, before the per-turn context.
        if conversation_summary:
            segments.append({
                "content": f"{summary_header}\n{conversation_summary}",
                "cache": False,
            })

        # Per-turn context from context_tools — volatile → not cached.
        if context_data:
            parts = [dynamic_context_header]
            for label, data in context_data.items():
                parts.append(f"\n### {label}")
                parts.append(data)
            segments.append({"content": "\n".join(parts), "cache": False})

        return segments

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
                    access_token = info.context.access_token if info.context else None
                    if not access_token:
                        logger.warning("[ContextTools] No access_token available, skipping context tools")
                    else:
                        context_tool_service = app_manager.get_service("context_tool")
                        context_data = await context_tool_service.execute_all(
                            context_tools,
                            session,
                            access_token,
                            **(page_context.params or {}),
                        )
                        logger.debug(
                            f"[ContextTools] Fetched data for {len(context_data)} labels"
                        )

        # Conversation + its current compaction summary, loaded before the system prompt
        # so the summary can be injected as a volatile system segment.
        conversation = await cls.get_or_create(user_id, session, conversation_id)
        current_summary = await cls._load_current_summary(conversation.id, session)

        # Build system prompt (cheap: only the summary load hits the DB; page prompt +
        # past-conversation summary + already-fetched context).
        system_segments = await cls._build_system_prompt(
            page_behaviour=page_behaviour,
            context_data=context_data,
            conversation_summary=current_summary.summary if current_summary else None,
        )
        logger.debug(f"[SystemPrompt] Built {len(system_segments)} segment(s)")

        # Get the appropriate executor based on config
        executor = await cls._get_tool_executor(tools, info, accessible_routes, page_context)

        message_service = app_manager.get_service("ai_message")
        ai_service = app_manager.get_service("ai")

        # Extract just the definitions for the LLM (tools contain operation_type metadata)
        llm_tools = [
            tool.get("definition", tool) if isinstance(tool, dict) and "definition" in tool else tool
            for tool in tools
        ]

        # Build messages with system prompt and history. When a compaction summary exists,
        # _build_messages returns only the verbatim window (messages after the summary
        # boundary); the older turns are carried by the summary system segment above.
        history = await cls._build_messages(conversation, session, current_summary=current_summary)
        # One system message per segment, carrying its cache flag. The base prompt is
        # prepended (uncached) by the AIService entry point; sitting before the cacheable
        # page segment, it is still covered by the breakpoint placed after that segment.
        messages = [
            {"role": "system", "content": seg["content"], "cache": seg["cache"]}
            for seg in system_segments
        ]

        # Add conversation history (filter out system messages)
        for msg in history:
            if msg.get("role") != "system":
                messages.append(msg)

        # Add new user message
        messages.append({"role": "user", "content": content})

        # Save user message to DB
        user_message = await message_service.create(
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
            "user_message_id": user_message.id,
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
                    latency_ms=latency_ms,
                    **cls._usage_fields(response.usage),
                )

                frontend_actions = list(getattr(info.context, "frontend_actions", []))

                result = {
                    "content": response.content,
                    "conversation_id": conversation.id,
                    "tool_calls_count": tool_calls_count,
                    "tool_results": tool_results,
                    "frontend_actions": frontend_actions if frontend_actions else None,
                }
                await cls.maybe_enqueue_compaction(conversation, session, response.usage)
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
                latency_ms=latency_ms,
                **cls._usage_fields(response.usage),
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

                    # Save error to DB (protected to avoid cascade failure)
                    try:
                        await message_service.add_tool_result(
                            conversation.id,
                            tool_call_id,
                            {"error": safe_error_msg},
                            session,
                        )
                    except Exception as db_err:
                        logger.error(f"Failed to save tool error to DB: {db_err}")

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
        user_message_id = ctx["user_message_id"]

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
                # Delete the orphaned user message to keep conversation history valid
                if iteration == 0:
                    try:
                        await message_service.delete(user_message_id, session)
                    except Exception as del_err:
                        logger.error(f"Failed to delete orphaned user message {user_message_id}: {del_err}")
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
                    **cls._usage_fields(last_usage),
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
                await cls.maybe_enqueue_compaction(conversation, session, last_usage)
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
                **cls._usage_fields(last_usage),
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

                    # Save error to DB (protected to avoid cascade failure)
                    try:
                        await message_service.add_tool_result(
                            conversation.id, tool_call_id,
                            {"error": safe_error_msg}, session,
                        )
                    except Exception as db_err:
                        logger.error(f"Failed to save tool error to DB: {db_err}")

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