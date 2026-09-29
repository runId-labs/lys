"""
Unit tests for WhiteboardService.

The session is a mock: what is checked is the order and the rules of the writes — who
may touch a board, what is locked, what is refused before anything is stored, and when
the owner is told. The commit-time signal is exercised on a real in-memory session, since
the behaviour under test is SQLAlchemy's transaction events.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from lys.apps.ai_whiteboard.modules.whiteboard import scene as scene_tools
from lys.apps.ai_whiteboard.modules.whiteboard.consts import TITLE_MAX_LENGTH
from lys.apps.ai_whiteboard.modules.whiteboard.services import WhiteboardService
from lys.core.errors import LysError

USER = str(uuid.uuid4())
BOARD_ID = str(uuid.uuid4())


def make_board(revision=1, scene=None):
    return SimpleNamespace(
        id=BOARD_ID,
        user_id=USER,
        title="Board",
        scene_json=scene or scene_tools.empty_scene(),
        revision=revision,
    )


def make_session(board=None):
    """Session whose lock query (and any other) resolves to ``board``."""
    session = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = board
    result.scalar_one_or_none.return_value = board
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def manager():
    """app_manager without a pubsub, so writes do not try to signal."""
    app_manager = MagicMock()
    app_manager.pubsub = None
    app_manager.settings.get_plugin_config.return_value = None
    with patch.object(WhiteboardService, "app_manager", app_manager, create=True):
        yield app_manager


class TestGetForUser:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_id", ["not-a-uuid", "", "1", 3, {"a": 1}])
    async def test_an_id_that_is_not_a_uuid_never_reaches_the_database(self, manager, bad_id):
        session = make_session(make_board())
        assert await WhiteboardService.get_for_user(bad_id, USER, session) is None
        session.execute.assert_not_called()


class TestResolveForConversation:
    def conversation(self, whiteboard_id=None, title="Title"):
        return SimpleNamespace(user_id=USER, whiteboard_id=whiteboard_id, title=title)

    @pytest.mark.asyncio
    async def test_named_board_wins(self, manager):
        named = make_board()
        with patch.object(WhiteboardService, "get_for_user", AsyncMock(return_value=named)) as get:
            result = await WhiteboardService.resolve_for_conversation(
                self.conversation(whiteboard_id="own"), MagicMock(), whiteboard_id=BOARD_ID
            )
        assert result is named
        get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_named_board_of_someone_else_is_refused_not_redirected(self, manager):
        with patch.object(WhiteboardService, "get_for_user", AsyncMock(return_value=None)):
            with pytest.raises(LysError) as error:
                await WhiteboardService.resolve_for_conversation(
                    self.conversation(whiteboard_id="own"), MagicMock(), whiteboard_id=BOARD_ID
                )
        assert error.value.detail == "WHITEBOARD_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_falls_back_on_the_conversations_own_board(self, manager):
        own = make_board()
        with patch.object(WhiteboardService, "get_for_user", AsyncMock(return_value=own)):
            result = await WhiteboardService.resolve_for_conversation(
                self.conversation(whiteboard_id=BOARD_ID), MagicMock()
            )
        assert result is own

    @pytest.mark.asyncio
    async def test_dangling_pointer_opens_a_new_board(self, manager):
        opened = make_board()
        with patch.object(WhiteboardService, "get_for_user", AsyncMock(return_value=None)), \
                patch.object(WhiteboardService, "open_for_conversation", AsyncMock(return_value=opened)) as open_:
            result = await WhiteboardService.resolve_for_conversation(
                self.conversation(whiteboard_id=BOARD_ID), MagicMock()
            )
        assert result is opened
        open_.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_board_opens_one(self, manager):
        opened = make_board()
        with patch.object(WhiteboardService, "open_for_conversation", AsyncMock(return_value=opened)):
            result = await WhiteboardService.resolve_for_conversation(self.conversation(), MagicMock())
        assert result is opened


class TestDraw:
    """Where the patch is committed, which is what the method exists to decide."""

    OPERATIONS = {"add": [{"name": "a"}]}

    @staticmethod
    def arguments(caller_session, current=None, named=None):
        return {
            "user_id": USER,
            "title": "Title",
            "current_whiteboard_id": current,
            "named_whiteboard_id": named,
            "operations": TestDraw.OPERATIONS,
            "caller_session": caller_session,
        }

    @pytest.fixture
    def drawn(self):
        """:meth:`_draw` stubbed: only the session it is handed is under test here."""
        with patch.object(
            WhiteboardService, "_draw", AsyncMock(return_value={"whiteboard_id": BOARD_ID}),
        ) as draw:
            yield draw

    @pytest.mark.asyncio
    async def test_a_backend_taking_a_second_writer_commits_the_board_apart(self, manager, drawn):
        own_session = MagicMock()

        @asynccontextmanager
        async def get_session():
            yield own_session

        manager.database.settings.type = "postgresql"
        manager.database.get_session = get_session
        caller_session = MagicMock()

        await WhiteboardService.draw(**self.arguments(caller_session))

        assert drawn.await_args.args[-1] is own_session

    @pytest.mark.asyncio
    async def test_a_single_writer_backend_draws_in_the_callers_session(self, manager, drawn):
        """SQLite: a second transaction would wait on a lock only the caller can release."""
        manager.database.settings.type = "sqlite"
        manager.database.get_session = MagicMock(
            side_effect=AssertionError("a second transaction must not be opened here")
        )
        caller_session = MagicMock()

        await WhiteboardService.draw(**self.arguments(caller_session))

        assert drawn.await_args.args[-1] is caller_session

    @pytest.mark.asyncio
    async def test_a_board_is_opened_only_when_there_is_none(self, manager):
        board = make_board()
        session = make_session(board)
        with patch.object(WhiteboardService, "find_for_conversation", AsyncMock(return_value=board)), \
                patch.object(WhiteboardService, "create_for_user", AsyncMock()) as create, \
                patch.object(WhiteboardService, "apply_operations", AsyncMock(return_value=board)):
            result = await WhiteboardService._draw(USER, "Title", BOARD_ID, None, self.OPERATIONS, session)

        create.assert_not_awaited()
        assert result["whiteboard_id"] == BOARD_ID

    @pytest.mark.asyncio
    async def test_nothing_to_draw_on_opens_a_board(self, manager):
        opened = make_board()
        session = make_session(opened)
        with patch.object(WhiteboardService, "find_for_conversation", AsyncMock(return_value=None)), \
                patch.object(WhiteboardService, "create_for_user", AsyncMock(return_value=opened)) as create, \
                patch.object(WhiteboardService, "apply_operations", AsyncMock(return_value=opened)):
            await WhiteboardService._draw(USER, "Title", None, None, self.OPERATIONS, session)

        create.assert_awaited_once_with(USER, "Title", session)


class TestFindForConversation:
    """A read resolves a board; it never opens one."""

    @pytest.mark.asyncio
    async def test_a_dangling_pointer_reads_as_no_board(self, manager):
        with patch.object(WhiteboardService, "get_for_user", AsyncMock(return_value=None)):
            assert await WhiteboardService.find_for_conversation(USER, BOARD_ID, None, MagicMock()) is None

    @pytest.mark.asyncio
    async def test_no_pointer_reads_as_no_board_without_touching_the_database(self, manager):
        session = make_session(make_board())
        assert await WhiteboardService.find_for_conversation(USER, None, None, session) is None
        session.execute.assert_not_called()


class TestSaveSceneValidation:
    """Refused before the row is even locked: nothing malformed costs a database round trip."""

    @pytest.mark.asyncio
    async def test_malformed_scene_is_refused_before_the_lock(self, manager):
        session = make_session(make_board())

        with pytest.raises(LysError) as error:
            await WhiteboardService.save_scene(make_board(), {"elements": "nope"}, 1, session)

        assert error.value.detail == "WHITEBOARD_INVALID_SCENE"
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_size_limit_comes_from_the_plugin_settings(self, manager):
        manager.settings.get_plugin_config.return_value = {"max_scene_bytes": 50}
        session = make_session(make_board())
        scene = {"elements": [], "files": {"img": "x" * 100}}

        with pytest.raises(LysError) as error:
            await WhiteboardService.save_scene(make_board(), scene, 1, session)

        assert error.value.detail == "WHITEBOARD_SCENE_TOO_LARGE"
        manager.settings.get_plugin_config.assert_called_with("ai_whiteboard")
        session.execute.assert_not_called()

    def test_default_limit_is_used_without_settings(self, manager):
        assert WhiteboardService._max_scene_bytes() == 10 * 1024 * 1024


class TestRename:
    @pytest.mark.asyncio
    async def test_renames_without_moving_the_revision(self, manager):
        board = make_board(revision=6)
        result = await WhiteboardService.rename(board, "y" * 400, make_session())
        assert result.title == "y" * TITLE_MAX_LENGTH
        assert result.revision == 6


class TestDescribe:
    def test_describes_a_board(self):
        board = make_board(scene=scene_tools.apply_operations(
            scene_tools.empty_scene(), {"add": [{"name": "a", "text": "hello"}]}
        ))
        assert [e["name"] for e in WhiteboardService.describe(board)] == ["a"]

    def test_describes_a_board_without_scene(self):
        board = make_board()
        board.scene_json = None
        assert WhiteboardService.describe(board) == []


class TestNotification:
    """The signal follows the commit — never the flush, never a rollback."""

    @pytest_asyncio.fixture
    async def session(self):
        engine = create_async_engine("sqlite+aiosqlite://")
        async with AsyncSession(engine) as session:
            yield session
        await engine.dispose()

    @pytest.fixture
    def pubsub(self):
        pubsub = MagicMock()
        pubsub.publish = AsyncMock()
        with patch.object(WhiteboardService, "app_manager", MagicMock(pubsub=pubsub), create=True):
            yield pubsub

    @staticmethod
    async def _begin(session):
        await session.execute(text("select 1"))

    @staticmethod
    async def _settle():
        for _ in range(3):
            await asyncio.sleep(0)

    @pytest.mark.asyncio
    async def test_nothing_is_published_before_the_commit(self, session, pubsub):
        await self._begin(session)
        WhiteboardService._notify(make_board(revision=2), session)
        await self._settle()
        pubsub.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_published_once_after_the_commit(self, session, pubsub):
        await self._begin(session)
        WhiteboardService._notify(make_board(revision=2), session)
        await session.commit()
        await self._settle()

        pubsub.publish.assert_awaited_once()
        channel, signal, params = pubsub.publish.await_args.args
        assert channel == f"user:{USER}"
        assert signal == "WHITEBOARD_UPDATED"
        assert params["revision"] == 2
        assert "scene" not in params

    @pytest.mark.asyncio
    async def test_a_rollback_publishes_nothing_and_leaves_no_hook_behind(self, session, pubsub):
        await self._begin(session)
        WhiteboardService._notify(make_board(revision=2), session)
        await session.rollback()

        await self._begin(session)
        await session.commit()
        await self._settle()

        pubsub.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_one_signal_per_notify(self, session, pubsub):
        await self._begin(session)
        WhiteboardService._notify(make_board(revision=2), session)
        await session.commit()
        await self._begin(session)
        await session.commit()
        await self._settle()
        assert pubsub.publish.await_count == 1

    @pytest.mark.asyncio
    async def test_a_failing_pubsub_does_not_raise(self, session, pubsub):
        pubsub.publish.side_effect = RuntimeError("redis down")
        await self._begin(session)
        WhiteboardService._notify(make_board(), session)
        await session.commit()
        await self._settle()

    @pytest.mark.asyncio
    async def test_without_pubsub_nothing_is_registered(self, session):
        with patch.object(WhiteboardService, "app_manager", MagicMock(pubsub=None), create=True):
            await self._begin(session)
            WhiteboardService._notify(make_board(), session)
            await session.commit()
