"""
Integration tests for the legal_document services: version resolution, publication,
consent proof, and retention/anonymization.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete

from lys.apps.legal.errors import LEGAL_VERSION_NOT_FOUND
from lys.apps.legal.modules.legal_document.consts import (
    FILE_STORAGE_PLUGIN_KEY,
    SALES_TERMS,
    TERMS_OF_USE,
)
from lys.core.errors import LysError
from lys.core.utils import storage as storage_module

pytestmark = pytest.mark.asyncio


def _now():
    return datetime.now(timezone.utc)


class _FakeStorageBackend:
    """In-memory storage backend for publication tests."""

    def __init__(self):
        self.uploaded = {}

    async def upload(self, path, data, content_type=None):
        self.uploaded[path] = data
        return path

    async def get_presigned_url(self, path, expires_in=300):
        return f"https://storage.example/{path}?expires={expires_in}"


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(legal_app_manager):
    """Truncate version + acceptance tables before each test (shared in-memory DB)."""
    version_entity = legal_app_manager.get_entity("legal_document_version")
    acceptance_entity = legal_app_manager.get_entity("legal_document_acceptance")
    async with legal_app_manager.database.get_session() as session:
        await session.execute(delete(acceptance_entity))
        await session.execute(delete(version_entity))
    yield


def _fake_user(user_id=None, email="alice@example.com", first="Alice", last="Doe",
               language_id="en"):
    # user_id is a soft FK to user with Uuid(as_uuid=False): must be a valid UUID string.
    private = SimpleNamespace(first_name=first, last_name=last)
    return SimpleNamespace(id=user_id or str(uuid.uuid4()), email=email,
                           private_data=private, language_id=language_id)


async def _make_version(app_manager, *, type_id=TERMS_OF_USE, language_id="en",
                        version_number=1, effective_date=None, markdown_hash=None):
    service = app_manager.get_service("legal_document_version")
    async with app_manager.database.get_session() as session:
        return await service.create(
            session=session,
            type_id=type_id,
            language_id=language_id,
            version_number=version_number,
            markdown_hash=markdown_hash or f"md{version_number}",
            pdf_hash=f"pdf{version_number}",
            object_key=f"legal/{type_id}/{language_id}/{version_number}.pdf",
            effective_date=effective_date or _now(),
        )


class TestEntityMapping:
    """Structural assertions requiring configured SQLAlchemy mappers (app loaded)."""

    async def test_version_columns_and_unique_constraint(self, legal_app_manager):
        version_entity = legal_app_manager.get_entity("legal_document_version")
        columns = {c.name for c in version_entity.__table__.columns}
        assert {
            "type_id", "language_id", "version_number", "markdown_hash",
            "pdf_hash", "object_key", "effective_date",
        } <= columns
        unique = {
            tuple(sorted(c.columns.keys()))
            for c in version_entity.__table__.constraints
            if c.__class__.__name__ == "UniqueConstraint"
        }
        assert ("language_id", "markdown_hash", "type_id") in unique

    async def test_acceptance_columns_and_nullable_user(self, legal_app_manager):
        acceptance_entity = legal_app_manager.get_entity("legal_document_acceptance")
        columns = {c.name for c in acceptance_entity.__table__.columns}
        assert {
            "version_id", "user_id", "accepted_by_email", "accepted_by_name",
            "acceptance_context", "retention_anchor_date",
        } <= columns
        assert acceptance_entity.__table__.columns["user_id"].nullable is True


class TestGetCurrentVersion:

    async def test_raises_when_no_version(self, legal_app_manager):
        service = legal_app_manager.get_service("legal_document_version")
        async with legal_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc:
                await service.get_current_version(TERMS_OF_USE, "en", session=session)
        assert exc.value.status_code == LEGAL_VERSION_NOT_FOUND[0]

    async def test_returns_greatest_effective_date_in_past(self, legal_app_manager):
        await _make_version(legal_app_manager, version_number=1,
                            effective_date=_now() - timedelta(days=10))
        await _make_version(legal_app_manager, version_number=2,
                            effective_date=_now() - timedelta(days=1))
        service = legal_app_manager.get_service("legal_document_version")
        async with legal_app_manager.database.get_session() as session:
            current = await service.get_current_version(TERMS_OF_USE, "en", session=session)
        assert current.version_number == 2

    async def test_ignores_future_effective_date(self, legal_app_manager):
        await _make_version(legal_app_manager, version_number=1,
                            effective_date=_now() - timedelta(days=1))
        await _make_version(legal_app_manager, version_number=2,
                            effective_date=_now() + timedelta(days=5))  # future
        service = legal_app_manager.get_service("legal_document_version")
        async with legal_app_manager.database.get_session() as session:
            current = await service.get_current_version(TERMS_OF_USE, "en", session=session)
        assert current.version_number == 1

    async def test_strict_language_no_fallback(self, legal_app_manager):
        await _make_version(legal_app_manager, language_id="fr", version_number=1)
        service = legal_app_manager.get_service("legal_document_version")
        async with legal_app_manager.database.get_session() as session:
            with pytest.raises(LysError):
                await service.get_current_version(TERMS_OF_USE, "en", session=session)


class TestPublish:

    async def test_publish_renders_and_registers(self, legal_app_manager, monkeypatch):
        service = legal_app_manager.get_service("legal_document_version")
        fake = _FakeStorageBackend()
        monkeypatch.setitem(storage_module._configured_backends, FILE_STORAGE_PLUGIN_KEY, fake)

        async with legal_app_manager.database.get_session() as session:
            version = await service.publish(
                TERMS_OF_USE, "en", "# Terms\n\nHello.", session=session
            )
        assert version.version_number == 1
        assert len(version.markdown_hash) == 64
        assert len(version.pdf_hash) == 64
        # A real PDF was rendered and uploaded through the backend.
        assert version.object_key in fake.uploaded
        assert fake.uploaded[version.object_key][:5] == b"%PDF-"

    async def test_publish_is_idempotent_on_markdown(self, legal_app_manager, monkeypatch):
        service = legal_app_manager.get_service("legal_document_version")
        fake = _FakeStorageBackend()
        monkeypatch.setitem(storage_module._configured_backends, FILE_STORAGE_PLUGIN_KEY, fake)

        async with legal_app_manager.database.get_session() as session:
            v1 = await service.publish(TERMS_OF_USE, "en", "# Same", session=session)
            v2 = await service.publish(TERMS_OF_USE, "en", "# Same", session=session)
        assert v1.id == v2.id  # identical source → same version, not republished

    async def test_publish_new_source_increments_version(self, legal_app_manager, monkeypatch):
        service = legal_app_manager.get_service("legal_document_version")
        fake = _FakeStorageBackend()
        monkeypatch.setitem(storage_module._configured_backends, FILE_STORAGE_PLUGIN_KEY, fake)

        async with legal_app_manager.database.get_session() as session:
            v1 = await service.publish(TERMS_OF_USE, "en", "# One", session=session)
            v2 = await service.publish(TERMS_OF_USE, "en", "# Two", session=session)
        assert v1.version_number == 1
        assert v2.version_number == 2


class TestRecordAcceptance:

    async def test_records_snapshot(self, legal_app_manager):
        version = await _make_version(legal_app_manager)
        service = legal_app_manager.get_service("legal_document_acceptance")
        user = _fake_user()
        async with legal_app_manager.database.get_session() as session:
            acceptance = await service.record_acceptance(
                user, version, session=session,
                ip_address="1.2.3.4", user_agent="pytest",
            )
        assert acceptance.accepted_by_email == "alice@example.com"
        assert acceptance.accepted_by_name == "Alice Doe"
        assert acceptance.user_id == user.id
        # IP minimized by the service (host octet zeroed), UA kept.
        assert acceptance.acceptance_context["ip_address"] == "1.2.3.0"
        assert acceptance.acceptance_context["user_agent"] == "pytest"

    async def test_idempotent_per_user_version(self, legal_app_manager):
        version = await _make_version(legal_app_manager)
        service = legal_app_manager.get_service("legal_document_acceptance")
        user = _fake_user()
        async with legal_app_manager.database.get_session() as session:
            a1 = await service.record_acceptance(user, version, session=session)
        async with legal_app_manager.database.get_session() as session:
            a2 = await service.record_acceptance(user, version, session=session)
        assert a1.id == a2.id

    async def test_raises_when_user_has_no_email(self, legal_app_manager):
        version = await _make_version(legal_app_manager)
        service = legal_app_manager.get_service("legal_document_acceptance")
        user = _fake_user(email=None)  # no email and no email_address → no anchor
        with pytest.raises(LysError) as exc:
            async with legal_app_manager.database.get_session() as session:
                await service.record_acceptance(user, version, session=session)
        assert exc.value.status_code == 422  # LEGAL_ACCEPTANCE_EMAIL_REQUIRED

    async def test_has_accepted_current_and_outstanding(self, legal_app_manager):
        version = await _make_version(legal_app_manager, type_id=TERMS_OF_USE)
        acceptance_service = legal_app_manager.get_service("legal_document_acceptance")
        user = _fake_user()

        async with legal_app_manager.database.get_session() as session:
            assert await acceptance_service.has_accepted_current(
                user, TERMS_OF_USE, "en", session=session
            ) is False
            outstanding = await acceptance_service.outstanding_acceptances(
                user, [TERMS_OF_USE], session=session
            )
            assert outstanding == [TERMS_OF_USE]

        async with legal_app_manager.database.get_session() as session:
            await acceptance_service.record_acceptance(user, version, session=session)

        async with legal_app_manager.database.get_session() as session:
            assert await acceptance_service.has_accepted_current(
                user, TERMS_OF_USE, "en", session=session
            ) is True
            outstanding = await acceptance_service.outstanding_acceptances(
                user, [TERMS_OF_USE], session=session
            )
            assert outstanding == []


class TestTypeGating:

    async def test_required_types_returns_gating_enabled_types(self, legal_app_manager):
        type_service = legal_app_manager.get_service("legal_document_type")
        async with legal_app_manager.database.get_session() as session:
            required = await type_service.required_types(session)
        # TOU + SALES gate; PRIVACY does not.
        assert set(required) == {TERMS_OF_USE, SALES_TERMS}

    async def test_outstanding_defaults_to_required_types(self, legal_app_manager):
        tou = await _make_version(legal_app_manager, type_id=TERMS_OF_USE)
        await _make_version(legal_app_manager, type_id=SALES_TERMS)
        acceptance_service = legal_app_manager.get_service("legal_document_acceptance")
        user = _fake_user()

        async with legal_app_manager.database.get_session() as session:
            await acceptance_service.record_acceptance(user, tou, session=session)

        # No explicit required_types → defaults to the gating types (TOU, SALES).
        async with legal_app_manager.database.get_session() as session:
            outstanding = await acceptance_service.outstanding_acceptances(user, session=session)
        assert outstanding == [SALES_TERMS]  # TOU accepted; PRIVACY not gating


class TestOnInitialize:

    async def test_publishes_declared_documents(self, legal_app_manager, tmp_path, monkeypatch):
        version_service = legal_app_manager.get_service("legal_document_version")
        fake = _FakeStorageBackend()
        monkeypatch.setitem(storage_module._configured_backends, FILE_STORAGE_PLUGIN_KEY, fake)

        md_file = tmp_path / "tou_en.md"
        md_file.write_text("# Terms\n\nHello.")
        # Nested shape: type -> {"languages": {lang: bare-path}}.
        monkeypatch.setattr(
            legal_app_manager.settings.legal, "documents",
            {TERMS_OF_USE: {"languages": {"en": str(md_file)}}},
        )

        await version_service.on_initialize()

        async with legal_app_manager.database.get_session() as session:
            current = await version_service.get_current_version(TERMS_OF_USE, "en", session=session)
        assert current.version_number == 1
        assert current.object_key in fake.uploaded

    async def test_no_documents_is_noop(self, legal_app_manager, monkeypatch):
        version_service = legal_app_manager.get_service("legal_document_version")
        monkeypatch.setattr(legal_app_manager.settings.legal, "documents", {})
        await version_service.on_initialize()  # must not raise
