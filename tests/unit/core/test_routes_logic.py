"""
Unit tests for core routes utility module logic.

Tests camel_to_snake, load_routes_manifest, filter_routes_by_permissions, and build_navigate_tool.
"""

import json
import os
import tempfile

from lys.core.utils.routes import (
    camel_to_snake,
    load_routes_manifest,
    filter_routes_by_permissions,
    build_navigate_tool,
)


class TestCamelToSnake:

    def test_simple(self):
        assert camel_to_snake("allClients") == "all_clients"

    def test_multiple_words(self):
        assert camel_to_snake("allClientUsers") == "all_client_users"

    def test_already_lower(self):
        assert camel_to_snake("simple") == "simple"

    def test_starts_with_upper(self):
        assert camel_to_snake("UserName") == "user_name"

    def test_single_char(self):
        assert camel_to_snake("a") == "a"

    def test_all_upper(self):
        result = camel_to_snake("ABC")
        assert result == "a_b_c"

    def test_empty_string(self):
        assert camel_to_snake("") == ""


class TestLoadRoutesManifest:

    def test_load_valid_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"routes": [{"path": "/home"}]}, f)
            f.flush()
            temp_path = f.name

        try:
            result = load_routes_manifest(temp_path)
            assert result == {"routes": [{"path": "/home"}]}
        finally:
            os.unlink(temp_path)

    def test_file_not_found(self):
        result = load_routes_manifest("/nonexistent/path.json")
        assert result is None

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json{{{")
            f.flush()
            temp_path = f.name

        try:
            result = load_routes_manifest(temp_path)
            assert result is None
        finally:
            os.unlink(temp_path)

    def test_empty_json_object(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            f.flush()
            temp_path = f.name

        try:
            result = load_routes_manifest(temp_path)
            assert result == {}
        finally:
            os.unlink(temp_path)


class TestFilterRoutesByPermissions:

    def test_public_routes_always_included(self):
        routes = [{"path": "/home", "webservice": None}]
        result = filter_routes_by_permissions(routes, set())
        assert len(result) == 1
        assert result[0]["path"] == "/home"

    def test_permitted_route_included(self):
        routes = [{"path": "/users", "webservice": "allUsers"}]
        result = filter_routes_by_permissions(routes, {"all_users"})
        assert len(result) == 1
        assert result[0]["path"] == "/users"

    def test_non_permitted_route_excluded(self):
        routes = [{"path": "/admin", "webservice": "adminPanel"}]
        result = filter_routes_by_permissions(routes, {"all_users"})
        assert len(result) == 0

    def test_mixed_routes(self):
        routes = [
            {"path": "/home", "webservice": None},
            {"path": "/users", "webservice": "allUsers"},
            {"path": "/admin", "webservice": "adminPanel"},
        ]
        result = filter_routes_by_permissions(routes, {"all_users"})
        assert len(result) == 2
        paths = [r["path"] for r in result]
        assert "/home" in paths
        assert "/users" in paths
        assert "/admin" not in paths

    def test_empty_routes(self):
        result = filter_routes_by_permissions([], {"all_users"})
        assert result == []

    def test_no_permissions(self):
        routes = [{"path": "/users", "webservice": "allUsers"}]
        result = filter_routes_by_permissions(routes, set())
        assert len(result) == 0

    def test_route_without_webservice_key(self):
        routes = [{"path": "/about"}]
        result = filter_routes_by_permissions(routes, set())
        assert len(result) == 1


class TestBuildNavigateTool:

    def test_basic_structure(self):
        routes = [{"path": "/home", "description": "Home page"}]
        tool = build_navigate_tool(routes)
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "navigate"
        assert "path" in tool["function"]["parameters"]["properties"]
        assert tool["function"]["parameters"]["properties"]["path"]["enum"] == ["/home"]

    def test_multiple_routes(self):
        routes = [
            {"path": "/home", "description": "Home"},
            {"path": "/users", "description": "Users"},
        ]
        tool = build_navigate_tool(routes)
        enum_values = tool["function"]["parameters"]["properties"]["path"]["enum"]
        assert len(enum_values) == 2
        assert "/home" in enum_values
        assert "/users" in enum_values

    def test_path_is_required(self):
        routes = [{"path": "/home", "description": "Home"}]
        tool = build_navigate_tool(routes)
        assert "path" in tool["function"]["parameters"]["required"]

    def test_has_continue_action_parameter(self):
        routes = [{"path": "/home", "description": "Home"}]
        tool = build_navigate_tool(routes)
        properties = tool["function"]["parameters"]["properties"]
        assert "continue_action" in properties
        assert properties["continue_action"]["type"] == "boolean"

    def test_description_includes_route_info(self):
        routes = [{"path": "/home", "description": "Home page"}]
        tool = build_navigate_tool(routes)
        description = tool["function"]["description"]
        assert "/home" in description
        assert "Home page" in description

    def test_route_without_description(self):
        routes = [{"path": "/home"}]
        tool = build_navigate_tool(routes)
        description = tool["function"]["description"]
        assert "No description" in description

    def test_empty_routes(self):
        routes = []
        tool = build_navigate_tool(routes)
        assert tool["function"]["parameters"]["properties"]["path"]["enum"] == []
