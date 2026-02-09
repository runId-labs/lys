"""
Unit tests for tool_generator utility module.

Tests cover:
- python_type_to_json_schema: Python type to JSON Schema conversion
- extract_strawberry_input_schema: Strawberry input class schema extraction
- entity_to_dict: SQLAlchemy entity serialization
- node_to_dict: Strawberry node serialization
- _is_scalar_type: scalar type detection
- _get_subfields: subfield extraction for complex types
- extract_node_fields: node field extraction for GraphQL queries
- extract_return_fields_from_type: return type field extraction
- extract_tool_from_field: StrawberryField tool definition extraction
- extract_tool_from_resolver: resolver function tool definition extraction
- _get_node_type_from_connection: node type extraction from Connection types
"""

import inspect
import types
from datetime import datetime
from typing import List, Optional, Union
from unittest.mock import MagicMock, patch

import pytest
import strawberry


# ---------------------------------------------------------------------------
# Helper classes for Strawberry wrapper type mocking
# ---------------------------------------------------------------------------

class StrawberryOptional:
    """Mock class matching Strawberry's StrawberryOptional by class name."""

    def __init__(self, of_type=None):
        if of_type is not None:
            self.of_type = of_type


class StrawberryList:
    """Mock class matching Strawberry's StrawberryList by class name."""

    def __init__(self, of_type=None):
        if of_type is not None:
            self.of_type = of_type


# ===========================================================================
# python_type_to_json_schema
# ===========================================================================

