"""
Whiteboard service: the only place a scene is written.

Everything the caller cannot be trusted with lives here — which board it is allowed to
touch, what a patch is allowed to do to the scene, and who is told afterwards. The scene
rules themselves are in ``scene.py``, without a session, so they can be exercised on
their own.
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import event, select, update

from lys.apps.ai_whiteboard.errors import WHITEBOARD_NOT_FOUND, WHITEBOARD_REVISION_CONFLICT
from lys.apps.ai_whiteboard.modules.whiteboard import scene as scene_tools
from lys.apps.ai_whiteboard.modules.whiteboard.consts import (
    DEFAULT_MAX_SCENE_BYTES,
    DEFAULT_TITLE,
    MAX_SCENE_BYTES_SETTING,
    PLUGIN_NAME,
    TITLE_MAX_LENGTH,
    USER_CHANNEL_TEMPLATE,
    WHITEBOARD_NODE_NAME,
    WHITEBOARD_UPDATED_SIGNAL,
)
from lys.apps.ai_whiteboard.modules.whiteboard.entities import Whiteboard
from lys.core.errors import LysError
from lys.core.graphql.client import build_global_id
from lys.core.registries import register_service
from lys.core.services import EntityService

logger = logging.getLogger(__name__)


@register_service()
class WhiteboardService(EntityService[Whiteboard]):
    """
    Reads and writes whiteboards, and tells the owner's browser when one moved.

    Every read here goes through the owner: a board id is the only thing a chatbot tool
    receives from a model, and a model can repeat an id from an earlier turn or invent
    one outright. Filtering on the owner at the query makes that a miss rather than a
    leak, without any caller having to remember.
    """

    # ==================== Reads ====================

    @classmethod
    async def get_for_user(cls, whiteboard_id: str, user_id: str, session) -> Optional[Whiteboard]:
        """
        One board, if it belongs to this user. None otherwise — never "forbidden".

        An id that is not a UUID is a miss too: it comes from a model, and handing it to
        the database would raise and abort the transaction of the whole turn.
        """
        try:
            uuid.UUID(str(whiteboard_id))
        except ValueError:
            return None
        result = await session.execute(
            select(cls.entity_class).where(
                cls.entity_class.id == whiteboard_id,
                cls.entity_class.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    def describe(cls, whiteboard: Whiteboard) -> List[Dict[str, Any]]:
        """What is on a board, in the terms its writer used to draw it."""
        return scene_tools.describe(whiteboard.scene_json or scene_tools.empty_scene())

    # ==================== Target resolution ====================

    @classmethod
    async def resolve_for_conversation(
        cls,
        conversation: Any,
        session,
        whiteboard_id: Optional[str] = None,
    ) -> Whiteboard:
        """
        Pick the board a tool call is about, and open one if the conversation has none.

        Named target wins; otherwise it is **always** the conversation's own board, never
        whatever the user happens to be looking at. A focused board is reachable, but only
        when the caller names it — so writing on the user's own board stays something that
        was asked for, not an ambient side effect of asking a question.

        A named board that is not this user's is refused with ``WHITEBOARD_NOT_FOUND``, the
        same answer whether it exists or not. It is not redirected to the conversation's
        own board: the model would believe it drew where it asked and the drawing would be
        somewhere else.

        Args:
            conversation: The AIConversation of the current turn.
            session: The session of the request.
            whiteboard_id: The board the caller named, if any.

        Returns:
            The board to write on, already attached to the conversation.

        Raises:
            LysError: A board was named and is not the user's.
        """
        if whiteboard_id:
            named = await cls.get_for_user(whiteboard_id, conversation.user_id, session)
            if named is None:
                logger.warning(f"Whiteboard '{whiteboard_id}' is not reachable for user '{conversation.user_id}'")
                raise LysError(WHITEBOARD_NOT_FOUND, f"Whiteboard '{whiteboard_id}' does not exist")
            return named

        # A pointer can outlive the board it names: whiteboard_id carries no foreign key,
        # and a board deleted elsewhere in the same session would leave it dangling. A
        # dead pointer opens a new board rather than failing the turn.
        if conversation.whiteboard_id:
            own = await cls.get_for_user(conversation.whiteboard_id, conversation.user_id, session)
            if own is not None:
                return own

        return await cls.open_for_conversation(conversation, session)

    @classmethod
    async def open_for_conversation(cls, conversation: Any, session) -> Whiteboard:
        """
        Open the conversation's board and point the conversation at it.

        The title is the conversation's. It is nullable there — a background task writes
        it after the first exchange — so a board opened before that falls back rather than
        leaving the column empty, which it refuses anyway.
        """
        whiteboard = cls.entity_class(
            user_id=conversation.user_id,
            title=(conversation.title or DEFAULT_TITLE)[:TITLE_MAX_LENGTH],
            scene_json=scene_tools.empty_scene(),
            revision=1,
        )
        session.add(whiteboard)
        await session.flush()

        conversation.whiteboard_id = whiteboard.id
        session.add(conversation)
        await session.flush()

        cls._notify(whiteboard, session)
        return whiteboard

    # ==================== Writes ====================

    @classmethod
    async def _lock(cls, whiteboard: Whiteboard, session) -> Whiteboard:
        """
        Reload a board under a row lock, so the read-modify-write that follows is serial.

        The revision comparison and the scene rebuild are Python: without the lock two
        writers (the browser saving, the model drawing) can both read revision N and both
        write N+1, the second silently replacing the first. ``populate_existing`` matters -
        the instance the caller holds may predate the lock, and a lock taken over a stale
        copy protects nothing.
        """
        result = await session.execute(
            select(cls.entity_class)
            .where(cls.entity_class.id == whiteboard.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()

    @classmethod
    def _max_scene_bytes(cls) -> int:
        """Size limit of a scene saved by the editor, from the plugin settings."""
        config = cls.app_manager.settings.get_plugin_config(PLUGIN_NAME) or {}
        return int(config.get(MAX_SCENE_BYTES_SETTING, DEFAULT_MAX_SCENE_BYTES))

    @classmethod
    async def apply_operations(
        cls,
        whiteboard: Whiteboard,
        operations: Dict[str, Any],
        session,
    ) -> Whiteboard:
        """
        Apply a patch to a board's scene.

        The scene is rebuilt in full by ``scene.apply_operations``, which raises before
        touching anything if one operation is invalid — so a patch is drawn whole or not
        at all, and a caller never leaves half an idea on the board.

        No expected revision here, unlike :meth:`save_scene`: the row is locked and re-read
        before the patch is applied, so the patch always lands on the latest scene rather
        than on the one the caller happened to hold. The revision it produces is what lets
        the browser notice.
        """
        whiteboard = await cls._lock(whiteboard, session)
        current = whiteboard.scene_json or scene_tools.empty_scene()
        whiteboard.scene_json = scene_tools.apply_operations(current, operations)
        whiteboard.revision = (whiteboard.revision or 0) + 1
        session.add(whiteboard)
        await session.flush()

        cls._notify(whiteboard, session)
        return whiteboard

    @classmethod
    async def save_scene(
        cls,
        whiteboard: Whiteboard,
        new_scene: Dict[str, Any],
        expected_revision: int,
        session,
    ) -> Whiteboard:
        """
        Replace a scene wholesale — what the editor sends after a manual edit.

        ``expected_revision`` is the revision the editor had when the user started
        drawing. A mismatch means something was written in between, and the only honest
        answer is to refuse: the incoming scene was built on a board that no longer
        exists, and taking it would erase whatever it did not know about. The caller
        reloads and the user sees both.

        Raises:
            LysError: The scene is malformed or too large, or the board moved since the
                caller read it.
        """
        scene_tools.validate_scene(new_scene, cls._max_scene_bytes())

        whiteboard = await cls._lock(whiteboard, session)
        if expected_revision != whiteboard.revision:
            raise LysError(
                WHITEBOARD_REVISION_CONFLICT,
                f"Whiteboard is at revision {whiteboard.revision}, caller wrote from {expected_revision}",
            )

        whiteboard.scene_json = new_scene
        whiteboard.revision = (whiteboard.revision or 0) + 1
        session.add(whiteboard)
        await session.flush()

        cls._notify(whiteboard, session)
        return whiteboard

    @classmethod
    async def rename(cls, whiteboard: Whiteboard, title: str, session) -> Whiteboard:
        """Rename a board. Does not touch the scene, so the revision does not move."""
        whiteboard.title = title[:TITLE_MAX_LENGTH]
        session.add(whiteboard)
        await session.flush()
        return whiteboard

    @classmethod
    async def forget_everywhere(cls, whiteboard_id: str, session) -> None:
        """
        Clear the conversations pointing at a board that is about to disappear.

        ``ai_conversation.whiteboard_id`` carries no foreign key — it must not, the ai app
        cannot reference a table that only exists when this app is loaded — so nothing in
        the database would clear it. Left behind, the pointer survives as an id that
        resolves to nothing.

        Separate from :meth:`delete` because the GraphQL path cannot use it: ``lys_delete``
        removes the row itself once the resolver returns, so the mutation calls this and
        never the delete below. One rule, reachable from both.
        """
        conversation_entity = cls.app_manager.get_entity("ai_conversation")
        await session.execute(
            update(conversation_entity)
            .where(conversation_entity.whiteboard_id == whiteboard_id)
            .values(whiteboard_id=None)
        )

    @classmethod
    async def delete(cls, entity_id: str, session) -> bool:
        """Delete a board, and clear the conversations that pointed at it."""
        await cls.forget_everywhere(entity_id, session)
        return await super().delete(entity_id, session)

    # ==================== Notification ====================

    @classmethod
    def _notify(cls, whiteboard: Whiteboard, session) -> None:
        """
        Tell the owner's open editors that the board moved — **once the write lands**.

        Not sent here and now, and that distinction is the whole method. A flush makes a
        row visible to this transaction and to nobody else, while the browser answers the
        signal over a connection of its own. Published inside the transaction, the signal
        outruns the data: the client asks for a board the database will not admit exists
        yet, gets nothing back, and sits on a spinner for good — with no error anywhere,
        because nothing went wrong, it was merely early.

        The gap is not a millisecond either. A chatbot turn holds its session open for the
        whole streamed answer, so the commit can be a minute after the drawing.

        Hence a one-shot hook on the commit itself. A transaction that rolls back
        publishes nothing, which is the honest outcome: nothing happened.

        Best-effort past that point: a board written and a signal not delivered is a screen
        one refresh behind, while failing the write because Redis is down is lost work. The
        payload carries the id and the revision, never the scene — signals are not replayed,
        so a client that missed one must be able to see the gap and refetch.
        """
        pubsub = getattr(cls.app_manager, "pubsub", None)
        if not pubsub:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("No running loop: whiteboard signal skipped")
            return

        channel = USER_CHANNEL_TEMPLATE.format(user_id=whiteboard.user_id)
        params = {
            # A GlobalID: the receiver is a GraphQL client, and it feeds this straight
            # back into the query that reads the board.
            "whiteboardId": build_global_id(WHITEBOARD_NODE_NAME, whiteboard.id),
            "revision": whiteboard.revision,
        }
        whiteboard_id = whiteboard.id

        async def publish() -> None:
            try:
                await pubsub.publish(channel, WHITEBOARD_UPDATED_SIGNAL, params)
            except Exception as e:
                logger.warning(f"Whiteboard signal not published for '{whiteboard_id}': {e}")

        # The listeners run in the sync greenlet the async session drives, so they can only
        # schedule the publication, not await it. Each one withdraws the other: a rolled
        # back transaction must not leave a hook that publishes on the next, unrelated
        # commit of the same session.
        sync_session = session.sync_session

        def on_commit(_session) -> None:
            if event.contains(sync_session, "after_rollback", on_rollback):
                event.remove(sync_session, "after_rollback", on_rollback)
            loop.create_task(publish())

        def on_rollback(_session) -> None:
            if event.contains(sync_session, "after_commit", on_commit):
                event.remove(sync_session, "after_commit", on_commit)

        event.listen(sync_session, "after_commit", on_commit, once=True)
        event.listen(sync_session, "after_rollback", on_rollback, once=True)
