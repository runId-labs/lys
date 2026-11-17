"""
Integration tests for WhiteboardService against a real database.

Covers what mocks cannot: ownership filtering in SQL, the reload that makes a stale
in-memory copy harmless, the pointer left on conversations, and the tools end to end.
"""

from types import SimpleNamespace
from datetime import UTC
from uuid import uuid4

import pytest
from sqlalchemy import select

from lys.apps.ai_whiteboard.modules.whiteboard import scene as scene_tools
from lys.core.errors import LysError
from lys.core.graphql.client import build_global_id


def same_instant(first, second) -> bool:
    """SQLite hands stored timestamps back without their timezone - the instants still match."""
    if first.tzinfo is None:
        first = first.replace(tzinfo=UTC)
    if second.tzinfo is None:
        second = second.replace(tzinfo=UTC)
    return first == second


async def make_conversation(app_manager, session, user_id):
    return await app_manager.get_service("ai_conversation").get_or_create(user_id, session)


class TestEntities:
    def test_whiteboard_defaults(self, whiteboard_app_manager):
        entity = whiteboard_app_manager.get_entity("whiteboard")
        assert entity.__table__.c.revision.default.arg == 1
        default = entity.__table__.c.scene_json.default.arg
        assert default(None) == {"elements": [], "appState": {}, "files": {}}
        assert default(None) is not default(None)

    def test_conversation_pointer_is_a_soft_reference(self, whiteboard_app_manager):
        entity = whiteboard_app_manager.get_entity("ai_conversation")
        column = entity.__table__.c.whiteboard_id
        assert column.nullable is True
        assert not column.foreign_keys

    def test_owner_filter_is_applied_in_sql(self, whiteboard_app_manager):
        entity = whiteboard_app_manager.get_entity("whiteboard")
        stmt, filters = entity.user_accessing_filters(select(entity), "u1")
        assert "whiteboard.user_id" in str(filters[0])


