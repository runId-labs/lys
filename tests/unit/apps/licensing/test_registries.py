"""
Unit tests for licensing registries.
"""
from unittest.mock import patch, MagicMock


class TestValidatorRegistry:
    """Tests for ValidatorRegistry class."""

    def test_validator_registry_exists(self):
        from lys.apps.licensing.registries import ValidatorRegistry
        assert ValidatorRegistry is not None

    def test_inherits_from_custom_registry(self):
        from lys.apps.licensing.registries import ValidatorRegistry
        from lys.core.registries import CustomRegistry
        assert issubclass(ValidatorRegistry, CustomRegistry)

    def test_name_is_validators(self):
        from lys.apps.licensing.registries import ValidatorRegistry
        assert ValidatorRegistry.name == "validators"


class TestDowngraderRegistry:
    """Tests for DowngraderRegistry class."""

    def test_downgrader_registry_exists(self):
        from lys.apps.licensing.registries import DowngraderRegistry
        assert DowngraderRegistry is not None

    def test_inherits_from_custom_registry(self):
        from lys.apps.licensing.registries import DowngraderRegistry
        from lys.core.registries import CustomRegistry
        assert issubclass(DowngraderRegistry, CustomRegistry)

    def test_name_is_downgraders(self):
        from lys.apps.licensing.registries import DowngraderRegistry
        assert DowngraderRegistry.name == "downgraders"


class TestRegisterValidatorDecorator:
    """Tests for register_validator decorator factory."""

    def test_register_validator_exists(self):
        from lys.apps.licensing.registries import register_validator
        assert callable(register_validator)

    def test_register_validator_returns_decorator(self):
        from lys.apps.licensing.registries import register_validator
        decorator = register_validator("TEST_RULE")
        assert callable(decorator)

    def test_decorator_returns_original_function(self):
        from lys.apps.licensing.registries import register_validator

        async def my_validator(session, client_id, app_id, limit_value):
            return (True, 0, 10)

        with patch("lys.apps.licensing.registries.LysAppRegistry") as mock_registry_cls:
            mock_registry_cls.return_value.get_registry.return_value = None
            result = register_validator("TEST_RULE")(my_validator)

        assert result is my_validator

    def test_decorator_registers_with_registry(self):
        from lys.apps.licensing.registries import register_validator

        async def my_validator(session, client_id, app_id, limit_value):
            return (True, 0, 10)

        mock_registry = MagicMock()
        with patch("lys.apps.licensing.registries.LysAppRegistry") as mock_registry_cls:
            mock_registry_cls.return_value.get_registry.return_value = mock_registry
            register_validator("MY_RULE")(my_validator)

        mock_registry.register.assert_called_once_with("MY_RULE", my_validator)


class TestRegisterDowngraderDecorator:
    """Tests for register_downgrader decorator factory."""

    def test_register_downgrader_exists(self):
        from lys.apps.licensing.registries import register_downgrader
        assert callable(register_downgrader)

    def test_register_downgrader_returns_decorator(self):
        from lys.apps.licensing.registries import register_downgrader
        decorator = register_downgrader("TEST_RULE")
        assert callable(decorator)

    def test_decorator_returns_original_function(self):
        from lys.apps.licensing.registries import register_downgrader

        def my_downgrader(session, client_id, app_id, new_limit):
            return True

        with patch("lys.apps.licensing.registries.LysAppRegistry") as mock_registry_cls:
            mock_registry_cls.return_value.get_registry.return_value = None
            result = register_downgrader("TEST_RULE")(my_downgrader)

        assert result is my_downgrader

    def test_decorator_registers_with_registry(self):
        from lys.apps.licensing.registries import register_downgrader

        def my_downgrader(session, client_id, app_id, new_limit):
            return True

        mock_registry = MagicMock()
        with patch("lys.apps.licensing.registries.LysAppRegistry") as mock_registry_cls:
            mock_registry_cls.return_value.get_registry.return_value = mock_registry
            register_downgrader("MY_RULE")(my_downgrader)

        mock_registry.register.assert_called_once_with("MY_RULE", my_downgrader)


class TestTypeAliases:
    """Tests for type aliases."""

    def test_validator_func_type_exists(self):
        from lys.apps.licensing.registries import ValidatorFunc
        assert ValidatorFunc is not None

    def test_downgrader_func_type_exists(self):
        from lys.apps.licensing.registries import DowngraderFunc
        assert DowngraderFunc is not None


class TestLicensingInitRegistries:
    """Tests for __registries__ in licensing __init__.py."""

    def test_registries_list_exists(self):
        from lys.apps.licensing import __registries__
        assert isinstance(__registries__, list)

    def test_registries_contains_validator_registry(self):
        from lys.apps.licensing import __registries__
        from lys.apps.licensing.registries import ValidatorRegistry
        assert ValidatorRegistry in __registries__

    def test_registries_contains_downgrader_registry(self):
        from lys.apps.licensing import __registries__
        from lys.apps.licensing.registries import DowngraderRegistry
        assert DowngraderRegistry in __registries__

    def test_registries_count(self):
        from lys.apps.licensing import __registries__
        assert len(__registries__) == 2
