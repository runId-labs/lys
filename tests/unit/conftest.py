"""
Unit test configuration.

Patches the LysAppRegistry singleton to allow webservice name overrides
during testing. This prevents ValueError when multiple apps register
webservices with the same name (e.g., both user_auth and organization
register 'all_users'). Only the singleton is patched; fresh AppRegistry
instances used in registry-specific tests remain unaffected.
"""

from lys.core.registries import LysAppRegistry

_singleton = LysAppRegistry()
_original = _singleton.register_webservice


def _register_webservice_with_override(*args, **kwargs):
    kwargs["allow_override"] = True
    return _original(*args, **kwargs)


_singleton.register_webservice = _register_webservice_with_override
