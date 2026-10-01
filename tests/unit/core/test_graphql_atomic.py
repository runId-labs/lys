"""
Unit tests for the atomic execution of a mutation resolver.

What is tested is the contract of run_atomic and of the root-mutation
detection: when the savepoint is rolled back, released, or left alone. The
SQL itself is SQLAlchemy's.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from lys.core.graphql.atomic import run_atomic
from lys.core.graphql.fields import _is_root_mutation


class _Savepoint:
    """
    A nested transaction whose ending can be observed.

    ``is_active`` and being part of the session's transaction differ, as in
    SQLAlchemy: a failed release deactivates the savepoint but leaves it open.
    """

    def __init__(self):
        self.is_active = True
        self.open = True
        self.sync_transaction = SimpleNamespace(parent=None)
        self.commit = AsyncMock(side_effect=self.close)
        self.rollback = AsyncMock(side_effect=self.close)

    def close(self):
        """What a release, a rollback or an explicit session.commit() does."""
        self.is_active = False
        self.open = False


def _session(savepoint):
    session = MagicMock()
    session.begin_nested = AsyncMock(return_value=savepoint)
    session.sync_session.get_nested_transaction = (
        lambda: savepoint.sync_transaction if savepoint.open else None
    )
    return session


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestRunAtomic:

    def test_releases_the_savepoint_and_returns_the_result(self):
        savepoint = _Savepoint()

        async def operation():
            return "node"

        assert _run(run_atomic(_session(savepoint), operation)) == "node"
        savepoint.commit.assert_awaited_once()
        savepoint.rollback.assert_not_awaited()

    def test_rolls_back_and_re_raises_when_the_operation_fails(self):
        """The refusal still reaches the response; the writes do not reach the commit."""
        savepoint = _Savepoint()

        async def operation():
            raise ValueError("third write refused")

        with pytest.raises(ValueError):
            _run(run_atomic(_session(savepoint), operation))
        savepoint.rollback.assert_awaited_once()
        savepoint.commit.assert_not_awaited()

    def test_rolls_back_on_cancellation(self):
        """A request cancelled mid-way must not leave its writes to the final commit."""
        savepoint = _Savepoint()

        async def operation():
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            _run(run_atomic(_session(savepoint), operation))
        savepoint.rollback.assert_awaited_once()

    def test_leaves_alone_a_savepoint_the_operation_closed_by_committing(self):
        """
        Persist-then-refuse: the operation commits explicitly, which closes the
        savepoint with the rest of the transaction, then raises. Nothing is
        rolled back — that is the documented way to keep a failed login attempt.
        """
        savepoint = _Savepoint()

        async def operation():
            savepoint.close()  # what an explicit session.commit() does
            raise ValueError("refused after committing")

        with pytest.raises(ValueError):
            _run(run_atomic(_session(savepoint), operation))
        savepoint.rollback.assert_not_awaited()
        savepoint.commit.assert_not_awaited()

    def test_does_not_release_a_savepoint_already_closed_on_success(self):
        savepoint = _Savepoint()

        async def operation():
            savepoint.close()
            return "node"

        assert _run(run_atomic(_session(savepoint), operation)) == "node"
        savepoint.commit.assert_not_awaited()

    def test_a_failure_while_releasing_is_the_operations_error(self):
        """Releasing flushes: a constraint violation surfaces here, not at the final commit."""
        savepoint = _Savepoint()
        savepoint.commit = AsyncMock(side_effect=RuntimeError("foreign key violation"))

        async def operation():
            return "node"

        with pytest.raises(RuntimeError):
            _run(run_atomic(_session(savepoint), operation))

    def test_a_savepoint_whose_release_failed_is_rolled_back(self):
        """
        The failed release deactivates the savepoint but leaves it open: not
        rolled back, the session refuses the final commit and the next mutation.
        """
        savepoint = _Savepoint()

        def fail_release():
            savepoint.is_active = False
            raise RuntimeError("foreign key violation")

        savepoint.commit = AsyncMock(side_effect=fail_release)

        async def operation():
            return "node"

        with pytest.raises(RuntimeError, match="foreign key violation"):
            _run(run_atomic(_session(savepoint), operation))
        savepoint.rollback.assert_awaited_once()

    def test_a_savepoint_under_one_the_resolver_left_open_is_rolled_back(self):
        """The resolver's own unclosed savepoint must not hide the mutation's."""
        savepoint = _Savepoint()
        session = _session(savepoint)
        inner = SimpleNamespace(parent=savepoint.sync_transaction)
        session.sync_session.get_nested_transaction = lambda: inner

        async def operation():
            raise ValueError("refused inside a nested savepoint")

        with pytest.raises(ValueError):
            _run(run_atomic(session, operation))
        savepoint.rollback.assert_awaited_once()

    def test_a_failing_rollback_does_not_replace_the_original_error(self):
        """
        A dropped connection makes the rollback fail too. The caller must still
        read why the mutation was refused, not the rollback's own failure —
        and the whole transaction is rolled back so nothing half-done lands.
        """
        savepoint = _Savepoint()
        savepoint.rollback = AsyncMock(side_effect=ConnectionError("connection lost"))
        session = _session(savepoint)
        session.rollback = AsyncMock()

        async def operation():
            raise ValueError("third write refused")

        with pytest.raises(ValueError, match="third write refused"):
            _run(run_atomic(session, operation))
        session.rollback.assert_awaited_once()

    def test_the_original_error_survives_both_rollbacks_failing(self):
        savepoint = _Savepoint()
        savepoint.rollback = AsyncMock(side_effect=ConnectionError("connection lost"))
        session = _session(savepoint)
        session.rollback = AsyncMock(side_effect=ConnectionError("connection lost"))

        async def operation():
            raise ValueError("third write refused")

        with pytest.raises(ValueError, match="third write refused"):
            _run(run_atomic(session, operation))

    def test_runs_plainly_without_a_session(self):
        async def operation():
            return "node"

        assert _run(run_atomic(None, operation)) == "node"


class TestIsRootMutation:

    @staticmethod
    def _info(operation: str, nested: bool = False):
        path = SimpleNamespace(prev=SimpleNamespace(prev=None) if nested else None)
        return SimpleNamespace(
            operation=SimpleNamespace(operation=SimpleNamespace(value=operation)), path=path
        )

    def test_a_root_field_of_a_mutation(self):
        assert _is_root_mutation(self._info("mutation")) is True

    def test_a_field_read_on_what_a_mutation_returned(self):
        assert _is_root_mutation(self._info("mutation", nested=True)) is False

    def test_a_query(self):
        assert _is_root_mutation(self._info("query")) is False

    def test_an_info_without_operation(self):
        """A resolver called outside a GraphQL execution (a test, a tool) is not a mutation."""
        assert _is_root_mutation(SimpleNamespace()) is False
