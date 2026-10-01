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

#: Backends that take one writer at a time, so a board cannot be committed in a
#: transaction of its own while the caller still holds theirs.
SINGLE_WRITER_BACKENDS = ("sqlite",)


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
    async def find_for_conversation(
        cls,
        user_id: str,
        current_whiteboard_id: Optional[str],
        named_whiteboard_id: Optional[str],
        session,
    ) -> Optional[Whiteboard]:
        """
        The board a tool call is about, **without opening one**.

        Named target wins; otherwise it is the board the conversation already points at,
        never whatever the user happens to be looking at. A focused board is reachable,
        but only when the caller names it — so writing on the user's own board stays
        something that was asked for, not an ambient side effect of asking a question.

        A named board that is not this user's is refused with ``WHITEBOARD_NOT_FOUND``,
        the same answer whether it exists or not. It is not redirected to the
        conversation's own board: the model would believe it drew where it asked and the
        drawing would be somewhere else.

        Args:
            user_id: The owner every read is filtered on.
            current_whiteboard_id: The board the conversation points at, if any.
            named_whiteboard_id: The board the caller named, if any.
            session: The session to read through.

        Returns:
            The board to work on, or None when there is none to work on yet. Opening one
            is the caller's decision — a read must not make it.

        Raises:
            LysError: A board was named and is not this user's.
        """
        if named_whiteboard_id:
            named = await cls.get_for_user(named_whiteboard_id, user_id, session)
            if named is None:
                logger.warning(f"Whiteboard '{named_whiteboard_id}' is not reachable for user '{user_id}'")
                raise LysError(WHITEBOARD_NOT_FOUND, f"Whiteboard '{named_whiteboard_id}' does not exist")
            return named

        # A pointer can outlive the board it names: whiteboard_id carries no foreign key,
        # and a board deleted elsewhere would leave it dangling. A dead pointer reads as
        # no board rather than failing the turn.
        if current_whiteboard_id:
            return await cls.get_for_user(current_whiteboard_id, user_id, session)

        return None

    @classmethod
    async def resolve_for_conversation(
        cls,
        conversation: Any,
        session,
        whiteboard_id: Optional[str] = None,
    ) -> Whiteboard:
        """
        Pick the board a tool call is about, and open one if the conversation has none.

        Both the board and the pointer land in the caller's session, so this is the path
        for a caller whose transaction ends soon. A chatbot turn's does not — it must go
        through :meth:`draw`, which commits the board apart.

        Args:
            conversation: The AIConversation of the current turn.
            session: The session of the request.
            whiteboard_id: The board the caller named, if any.

        Returns:
            The board to write on, already attached to the conversation.

        Raises:
            LysError: A board was named and is not the user's.
        """
        whiteboard = await cls.find_for_conversation(
            conversation.user_id, conversation.whiteboard_id, whiteboard_id, session,
        )
        if whiteboard is not None:
            return whiteboard

        return await cls.open_for_conversation(conversation, session)

    @classmethod
    async def create_for_user(
        cls,
        user_id: str,
        title: Optional[str],
        session,
    ) -> Whiteboard:
        """
        Open an empty board for a user, attached to nothing.

        Whoever wanted it points at it: a conversation writes the pointer on its own row,
        in its own transaction, which is not this board's business.

        The title falls back because a conversation's is nullable — a background task
        writes it after the first exchange — and the column here refuses empty.
        """
        whiteboard = cls.entity_class(
            user_id=user_id,
            title=(title or DEFAULT_TITLE)[:TITLE_MAX_LENGTH],
            scene_json=scene_tools.empty_scene(),
            revision=1,
        )
        session.add(whiteboard)
        await session.flush()

        cls._notify(whiteboard, session)
        return whiteboard

    @classmethod
    async def open_for_conversation(cls, conversation: Any, session) -> Whiteboard:
        """
        Open the conversation's board and point the conversation at it.

        Both writes in the caller's session: the board is only visible to other
        connections once that session commits. See :meth:`resolve_for_conversation` for
        who may use this.
        """
        whiteboard = await cls.create_for_user(
            conversation.user_id, conversation.title, session,
        )

        conversation.whiteboard_id = whiteboard.id
        session.add(conversation)
        await session.flush()

        return whiteboard

    @classmethod
    def _can_commit_apart(cls) -> bool:
        """
        Whether a second transaction can write while the caller's is already open.

        On a single-writer backend it cannot: the caller's turn has written its own rows
        long before a tool runs, so a second transaction would wait for a lock the caller
        only releases once this call returns. That is a deadlock, not a slow query.
        """
        return cls.app_manager.database.settings.type not in SINGLE_WRITER_BACKENDS

    @classmethod
    async def draw(
        cls,
        *,
        user_id: str,
        title: Optional[str],
        current_whiteboard_id: Optional[str],
        named_whiteboard_id: Optional[str],
        operations: Dict[str, Any],
        caller_session,
        focus: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Apply a patch to a board, committed as soon as the backend allows.

        With no patch and a ``focus``, nothing is written: the owner's view is brought
        onto the named elements (see :meth:`show`). It travels the same way because it
        has the same constraint - the browser is told at the commit, and told at the end
        of a streamed answer it moves the view after the sentence that announced it.

        Why not simply the caller's session: a chatbot turn holds its session open for
        the whole streamed answer, and the browser is only told a board moved when the
        transaction commits (see :meth:`_notify`). Drawn in the turn's session, a board
        therefore appears AFTER the answer — the user hears the sentence naming it before
        seeing it. Committed apart, it appears when it was drawn, which is before the
        first word.

        What that trades: a board survives a turn that fails afterwards. A drawing nobody
        asked about is a far smaller wrong than an answer pointing at a drawing that is
        not there.

        On a single-writer backend the patch goes in the caller's session instead (see
        :meth:`_can_commit_apart`): the board then appears at the end of the turn, which
        is late but correct — the alternative is a turn that hangs on a lock.

        The pointer stays the caller's to write, in the caller's transaction: this board
        knows nothing of conversations. Returns what a tool has to hand back to the model
        — plain values, so nothing depends on a session that is closed by then.

        Args:
            user_id: The owner every read is filtered on.
            title: Title for a board opened here, when there is none to draw on.
            current_whiteboard_id: The board the caller already points at, if any.
            named_whiteboard_id: The board the model named, if any.
            operations: The patch, as :meth:`apply_operations` takes it. May be empty
                when ``focus`` is given.
            caller_session: The caller's session, used only where a second one cannot be.
            focus: Names of the elements to bring into the owner's view. Without it, a
                patch shows what it drew.

        Returns:
            The board id, its title and its elements, as plain values - and ``overlaps``
            when the patch left an element on top of another (see ``scene.overlaps``).

        Raises:
            LysError: A board was named and is not this user's, the patch is refused, or
                ``focus`` names something that is not on the board.
        """
        if not cls._can_commit_apart():
            return await cls._draw(
                user_id, title, current_whiteboard_id, named_whiteboard_id, operations, caller_session, focus=focus,
            )

        async with cls.app_manager.database.get_session() as session:
            return await cls._draw(
                user_id, title, current_whiteboard_id, named_whiteboard_id, operations, session, focus=focus,
            )

    @classmethod
    async def _draw(
        cls,
        user_id: str,
        title: Optional[str],
        current_whiteboard_id: Optional[str],
        named_whiteboard_id: Optional[str],
        operations: Dict[str, Any],
        session,
        focus: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve the target through one session, opening a board if there is none.

        Only a patch opens a board: showing something on a board that does not exist is
        refused, not answered with an empty one thrown open in front of the user.
        """
        whiteboard = await cls.find_for_conversation(
            user_id, current_whiteboard_id, named_whiteboard_id, session,
        )
        if whiteboard is None:
            if not operations:
                raise LysError(WHITEBOARD_NOT_FOUND, "There is no whiteboard to show yet: drawing on one opens it")
            whiteboard = await cls.create_for_user(user_id, title, session)

        if operations:
            await cls.apply_operations(whiteboard, operations, session, focus=focus)
        else:
            cls.show(whiteboard, focus, session)

        result: Dict[str, Any] = {
            "whiteboard_id": whiteboard.id,
            "title": whiteboard.title,
            "elements": cls.describe(whiteboard),
        }
        # What the patch put on top of something else. Reported, not refused: the caller
        # chose its coordinates before any size existed and cannot see the board, so the
        # drawing stands and the caller is told what to move. The key is absent when
        # there is nothing to say.
        if operations:
            found = scene_tools.overlaps(whiteboard.scene_json, scene_tools.drawn_names(operations))
            if found:
                result["overlaps"] = found
        return result

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
        focus: Optional[List[str]] = None,
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

        The browser is also told what to look at: ``focus`` when the caller named it,
        otherwise what the patch drew. A board grows away from where its owner is
        looking, and a drawing announced in the chat that landed off screen reads as
        nothing having happened. ``focus`` is checked against the scene the patch
        produces, before anything is written - so it may name what the same patch adds.
        """
        whiteboard = await cls._lock(whiteboard, session)
        current = whiteboard.scene_json or scene_tools.empty_scene()
        scene = scene_tools.apply_operations(current, operations)
        shown = scene_tools.resolve_focus(scene, focus) if focus else scene_tools.drawn_names(operations)

        whiteboard.scene_json = scene
        whiteboard.revision = (whiteboard.revision or 0) + 1
        session.add(whiteboard)
        await session.flush()

        cls._notify(whiteboard, session, focus=shown)
        return whiteboard

    @classmethod
    def show(cls, whiteboard: Whiteboard, names: Optional[List[str]], session) -> Whiteboard:
        """
        Bring elements of a board into its owner's view, without touching the board.

        Nothing is written and the revision does not move: the signal alone carries it,
        and an editor that is not open at that moment simply opens on those elements.

        Raises:
            LysError: A name that is not on the board.
        """
        shown = scene_tools.resolve_focus(whiteboard.scene_json or scene_tools.empty_scene(), names)
        cls._notify(whiteboard, session, focus=shown)
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
    def _notify(cls, whiteboard: Whiteboard, session, focus: Optional[List[str]] = None) -> None:
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

        ``focus`` rides along when there is something to look at: the names of the
        elements the editor should bring into view. An editor save sends none - the
        owner's other tabs follow the content, not the viewport of the one that drew.
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
        if focus:
            params["focus"] = list(focus)
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
