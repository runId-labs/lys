"""
Integration tests for user token GDPR retention (869e7tjpn): the sync purge methods
(`UserRefreshTokenService.purge_expired`, `OneTimeTokenService.purge_expired` via
`UserOneTimeTokenService`) and their Celery task wrappers.

Uses a dedicated sync AppManager with a StaticPool sqlite :memory: DB so a single
connection persists across sync sessions (the async conftest DB is a separate
connection) - same convention as tests/integration/apps/legal/test_legal_retention.py.

FK columns (user_id, type_id, status_id) are plain string columns here: SQLite does
not enforce foreign keys unless PRAGMA foreign_keys=ON is set, which create_all()
does not do, so a real `user` row is never needed - only `type_id`/`status_id` need
a real row, because OneTimeToken.expires_at resolves `self.type` through the ORM
relationship, not the raw column.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from celery import current_app
from sqlalchemy.pool import StaticPool

from lys.apps.base.modules.one_time_token.consts import (
    PASSWORD_RESET_TOKEN_TYPE,
    PENDING_TOKEN_STATUS,
    USED_TOKEN_STATUS,
)
from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager
from lys.core.managers.database import Base
from lys.core.utils.datetime import ensure_utc


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def sync_manager():
    settings = LysAppSettings()
    settings.database.configure(type="sqlite", database=":memory:", poolclass=StaticPool)
    settings.apps = ["lys.apps.base", "lys.apps.user_auth"]
    manager = AppManager(settings=settings)
    manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
    ])
    manager.load_all_components()
    Base.metadata.create_all(manager.database.get_sync_engine())

    with manager.database.get_sync_session() as session:
        session.add(manager.get_entity("one_time_token_status")(id=PENDING_TOKEN_STATUS, enabled=True))
        session.add(manager.get_entity("one_time_token_status")(id=USED_TOKEN_STATUS, enabled=True))
        session.add(manager.get_entity("one_time_token_type")(
            id=PASSWORD_RESET_TOKEN_TYPE, enabled=True, duration=60,
        ))
    return manager


@pytest.fixture(autouse=True)
def _clean_tokens(sync_manager):
    from sqlalchemy import delete
    with sync_manager.database.get_sync_session() as session:
        session.execute(delete(sync_manager.get_entity("user_refresh_token")))
        session.execute(delete(sync_manager.get_entity("user_one_time_token")))
    yield


def _insert_refresh_token(manager, *, connection_expire_at, revoked_at=None):
    entity = manager.get_entity("user_refresh_token")
    with manager.database.get_sync_session() as session:
        session.add(entity(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            connection_expire_at=connection_expire_at,
            revoked_at=revoked_at,
        ))


def _insert_one_time_token(manager, *, created_at, used_at=None):
    entity = manager.get_entity("user_one_time_token")
    with manager.database.get_sync_session() as session:
        session.add(entity(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            type_id=PASSWORD_RESET_TOKEN_TYPE,
            status_id=USED_TOKEN_STATUS if used_at else PENDING_TOKEN_STATUS,
            created_at=created_at,
            used_at=used_at,
        ))


class TestPurgeRefreshTokens:

    def test_purge_respects_connection_expire_at(self, sync_manager):
        _insert_refresh_token(sync_manager, connection_expire_at=_now() + timedelta(days=1))  # live
        _insert_refresh_token(sync_manager, connection_expire_at=_now() - timedelta(days=40))  # long expired
        service = sync_manager.get_service("user_refresh_token")

        with sync_manager.database.get_sync_session() as session:
            deleted = service.purge_expired(30, session=session)
        assert deleted == 1

        entity = sync_manager.get_entity("user_refresh_token")
        from sqlalchemy import select
        with sync_manager.database.get_sync_session() as session:
            remaining = session.execute(select(entity)).scalars().all()
        assert len(remaining) == 1
        assert ensure_utc(remaining[0].connection_expire_at) > _now()  # the live one survived

    def test_purge_respects_revoked_at_even_if_connection_not_yet_expired(self, sync_manager):
        # Revoked well within the connection window (e.g. explicit logout) - dead at
        # revocation, not at the (still future) connection_expire_at.
        _insert_refresh_token(
            sync_manager,
            connection_expire_at=_now() + timedelta(days=10),
            revoked_at=_now() - timedelta(days=40),
        )
        service = sync_manager.get_service("user_refresh_token")

        with sync_manager.database.get_sync_session() as session:
            deleted = service.purge_expired(30, session=session)
        assert deleted == 1


class TestPurgeOneTimeTokens:

    def test_purge_respects_used_at(self, sync_manager):
        _insert_one_time_token(sync_manager, created_at=_now() - timedelta(days=50), used_at=_now())  # used today
        _insert_one_time_token(sync_manager, created_at=_now() - timedelta(days=50), used_at=_now() - timedelta(days=40))  # used long ago
        service = sync_manager.get_service("user_one_time_token")

        with sync_manager.database.get_sync_session() as session:
            deleted = service.purge_expired(30, session=session)
        assert deleted == 1

    def test_purge_respects_computed_expiry_when_never_used(self, sync_manager):
        # type duration is 60 minutes - a token created 40 days ago and never used
        # expired 40 days ago for retention purposes, not "40 days minus an hour".
        _insert_one_time_token(sync_manager, created_at=_now() - timedelta(days=40))
        _insert_one_time_token(sync_manager, created_at=_now() - timedelta(hours=1))  # too recent
        service = sync_manager.get_service("user_one_time_token")

        with sync_manager.database.get_sync_session() as session:
            deleted = service.purge_expired(30, session=session)
        assert deleted == 1

    def test_no_purge_when_nothing_qualifies(self, sync_manager):
        _insert_one_time_token(sync_manager, created_at=_now() - timedelta(minutes=5))
        service = sync_manager.get_service("user_one_time_token")

        with sync_manager.database.get_sync_session() as session:
            deleted = service.purge_expired(30, session=session)
        assert deleted == 0


class TestCeleryTasks:

    def test_purge_refresh_tokens_task(self, sync_manager):
        from lys.apps.user_auth.modules.user.tasks import purge_expired_refresh_tokens
        _insert_refresh_token(sync_manager, connection_expire_at=_now() - timedelta(days=40))

        current_app.app_manager = sync_manager
        deleted = purge_expired_refresh_tokens()
        assert deleted == 1

    def test_purge_one_time_tokens_task(self, sync_manager):
        from lys.apps.user_auth.modules.user.tasks import purge_expired_one_time_tokens
        _insert_one_time_token(sync_manager, created_at=_now() - timedelta(days=40))

        current_app.app_manager = sync_manager
        deleted = purge_expired_one_time_tokens()
        assert deleted == 1
