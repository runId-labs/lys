"""
Whiteboard service: the only place a scene is written.

Everything the caller cannot be trusted with lives here — which board it is allowed to
touch, what a patch is allowed to do to the scene, and who is told afterwards. The scene
rules themselves are in ``scene.py``, without a session, so they can be exercised on
their own.
"""

import asyncio
import copy
import logging
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Update, event, select, update
from sqlalchemy.orm.attributes import set_committed_value

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

    @classmethod
    def theme(cls, whiteboard: Whiteboard) -> Dict[str, str]:
        """The board's look: background and default stroke."""
        return scene_tools.theme(whiteboard.scene_json or scene_tools.empty_scene())

    @classmethod
    def slides(cls, whiteboard: Whiteboard) -> List[Dict[str, Any]]:
        """The board's deck: its frames in the order they are presented."""
        return scene_tools.slides(whiteboard.scene_json or scene_tools.empty_scene())

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
    async def copy_for_user(
        cls,
        source: Whiteboard,
        title: Optional[str],
        session,
    ) -> Whiteboard:
        """
        Open a board as a copy of another, attached to nothing - "make a copy".

        A board serves as a template: the same deck next month, or for another company.
        The scene is copied whole, server side, so the copy keeps the layout, the charts
        and the slides exactly; redrawing it element by element would lose them. The copy
        starts its own life: revision 1, neither archived nor pinned - the source's
        filing is about the source.

        The copy belongs to the source's owner. Reaching the source is the caller's
        check (``get_for_user``): a board is never copied across users.

        Args:
            source: The board to copy, already checked to be the caller's.
            title: The copy's name; the source's when left out.
            session: The session of the request.

        Returns:
            The new board, flushed, its owner told it exists.
        """
        whiteboard = cls.entity_class(
            user_id=source.user_id,
            title=(title or source.title or DEFAULT_TITLE)[:TITLE_MAX_LENGTH],
            scene_json=copy.deepcopy(source.scene_json or scene_tools.empty_scene()),
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

        The board is born in step with the exchange that opened it: it takes the
        conversation's visibility flags, so a board drawn during an archived
        conversation starts archived too - otherwise it would escape both the sync
        (which only fires on an action) and the cleanup that follows the archive,
        and pile up with no one to file it away. A board opened by hand, or named by a
        later conversation, takes nothing: the flags are inherited at birth only.

        Args:
            conversation: The AIConversation of the current turn.
            session: The session of the request.

        Returns:
            The board to write on, already attached to the conversation.
        """
        whiteboard = await cls.create_for_user(
            conversation.user_id, conversation.title, session,
        )

        conversation.whiteboard_id = whiteboard.id
        session.add(conversation)

        await session.flush()

        if conversation.archived_at is not None:
            await cls._set_flag(whiteboard, "archived_at", conversation.archived_at, session)
        if conversation.pinned_at is not None:
            await cls._set_flag(whiteboard, "pinned_at", conversation.pinned_at, session)

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
        copy_from_whiteboard_id: Optional[str] = None,
        patches: Optional[List[Dict[str, Any]]] = None,
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
            copy_from_whiteboard_id: A board of the owner's to copy: the patch then
                lands on a NEW board opened as its copy (see :meth:`copy_for_user`),
                never on the source. ``title`` names the copy.
            patches: Several patches to apply in order, in place of ``operations`` - a
                drafted drawing (see ``drafting.py``): written as one revision.

        Returns:
            The board id, its title and its elements, as plain values - and ``overlaps``
            when the patch left an element on top of another (see ``scene.overlaps``).

        Raises:
            LysError: A board was named and is not this user's, the patch is refused, or
                ``focus`` names something that is not on the board.
        """
        if not cls._can_commit_apart():
            return await cls._draw(
                user_id, title, current_whiteboard_id, named_whiteboard_id, operations, caller_session,
                focus=focus, copy_from_whiteboard_id=copy_from_whiteboard_id, patches=patches,
            )

        async with cls.app_manager.database.get_session() as session:
            return await cls._draw(
                user_id, title, current_whiteboard_id, named_whiteboard_id, operations, session,
                focus=focus, copy_from_whiteboard_id=copy_from_whiteboard_id, patches=patches,
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
        copy_from_whiteboard_id: Optional[str] = None,
        patches: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve the target through one session, opening a board if there is none.

        Only a patch - or a copy - opens a board: showing something on a board that does
        not exist is refused, not answered with an empty one thrown open in front of the
        user. A copy alone is a call worth making: the board it opens is shown as it is.
        """
        patches = [patch for patch in (patches if patches is not None else [operations]) if patch]
        if copy_from_whiteboard_id:
            source = await cls.get_for_user(copy_from_whiteboard_id, user_id, session)
            if source is None:
                logger.warning(f"Whiteboard '{copy_from_whiteboard_id}' is not reachable for user '{user_id}'")
                raise LysError(WHITEBOARD_NOT_FOUND, f"Whiteboard '{copy_from_whiteboard_id}' does not exist")
            whiteboard = await cls.copy_for_user(source, title, session)
        else:
            whiteboard = await cls.find_for_conversation(
                user_id, current_whiteboard_id, named_whiteboard_id, session,
            )
            if whiteboard is None:
                if not patches:
                    raise LysError(WHITEBOARD_NOT_FOUND, "There is no whiteboard to show yet: drawing on one opens it")
                whiteboard = await cls.create_for_user(user_id, title, session)

        if patches:
            await cls.apply_patches(whiteboard, patches, session, focus=focus)
        elif focus:
            cls.show(whiteboard, focus, session)

        result: Dict[str, Any] = {
            "whiteboard_id": whiteboard.id,
            "title": whiteboard.title,
            "elements": cls.describe(whiteboard),
            "slides": cls.slides(whiteboard),
            "theme": cls.theme(whiteboard),
        }
        # What the patch put on top of something else. Reported, not refused: the caller
        # chose its coordinates before any size existed and cannot see the board, so the
        # drawing stands and the caller is told what to move. The key is absent when
        # there is nothing to say.
        if patches:
            found = scene_tools.overlaps(whiteboard.scene_json, _drawn_names(patches))
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
    def scene_for_editor(cls, whiteboard: Whiteboard) -> Dict[str, Any]:
        """
        A board's scene as the editor is handed it: the palette applied to the elements that keep
        a tone as their class (``scene.restyled``). Nothing is written - the editor saves what it
        shows. A scene the palette cannot be applied to is handed as it is, never refused.
        """
        scene = whiteboard.scene_json or {}
        try:
            return scene_tools.restyled(scene, cls.style()) if scene.get("elements") else scene
        except LysError as error:
            logger.warning(f"Whiteboard '{whiteboard.id}': palette not applied ({error.debug_message})")
            return scene

    @classmethod
    def style(cls) -> scene_tools.BoardStyle:
        """How boards draw what a caller leaves unsaid: the plugin's ``palette``, ``corners`` and
        ``note_background`` (``scene.style_of``)."""
        return scene_tools.style_of(cls.app_manager.settings.get_plugin_config(PLUGIN_NAME))

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
        return await cls.apply_patches(whiteboard, [operations], session, focus=focus)

    @classmethod
    async def apply_patches(
        cls,
        whiteboard: Whiteboard,
        patches: List[Dict[str, Any]],
        session,
        focus: Optional[List[str]] = None,
    ) -> Whiteboard:
        """
        Apply patches to a board's scene in order, as one revision - what a drafter applied
        one after the other in memory (``drafting.py``), written as one drawing. Same rules as
        :meth:`apply_operations`: on the latest scene, under the row lock, all or nothing.
        """
        whiteboard = await cls._lock(whiteboard, session)
        scene = whiteboard.scene_json or scene_tools.empty_scene()
        style = cls.style()
        for patch in patches:
            scene = scene_tools.apply_operations(scene, patch, style)
        shown = scene_tools.resolve_focus(scene, focus) if focus else _drawn_names(patches)

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
        # An element the user recoloured by hand - against the scene the editor was handed -
        # leaves its tone's class: their colour wins
        new_scene = scene_tools.unclassed(cls.scene_for_editor(whiteboard), new_scene)

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

    # ==================== Visibility flags ====================

    @classmethod
    async def archive(cls, whiteboard: Whiteboard, session) -> Whiteboard:
        """
        Archive a board, and the conversations pointing at it.

        In step on purpose: the board is the artifact of the exchange that produced it,
        and filing the one away while the other stays in every listing is a divergence
        nobody acted on. See :meth:`follow_conversation_archive` for the other direction -
        a conversation acted on, the board follows.

        Idempotent: archiving an already-archived board leaves the original date
        untouched, because that date records when it was archived. Overwriting it on a
        second call - a double click, a retry - would lose that fact silently, and
        raising instead would turn a harmless repeat into an error the client must handle.

        Args:
            whiteboard: The board to archive (fetched and validated by lys_edition)
            session: The session of the request

        Returns:
            Whiteboard: the archived whiteboard
        """
        if whiteboard.archived_at is None:
            await cls._set_flag(whiteboard, "archived_at", datetime.now(UTC), session)

        await cls._spread_archive_to_conversations(whiteboard, session)
        return whiteboard

    @classmethod
    async def unarchive(cls, whiteboard: Whiteboard, session) -> Whiteboard:
        """
        Restore an archived board to the default listing, conversations included.

        Args:
            whiteboard: The board to restore (fetched and validated by lys_edition)
            session: The session of the request

        Returns:
            Whiteboard: the restored whiteboard
        """
        if whiteboard.archived_at is not None:
            await cls._set_flag(whiteboard, "archived_at", None, session)

        await cls._spread_archive_to_conversations(whiteboard, session)
        return whiteboard

    @classmethod
    async def pin(cls, whiteboard: Whiteboard, session) -> Whiteboard:
        """
        Pin a board, and the conversations pointing at it.

        Pinned and archived are orthogonal: pinning does not restore an archived board,
        and unpinning does not archive a pinned one.

        Idempotent: pinning an already-pinned board leaves the original date untouched,
        for the same reason archiving does - overwriting it on a second call (a double
        click, a retry) would lose when the board was pinned, and raising instead would
        turn a harmless repeat into an error the client must handle. The date kept is
        also what a pinned listing orders by.

        Args:
            whiteboard: The board to pin (fetched and validated by lys_edition)
            session: The session of the request

        Returns:
            Whiteboard: the pinned whiteboard
        """
        if whiteboard.pinned_at is None:
            await cls._set_flag(whiteboard, "pinned_at", datetime.now(UTC), session)

        await cls._spread_pin_to_conversations(whiteboard, session)
        return whiteboard

    @classmethod
    async def unpin(cls, whiteboard: Whiteboard, session) -> Whiteboard:
        """
        Unpin a board, conversations included.

        Args:
            whiteboard: The board to unpin (fetched and validated by lys_edition)
            session: The session of the request

        Returns:
            Whiteboard: the unpinned whiteboard
        """
        if whiteboard.pinned_at is not None:
            await cls._set_flag(whiteboard, "pinned_at", None, session)

        await cls._spread_pin_to_conversations(whiteboard, session)
        return whiteboard

    @classmethod
    async def follow_conversation_archive(cls, conversation: Any, session) -> None:
        """
        The conversation archived or unarchived; keep the board it points at in step.

        The other half of the sync, reached from the conversation service's overrides
        (this app extends it) - a flag acted on from either side lands on both. The
        board takes the conversation's state and date when its own is empty: the first
        date each row carries is kept, so a repeat on either side cannot move it.

        The conversations sharing the board follow along, through the same spread as a
        board-originated action: a flag is a fact about the board and every exchange
        pointing at it, never about one of them.

        Nothing to raise on: a conversation without a board, or whose pointer names a
        deleted one, has nothing to follow - the pointer carries no foreign key, and a
        dangling one reads as no board here exactly as it does for the drawing tools.

        Args:
            conversation: The conversation whose archive flag just moved
            session: The session of the request
        """
        board = await cls._board_of_conversation(conversation, session)
        if board is None:
            return

        if conversation.archived_at is not None:
            if board.archived_at is None:
                await cls._set_flag(board, "archived_at", conversation.archived_at, session)
        elif board.archived_at is not None:
            await cls._set_flag(board, "archived_at", None, session)

        await cls._spread_archive_to_conversations(board, session)

    @classmethod
    async def follow_conversation_pin(cls, conversation: Any, session) -> None:
        """
        The conversation pinned or unpinned; keep the board it points at in step.

        Same rule and same reasoning as :meth:`follow_conversation_archive`, for the pin.

        Args:
            conversation: The conversation whose pin flag just moved
            session: The session of the request
        """
        board = await cls._board_of_conversation(conversation, session)
        if board is None:
            return

        if conversation.pinned_at is not None:
            if board.pinned_at is None:
                await cls._set_flag(board, "pinned_at", conversation.pinned_at, session)
        elif board.pinned_at is not None:
            await cls._set_flag(board, "pinned_at", None, session)

        await cls._spread_pin_to_conversations(board, session)

    @classmethod
    async def _set_flag(cls, whiteboard: Whiteboard, column: str, value: Optional[datetime], session) -> None:
        """
        Write a visibility flag without moving the board's updated_at.

        updated_at is the board's last edit: what the listing orders by and what a
        client shows as "modified". A flag records where the board is filed, not an edit
        of it - written through the ORM, it would fire the column's onupdate and present
        a pin as a change to the drawing. Naming updated_at in the SET clause keeps it as
        it was (an explicit value suppresses onupdate), and the loaded object takes the
        new flag as already persisted, so the flush has nothing left to write.

        Args:
            whiteboard: The board to flag, as loaded in this session
            column: "archived_at" or "pinned_at"
            value: The flag's new date, or None to clear it
            session: The session of the request
        """
        entity = type(whiteboard)
        await session.execute(
            update(entity)
            .where(entity.id == whiteboard.id)
            .values({column: value, "updated_at": entity.updated_at})
            .execution_options(synchronize_session=False)
        )
        set_committed_value(whiteboard, column, value)

    @classmethod
    async def _board_of_conversation(cls, conversation: Any, session) -> Optional[Whiteboard]:
        """
        The board this conversation points at, if there is one to follow.

        None when the pointer is empty, and when it names a board that is gone: reaching
        it through the owner's read (see :meth:`get_for_user`) keeps a dangling pointer
        and a stranger's board id in the same place - a miss, not a leak.
        """
        if not conversation.whiteboard_id:
            return None

        return await cls.get_for_user(conversation.whiteboard_id, conversation.user_id, session)

    @classmethod
    async def _spread_archive_to_conversations(cls, whiteboard: Whiteboard, session) -> None:
        """
        Make every conversation pointing at this board share its archive flag.

        Rows entering the state take the board's date - when the state began - rather
        than the date of whichever action reached them: the date is a fact about the
        state, and one clique carries one date. Rows leaving it are cleared whatever
        their own date was: the conversation service's caller already moved its own row,
        and the board is the single source of the state being spread.

        Both directions touch only the rows whose state actually changes: a row already
        in step is left alone, so a repeat - or an action on one conversation - never
        bumps the updated_at of the others.
        """
        conversation, stmt = cls._update_conversations_of(whiteboard)
        if whiteboard.archived_at is None:
            stmt = stmt.where(conversation.archived_at.isnot(None)).values(archived_at=None)
        else:
            stmt = stmt.where(conversation.archived_at.is_(None)).values(archived_at=whiteboard.archived_at)

        await session.execute(stmt)

    @classmethod
    async def _spread_pin_to_conversations(cls, whiteboard: Whiteboard, session) -> None:
        """Same rule and same reasoning as :meth:`_spread_archive_to_conversations`, for the pin."""
        conversation, stmt = cls._update_conversations_of(whiteboard)
        if whiteboard.pinned_at is None:
            stmt = stmt.where(conversation.pinned_at.isnot(None)).values(pinned_at=None)
        else:
            stmt = stmt.where(conversation.pinned_at.is_(None)).values(pinned_at=whiteboard.pinned_at)

        await session.execute(stmt)

    @classmethod
    def _update_conversations_of(cls, whiteboard: Whiteboard) -> Tuple[Any, Update]:
        """
        The conversation entity, and an UPDATE scoped to the conversations of this board.

        Scoped on the owner as well as the pointer. Today a conversation only ever
        points at a board of its own user, so the owner clause filters nothing - it is
        there so that a flag set on one user's board can never write another user's
        conversation, should a pointer ever cross users.
        """
        conversation = cls.app_manager.get_entity("ai_conversation")
        stmt = update(conversation).where(
            conversation.whiteboard_id == whiteboard.id,
            conversation.user_id == whiteboard.user_id,
        )
        return conversation, stmt

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


def _drawn_names(patches: List[Dict[str, Any]]) -> List[str]:
    """What a series of patches draws, by name, each once, in the order they name it."""
    names: List[str] = []
    for patch in patches:
        names += [name for name in scene_tools.drawn_names(patch) if name not in names]
    return names

