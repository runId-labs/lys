"""
Unit tests for core contexts module logic.

Tests Context class properties and get_context factory function.
"""

from unittest.mock import MagicMock

from lys.core.contexts import Context, get_context


class TestContext:

    def test_init_defaults(self):
        ctx = Context()
        assert ctx.session is None
        assert ctx.app_manager is None

    def test_get_from_request_state_with_request(self):
        ctx = Context()
        mock_request = MagicMock()
        mock_request.state.my_attr = "value"
        ctx.request = mock_request
        result = ctx.get_from_request_state("my_attr")
        assert result == "value"

    def test_get_from_request_state_no_request(self):
        ctx = Context()
        ctx.request = None
        result = ctx.get_from_request_state("missing", "default")
        assert result == "default"

    def test_get_from_request_state_missing_attr_returns_default(self):
        ctx = Context()
        mock_request = MagicMock()
        # state exists but does not have 'nonexistent' as a real attribute
        # getattr with default will return the default
        mock_state = MagicMock(spec=[])
        mock_request.state = mock_state
        ctx.request = mock_request
        result = ctx.get_from_request_state("nonexistent", "fallback")
        assert result == "fallback"

    def test_set_to_request_state(self):
        ctx = Context()
        mock_request = MagicMock()
        ctx.request = mock_request
        ctx.set_to_request_state("my_key", "my_value")
        assert mock_request.state.my_key == "my_value"

    def test_connected_user_property_setter_getter(self):
        ctx = Context()
        mock_request = MagicMock()
        ctx.request = mock_request
        ctx.connected_user = {"sub": "user1"}
        assert mock_request.state.connected_user == {"sub": "user1"}

    def test_webservice_name_property_setter_getter(self):
        ctx = Context()
        mock_request = MagicMock()
        ctx.request = mock_request
        ctx.webservice_name = "test_ws"
        assert mock_request.state.webservice_name == "test_ws"

    def test_access_type_default(self):
        ctx = Context()
        ctx.request = None
        assert ctx.access_type is False

    def test_access_type_property_setter_getter(self):
        ctx = Context()
        mock_request = MagicMock()
        ctx.request = mock_request
        ctx.access_type = {"role": True}
        assert mock_request.state.access_type == {"role": True}

    def test_webservice_parameters_default(self):
        ctx = Context()
        ctx.request = None
        assert ctx.webservice_parameters == {}

    def test_webservice_parameters_property_setter_getter(self):
        ctx = Context()
        mock_request = MagicMock()
        ctx.request = mock_request
        ctx.webservice_parameters = {"key": "val"}
        assert mock_request.state.webservice_parameters == {"key": "val"}

    def test_service_caller_default(self):
        ctx = Context()
        ctx.request = None
        assert ctx.service_caller is None

    def test_service_caller_property_setter_getter(self):
        ctx = Context()
        mock_request = MagicMock()
        ctx.request = mock_request
        ctx.service_caller = {"service": "auth"}
        assert mock_request.state.service_caller == {"service": "auth"}

    def test_access_token_default(self):
        ctx = Context()
        ctx.request = None
        assert ctx.access_token is None


class TestGetContext:

    def test_get_context_returns_context_instance(self):
        ctx = get_context()
        assert isinstance(ctx, Context)

    def test_get_context_returns_fresh_instance(self):
        ctx1 = get_context()
        ctx2 = get_context()
        assert ctx1 is not ctx2
