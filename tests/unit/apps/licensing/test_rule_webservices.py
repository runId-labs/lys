"""
Unit tests for licensing rule webservices.

Tests LicenseRuleQuery structure and the all_license_rules() resolver logic
directly, following the pattern used for the plan webservices tests.

Note: Webservice modules use a singleton registry that can raise ValueError
when multiple apps register webservices with the same name.
We handle this by catching import errors and using sys.modules.
"""
import asyncio
import inspect
import sys
from unittest.mock import MagicMock, AsyncMock, patch


def _import_rule_webservices():
    """Import licensing rule webservices module, handling registry conflicts."""
    module_name = "lys.apps.licensing.modules.rule.webservices"
    if module_name in sys.modules:
        return sys.modules[module_name]
    try:
        import importlib
        return importlib.import_module(module_name)
    except ValueError:
        return sys.modules.get(module_name)


def _get_resolver():
    """Get the raw resolver function from the query.

    lys_connection wraps the original function in an inner_resolver closure.
    The original resolver is stored in the closure as 'resolver' freevar.
    """
    mod = _import_rule_webservices()
    wrapped = mod.LicenseRuleQuery.__dict__["all_license_rules"]
    idx = wrapped.__code__.co_freevars.index("resolver")
    return wrapped.__closure__[idx].cell_contents


class TestLicenseRuleQuery:
    """Tests for LicenseRuleQuery webservice class structure and methods."""

    def test_class_exists(self):
        mod = _import_rule_webservices()
        assert hasattr(mod, "LicenseRuleQuery")

    def test_has_all_license_rules_method(self):
        mod = _import_rule_webservices()
        assert hasattr(mod.LicenseRuleQuery, "all_license_rules")

    def test_all_license_rules_is_async(self):
        mod = _import_rule_webservices()
        assert inspect.iscoroutinefunction(mod.LicenseRuleQuery.all_license_rules)


class TestAllLicenseRulesLogic:
    """Tests for LicenseRuleQuery.all_license_rules() resolver logic."""

    def _setup_info(self):
        mock_info = MagicMock()
        mock_rule_entity = MagicMock()
        mock_info.context.app_manager.get_entity.side_effect = lambda name: {
            "license_rule": mock_rule_entity,
        }[name]
        return mock_info, mock_rule_entity

    def _run(self, resolver, info, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(resolver(None, info=info, **kwargs))
        finally:
            loop.close()

    @patch("lys.apps.licensing.modules.rule.webservices.select")
    def test_resolves_entity_via_app_manager(self, mock_select):
        resolver = _get_resolver()
        mock_info, mock_rule_entity = self._setup_info()

        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt

        self._run(resolver, mock_info)

        mock_info.context.app_manager.get_entity.assert_called_once_with("license_rule")
        mock_select.assert_called_once_with(mock_rule_entity)

    @patch("lys.apps.licensing.modules.rule.webservices.select")
    def test_no_filter_when_enabled_not_given(self, mock_select):
        resolver = _get_resolver()
        mock_info, _ = self._setup_info()

        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt

        self._run(resolver, mock_info)

        mock_stmt.where.assert_not_called()

    @patch("lys.apps.licensing.modules.rule.webservices.select")
    def test_filters_by_enabled_when_given(self, mock_select):
        resolver = _get_resolver()
        mock_info, mock_rule_entity = self._setup_info()

        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt

        result = self._run(resolver, mock_info, enabled=True)

        mock_stmt.where.assert_called_once()
        mock_stmt.order_by.assert_called_once_with(mock_rule_entity.id)
        assert result is mock_stmt

    @patch("lys.apps.licensing.modules.rule.webservices.select")
    def test_ordered_by_id(self, mock_select):
        resolver = _get_resolver()
        mock_info, mock_rule_entity = self._setup_info()

        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt

        self._run(resolver, mock_info)

        mock_stmt.order_by.assert_called_once_with(mock_rule_entity.id)
