"""
Unit tests for user_auth modules __init__.py.
"""


def _get_submodule_names():
    """Extract module short names from __submodules__ list."""
    from lys.apps.user_auth.modules import __submodules__
    return [m.__name__.split(".")[-1] if hasattr(m, "__name__") else str(m) for m in __submodules__]


class TestUserAuthSubmodules:
    """Tests for user_auth __submodules__ list."""

    def test_submodules_list_exists(self):
        from lys.apps.user_auth.modules import __submodules__
        assert isinstance(__submodules__, list)

    def test_submodules_contains_user(self):
        assert "user" in _get_submodule_names()

    def test_submodules_contains_auth(self):
        assert "auth" in _get_submodule_names()

    def test_submodules_contains_event(self):
        assert "event" in _get_submodule_names()

    def test_submodules_contains_emailing(self):
        assert "emailing" in _get_submodule_names()

    def test_submodules_contains_notification(self):
        assert "notification" in _get_submodule_names()

    def test_submodules_contains_webservice(self):
        assert "webservice" in _get_submodule_names()

    def test_submodules_contains_access_level(self):
        assert "access_level" in _get_submodule_names()
