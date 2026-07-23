"""
E2E harness for the legal app: a full FastAPI application (base + user_auth + legal) with
GraphQL + the public REST PDF routes, exercised over httpx.AsyncClient.

Provides:
- `legal_app` / `legal_client` / `legal_manager` — the app, HTTP client, and manager.
- `user_token(...)` / `service_token()` helpers — opaque user JWT and internal Service JWT.
- a seeded current version, and an anonymized user (for the reconciliation feed).
- a fake storage backend injected into the shared cache so REST routes can presign.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lys.apps.legal.modules.legal_document.consts import (
    FILE_STORAGE_PLUGIN_KEY,
    TERMS_OF_USE,
)

E2E_SECRET_KEY = "test-legal-e2e-secret-key-1234567890"
E2E_ALGORITHM = "HS256"


class _FakePubSub:
    def __init__(self):
        self.store = {}

    async def set_key(self, key, value, ttl_seconds=None) -> bool:
        self.store[key] = value
        return True

    async def get_key(self, key):
        return self.store.get(key)

    async def delete_key(self, key) -> bool:
        existed = key in self.store
        self.store.pop(key, None)
        return existed


class _FakeStorageBackend:
    async def get_presigned_url(self, path, expires_in=300):
        return f"https://storage.example/{path}?expires={expires_in}"

    async def upload(self, path, data, content_type=None):
        return path


@pytest_asyncio.fixture
async def legal_app():
    from lys.core.configs import LysAppSettings
    from lys.core.consts.component_types import AppComponentTypeEnum
    from lys.core.consts.environments import EnvironmentEnum
    from lys.core.managers.app import LysAppManager
    from lys.core.utils.manager import AppManagerCallerMixin
    from lys.core.utils import storage as storage_module
    from tests.fixtures.database import create_all_tables

    settings = LysAppSettings()
    settings.database.configure(type="sqlite", database=":memory:", echo=False)
    settings.secret_key = E2E_SECRET_KEY
    settings.apps = ["lys.apps.base", "lys.apps.user_auth", "lys.apps.legal"]
    settings.env = EnvironmentEnum.DEV
    settings.configure_plugin(
        "auth",
        encryption_algorithm=E2E_ALGORITHM,
        access_token_expire_minutes=30,
        connection_expire_minutes=10080,
        login_rate_limit_enabled=False,
        refresh_token_used_once=False,
        check_xsrf_token=False,
        cookie_secure=False,
    )
    settings.middlewares = [
        "lys.apps.base.middlewares.ServiceAuthMiddleware",
        "lys.apps.user_auth.middlewares.UserAuthMiddleware",
        "lys.core.middlewares.ErrorManagerMiddleware",
    ]
    settings.permissions = [
        "lys.apps.base.permissions.InternalServicePermission",
        "lys.apps.user_auth.permissions.AnonymousPermission",
        "lys.apps.user_auth.permissions.JWTPermission",
    ]

    # Use the LysAppManager singleton so the REST routes' `LysAppManager()` resolves to this
    # same manager (with tables), matching the production wiring (forked per test → fresh).
    manager = LysAppManager(settings=settings)
    manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
        AppComponentTypeEnum.FIXTURES,
        AppComponentTypeEnum.NODES,
        AppComponentTypeEnum.WEBSERVICES,
    ])
    AppManagerCallerMixin._app_manager = manager

    app = manager.initialize_app(title="Legal E2E", description="Legal E2E", version="0.0.1")
    await create_all_tables(manager.database)
    manager.pubsub = _FakePubSub()
    await manager._load_fixtures_in_order()

    # Inject a fake storage backend so REST routes can presign without real S3.
    storage_module._configured_backends[FILE_STORAGE_PLUGIN_KEY] = _FakeStorageBackend()

    # Seed a current version + an anonymized user.
    version_id = str(uuid.uuid4())
    anonymized_user_id = str(uuid.uuid4())
    async with manager.database.get_session() as session:
        session.add(manager.get_entity("legal_document_version")(
            id=version_id,
            type_id=TERMS_OF_USE,
            language_id="en",
            version_number=1,
            markdown_hash="h" * 64,
            pdf_hash="p" * 64,
            object_key="legal/TERMS_OF_USE/en/1.pdf",
            effective_date=datetime.now(timezone.utc) - timedelta(days=1),
        ))
        # A user whose private data is anonymized (feeds anonymizedUsers).
        session.add(manager.get_entity("user")(
            id=anonymized_user_id, is_super_user=False, language_id="en",
        ))
        session.add(manager.get_entity("user_private_data")(
            id=str(uuid.uuid4()),
            user_id=anonymized_user_id,
            anonymized_at=datetime.now(timezone.utc) - timedelta(hours=2),
        ))

    manager._e2e_version_id = version_id
    manager._e2e_anonymized_user_id = anonymized_user_id

    yield app, manager

    storage_module.clear_configured_storage_backends()
    await manager.database.close()
    AppManagerCallerMixin._app_manager = None


@pytest_asyncio.fixture
async def legal_client(legal_app):
    app, _ = legal_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def legal_manager(legal_app):
    _, manager = legal_app
    return manager


@pytest_asyncio.fixture
async def user_token(legal_manager):
    """Factory: create an opaque user token with given webservices claim / super-user flag."""
    async def _make(user_id=None, is_super_user=False, webservices=None, expire_minutes=30):
        user_id = user_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        claims = {
            "sub": str(user_id),
            "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
            "iat": int(now.timestamp()),
            "is_super_user": is_super_user,
            "xsrf_token": "test-xsrf",
            "webservices": webservices or {},
        }
        token_id = str(uuid.uuid4())
        await legal_manager.pubsub.set_key(
            f"lys:access_token:{token_id}", json.dumps(claims), ttl_seconds=expire_minutes * 60
        )
        return token_id, user_id
    return _make


@pytest.fixture
def service_token():
    """Generate an internal Service JWT for INTERNAL_SERVICE_ACCESS_LEVEL calls."""
    from lys.core.utils.auth import ServiceAuthUtils
    return ServiceAuthUtils(E2E_SECRET_KEY).generate_token("legal")