class TestPythonTypeToJsonSchema:
    """Test python_type_to_json_schema conversion."""

    def test_none_type(self):
        """Test NoneType converts to null schema."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(type(None))
        assert result == {"type": "null"}

    def test_str_required(self):
        """Test str converts to string schema with required GraphQL type."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(str)
        assert result == {"type": "string", "_graphql_type": "String!"}

    def test_str_optional(self):
        """Test str with is_optional=True drops the '!' suffix."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(str, is_optional=True)
        assert result == {"type": "string", "_graphql_type": "String"}

    def test_int_required(self):
        """Test int converts to integer schema."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(int)
        assert result == {"type": "integer", "_graphql_type": "Int!"}

    def test_float_required(self):
        """Test float converts to number schema."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(float)
        assert result == {"type": "number", "_graphql_type": "Float!"}

    def test_bool_required(self):
        """Test bool converts to boolean schema."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(bool)
        assert result == {"type": "boolean", "_graphql_type": "Boolean!"}

    def test_datetime_required(self):
        """Test datetime converts to string schema with date-time format."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(datetime)
        assert result == {
            "type": "string",
            "format": "date-time",
            "_graphql_type": "DateTime!",
        }

    def test_optional_str_via_union(self):
        """Test Optional[str] (Union[str, None]) is handled as optional string."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(Optional[str])
        assert result == {"type": "string", "_graphql_type": "String"}

    def test_list_of_int(self):
        """Test List[int] converts to array schema with integer items."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(List[int])
        assert result == {
            "type": "array",
            "items": {"type": "integer", "_graphql_type": "Int!"},
        }

    def test_real_union_produces_any_of(self):
        """Test Union[str, int] (not Optional) produces anyOf schema."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        result = python_type_to_json_schema(Union[str, int])
        assert "anyOf" in result
        assert len(result["anyOf"]) == 2
        assert {"type": "string", "_graphql_type": "String!"} in result["anyOf"]
        assert {"type": "integer", "_graphql_type": "Int!"} in result["anyOf"]

    def test_strawberry_optional_with_of_type(self):
        """Test StrawberryOptional wrapper with of_type recurses with is_optional=True."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        wrapper = StrawberryOptional(of_type=str)
        result = python_type_to_json_schema(wrapper)
        assert result == {"type": "string", "_graphql_type": "String"}

    def test_strawberry_optional_without_of_type(self):
        """Test StrawberryOptional without of_type defaults to string."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        wrapper = StrawberryOptional()
        result = python_type_to_json_schema(wrapper)
        assert result == {"type": "string"}

    def test_strawberry_list_with_of_type(self):
        """Test StrawberryList wrapper with of_type produces array schema."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        wrapper = StrawberryList(of_type=int)
        result = python_type_to_json_schema(wrapper)
        assert result == {
            "type": "array",
            "items": {"type": "integer", "_graphql_type": "Int!"},
        }

    def test_strawberry_list_without_of_type(self):
        """Test StrawberryList without of_type defaults to bare array."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        wrapper = StrawberryList()
        result = python_type_to_json_schema(wrapper)
        assert result == {"type": "array"}

    def test_global_id_type(self):
        """Test type with GlobalID in __name__ converts to ID schema."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        class GlobalID:
            pass

        result = python_type_to_json_schema(GlobalID)
        assert result["type"] == "string"
        assert result["description"] == "Global ID"
        assert result["_graphql_type"] == "ID!"

    def test_strawberry_input_type_delegates_to_extract(self):
        """Test type with __strawberry_definition__ delegates to extract_strawberry_input_schema."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        @strawberry.input
        class SampleInput:
            name: str

        result = python_type_to_json_schema(SampleInput)
        assert result["type"] == "object"
        assert "name" in result["properties"]
        assert result["_graphql_type"] == "SampleInput!"

    def test_unknown_type_defaults_to_string(self):
        """Test unknown type defaults to string schema."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        class SomeCustomType:
            pass

        result = python_type_to_json_schema(SomeCustomType)
        assert result == {"type": "string", "_graphql_type": "String!"}

    def test_python310_union_syntax(self):
        """Test types.UnionType (str | int syntax) is handled."""
        from lys.core.utils.tool_generator import python_type_to_json_schema

        union_type = eval("str | int")  # Creates types.UnionType on Python >= 3.10
        result = python_type_to_json_schema(union_type)
        assert "anyOf" in result
        assert len(result["anyOf"]) == 2


# ===========================================================================
# extract_strawberry_input_schema
# ===========================================================================

class TestExtractStrawberryInputSchema:
    """Test extract_strawberry_input_schema."""

    def test_required_and_optional_fields(self):
        """Test extraction detects field types correctly."""
        from lys.core.utils.tool_generator import extract_strawberry_input_schema

        @strawberry.input
        class TestInput:
            name: str
            age: int
            email: Optional[str] = None

        result = extract_strawberry_input_schema(TestInput)

        assert result["type"] == "object"
        assert "name" in result["properties"]
        assert "age" in result["properties"]
        assert "email" in result["properties"]
        assert result["properties"]["name"]["type"] == "string"
        assert result["properties"]["age"]["type"] == "integer"
        # email is Optional[str] so _graphql_type should be without "!"
        assert result["properties"]["email"]["_graphql_type"] == "String"
        # Optional fields should not be in required
        assert "email" not in result.get("required", [])

    def test_all_optional_no_required_key(self):
        """Test input where all fields are optional omits the required key entirely."""
        from lys.core.utils.tool_generator import extract_strawberry_input_schema

        @strawberry.input
        class AllOptionalInput:
            name: Optional[str] = None
            age: Optional[int] = None

        result = extract_strawberry_input_schema(AllOptionalInput)
        assert result["type"] == "object"
        assert "required" not in result

    def test_class_without_strawberry_definition(self):
        """Test class without __strawberry_definition__ returns empty object schema."""
        from lys.core.utils.tool_generator import extract_strawberry_input_schema

        class PlainClass:
            pass

        result = extract_strawberry_input_schema(PlainClass)
        assert result == {"type": "object", "properties": {}}


# ===========================================================================
# entity_to_dict
# ===========================================================================

class TestEntityToDict:
    """Test entity_to_dict serialization."""

    def test_none_entity(self):
        """Test None input returns None."""
        from lys.core.utils.tool_generator import entity_to_dict

        assert entity_to_dict(None) is None

    def test_max_depth_zero(self):
        """Test max_depth=0 returns None."""
        from lys.core.utils.tool_generator import entity_to_dict

        assert entity_to_dict(MagicMock(), max_depth=0) is None

    @patch("lys.core.utils.tool_generator.sa_inspect")
    def test_excluded_fields_skipped(self, mock_sa_inspect):
        """Test that EXCLUDED_FIELDS (e.g. password) are omitted from the result."""
        from lys.core.utils.tool_generator import entity_to_dict

        entity = MagicMock()
        entity.id = "abc-123"
        entity.name = "Alice"
        entity.password = "secret"

        mapper = MagicMock()
        mapper.column_attrs = [MagicMock(key="id"), MagicMock(key="name"), MagicMock(key="password")]
        mapper.relationships = []

        instance_state = MagicMock()
        instance_state.dict = {}

        mock_sa_inspect.side_effect = lambda arg: mapper if arg is entity.__class__ else instance_state

        result = entity_to_dict(entity)
        assert result["id"] == "abc-123"
        assert result["name"] == "Alice"
        assert "password" not in result

    @patch("lys.core.utils.tool_generator.sa_inspect")
    def test_isoformat_values(self, mock_sa_inspect):
        """Test values with isoformat() are serialized via isoformat."""
        from lys.core.utils.tool_generator import entity_to_dict

        mock_dt = MagicMock()
        mock_dt.isoformat.return_value = "2024-06-15T10:30:00"

        entity = MagicMock()
        entity.created_at = mock_dt

        mapper = MagicMock()
        mapper.column_attrs = [MagicMock(key="created_at")]
        mapper.relationships = []

        instance_state = MagicMock()
        instance_state.dict = {}

        mock_sa_inspect.side_effect = lambda arg: mapper if arg is entity.__class__ else instance_state

        result = entity_to_dict(entity)
        assert result["created_at"] == "2024-06-15T10:30:00"

    @patch("lys.core.utils.tool_generator.sa_inspect")
    def test_hex_values(self, mock_sa_inspect):
        """Test values with hex attr (but no isoformat) are serialized via str()."""
        from lys.core.utils.tool_generator import entity_to_dict

        mock_uuid = MagicMock(spec=[])  # spec=[] prevents auto-creating isoformat
        mock_uuid.hex = "aabbccdd"

        entity = MagicMock()
        entity.ref_id = mock_uuid

        mapper = MagicMock()
        mapper.column_attrs = [MagicMock(key="ref_id")]
        mapper.relationships = []

        instance_state = MagicMock()
        instance_state.dict = {}

        mock_sa_inspect.side_effect = lambda arg: mapper if arg is entity.__class__ else instance_state

        result = entity_to_dict(entity)
        assert result["ref_id"] == str(mock_uuid)

    @patch("lys.core.utils.tool_generator.sa_inspect")
    def test_one_to_many_relation_loaded(self, mock_sa_inspect):
        """Test loaded uselist=True relation serializes children as list."""
        from lys.core.utils.tool_generator import entity_to_dict

        child = MagicMock()
        child.id = "child-1"

        entity = MagicMock()
        entity.id = "parent-1"
        entity.children = [child]

        parent_mapper = MagicMock()
        parent_mapper.column_attrs = [MagicMock(key="id")]
        parent_mapper.relationships = [MagicMock(key="children", uselist=True)]

        parent_state = MagicMock()
        parent_state.dict = {"children": [child]}

        child_mapper = MagicMock()
        child_mapper.column_attrs = [MagicMock(key="id")]
        child_mapper.relationships = []
        child_state = MagicMock()
        child_state.dict = {}

        def inspect_side_effect(arg):
            if arg is entity.__class__:
                return parent_mapper
            if arg is entity:
                return parent_state
            if arg is child.__class__:
                return child_mapper
            if arg is child:
                return child_state
            return MagicMock()

        mock_sa_inspect.side_effect = inspect_side_effect

        result = entity_to_dict(entity)
        assert "children" in result
        assert isinstance(result["children"], list)
        assert len(result["children"]) == 1
        assert result["children"][0]["id"] == "child-1"

    @patch("lys.core.utils.tool_generator.sa_inspect")
    def test_many_to_one_relation_loaded(self, mock_sa_inspect):
        """Test loaded uselist=False relation serializes as nested dict."""
        from lys.core.utils.tool_generator import entity_to_dict

        parent = MagicMock()
        parent.id = "parent-1"

        entity = MagicMock()
        entity.id = "child-1"
        entity.parent = parent

        entity_mapper = MagicMock()
        entity_mapper.column_attrs = [MagicMock(key="id")]
        entity_mapper.relationships = [MagicMock(key="parent", uselist=False)]

        entity_state = MagicMock()
        entity_state.dict = {"parent": parent}

        parent_mapper = MagicMock()
        parent_mapper.column_attrs = [MagicMock(key="id")]
        parent_mapper.relationships = []
        parent_state = MagicMock()
        parent_state.dict = {}

        def inspect_side_effect(arg):
            if arg is entity.__class__:
                return entity_mapper
            if arg is entity:
                return entity_state
            if arg is parent.__class__:
                return parent_mapper
            if arg is parent:
                return parent_state
            return MagicMock()

        mock_sa_inspect.side_effect = inspect_side_effect

        result = entity_to_dict(entity)
        assert "parent" in result
        assert result["parent"]["id"] == "parent-1"

    @patch("lys.core.utils.tool_generator.sa_inspect")
    def test_not_loaded_relation_skipped(self, mock_sa_inspect):
        """Test relation not in instance_state.dict is skipped entirely."""
        from lys.core.utils.tool_generator import entity_to_dict

        entity = MagicMock()
        entity.id = "abc"

        mapper = MagicMock()
        mapper.column_attrs = [MagicMock(key="id")]
        mapper.relationships = [MagicMock(key="children", uselist=True)]

        instance_state = MagicMock()
        instance_state.dict = {}  # children NOT loaded

        mock_sa_inspect.side_effect = lambda arg: mapper if arg is entity.__class__ else instance_state

        result = entity_to_dict(entity)
        assert "children" not in result

    @patch("lys.core.utils.tool_generator.sa_inspect")
    def test_include_relations_false(self, mock_sa_inspect):
        """Test include_relations=False skips all relations."""
        from lys.core.utils.tool_generator import entity_to_dict

        entity = MagicMock()
        entity.id = "abc"

        mapper = MagicMock()
        mapper.column_attrs = [MagicMock(key="id")]
        mapper.relationships = [MagicMock(key="items", uselist=True)]

        instance_state = MagicMock()
        instance_state.dict = {"items": []}

        mock_sa_inspect.side_effect = lambda arg: mapper if arg is entity.__class__ else instance_state

        result = entity_to_dict(entity, include_relations=False)
        assert "items" not in result
        assert result["id"] == "abc"


# ===========================================================================
# node_to_dict
# ===========================================================================

class TestNodeToDict:
    """Test node_to_dict serialization."""

    def test_none_node(self):
        """Test None input returns None."""
        from lys.core.utils.tool_generator import node_to_dict

        assert node_to_dict(None) is None

    @patch("lys.core.utils.tool_generator.entity_to_dict")
    def test_node_with_entity(self, mock_entity_to_dict):
        """Test node with _entity attribute delegates to entity_to_dict."""
        from lys.core.utils.tool_generator import node_to_dict

        mock_entity = MagicMock()
        node = MagicMock()
        node._entity = mock_entity

        mock_entity_to_dict.return_value = {"id": "123", "name": "Test"}
        result = node_to_dict(node)

        mock_entity_to_dict.assert_called_once_with(mock_entity)
        assert result == {"id": "123", "name": "Test"}

    @patch("lys.core.utils.tool_generator.strawberry")
    def test_node_without_entity_uses_asdict(self, mock_strawberry_module):
        """Test node without _entity uses strawberry.asdict and filters private/callable keys."""
        from lys.core.utils.tool_generator import node_to_dict

        node = MagicMock(spec=[])  # No _entity attribute
        mock_strawberry_module.asdict.return_value = {
            "id": "456",
            "name": "Bob",
            "_internal": "hidden",
        }

        result = node_to_dict(node)
        assert result == {"id": "456", "name": "Bob"}
        assert "_internal" not in result


# ===========================================================================
# _is_scalar_type
# ===========================================================================

class TestIsScalarType:
    """Test _is_scalar_type detection."""

    def test_basic_python_scalars(self):
        """Test str, int, float, bool, datetime, NoneType are all scalar."""
        from lys.core.utils.tool_generator import _is_scalar_type

        for scalar_type in (str, int, float, bool, datetime, type(None)):
            assert _is_scalar_type(scalar_type) is True, f"{scalar_type} should be scalar"

    def test_type_with_strawberry_definition_is_not_scalar(self):
        """Test type with __strawberry_definition__ is NOT scalar (complex type)."""
        from lys.core.utils.tool_generator import _is_scalar_type

        class ComplexType:
            __strawberry_definition__ = MagicMock()

        assert _is_scalar_type(ComplexType) is False

    def test_wrapped_of_type_is_unwrapped(self):
        """Test StrawberryOptional wrapping a scalar type unwraps and detects scalar."""
        from lys.core.utils.tool_generator import _is_scalar_type

        wrapper = StrawberryOptional(of_type=str)
        assert _is_scalar_type(wrapper) is True

    def test_enum_in_name_is_scalar(self):
        """Test type with 'Enum' in name is detected as scalar."""
        from lys.core.utils.tool_generator import _is_scalar_type

        class StatusEnum:
            pass

        assert _is_scalar_type(StatusEnum) is True


# ===========================================================================
# _get_subfields
# ===========================================================================

class TestGetSubfields:
    """Test _get_subfields extraction."""

    def test_type_without_definition_returns_id(self):
        """Test type without __strawberry_definition__ returns ['id']."""
        from lys.core.utils.tool_generator import _get_subfields

        class PlainType:
            pass

        assert _get_subfields(PlainType) == ["id"]

    def test_filters_private_and_excluded_fields(self):
        """Test _private fields and EXCLUDED_FIELDS are filtered out."""
        from lys.core.utils.tool_generator import _get_subfields

        field_id = MagicMock()
        field_id.name = "id"
        field_id.type = str

        field_name = MagicMock()
        field_name.name = "name"
        field_name.type = str

        field_private = MagicMock()
        field_private.name = "_internal"
        field_private.type = str

        field_secret = MagicMock()
        field_secret.name = "password"
        field_secret.type = str

        mock_def = MagicMock()
        mock_def.fields = [field_id, field_name, field_private, field_secret]

        class TypeWithDef:
            __strawberry_definition__ = mock_def

        result = _get_subfields(TypeWithDef)
        assert "id" in result
        assert "name" in result
        assert "_internal" not in result
        assert "password" not in result

    def test_all_fields_excluded_returns_id(self):
        """Test when all fields are filtered out, returns ['id'] as fallback."""
        from lys.core.utils.tool_generator import _get_subfields

        field_pw = MagicMock()
        field_pw.name = "password"
        field_pw.type = str

        mock_def = MagicMock()
        mock_def.fields = [field_pw]

        class TypeWithOnlyExcluded:
            __strawberry_definition__ = mock_def

        assert _get_subfields(TypeWithOnlyExcluded) == ["id"]


# ===========================================================================
# extract_node_fields
# ===========================================================================

class TestExtractNodeFields:
    """Test extract_node_fields extraction."""

    def test_none_returns_empty_list(self):
        """Test None input returns empty list."""
        from lys.core.utils.tool_generator import extract_node_fields

        assert extract_node_fields(None) == []

    def test_no_strawberry_definition_returns_empty(self):
        """Test type without __strawberry_definition__ returns empty list."""
        from lys.core.utils.tool_generator import extract_node_fields

        class PlainType:
            pass

        assert extract_node_fields(PlainType) == []

    def test_scalar_and_complex_fields(self):
        """Test extraction generates plain names for scalars and braced subfields for complex types."""
        from lys.core.utils.tool_generator import extract_node_fields

        scalar_field = MagicMock()
        scalar_field.name = "name"
        scalar_field.type = str

        sub_id = MagicMock()
        sub_id.name = "id"
        sub_id.type = str

        sub_code = MagicMock()
        sub_code.name = "code"
        sub_code.type = str

        sub_def = MagicMock()
        sub_def.fields = [sub_id, sub_code]

        complex_inner_type = MagicMock()
        complex_inner_type.__strawberry_definition__ = sub_def
        complex_inner_type.__name__ = "StatusType"
        del complex_inner_type.of_type

        complex_field = MagicMock()
        complex_field.name = "status"
        complex_field.type = complex_inner_type

        mock_def = MagicMock()
        mock_def.fields = [scalar_field, complex_field]

        class NodeType:
            __strawberry_definition__ = mock_def

        result = extract_node_fields(NodeType)
        assert "name" in result
        status_entries = [f for f in result if f.startswith("status")]
        assert len(status_entries) == 1
        assert "id" in status_entries[0]
        assert "code" in status_entries[0]


# ===========================================================================
# extract_return_fields_from_type
# ===========================================================================

class TestExtractReturnFieldsFromType:
    """Test extract_return_fields_from_type."""

    def test_connection_type_fallback(self):
        """Test Connection type without resolvable node falls back to 'edges { node { id } }'."""
        from lys.core.utils.tool_generator import extract_return_fields_from_type

        class SomeConnection:
            __name__ = "SomeConnection"

        result = extract_return_fields_from_type(SomeConnection)
        assert result == "edges { node { id } }"

    def test_simple_node_type(self):
        """Test simple node type returns space-joined field names."""
        from lys.core.utils.tool_generator import extract_return_fields_from_type

        field_id = MagicMock()
        field_id.name = "id"
        field_id.type = str

        field_name = MagicMock()
        field_name.name = "name"
        field_name.type = str

        mock_def = MagicMock()
        mock_def.fields = [field_id, field_name]

        class SimpleNode:
            __strawberry_definition__ = mock_def

        result = extract_return_fields_from_type(SimpleNode)
        assert "id" in result
        assert "name" in result

    def test_type_with_no_fields_returns_id(self):
        """Test type whose extract_node_fields returns empty list produces 'id'."""
        from lys.core.utils.tool_generator import extract_return_fields_from_type

        mock_def = MagicMock()
        mock_def.fields = []

        class EmptyNode:
            __strawberry_definition__ = mock_def

        result = extract_return_fields_from_type(EmptyNode)
        assert result == "id"

    def test_wrapped_type_unwrapped(self):
        """Test StrawberryOptional wrapping is unwrapped before processing."""
        from lys.core.utils.tool_generator import extract_return_fields_from_type

        field_id = MagicMock()
        field_id.name = "id"
        field_id.type = str

        mock_def = MagicMock()
        mock_def.fields = [field_id]

        class InnerNode:
            __strawberry_definition__ = mock_def

        wrapper = StrawberryOptional(of_type=InnerNode)
        result = extract_return_fields_from_type(wrapper)
        assert "id" in result


# ===========================================================================
# extract_tool_from_field
# ===========================================================================

class TestExtractToolFromField:
    """Test extract_tool_from_field."""

    def test_field_without_resolver_raises_value_error(self):
        """Test field without base_resolver raises ValueError."""
        from lys.core.utils.tool_generator import extract_tool_from_field

        field = MagicMock()
        field.base_resolver = None

        with pytest.raises(ValueError, match="does not have a resolver"):
            extract_tool_from_field(field)

    def test_basic_params_and_explicit_description(self):
        """Test extracts function name, params, and explicit description override."""
        from lys.core.utils.tool_generator import extract_tool_from_field

        def get_user(self, info, user_id: str) -> None:
            """Get a user by ID."""
            pass

        field = MagicMock()
        field.base_resolver.wrapped_func = get_user
        field.description = "Retrieve a user"
        field.type = None

        result = extract_tool_from_field(field, description="Custom description")

        assert result["type"] == "function"
        assert result["function"]["name"] == "get_user"
        assert result["function"]["description"] == "Custom description"
        props = result["function"]["parameters"]["properties"]
        assert "user_id" in props
        assert "self" not in props
        assert "info" not in props
        assert "user_id" in result["function"]["parameters"].get("required", [])

    def test_docstring_description_fallback(self):
        """Test description falls back to first line of resolver docstring."""
        from lys.core.utils.tool_generator import extract_tool_from_field

        def list_items(info, page: int = 1) -> None:
            """List all items in the system."""
            pass

        field = MagicMock()
        field.base_resolver.wrapped_func = list_items
        field.description = None
        field.type = None

        result = extract_tool_from_field(field)
        assert result["function"]["description"] == "List all items in the system."
        assert "page" not in result["function"]["parameters"].get("required", [])

    def test_strawberry_input_flattening(self):
        """Test strawberry input parameter is flattened into tool properties with input_wrappers."""
        from lys.core.utils.tool_generator import extract_tool_from_field

        @strawberry.input
        class CreateUserInput:
            name: str
            email: str

        def create_user(info, input: CreateUserInput) -> None:
            """Create a new user."""
            pass

        field = MagicMock()
        field.base_resolver.wrapped_func = create_user
        field.description = "Create user"
        field.type = None

        result = extract_tool_from_field(field)

        props = result["function"]["parameters"]["properties"]
        assert "name" in props
        assert "email" in props
        assert "input" not in props
        wrappers = result["_graphql"]["input_wrappers"]
        assert wrappers is not None
        assert wrappers[0]["param_name"] == "input"
        assert "name" in wrappers[0]["fields"]
        assert "email" in wrappers[0]["fields"]

    def test_return_type_used_for_return_fields(self):
        """Test field.type is used to extract return fields in _graphql metadata."""
        from lys.core.utils.tool_generator import extract_tool_from_field

        def get_item(info, item_id: str) -> None:
            pass

        field_id = MagicMock()
        field_id.name = "id"
        field_id.type = str

        field_name = MagicMock()
        field_name.name = "name"
        field_name.type = str

        mock_def = MagicMock()
        mock_def.fields = [field_id, field_name]

        class ItemNode:
            __strawberry_definition__ = mock_def

        field = MagicMock()
        field.base_resolver.wrapped_func = get_item
        field.description = "Get item"
        field.type = ItemNode

        result = extract_tool_from_field(field)
        assert "id" in result["_graphql"]["return_fields"]
        assert "name" in result["_graphql"]["return_fields"]


# ===========================================================================
# extract_tool_from_resolver
# ===========================================================================

class TestExtractToolFromResolver:
    """Test extract_tool_from_resolver."""

    def test_typed_params_and_explicit_description(self):
        """Test basic resolver with typed parameters and explicit description."""
        from lys.core.utils.tool_generator import extract_tool_from_resolver

        def search_users(query: str, limit: int = 10) -> None:
            pass

        result = extract_tool_from_resolver(search_users, description="Search for users")

        assert result["function"]["name"] == "search_users"
        assert result["function"]["description"] == "Search for users"
        props = result["function"]["parameters"]["properties"]
        assert props["query"]["type"] == "string"
        assert props["limit"]["type"] == "integer"
        assert "query" in result["function"]["parameters"].get("required", [])
        assert "limit" not in result["function"]["parameters"].get("required", [])

    def test_docstring_description(self):
        """Test description extracted from docstring when not provided."""
        from lys.core.utils.tool_generator import extract_tool_from_resolver

        def fetch_data(key: str) -> None:
            """Fetch data from the store."""
            pass

        result = extract_tool_from_resolver(fetch_data)
        assert result["function"]["description"] == "Fetch data from the store."

    def test_default_description_when_none(self):
        """Test resolver without description or docstring gets 'Execute X operation' default."""
        from lys.core.utils.tool_generator import extract_tool_from_resolver

        def do_something(value: int) -> None:
            pass

        result = extract_tool_from_resolver(do_something)
        assert result["function"]["description"] == "Execute do_something operation"

    def test_optional_params_not_required(self):
        """Test optional params are not in required list."""
        from lys.core.utils.tool_generator import extract_tool_from_resolver

        def find_items(name: Optional[str] = None, status: str = "active") -> None:
            pass

        result = extract_tool_from_resolver(find_items)
        assert "required" not in result["function"]["parameters"]

    def test_graphql_metadata(self):
        """Test _graphql metadata has correct operation_name, return_fields, node_type."""
        from lys.core.utils.tool_generator import extract_tool_from_resolver

        def get_user_by_email(email: str) -> None:
            pass

        result = extract_tool_from_resolver(get_user_by_email)
        graphql = result["_graphql"]
        assert graphql["operation_name"] == "getUserByEmail"
        assert graphql["return_fields"] == "id"
        assert graphql["node_type"] is None
        assert graphql["input_wrappers"] is None

    def test_strawberry_input_flattening(self):
        """Test resolver with strawberry input type flattens fields and populates input_wrappers."""
        from lys.core.utils.tool_generator import extract_tool_from_resolver

        @strawberry.input
        class UpdateInput:
            name: str
            active: bool

        def update_entity(self, info, data: UpdateInput) -> None:
            pass

        result = extract_tool_from_resolver(update_entity)

        props = result["function"]["parameters"]["properties"]
        assert "name" in props
        assert "active" in props
        assert "data" not in props
        assert result["_graphql"]["input_wrappers"] is not None


# ===========================================================================
# _get_node_type_from_connection
# ===========================================================================

class TestGetNodeTypeFromConnection:
    """Test _get_node_type_from_connection."""

    def test_connection_with_orig_bases_containing_connection_generic(self):
        """Test connection with __orig_bases__ containing Connection[NodeType] returns NodeType."""
        from lys.core.utils.tool_generator import _get_node_type_from_connection

        class FakeNode:
            __strawberry_definition__ = MagicMock()

        # Create a fake generic base that simulates Connection[FakeNode]
        fake_base = MagicMock()

        class FakeConnection:
            __orig_bases__ = (fake_base,)

        with patch("lys.core.utils.tool_generator.get_origin") as mock_get_origin, \
             patch("lys.core.utils.tool_generator.get_args") as mock_get_args:

            mock_origin = MagicMock()
            mock_origin.__name__ = "ListConnection"
            mock_get_origin.return_value = mock_origin
            mock_get_args.return_value = (FakeNode,)

            result = _get_node_type_from_connection(FakeConnection)
            assert result is FakeNode

    def test_connection_fallback_to_edges_node_field(self):
        """Test connection without matching __orig_bases__ falls back to edges.node extraction."""
        from lys.core.utils.tool_generator import _get_node_type_from_connection

        class FakeNode:
            __strawberry_definition__ = MagicMock()

        # Build node field: type is FakeNode directly (no of_type wrapping)
        node_field = MagicMock(spec=["name", "type"])
        node_field.name = "node"
        node_field.type = FakeNode

        edge_def = MagicMock()
        edge_def.fields = [node_field]

        # edge_type: no of_type wrapping, has __strawberry_definition__
        edge_type = MagicMock(spec=["__strawberry_definition__"])
        edge_type.__strawberry_definition__ = edge_def

        # edges_field: type is edge_type (no of_type)
        edges_field = MagicMock(spec=["name", "type"])
        edges_field.name = "edges"
        edges_field.type = edge_type

        conn_def = MagicMock()
        conn_def.fields = [edges_field]

        class FakeConnection:
            __orig_bases__ = ()
            __strawberry_definition__ = conn_def

        result = _get_node_type_from_connection(FakeConnection)
        assert result is FakeNode

    def test_connection_without_definition_returns_none(self):
        """Test connection without __strawberry_definition__ and empty __orig_bases__ returns None."""
        from lys.core.utils.tool_generator import _get_node_type_from_connection

        class EmptyConnection:
            __orig_bases__ = ()

        result = _get_node_type_from_connection(EmptyConnection)
        assert result is None
