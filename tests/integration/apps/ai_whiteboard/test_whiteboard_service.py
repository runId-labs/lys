"""
Integration tests for WhiteboardService against a real database.

Covers what mocks cannot: ownership filtering in SQL, the reload that makes a stale
in-memory copy harmless, the pointer left on conversations, and the tools end to end.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from lys.apps.ai_whiteboard.modules.whiteboard import scene as scene_tools
from lys.core.errors import LysError


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
            assert read["whiteboard_id"] == drawn["whiteboard_id"] == conversation.whiteboard_id

    @pytest.mark.asyncio
    async def test_a_malformed_patch_is_returned_to_the_model(self, whiteboard_app_manager):
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            context = {"session": session, "conversation_id": conversation.id}

            result = await conversation_service._handle_draw_on_whiteboard({"add": ["not an object"]}, context)

            assert result["error"] == "WHITEBOARD_INVALID_OPERATION"

    @pytest.mark.asyncio
    async def test_an_invented_board_id_is_refused(self, whiteboard_app_manager):
        conversation_service = whiteboard_app_manager.get_service("ai_conversation")

        async with whiteboard_app_manager.database.get_session() as session:
            conversation = await make_conversation(whiteboard_app_manager, session, str(uuid4()))
            context = {"session": session, "conversation_id": conversation.id}

            for invented in (str(uuid4()), "board-42"):
                result = await conversation_service._handle_read_whiteboard({"whiteboard_id": invented}, context)
                assert result["error"] == "WHITEBOARD_NOT_FOUND"
