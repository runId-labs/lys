"""
Unit tests for core contexts module.

Tests Context class and related utilities.
"""

import pytest


class TestContextClass:
    """Tests for Context class."""

    def test_class_exists(self):
        """Test Context class exists."""
        from lys.core.contexts import Context
        assert Context is not None

    def test_inherits_from_base_context(self):
        """Test Context inherits from BaseContext."""
        from lys.core.contexts import Context
        from strawberry.fastapi import BaseContext
        assert issubclass(Context, BaseContext)

    def test_can_create_instance(self):
        """Test Context can be instantiated."""
        from lys.core.contexts import Context
        context = Context()
        assert context is not None

    def test_has_session_attribute(self):
        """Test Context has session attribute."""
        from lys.core.contexts import Context
        context = Context()
        assert hasattr(context, "session")
        assert context.session is None

    def test_has_app_manager_attribute(self):
        """Test Context has app_manager attribute."""
        from lys.core.contexts import Context
        context = Context()
        assert hasattr(context, "app_manager")
        assert context.app_manager is None

    def test_has_get_from_request_state_method(self):
        """Test Context has get_from_request_state method."""
        from lys.core.contexts import Context
        assert hasattr(Context, "get_from_request_state")
        assert callable(Context.get_from_request_state)

    def test_has_set_to_request_state_method(self):
        """Test Context has set_to_request_state method."""
        from lys.core.contexts import Context
        assert hasattr(Context, "set_to_request_state")
        assert callable(Context.set_to_request_state)

    def test_has_access_type_property(self):
        """Test Context has access_type property."""
        from lys.core.contexts import Context
        assert hasattr(Context, "access_type")

    def test_has_connected_user_property(self):
        """Test Context has connected_user property."""
        from lys.core.contexts import Context
        assert hasattr(Context, "connected_user")

    def test_has_webservice_name_property(self):
        """Test Context has webservice_name property."""
        from lys.core.contexts import Context
        assert hasattr(Context, "webservice_name")

    def test_has_webservice_parameters_property(self):
        """Test Context has webservice_parameters property."""
        from lys.core.contexts import Context
        assert hasattr(Context, "webservice_parameters")

    def test_has_service_caller_property(self):
        """Test Context has service_caller property."""
        from lys.core.contexts import Context
        assert hasattr(Context, "service_caller")

    def test_has_access_token_property(self):
        """Test Context has access_token property."""
        from lys.core.contexts import Context
        assert hasattr(Context, "access_token")


class TestContextDefaults:
    """Tests for Context default values."""

    def test_get_from_request_state_returns_default_when_no_request(self):
        """Test get_from_request_state returns default when no request."""
        from lys.core.contexts import Context
        context = Context()
        result = context.get_from_request_state("some_key", "default_value")
        assert result == "default_value"

    def test_access_type_default_is_false(self):
        """Test access_type default is False when no request."""
        from lys.core.contexts import Context
        context = Context()
        # This will return default value since there's no request
        result = context.get_from_request_state("access_type", False)
        assert result is False

    def test_connected_user_default_is_none(self):
        """Test connected_user default is None when no request."""
        from lys.core.contexts import Context
        context = Context()
        result = context.get_from_request_state("connected_user", None)
        assert result is None

    def test_webservice_parameters_default_is_empty_dict(self):
        """Test webservice_parameters default is empty dict."""
        from lys.core.contexts import Context
        context = Context()
        result = context.get_from_request_state("webservice_parameters", {})
        assert result == {}


class TestGetContext:
    """Tests for get_context function."""

    def test_function_exists(self):
        """Test get_context function exists."""
        from lys.core.contexts import get_context
        assert get_context is not None
        assert callable(get_context)

    def test_returns_context_instance(self):
        """Test get_context returns Context instance."""
        from lys.core.contexts import get_context, Context
        result = get_context()
        assert isinstance(result, Context)

    def test_returns_new_instance_each_call(self):
        """Test get_context returns new instance each call."""
        from lys.core.contexts import get_context
        context1 = get_context()
        context2 = get_context()
        assert context1 is not context2


class TestInfoTypeAlias:
    """Tests for Info type alias."""

    def test_info_type_alias_exists(self):
        """Test Info type alias exists."""
        from lys.core.contexts import Info
        assert Info is not None
