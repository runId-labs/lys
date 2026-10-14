"""
Unit tests for core routes utility module logic.

Tests camel_to_snake, load_routes_manifest, filter_routes_by_permissions, and build_navigate_tool.
"""

import json
import logging
import os
import tempfile

from lys.core.utils.routes import (
    camel_to_snake,
    load_routes_manifest,
    filter_routes_by_permissions,
    build_navigate_tool,
    route_page_params,
    writable_param_names,
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


    @staticmethod
    def _load(manifest, tmp_path):
        path = tmp_path / "routes-manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return load_routes_manifest(str(path))

    def test_warns_when_no_route_declares_a_gate(self, tmp_path, caplog):
        """A manifest older than main_webservices lists every page to every user: say so."""
        with caplog.at_level(logging.WARNING, logger="lys.core.utils.routes"):
            self._load({"routes": [{"path": "/home"}, {"path": "/users", "webservices": ["allUsers"]}]}, tmp_path)
        assert "main_webservices" in caplog.text

    def test_no_warning_when_routes_declare_gates(self, tmp_path, caplog):
        with caplog.at_level(logging.WARNING, logger="lys.core.utils.routes"):
            self._load({"routes": [{"path": "/home", "main_webservices": []}]}, tmp_path)
        assert caplog.text == ""

class TestFilterRoutesByPermissions:

    def test_ungated_routes_always_included(self):
        routes = [{"path": "/home", "main_webservices": []}]
        result = filter_routes_by_permissions(routes, set())
        assert len(result) == 1
        assert result[0]["path"] == "/home"

    def test_permitted_route_included(self):
        routes = [{"path": "/users", "main_webservices": ["allUsers"]}]
        result = filter_routes_by_permissions(routes, {"all_users"})
        assert len(result) == 1
        assert result[0]["path"] == "/users"

    def test_non_permitted_route_excluded(self):
        routes = [{"path": "/admin", "main_webservices": ["adminPanel"]}]
        result = filter_routes_by_permissions(routes, {"all_users"})
        assert len(result) == 0

    def test_any_of_gate_needs_one_of_them(self):
        routes = [{"path": "/users", "main_webservices": ["allUsers", "allClients"]}]
        assert len(filter_routes_by_permissions(routes, {"all_clients"})) == 1
        assert len(filter_routes_by_permissions(routes, {"all_users"})) == 1
        assert len(filter_routes_by_permissions(routes, {"all_products"})) == 0

    def test_mixed_routes(self):
        routes = [
            {"path": "/home", "main_webservices": []},
            {"path": "/users", "main_webservices": ["allUsers"]},
            {"path": "/admin", "main_webservices": ["adminPanel"]},
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
        routes = [{"path": "/users", "main_webservices": ["allUsers"]}]
        result = filter_routes_by_permissions(routes, set())
        assert len(result) == 0

    def test_route_without_gate_key(self):
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


class TestManifestParamAccessors:
    """The one accessor both schema readers go through: the AI service
    resolving a page by name, and the navigate tool resolving a route by
    path. A malformed or missing declaration must read the same on both."""

    def test_a_route_without_params_declares_none(self):
        assert route_page_params({"path": "/x"}) is None

    def test_a_malformed_params_declaration_is_no_declaration(self):
        assert route_page_params({"params": ["pastMonths"]}) is None
        assert route_page_params({"params": None}) is None

    def test_a_non_route_declares_none(self):
        assert route_page_params(None) is None

    def test_the_declared_params_come_back_as_declared(self):
        schema = {"pastMonths": {"type": "int", "writable": True}}
        assert route_page_params({"params": schema}) is schema

    def test_only_the_writable_params_are_named_and_sorted(self):
        schema = {
            "pastMonths": {"type": "int", "writable": True},
            "clientId": {"type": "global_id"},
            "activeTab": {"type": "enum", "writable": True},
            "broken": "not a spec",
        }
        assert writable_param_names(schema) == ["activeTab", "pastMonths"]

    def test_no_schema_names_no_writable_param(self):
        assert writable_param_names(None) == []
        assert writable_param_names({"clientId": {"type": "global_id"}}) == []
