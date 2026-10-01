"""
Atomic execution of a mutation resolver.

The request session is committed once, when the GraphQL operation ends — and a
resolver that raises does not stop that: the GraphQL layer catches the error to
report it in the response, so nothing reaches the session extension and whatever
the resolver had already flushed is committed with the rest. A mutation that
writes three rows and refuses the fourth leaves three rows behind, and tells its
caller it failed.

A mutation therefore runs inside a savepoint of its own. One savepoint per
mutation and not a rollback of the whole request: an operation may carry several
mutations, and one that succeeded — and said so in the response — must not be
undone by the next one failing.
"""
import logging
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def run_atomic(session: Any, operation: Callable[[], Awaitable[T]]) -> T:
    """
    Run a mutation's writes inside a savepoint: all of them land, or none.

    On an error the savepoint is rolled back and the error re-raised, so the
    response still reports it. On success the savepoint is released, which
    flushes: a constraint violation surfaces here, as the mutation's own error,
    instead of at the final commit where it could no longer be reported — and
    the savepoint is rolled back, so the session stays usable for the final
    commit and for the next mutation.

    A resolver that must persist something BEFORE refusing — a failed login
    attempt, an audit line — commits explicitly (``await session.commit()``)
    and then raises. The commit closes the savepoint with the rest of the
    transaction; it is then no longer active and is left alone.

    Which has a cost the resolver must know: an explicit commit ends the
    protection. Whatever the resolver writes AFTER it is in a new transaction
    this function no longer covers, and a later error leaves those writes to
    the final commit. Commit last, or open a savepoint for what follows.

    Args:
        session: The request session, or None when the field runs without one.
        operation: The writes, as a coroutine function taking no argument.

    Returns:
        Whatever ``operation`` returns.
    """
    if session is None:
        return await operation()

    savepoint = await session.begin_nested()
    try:
        result = await operation()
        if savepoint.is_active:
            # Releasing flushes: a constraint violation raises here, and the
            # savepoint is still open — undone below like any other error.
            await savepoint.commit()
    except BaseException:
        # BaseException: a cancelled request (client gone) must not leave its
        # half-done writes to the final commit either.
        if _is_open(session, savepoint):
            await _undo(session, savepoint)
        raise
    return result


def _is_open(session: Any, savepoint: Any) -> bool:
    """
    Whether the savepoint is still part of the session's transaction, and so
    still has to be rolled back.

    ``is_active`` cannot tell: it is False both for a savepoint an explicit
    commit closed — to be left alone — and for one whose release failed on a
    flush error — still open, and leaving the whole session unusable until it
    is rolled back. The savepoint is looked for from the innermost nested
    transaction up, since the resolver may have left one of its own open.
    """
    target = savepoint.sync_transaction
    transaction = session.sync_session.get_nested_transaction()
    while transaction is not None:
        if transaction is target:
            return True
        transaction = transaction.parent
    return False


async def _undo(session: Any, savepoint: Any) -> None:
    """
    Roll the savepoint back without ever replacing the error being raised.

    A rollback can fail itself — a dropped connection is enough — and raised
    from here it would be the error the caller reads, hiding why the mutation
    was refused. It is logged instead, and the original error goes on.

    A savepoint that could not be rolled back leaves the mutation's writes in
    the transaction, where the final commit would land them. The whole
    transaction is then rolled back: an earlier mutation of the same operation
    is undone with it, which is the lesser harm next to half a mutation saved.
    On a dead connection that fails too, and nothing can be committed anyway.
    """
    try:
        await savepoint.rollback()
        return
    except Exception:
        logger.exception("Savepoint rollback failed; rolling the whole transaction back")
    try:
        await session.rollback()
    except Exception:
        logger.exception("Transaction rollback failed after a failed savepoint rollback")
