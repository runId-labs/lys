"""
Integration tests for the synchronous retention/anonymization path: the sync service
methods (`reconcile_anonymized`, `purge_expired`) and the Celery task wrappers.

Uses a dedicated sync AppManager with a StaticPool sqlite :memory: DB so a single
connection persists across sync sessions (the async conftest DB is a separate connection).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from celery import current_app
from sqlalchemy import select
from sqlalchemy.pool import StaticPool

from lys.apps.legal.modules.legal_document.consts import TERMS_OF_USE
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
    settings.apps = ["lys.apps.base", "lys.apps.legal"]
    manager = AppManager(settings=settings)
    manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
    ])
    manager.load_all_components()
    Base.metadata.create_all(manager.database.get_sync_engine())

    with manager.database.get_sync_session() as session:
        session.add(manager.get_entity("language")(id="en", enabled=True))
        session.add(manager.get_entity("legal_document_type")(id=TERMS_OF_USE, enabled=True))
        session.add(manager.get_entity("legal_document_version")(
            id=str(uuid.uuid4()),
            type_id=TERMS_OF_USE,
            language_id="en",
            version_number=1,
            markdown_hash="h" * 64,
            pdf_hash="p" * 64,
            object_key="legal/TERMS_OF_USE/en/1.pdf",
            effective_date=_now(),
        ))
    return manager


@pytest.fixture()
def version_id(sync_manager):
    with sync_manager.database.get_sync_session() as session:
        return session.execute(
            select(sync_manager.get_entity("legal_document_version").id)
        ).scalars().first()


@pytest.fixture(autouse=True)
def _clean_acceptances(sync_manager):
    from sqlalchemy import delete
    with sync_manager.database.get_sync_session() as session:
        session.execute(delete(sync_manager.get_entity("legal_document_acceptance")))
    yield


def _insert_acceptance(manager, version_id, *, user_id, email, anchor=None):
    entity = manager.get_entity("legal_document_acceptance")
    with manager.database.get_sync_session() as session:
        session.add(entity(
            id=str(uuid.uuid4()),
            version_id=version_id,
            user_id=user_id,
            accepted_by_email=email,
            retention_anchor_date=anchor,
        ))


class TestReconcileSync:

    def test_nulls_user_and_sets_anchor(self, sync_manager, version_id):
        user_id = str(uuid.uuid4())
        _insert_acceptance(sync_manager, version_id, user_id=user_id, email="a@example.com")
        service = sync_manager.get_service("legal_document_acceptance")
        anonymized_at = _now() - timedelta(days=1)

        with sync_manager.database.get_sync_session() as session:
            updated = service.reconcile_anonymized(
                [{"id": user_id, "anonymized_at": anonymized_at}], session=session
            )
        assert updated == 1

        entity = sync_manager.get_entity("legal_document_acceptance")
        with sync_manager.database.get_sync_session() as session:
            row = session.execute(
                select(entity).where(entity.accepted_by_email == "a@example.com")
            ).scalar_one()
        assert row.user_id is None
        assert row.retention_anchor_date is not None
        assert row.accepted_by_email == "a@example.com"  # snapshot frozen

    def test_idempotent(self, sync_manager, version_id):
        user_id = str(uuid.uuid4())
        _insert_acceptance(sync_manager, version_id, user_id=user_id, email="b@example.com")
        service = sync_manager.get_service("legal_document_acceptance")
        payload = [{"id": user_id, "anonymized_at": _now()}]

        with sync_manager.database.get_sync_session() as session:
            first = service.reconcile_anonymized(payload, session=session)
        with sync_manager.database.get_sync_session() as session:
            second = service.reconcile_anonymized(payload, session=session)
        assert first == 1
        assert second == 0  # already reconciled → no-op


class TestPurgeSync:

    def test_purge_respects_anchor(self, sync_manager, version_id):
        _insert_acceptance(sync_manager, version_id, user_id=str(uuid.uuid4()),
                           email="live@example.com")  # anchor NULL → never purged
        _insert_acceptance(sync_manager, version_id, user_id=None,
                           email="expired@example.com",
                           anchor=_now() - timedelta(days=4000))  # long expired
        service = sync_manager.get_service("legal_document_acceptance")

        with sync_manager.database.get_sync_session() as session:
            deleted = service.purge_expired(365 * 5, session=session)
        assert deleted == 1

        entity = sync_manager.get_entity("legal_document_acceptance")
        with sync_manager.database.get_sync_session() as session:
            remaining = session.execute(select(entity)).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].accepted_by_email == "live@example.com"


class TestCeleryTasks:

    def test_purge_task(self, sync_manager, version_id):
        from lys.apps.legal.tasks import legal_purge_expired_acceptances
        _insert_acceptance(sync_manager, version_id, user_id=None, email="old@example.com",
                           anchor=_now() - timedelta(days=4000))
        current_app.app_manager = sync_manager
        deleted = legal_purge_expired_acceptances()
        assert deleted == 1

    def test_reconcile_task_skips_without_endpoint(self, sync_manager):
        from lys.apps.legal import tasks
        current_app.app_manager = sync_manager
        sync_manager.settings.legal.anonymized_users_endpoint = None
        assert tasks.legal_reconcile_anonymized_users() == 0

    def test_reconcile_task_with_fetched_users(self, sync_manager, version_id, monkeypatch):
        from lys.apps.legal import tasks
        user_id = str(uuid.uuid4())
        _insert_acceptance(sync_manager, version_id, user_id=user_id, email="c@example.com")

        current_app.app_manager = sync_manager
        sync_manager.settings.legal.anonymized_users_endpoint = "http://user-auth/graphql"
        monkeypatch.setattr(
            tasks, "_fetch_anonymized_users",
            lambda settings, endpoint, since: [{"id": user_id, "anonymized_at": _now()}],
        )
        updated = tasks.legal_reconcile_anonymized_users()
        assert updated == 1
