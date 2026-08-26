"""
Unit tests for SSO link webservices logic.

Tests the sso_providers resolver logic directly, bypassing the lys_field wrapper.
"""

import asyncio
from unittest.mock import MagicMock


def _make_node_constructable(cls):
    """Patch a ServiceNode subclass to accept kwargs in __init__.

    Strawberry @type decorator adds __init__ at schema build time,
    which hasn't happened in unit tests. This adds a simple kwargs-based init.
    """
    original_init = cls.__init__

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    cls.__init__ = __init__
    return original_init


class TestSsoProvidersLogic:
    """Tests for sso_providers() internal logic."""

    def _get_resolver(self):
        """Import and get the raw resolver function.

        lys_field wraps the original function in an inner_resolver closure.
        The original resolver is stored in the closure as 'resolver' freevar.
        """
        from lys.apps.sso.modules.sso_link.webservices import SSOProviderQuery
        wrapped = SSOProviderQuery.__dict__["sso_providers"]
        idx = wrapped.__code__.co_freevars.index("resolver")
        return wrapped.__closure__[idx].cell_contents

    def _run(self, resolver, info):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(resolver(None, info=info))
        finally:
            loop.close()

    def test_lists_providers_with_client_id(self):
        from lys.apps.sso.modules.sso_link.nodes import SSOProvidersNode
        original_init = _make_node_constructable(SSOProvidersNode)
        try:
            resolver = self._get_resolver()

            mock_info = MagicMock()
            mock_info.context.app_manager.settings.get_plugin_config.return_value = {
                "callback_base_url": "https://api.example.com",
                "providers": {
                    "microsoft": {"client_id": "abc", "display_name": "Microsoft"},
                    "okta": {"client_id": "xyz"},
                },
            }

            result = self._run(resolver, mock_info)

            assert len(result.providers) == 2
            assert result.providers[0].provider_id == "microsoft"
            assert result.providers[0].name == "Microsoft"
            assert result.providers[0].login_url == "https://api.example.com/auth/sso/microsoft/login"
            assert result.providers[1].provider_id == "okta"
            assert result.providers[1].name == "Okta"
            assert result.providers[1].login_url == "https://api.example.com/auth/sso/okta/login"
        finally:
            SSOProvidersNode.__init__ = original_init

    def test_skips_providers_without_client_id(self):
        from lys.apps.sso.modules.sso_link.nodes import SSOProvidersNode
        original_init = _make_node_constructable(SSOProvidersNode)
        try:
            resolver = self._get_resolver()

            mock_info = MagicMock()
            mock_info.context.app_manager.settings.get_plugin_config.return_value = {
                "callback_base_url": "https://api.example.com",
                "providers": {
                    "google": {"client_id": "", "display_name": "Google"},
                    "github": {"display_name": "GitHub"},
                    "microsoft": {"client_id": "abc", "display_name": "Microsoft"},
                },
            }

            result = self._run(resolver, mock_info)

            assert len(result.providers) == 1
            assert result.providers[0].provider_id == "microsoft"
        finally:
            SSOProvidersNode.__init__ = original_init

    def test_falls_back_to_capitalized_provider_id_when_no_display_name(self):
        from lys.apps.sso.modules.sso_link.nodes import SSOProvidersNode
        original_init = _make_node_constructable(SSOProvidersNode)
        try:
            resolver = self._get_resolver()

            mock_info = MagicMock()
            mock_info.context.app_manager.settings.get_plugin_config.return_value = {
                "callback_base_url": "https://api.example.com",
                "providers": {
                    "okta": {"client_id": "xyz"},
                },
            }

            result = self._run(resolver, mock_info)

            assert result.providers[0].name == "Okta"
        finally:
            SSOProvidersNode.__init__ = original_init

    def test_empty_providers_config_returns_empty_list(self):
        from lys.apps.sso.modules.sso_link.nodes import SSOProvidersNode
        original_init = _make_node_constructable(SSOProvidersNode)
        try:
            resolver = self._get_resolver()

            mock_info = MagicMock()
            mock_info.context.app_manager.settings.get_plugin_config.return_value = {
                "callback_base_url": "https://api.example.com",
                "providers": {},
            }

            result = self._run(resolver, mock_info)

            assert result.providers == []
        finally:
            SSOProvidersNode.__init__ = original_init

    def test_missing_providers_key_returns_empty_list(self):
        from lys.apps.sso.modules.sso_link.nodes import SSOProvidersNode
        original_init = _make_node_constructable(SSOProvidersNode)
        try:
            resolver = self._get_resolver()

            mock_info = MagicMock()
            mock_info.context.app_manager.settings.get_plugin_config.return_value = {}

            result = self._run(resolver, mock_info)

            assert result.providers == []
        finally:
            SSOProvidersNode.__init__ = original_init

    def test_missing_callback_base_url_defaults_to_empty_string(self):
        from lys.apps.sso.modules.sso_link.nodes import SSOProvidersNode
        original_init = _make_node_constructable(SSOProvidersNode)
        try:
            resolver = self._get_resolver()

            mock_info = MagicMock()
            mock_info.context.app_manager.settings.get_plugin_config.return_value = {
                "providers": {"okta": {"client_id": "xyz"}},
            }

            result = self._run(resolver, mock_info)

            assert result.providers[0].login_url == "/auth/sso/okta/login"
        finally:
            SSOProvidersNode.__init__ = original_init

    def test_reads_config_via_sso_plugin_key(self):
        from lys.apps.sso.consts import SSO_PLUGIN_KEY
        from lys.apps.sso.modules.sso_link.nodes import SSOProvidersNode
        original_init = _make_node_constructable(SSOProvidersNode)
        try:
            resolver = self._get_resolver()

            mock_info = MagicMock()
            mock_info.context.app_manager.settings.get_plugin_config.return_value = {
                "providers": {},
            }

            self._run(resolver, mock_info)

            mock_info.context.app_manager.settings.get_plugin_config.assert_called_once_with(SSO_PLUGIN_KEY)
        finally:
            SSOProvidersNode.__init__ = original_init

    def test_is_public_and_access_metadata(self):
        """sso_providers must remain reachable by both anonymous and connected callers,
        and must not require a license, since it only exposes global provider config."""
        import lys.apps.sso.modules.sso_link.webservices  # noqa: F401 (ensures registration)
        from lys.core.registries import LysAppRegistry

        webservice = LysAppRegistry().webservices["sso_providers"]

        assert webservice["attributes"]["public_type"] == "NO_LIMITATION"
        assert webservice["attributes"]["is_licenced"] is False
