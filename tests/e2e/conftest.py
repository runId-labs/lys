"""
Pytest configuration for E2E tests.

E2E tests use a full FastAPI application with httpx.AsyncClient
to test the complete request/response cycle including middleware,
GraphQL resolvers, and database operations.

Like integration tests, E2E tests run in forked subprocesses for
LysAppRegistry singleton isolation.
"""

import os

import jwt
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
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


def make_test_token(user_id, is_super_user=False, webservices=None, expire_minutes=30):
    """Generate a valid JWT access token for E2E testing."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
        "iat": int(now.timestamp()),
        "is_super_user": is_super_user,
        "xsrf_token": "test-xsrf-token-e2e",
        "webservices": webservices or {},
    }
    return jwt.encode(claims, E2E_SECRET_KEY, algorithm=E2E_ALGORITHM)


def make_expired_token(user_id):
    """Generate an expired JWT token for testing."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "exp": int((now - timedelta(minutes=10)).timestamp()),
        "iat": int((now - timedelta(minutes=40)).timestamp()),
        "is_super_user": False,
        "xsrf_token": "test-xsrf-expired",
        "webservices": {},
    }
    return jwt.encode(claims, E2E_SECRET_KEY, algorithm=E2E_ALGORITHM)


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
    await app_manager.database.initialize_database()
    await app_manager._load_fixtures_in_order()

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