class TestOwnership:
    @pytest.mark.asyncio
    async def test_a_board_is_only_reachable_by_its_owner(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")
        owner, stranger = str(uuid4()), str(uuid4())

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, owner)
            board = await service.open_for_conversation(conversation, session)

            assert await service.get_for_user(board.id, owner, session) is board
            assert await service.get_for_user(board.id, stranger, session) is None

    @pytest.mark.asyncio
    async def test_naming_someone_elses_board_is_refused(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")
        owner, stranger = str(uuid4()), str(uuid4())

        async with whiteboard_app_manager.database.get_session() as session:
            owners_conversation = await make_conversation(whiteboard_app_manager, session, owner)
            board = await service.open_for_conversation(owners_conversation, session)
            strangers_conversation = await make_conversation(whiteboard_app_manager, session, stranger)

            with pytest.raises(LysError) as error:
                await service.resolve_for_conversation(strangers_conversation, session, whiteboard_id=board.id)

        assert error.value.detail == "WHITEBOARD_NOT_FOUND"


class TestOpenAndResolve:
    @pytest.mark.asyncio
    async def test_opening_points_the_conversation_at_the_board(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            assert board.revision == 1
            assert board.title == "Untitled whiteboard"
            assert board.scene_json == scene_tools.empty_scene()
            assert conversation.whiteboard_id == board.id

    @pytest.mark.asyncio
    async def test_resolve_reuses_the_conversations_board(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            first = await service.resolve_for_conversation(conversation, session)
            second = await service.resolve_for_conversation(conversation, session)

            assert first.id == second.id

    @pytest.mark.asyncio
    async def test_a_dangling_pointer_opens_a_new_board(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            conversation.whiteboard_id = str(uuid4())

            board = await service.resolve_for_conversation(conversation, session)

            assert conversation.whiteboard_id == board.id


class TestWrites:
    @pytest.mark.asyncio
    async def test_patch_persists_and_bumps_the_revision(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")
        user_id = str(uuid4())

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, user_id)
            board = await service.open_for_conversation(conversation, session)
            await service.apply_operations(board, {"add": [{"name": "a", "text": "hello"}]}, session)
            await session.commit()
            board_id = board.id

        async with whiteboard_app_manager.database.get_session() as session:
            stored = await service.get_for_user(board_id, user_id, session)
            assert stored.revision == 2
            assert scene_tools.element_names(stored.scene_json) == ["a"]

    @pytest.mark.asyncio
    async def test_a_refused_patch_changes_nothing(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            with pytest.raises(LysError):
                await service.apply_operations(board, {"update": [{"name": "nowhere", "text": "x"}]}, session)

            assert board.revision == 1
            assert board.scene_json == scene_tools.empty_scene()

    @pytest.mark.asyncio
    async def test_save_replaces_the_scene(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")
        scene = {"elements": [{"id": "x", "type": "rectangle"}], "appState": {}, "files": {}}

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            saved = await service.save_scene(board, scene, 1, session)

            assert saved.revision == 2
            assert saved.scene_json == scene

    @pytest.mark.asyncio
    async def test_a_save_from_a_stale_copy_is_refused(self, whiteboard_app_manager):
        """Two writers, each holding its own copy of revision 1: the second must lose."""
        service = whiteboard_app_manager.get_service("whiteboard")
        user_id = str(uuid4())
        database = whiteboard_app_manager.database

        async with database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, user_id)
            board = await service.open_for_conversation(conversation, session)
            await session.commit()
            board_id = board.id

        async with database.get_session() as browser, database.get_session() as model:
            browser_copy = await service.get_for_user(board_id, user_id, browser)
            model_copy = await service.get_for_user(board_id, user_id, model)

            await service.apply_operations(model_copy, {"add": [{"name": "a", "text": "x"}]}, model)
            await model.commit()

            with pytest.raises(LysError) as error:
                await service.save_scene(browser_copy, scene_tools.empty_scene(), 1, browser)

        assert error.value.detail == "WHITEBOARD_REVISION_CONFLICT"

    @pytest.mark.asyncio
    async def test_a_patch_lands_on_the_latest_scene(self, whiteboard_app_manager):
        """The model's patch must not overwrite what the browser saved in between."""
        service = whiteboard_app_manager.get_service("whiteboard")
        user_id = str(uuid4())
        database = whiteboard_app_manager.database
        drawn = {"elements": [{"id": "by-hand", "type": "rectangle"}], "appState": {}, "files": {}}

        async with database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, user_id)
            board = await service.open_for_conversation(conversation, session)
            await session.commit()
            board_id = board.id

        async with database.get_session() as browser, database.get_session() as model:
            browser_copy = await service.get_for_user(board_id, user_id, browser)
            model_copy = await service.get_for_user(board_id, user_id, model)

            await service.save_scene(browser_copy, drawn, 1, browser)
            await browser.commit()

            result = await service.apply_operations(model_copy, {"add": [{"name": "b", "text": "y"}]}, model)

            assert result.revision == 3
            assert set(scene_tools.element_names(result.scene_json)) == {"by-hand", "b"}


class TestDelete:
    @pytest.mark.asyncio
    async def test_deleting_clears_the_pointer_of_conversations(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")
        user_id = str(uuid4())

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, user_id)
            board = await service.open_for_conversation(conversation, session)
            board_id = board.id

            assert await service.delete(board_id, session) is True
            await session.refresh(conversation)

            assert conversation.whiteboard_id is None
            assert await service.get_for_user(board_id, user_id, session) is None

    @pytest.mark.asyncio
    async def test_forget_leaves_other_conversations_alone(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            first = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            second = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(first, session)
            other = await service.open_for_conversation(second, session)

            await service.forget_everywhere(board.id, session)
            await session.refresh(first)
            await session.refresh(second)

            assert first.whiteboard_id is None
            assert second.whiteboard_id == other.id


class TestVisibilityFlags:
    """Archive and pin, and the step they keep a board and its conversations in.

    The conversation service the app registers extends the whiteboard's, so every
    action from either side lands on both: the flag is the same fact read from two
    listings.
    """

    @pytest.mark.asyncio
    async def test_a_board_is_born_in_step_with_its_conversation(self, whiteboard_app_manager):
        """Born during an archived, pinned exchange: archived and pinned from the start.

        The sync fires on an action; a birth is not one, so nobody would ever bring
        this board in step - and it would escape the cleanup that follows the
        conversation, piling up with nobody to file it away.
        """
        service = whiteboard_app_manager.get_service("whiteboard")
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            user_id = str(uuid4())
            conversation = await make_conversation(whiteboard_app_manager, session, user_id)
            await conversation_service.archive(conversation, session)
            await conversation_service.pin(conversation, session)

            board = await service.open_for_conversation(conversation, session)

            assert board.archived_at is not None
            assert board.pinned_at is not None

    @pytest.mark.asyncio
    async def test_a_board_born_of_an_active_conversation_starts_active(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))

            board = await service.open_for_conversation(conversation, session)

            assert board.archived_at is None
            assert board.pinned_at is None

    @pytest.mark.asyncio
    async def test_archiving_a_board_archives_its_conversations(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            archived = await service.archive(board, session)
            await session.refresh(conversation)

            assert archived.archived_at is not None
            assert same_instant(conversation.archived_at, board.archived_at)

    @pytest.mark.asyncio
    async def test_a_flag_never_spreads_to_another_users_conversation(self, whiteboard_app_manager):
        """The spread is scoped on the owner too: a pointer crossing users is not followed."""
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)
            stranger = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            stranger.whiteboard_id = board.id
            await session.flush()

            await service.archive(board, session)
            await service.pin(board, session)
            await session.refresh(conversation)
            await session.refresh(stranger)

            assert conversation.archived_at is not None
            assert conversation.pinned_at is not None
            assert stranger.archived_at is None
            assert stranger.pinned_at is None

    @pytest.mark.asyncio
    async def test_unarchiving_a_board_restores_its_conversations(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)
            await service.archive(board, session)

            restored = await service.unarchive(board, session)
            await session.refresh(conversation)

            assert restored.archived_at is None
            assert conversation.archived_at is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", ["unarchive", "unpin"])
    async def test_clearing_a_flag_leaves_conversations_already_in_step_untouched(
        self, whiteboard_app_manager, action,
    ):
        """A conversation already without the flag is not rewritten: its updated_at stays.

        Otherwise every repeat - or an action on one conversation - would bump the
        others and move them up a listing ordered by last activity.
        """
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)
            await session.refresh(conversation)
            touched_at = conversation.updated_at

            await getattr(service, action)(board, session)
            await session.flush()
            await session.refresh(conversation)

            assert conversation.updated_at == touched_at

    @pytest.mark.asyncio
    @pytest.mark.parametrize("actions", [["archive"], ["pin"], ["archive", "unarchive"], ["pin", "unpin"]])
    async def test_a_flag_never_moves_the_board_updated_at(self, whiteboard_app_manager, actions):
        """updated_at is the board's last edit: filing it away or pinning it is not one.

        Otherwise a pin would show on the board as a change to the drawing, and move it
        up a listing ordered by last edit.
        """
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)
            await service.rename(board, "Edited once", session)
            await session.refresh(board)
            edited_at = board.updated_at
            assert edited_at is not None

            for action in actions:
                await getattr(service, action)(board, session)
            await session.flush()
            await session.refresh(board)

            assert board.updated_at == edited_at
            assert (board.archived_at is not None) == (actions == ["archive"])
            assert (board.pinned_at is not None) == (actions == ["pin"])

    @pytest.mark.asyncio
    async def test_a_conversation_flag_never_moves_the_board_updated_at(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)
            await session.refresh(board)
            touched_at = board.updated_at

            await conversation_service.archive(conversation, session)
            await conversation_service.pin(conversation, session)
            await session.flush()
            await session.refresh(board)

            assert board.archived_at is not None
            assert board.pinned_at is not None
            assert board.updated_at == touched_at

    @pytest.mark.asyncio
    async def test_pinning_a_board_pins_its_conversations(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            pinned = await service.pin(board, session)
            await session.refresh(conversation)

            assert pinned.pinned_at is not None
            assert pinned.archived_at is None
            assert same_instant(conversation.pinned_at, board.pinned_at)

            unpinned = await service.unpin(board, session)
            await session.refresh(conversation)

            assert unpinned.pinned_at is None
            assert conversation.pinned_at is None

    @pytest.mark.asyncio
    async def test_a_repeat_keeps_the_first_date(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            first = await service.archive(board, session)
            archived_at = first.archived_at
            second = await service.archive(first, session)

            assert second.archived_at == archived_at

    @pytest.mark.asyncio
    async def test_archiving_a_conversation_archives_its_board(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            archived = await conversation_service.archive(conversation, session)

            assert archived.archived_at is not None
            assert same_instant(board.archived_at, conversation.archived_at)

    @pytest.mark.asyncio
    async def test_unarchiving_a_conversation_restores_its_board(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            await conversation_service.archive(conversation, session)
            restored = await conversation_service.unarchive(conversation, session)

            assert restored.archived_at is None
            assert board.archived_at is None

    @pytest.mark.asyncio
    async def test_pin_travels_from_a_conversation_to_its_board(self, whiteboard_app_manager):
        service = whiteboard_app_manager.get_service("whiteboard")
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            pinned = await conversation_service.pin(conversation, session)
            # Read now, not after the unpin: the identity map returns the same instance
            # on both calls, and its attributes show the current state, not the one at
            # the time of the return.
            assert pinned.pinned_at is not None
            assert same_instant(board.pinned_at, pinned.pinned_at)

            unpinned = await conversation_service.unpin(conversation, session)

            assert unpinned.pinned_at is None
            assert board.pinned_at is None

    @pytest.mark.asyncio
    async def test_two_conversations_sharing_a_board_follow_either(self, whiteboard_app_manager):
        """The reprise case: acting on one side moves the whole clique, nobody is left."""
        service = whiteboard_app_manager.get_service("whiteboard")
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            first = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            second = await make_conversation(whiteboard_app_manager, session, first.user_id)
            board = await service.open_for_conversation(first, session)
            second.whiteboard_id = board.id
            session.add(second)
            await session.flush()

            await conversation_service.archive(first, session)
            await session.refresh(second)

            assert board.archived_at is not None
            assert same_instant(second.archived_at, board.archived_at)

            restored = await conversation_service.unarchive(first, session)
            await session.refresh(second)

            assert second.archived_at is None

    @pytest.mark.asyncio
    async def test_a_conversation_without_a_board_archives_alone(self, whiteboard_app_manager):
        """No pointer, or a pointer to a deleted board: the flag moves, nothing follows."""
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            conversation.whiteboard_id = str(uuid4())

            archived = await conversation_service.archive(conversation, session)

            assert archived.archived_at is not None

    @pytest.mark.asyncio
    async def test_a_board_keeps_its_own_date_when_the_conversation_archives_later(
        self, whiteboard_app_manager
    ):
        """Archived from its own listing first, the board keeps the date it recorded."""
        service = whiteboard_app_manager.get_service("whiteboard")
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            board = await service.open_for_conversation(conversation, session)

            board_date = (await service.archive(board, session)).archived_at
            conversation_date = (await conversation_service.archive(conversation, session)).archived_at

            assert board.archived_at == board_date
            assert conversation.archived_at == conversation_date
            assert conversation_date != board_date


class TestTools:
    """The handlers on real rows: what the model draws is what is stored."""

    @pytest.mark.asyncio
    async def test_draw_then_read(self, whiteboard_app_manager):
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")
        assert hasattr(conversation_service, "_handle_draw_on_whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            context = {"session": session, "conversation_id": conversation.id}
            drawn = await conversation_service._handle_draw_on_whiteboard(
                {"add": [{"name": "Idea", "text": "hello"}]}, context
            )
            read = await conversation_service._handle_read_whiteboard({}, context)

            assert [e["name"] for e in drawn["elements"]] == ["idea"]
            # The model gets the GlobalID; the conversation keeps the raw pointer.
            board_gid = build_global_id("WhiteboardNode", conversation.whiteboard_id)
            assert read["whiteboard_id"] == drawn["whiteboard_id"] == board_gid

    @pytest.mark.asyncio
    async def test_the_board_on_screen_is_read_by_the_id_the_page_context_gives(self, whiteboard_app_manager):
        """A board of the user's, not this conversation's, read by the GlobalID the page names."""
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            user_id = str(uuid4())
            other = await make_conversation(whiteboard_app_manager, session, user_id)
            on_screen = await service.open_for_conversation(other, session)
            conversation = await make_conversation(whiteboard_app_manager, session, user_id)
            context = {"session": session, "conversation_id": conversation.id}

            read = await conversation_service._handle_read_whiteboard(
                {"whiteboard_id": build_global_id("WhiteboardNode", on_screen.id)}, context,
            )

            assert read["whiteboard_id"] == build_global_id("WhiteboardNode", on_screen.id)

    @pytest.mark.asyncio
    async def test_drawing_on_a_board_named_by_id_leaves_it_where_it_belongs(self, whiteboard_app_manager):
        """The board on screen is changed in place: this conversation does not take it over."""
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            user_id = str(uuid4())
            owner = await make_conversation(whiteboard_app_manager, session, user_id)
            on_screen = await service.open_for_conversation(owner, session)
            conversation = await make_conversation(whiteboard_app_manager, session, user_id)
            context = {"session": session, "conversation_id": conversation.id}

            drawn = await conversation_service._handle_draw_on_whiteboard(
                {"add": [{"name": "Conclusion", "text": "end"}],
                 "whiteboard_id": build_global_id("WhiteboardNode", on_screen.id)},
                context,
            )
            await session.refresh(on_screen)

            assert drawn["conversation_board"] is False
            assert conversation.whiteboard_id is None
            assert owner.whiteboard_id == on_screen.id
            assert "conclusion" in [e["name"] for e in service.describe(on_screen)]

    @pytest.mark.asyncio
    async def test_a_copy_is_a_new_board_and_the_original_is_untouched(self, whiteboard_app_manager):
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            user_id = str(uuid4())
            owner = await make_conversation(whiteboard_app_manager, session, user_id)
            model = await service.open_for_conversation(owner, session)
            await service.apply_operations(model, {"add": [{"name": "Idea", "text": "EXFORMAN"}]}, session)
            await service.pin(model, session)
            conversation = await make_conversation(whiteboard_app_manager, session, user_id)
            context = {"session": session, "conversation_id": conversation.id}

            drawn = await conversation_service._handle_draw_on_whiteboard(
                {"copy_from": build_global_id("WhiteboardNode", model.id), "title": "Next month",
                 "update": [{"name": "idea", "text": "VALROMEX"}]},
                context,
            )
            await session.refresh(model)
            copy = await service.get_for_user(conversation.whiteboard_id, user_id, session)

            assert drawn["conversation_board"] is True
            assert copy.id != model.id
            assert copy.title == "Next month"
            assert copy.pinned_at is None
            assert [e["text"] for e in service.describe(copy) if e["name"] == "idea"] == ["VALROMEX"]
            assert [e["text"] for e in service.describe(model) if e["name"] == "idea"] == ["EXFORMAN"]
            assert owner.whiteboard_id == model.id

    @pytest.mark.asyncio
    async def test_a_board_of_another_user_is_never_copied(self, whiteboard_app_manager):
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")
        service = whiteboard_app_manager.get_service("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            stranger = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            foreign = await service.open_for_conversation(stranger, session)
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            context = {"session": session, "conversation_id": conversation.id}

            result = await conversation_service._handle_draw_on_whiteboard(
                {"copy_from": build_global_id("WhiteboardNode", foreign.id)}, context,
            )

            assert result["error"] == "WHITEBOARD_NOT_FOUND"
            assert conversation.whiteboard_id is None

    @pytest.mark.asyncio
    async def test_a_malformed_patch_is_returned_to_the_model(self, whiteboard_app_manager):
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            context = {"session": session, "conversation_id": conversation.id}
            result = await conversation_service._handle_draw_on_whiteboard({"add": ["not an object"]}, context)

            assert result["error"] == "WHITEBOARD_INVALID_OPERATION"

    @pytest.mark.asyncio
    async def test_reading_first_leaves_exactly_one_board(self, whiteboard_app_manager):
        """A read must not open a board: the draw that follows would open a second one."""
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")
        whiteboard_entity = whiteboard_app_manager.get_entity("whiteboard")

        async with whiteboard_app_manager.database.get_session() as session:
            user_id = str(uuid4())
            conversation = await make_conversation(whiteboard_app_manager, session, user_id)
            context = {"session": session, "conversation_id": conversation.id}

            empty = await conversation_service._handle_read_whiteboard({}, context)
            assert empty["error"] == "NO_WHITEBOARD"
            assert conversation.whiteboard_id is None

            drawn = await conversation_service._handle_draw_on_whiteboard(
                {"add": [{"name": "Idea", "text": "hello"}]}, context
            )

            boards = await session.execute(
                select(whiteboard_entity).where(whiteboard_entity.user_id == user_id)
            )
            assert [board.id for board in boards.scalars().all()] == [conversation.whiteboard_id]
            assert drawn["whiteboard_id"] == build_global_id("WhiteboardNode", conversation.whiteboard_id)

    @pytest.mark.asyncio
    async def test_an_invented_board_id_is_refused(self, whiteboard_app_manager):
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            context = {"session": session, "conversation_id": conversation.id}

            # A well-formed id naming no board of this user's: the same answer whether it
            # exists or not.
            invented = build_global_id("WhiteboardNode", str(uuid4()))
            result = await conversation_service._handle_read_whiteboard({"whiteboard_id": invented}, context)
            assert result["error"] == "WHITEBOARD_NOT_FOUND"

            # Not a whiteboard GlobalID at all: the model is told what to pass instead.
            for malformed in (str(uuid4()), "board-42"):
                result = await conversation_service._handle_read_whiteboard({"whiteboard_id": malformed}, context)
                assert result["error"] == "INVALID_WHITEBOARD_ID"
