"""
Unit tests for licensing plan GraphQL nodes.
"""
import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestLicensePlanNode:
    """Tests for LicensePlanNode."""

    def test_node_exists(self):
        from lys.apps.licensing.modules.plan.nodes import LicensePlanNode
        assert LicensePlanNode is not None

    def test_is_strawberry_type(self):
        from lys.apps.licensing.modules.plan.nodes import LicensePlanNode
        assert hasattr(LicensePlanNode, "__strawberry_definition__") or hasattr(LicensePlanNode, "_type_definition")


class TestLicensePlanVersionNode:
    """Tests for LicensePlanVersionNode."""

    def test_node_exists(self):
        from lys.apps.licensing.modules.plan.nodes import LicensePlanVersionNode
        assert LicensePlanVersionNode is not None

    def test_is_strawberry_type(self):
        from lys.apps.licensing.modules.plan.nodes import LicensePlanVersionNode
        assert hasattr(LicensePlanVersionNode, "__strawberry_definition__") or hasattr(LicensePlanVersionNode, "_type_definition")


class TestLicensePlanVersionRuleNode:
    """Tests for LicensePlanVersionRuleNode."""

    def test_node_exists(self):
        from lys.apps.licensing.modules.plan.nodes import LicensePlanVersionRuleNode
        assert LicensePlanVersionRuleNode is not None

    def test_is_strawberry_type(self):
        from lys.apps.licensing.modules.plan.nodes import LicensePlanVersionRuleNode
        assert hasattr(LicensePlanVersionRuleNode, "__strawberry_definition__") or hasattr(LicensePlanVersionRuleNode, "_type_definition")
