"""
Unit tests for licensing modules __init__.py.
"""


class TestLicensingSubmodules:
    """Tests for licensing __submodules__ list."""

    def test_submodules_list_exists(self):
        from lys.apps.licensing.modules import __submodules__
        assert isinstance(__submodules__, list)

    def test_submodules_is_not_empty(self):
        from lys.apps.licensing.modules import __submodules__
        assert len(__submodules__) > 0

    def test_submodules_contains_expected_modules(self):
        """Licensing should have core modules registered."""
        from lys.apps.licensing.modules import __submodules__
        module_names = [
            m.__name__.split(".")[-1] if hasattr(m, "__name__") else str(m)
            for m in __submodules__
        ]
        # At minimum, these modules should be present
        assert "checker" in module_names
        assert "subscription" in module_names
        assert "plan" in module_names
        assert "user" in module_names
