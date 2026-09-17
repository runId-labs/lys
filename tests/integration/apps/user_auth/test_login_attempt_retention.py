"""
Integration tests for login attempt GDPR retention (869e7tjpn): the sync
`UserLoginAttemptService.purge_expired` method and its Celery task wrapper.

Uses a dedicated sync AppManager with a StaticPool sqlite :memory: DB so a single
connection persists across sync sessions (the async conftest DB is a separate
connection) - same convention as test_token_retention.py.

`status_id`/`user_id` are plain string columns here: SQLite does not enforce
foreign keys unless PRAGMA foreign_keys=ON is set, which create_all() does not
do, and `purge_expired` only issues a bulk `delete()` - it never loads an ORM
instance or follows the `status`/`user` relationships - so no real status or
user row is needed.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from celery import current_app
from sqlalchemy import delete, select
from sqlalchemy.pool import StaticPool

from lys.apps.user_auth.modules.auth.consts import SUCCEED_LOGIN_ATTEMPT_STATUS
from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager
from lys.core.managers.database import Base


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
    return manager


@pytest.fixture(autouse=True)
def _clean_login_attempts(sync_manager):
    with sync_manager.database.get_sync_session() as session:
        session.execute(delete(sync_manager.get_entity("user_login_attempt")))
    yield


def _insert_login_attempt(manager, *, created_at):
    entity = manager.get_entity("user_login_attempt")
    with manager.database.get_sync_session() as session:
        session.add(entity(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            status_id=SUCCEED_LOGIN_ATTEMPT_STATUS,
            created_at=created_at,
        ))


class TestPurgeLoginAttempts:

    def test_purge_respects_created_at(self, sync_manager):
        _insert_login_attempt(sync_manager, created_at=_now() - timedelta(days=10))  # recent
        _insert_login_attempt(sync_manager, created_at=_now() - timedelta(days=400))  # past retention
        service = sync_manager.get_service("user_login_attempt")

        with sync_manager.database.get_sync_session() as session:
            deleted = service.purge_expired(365, session=session)
        assert deleted == 1

        entity = sync_manager.get_entity("user_login_attempt")
        with sync_manager.database.get_sync_session() as session:
            remaining = session.execute(select(entity)).scalars().all()
        assert len(remaining) == 1

    def test_no_purge_when_nothing_qualifies(self, sync_manager):
        _insert_login_attempt(sync_manager, created_at=_now() - timedelta(days=1))
        service = sync_manager.get_service("user_login_attempt")

        with sync_manager.database.get_sync_session() as session:
            deleted = service.purge_expired(365, session=session)
        assert deleted == 0


class TestCeleryTask:

    def test_purge_login_attempts_task(self, sync_manager):
        from lys.apps.user_auth.modules.auth.tasks import purge_expired_login_attempts
        _insert_login_attempt(sync_manager, created_at=_now() - timedelta(days=400))

        current_app.app_manager = sync_manager
        deleted = purge_expired_login_attempts()
        assert deleted == 1
