"""
Unit tests for licensing user GraphQL nodes.
"""
import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestLicensingUserNode:
    """Tests for licensing UserNode."""

    def test_node_exists(self):
        from lys.apps.licensing.modules.user.nodes import UserNode
        assert UserNode is not None

    def test_inherits_from_entity_node(self):
        from lys.apps.licensing.modules.user.nodes import UserNode
        from lys.core.graphql.nodes import EntityNode
        assert issubclass(UserNode, EntityNode)

    def test_has_is_licensed_field(self):
        from lys.apps.licensing.modules.user.nodes import UserNode
        assert hasattr(UserNode, "is_licensed")
