"""Unit tests for the Celery ``worker_init`` hook that runs the services' on_initialize."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from lys.core import celery_app as celery_module


def _app_manager():
    app_manager = MagicMock()
    app_manager.registry.initialize_services = AsyncMock()
    app_manager.database.close = AsyncMock()
    return app_manager


def test_init_worker_runs_hooks_then_disposes_the_engine(monkeypatch):
    app_manager = _app_manager()
    order = []
    app_manager.registry.initialize_services.side_effect = lambda: order.append("init")
    app_manager.database.close.side_effect = lambda: order.append("close")
    monkeypatch.setattr(celery_module.current_app, "app_manager", app_manager, raising=False)

    celery_module.init_worker()

    assert order == ["init", "close"]


def test_a_failing_hook_still_disposes_the_engine_and_aborts_the_boot(monkeypatch):
    app_manager = _app_manager()
    app_manager.registry.initialize_services.side_effect = RuntimeError("boom")
    monkeypatch.setattr(celery_module.current_app, "app_manager", app_manager, raising=False)

    with pytest.raises(RuntimeError, match="boom"):
        celery_module.init_worker()

    app_manager.database.close.assert_awaited_once()


def test_init_worker_is_a_noop_without_an_app_manager(monkeypatch):
    monkeypatch.delattr(celery_module.current_app, "app_manager", raising=False)

    celery_module.init_worker()  # must not raise
