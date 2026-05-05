"""
Pytest configuration for E2E tests.

E2E tests use a full FastAPI application with httpx.AsyncClient
to test the complete request/response cycle including middleware,
GraphQL resolvers, and database operations.

Like integration tests, E2E tests run in forked subprocesses for
LysAppRegistry singleton isolation.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


def pytest_collection_modifyitems(items):
    """Auto-mark all E2E tests to run in forked subprocess."""
    for item in items:
        item.add_marker(pytest.mark.forked)


def pytest_configure(config):
    """Patch pytest-forked to collect coverage in forked child processes."""
    cov_source = getattr(getattr(config, "option", None), "cov_source", None)
    if not cov_source:
        return

    try:
        import pytest_forked
        import coverage as coverage_mod
    except ImportError:
        return

    def _coverage_forked_run_report(item):
        from _pytest import runner
        from _pytest.runner import runtestprotocol
        from pytest_forked import serialize_report
        import marshal
        import py

        EXITSTATUS_TESTEXIT = 4
        config_file = str(item.config.rootpath / "pyproject.toml")

        def runforked():
            cov = coverage_mod.Coverage(data_suffix=True, config_file=config_file)
            cov.start()
            try:
                reports = runtestprotocol(item, log=False)
            except KeyboardInterrupt:
                cov.stop()
                cov.save()
                os._exit(EXITSTATUS_TESTEXIT)
            cov.stop()
            cov.save()
            return marshal.dumps([serialize_report(x) for x in reports])

        ff = py.process.ForkedFunc(runforked)
        result = ff.waitfinish()
        if result.retval is not None:
            report_dumps = marshal.loads(result.retval)
            return [runner.TestReport(**x) for x in report_dumps]
        else:
            if result.exitstatus == EXITSTATUS_TESTEXIT:
                pytest.exit(f"forked test item {item} raised Exit")
            return pytest_forked.report_process_crash(item, result)

    pytest_forked.forked_run_report = _coverage_forked_run_report


# E2E test constants
E2E_SECRET_KEY = "test-e2e-secret-key-1234567890abcdef"
E2E_ALGORITHM = "HS256"

# Dev fixture users (created by UserDevFixtures when env=DEV)
ENABLED_USER_EMAIL = "enabled_user@lys-test.fr"
DISABLED_USER_EMAIL = "disabled_user@lys-test.fr"
SUPER_USER_EMAIL = "super_user@lys-test.fr"
DEV_USER_PASSWORD = "password"


class _FakePubSubE2E:
    """In-memory pubsub stand-in for E2E tests — same surface as PubSubManager.

    Implements only the key/value subset that AccessTokenStore touches.
    PubSub publish/subscribe semantics are not exercised by the auth flow,
    so the stub is intentionally minimal.
    """

    def __init__(self):
        self.store: dict[str, str] = {}

    async def set_key(self, key, value, ttl_seconds=None) -> bool:
        self.store[key] = value
        return True

    async def get_key(self, key):
        return self.store.get(key)

    async def delete_key(self, key) -> bool:
        existed = key in self.store
        self.store.pop(key, None)
        return existed


async def make_test_token(app_manager, user_id, is_super_user=False, webservices=None, expire_minutes=30):
    """
    Insert a fake access token directly into the AccessTokenStore and return its opaque id.

    This is the E2E equivalent of going through ``AuthService.login`` but
    skipping the password/refresh-token machinery — useful when the test
    only cares that the middleware accepts a known token.
    """
    from lys.apps.user_auth.modules.auth.store import AccessTokenStore

    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
        "iat": int(now.timestamp()),
        "is_super_user": is_super_user,
        "xsrf_token": "test-xsrf-token-e2e",
        "webservices": webservices or {},
    }

    token_id = str(uuid.uuid4())
    store = AccessTokenStore(app_manager.pubsub)
    # Bypass create() so we control the UUID — easier to assert against.
    await app_manager.pubsub.set_key(
        f"lys:access_token:{token_id}",
        json.dumps(claims),
        ttl_seconds=expire_minutes * 60,
    )
    return token_id


def make_unknown_token():
    """
    Return an opaque token id that is NOT registered in the store.

    Equivalent semantically to a previously-expired JWT: the middleware
    looks it up, finds nothing, and treats the request as anonymous.
    """
    return str(uuid.uuid4())


@pytest_asyncio.fixture
async def e2e_app():
    """
    Create a full FastAPI application with all components loaded.

    Returns (app, app_manager) tuple. Fixtures are loaded automatically
    which seeds parametric data and dev users.
    """
    from lys.core.configs import LysAppSettings
    from lys.core.consts.component_types import AppComponentTypeEnum
    from lys.core.consts.environments import EnvironmentEnum
    from lys.core.managers.app import AppManager
    from lys.core.utils.manager import AppManagerCallerMixin
    from tests.fixtures.database import create_all_tables

    settings = LysAppSettings()
    settings.database.configure(type="sqlite", database=":memory:", echo=False)
    settings.secret_key = E2E_SECRET_KEY
    settings.apps = ["lys.apps.base", "lys.apps.user_auth"]
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
    settings.configure_plugin(
        "cors",
        allow_origins=["http://test"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    settings.middlewares = [
        "lys.apps.user_auth.middlewares.UserAuthMiddleware",
        "lys.core.middlewares.ErrorManagerMiddleware",
        "lys.core.middlewares.LysCorsMiddleware",
    ]
    settings.permissions = [
        "lys.apps.user_auth.permissions.AnonymousPermission",
        "lys.apps.user_auth.permissions.JWTPermission",
    ]

    app_manager = AppManager(settings=settings)
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
        AppComponentTypeEnum.FIXTURES,
        AppComponentTypeEnum.NODES,
        AppComponentTypeEnum.WEBSERVICES,
    ])

    # Set app_manager on the base mixin so all services and utilities use it
    AppManagerCallerMixin._app_manager = app_manager

    app = app_manager.initialize_app(
        title="E2E Test",
        description="E2E Test App",
        version="0.0.1"
    )

    # Manually run startup tasks (bypass ASGI lifespan)
    await create_all_tables(app_manager.database)

    # Inject an in-memory pubsub stand-in so the AccessTokenStore can store
    # and resolve opaque access tokens. The lifespan that normally
    # initialises a real Redis-backed PubSubManager is bypassed in E2E,
    # so we wire a fake here for the auth flow to function.
    app_manager.pubsub = _FakePubSubE2E()

    await app_manager._load_fixtures_in_order()

    # Reset dev fixture passwords to known values for E2E testing.
    # H6 security fix makes format_password() generate random passwords,
    # so we need to set them to DEV_USER_PASSWORD after fixture loading.
    from lys.apps.user_auth.utils import AuthUtils
    hashed = AuthUtils.hash_password(DEV_USER_PASSWORD)
    user_service = app_manager.get_service("user")
    async with app_manager.database.get_session() as session:
        for email in [ENABLED_USER_EMAIL, DISABLED_USER_EMAIL, SUPER_USER_EMAIL]:
            user = await user_service.get_by_email(email, session)
            if user:
                user.password = hashed

    yield app, app_manager

    await app_manager.database.close()
    AppManagerCallerMixin._app_manager = None


@pytest_asyncio.fixture
async def client(e2e_app):
    """Create httpx.AsyncClient bound to the E2E FastAPI app."""
    app, _ = e2e_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def e2e_app_manager(e2e_app):
    """Convenience fixture to access the app_manager."""
    _, app_manager = e2e_app
    return app_manager
