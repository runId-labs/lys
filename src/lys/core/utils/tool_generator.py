"""
Tool generator utility for converting webservices to LLM tool definitions.

This module provides functionality to extract tool definitions from Strawberry GraphQL
fields, compatible with LLM function calling APIs (MistralAI, OpenAI, etc.).
"""

import inspect
import types
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, Union, get_args, get_origin

import strawberry

from lys.core.utils.strings import to_camel_case
from strawberry.types.field import StrawberryField
from sqlalchemy.inspection import inspect as sa_inspect


# Fields to exclude from serialization for security reasons
EXCLUDED_FIELDS = {
    "password",
    "hashed_password",
    "password_hash",
    "secret",
    "secret_key",
    "api_key",
    "token",
    "refresh_token",
    "access_token",
}


def entity_to_dict(entity, include_relations: bool = True, max_depth: int = 2) -> dict:
    """
    Serialize a SQLAlchemy entity to dict.

    Args:
        entity: SQLAlchemy entity instance
        include_relations: Whether to include loaded relations (many-to-one and one-to-many)
        max_depth: Maximum depth for nested relations

    Returns:
        Dict representation of the entity
    """
    if entity is None or max_depth <= 0:
        return None

    result = {}
    mapper = sa_inspect(entity.__class__)

    # All mapped columns (including inherited)
    for attr in mapper.column_attrs:
        # Skip sensitive fields
        if attr.key in EXCLUDED_FIELDS:
            continue

        value = getattr(entity, attr.key)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif hasattr(value, "hex"):
            value = str(value)
        result[attr.key] = value

    # Relations (many-to-one and one-to-many)
    # Only include relations that are already loaded to avoid lazy-loading errors
    if include_relations:
        # Get the instance state to check which relations are loaded
        instance_state = sa_inspect(entity)

        for rel in mapper.relationships:
            # Skip if relation is not loaded (would trigger lazy-loading)
            if rel.key not in instance_state.dict:
                continue

            if rel.uselist:
                # One-to-many relation - always return [] instead of None
                values = getattr(entity, rel.key, None)
                if values is not None:
                    result[rel.key] = [
                        entity_to_dict(item, True, max_depth - 1)
                        for item in values
                    ]
                else:
                    result[rel.key] = []
            else:
                # Many-to-one relation
                value = getattr(entity, rel.key, None)
                if value is not None:
                    result[rel.key] = entity_to_dict(value, True, max_depth - 1)

    return result


def node_to_dict(node) -> dict:
    """
    Serialize any Strawberry node to dict.

    Handles both EntityNodes (with _entity) and ServiceNodes (simple dataclasses).

    Args:
        node: Strawberry node instance

    Returns:
        Dict representation of the node
    """
    if node is None:
        return None

    # EntityNode or ParametricNode with _entity
    if hasattr(node, "_entity") and node._entity is not None:
        return entity_to_dict(node._entity)

    # ServiceNode or other - use strawberry.asdict
    result = strawberry.asdict(node)
    return {
        k: v for k, v in result.items()
        if not k.startswith("_") and not callable(v)
    }


def python_type_to_json_schema(python_type: Any, is_optional: bool = False) -> Dict[str, Any]:
    """
    Convert a Python type annotation to JSON Schema type definition.

    Args:
        python_type: Python type annotation (str, int, Optional[str], etc.)
        is_optional: Whether this type is optional (for GraphQL type suffix)

    Returns:
        JSON Schema type definition dict
    """
    origin = get_origin(python_type)
    args = get_args(python_type)

    # Handle None type
    if python_type is type(None):
        return {"type": "null"}

    # Handle Strawberry wrapper types
    type_class_name = type(python_type).__name__

    # StrawberryOptional (Strawberry's wrapper for Optional types)
    if type_class_name == "StrawberryOptional":
        if hasattr(python_type, "of_type"):
            return python_type_to_json_schema(python_type.of_type, is_optional=True)
        return {"type": "string"}

    # StrawberryList (Strawberry's wrapper for List types)
    if type_class_name == "StrawberryList":
        if hasattr(python_type, "of_type"):
            return {
                "type": "array",
                "items": python_type_to_json_schema(python_type.of_type)
            }
        return {"type": "array"}

    # Handle Optional (Union with None) - both typing.Union and types.UnionType (X | Y syntax)
    if origin is Union or isinstance(python_type, types.UnionType):
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1:
            # It's Optional[X]
            return python_type_to_json_schema(non_none_args[0], is_optional=True)
        else:
            # It's a real Union, use anyOf
            return {
                "anyOf": [python_type_to_json_schema(arg) for arg in args]
            }

    # Handle List
    if origin is list:
        if args:
            return {
                "type": "array",
                "items": python_type_to_json_schema(args[0])
            }
        return {"type": "array"}

    # Handle basic types
    if python_type is str:
        return {"type": "string", "_graphql_type": "String" if is_optional else "String!"}
    if python_type is int:
        return {"type": "integer", "_graphql_type": "Int" if is_optional else "Int!"}
    if python_type is float:
        return {"type": "number", "_graphql_type": "Float" if is_optional else "Float!"}
    if python_type is bool:
        return {"type": "boolean", "_graphql_type": "Boolean" if is_optional else "Boolean!"}
    if python_type is datetime:
        return {"type": "string", "format": "date-time", "_graphql_type": "DateTime" if is_optional else "DateTime!"}

    # Handle strawberry.ID and relay.GlobalID
    type_name = getattr(python_type, "__name__", str(python_type))
    if "GlobalID" in type_name or type_name == "ID":
        return {"type": "string", "description": "Global ID", "_graphql_type": "ID" if is_optional else "ID!"}

    # Handle Strawberry input types
    if hasattr(python_type, "__strawberry_definition__"):
        return extract_strawberry_input_schema(python_type)

    # Default to string for unknown types
    return {"type": "string", "_graphql_type": "String" if is_optional else "String!"}


def extract_strawberry_input_schema(input_class: type) -> Dict[str, Any]:
    """
    Extract JSON Schema from a Strawberry input class.

    Args:
        input_class: Strawberry input class decorated with @strawberry.input

    Returns:
        JSON Schema object definition with properties
    """
    properties = {}
    required = []

    # Get the Strawberry definition
    strawberry_def = getattr(input_class, "__strawberry_definition__", None)

    if strawberry_def and hasattr(strawberry_def, "fields"):
        # Check if this is a Pydantic-based input
        pydantic_model = getattr(strawberry_def, "pydantic_type", None)

        for field in strawberry_def.fields:
            field_name = field.name
            field_type = field.type

            # Resolve the actual type from StrawberryAnnotation
            if hasattr(field_type, "annotation"):
                actual_type = field_type.annotation
            else:
                actual_type = field_type

            # For Pydantic-based inputs, get the type from the Pydantic model
            # Check if it's strawberry.auto (can be compared by type name)
            is_auto = (
                actual_type is strawberry.auto or
                getattr(actual_type, "__name__", "") == "auto" or
                str(actual_type) == "<class 'strawberry.auto'>"
            )
            if pydantic_model and is_auto:
                model_fields = pydantic_model.model_fields
                if field_name in model_fields:
                    pydantic_field = model_fields[field_name]
                    actual_type = pydantic_field.annotation

            # Convert to JSON schema
            schema = python_type_to_json_schema(actual_type)

            # Add description if available
            if hasattr(field, "description") and field.description:
                schema["description"] = field.description

            properties[field_name] = schema

            # Check if field is required (not Optional)
            origin = get_origin(actual_type)
            args = get_args(actual_type)
            is_optional = origin is Union and type(None) in args

            # Check for default values - Strawberry uses different attributes
            has_default = False
            if hasattr(field, "default"):
                has_default = field.default is not strawberry.UNSET
            if hasattr(field, "default_value"):
                has_default = has_default or field.default_value is not strawberry.UNSET

            if not is_optional and not has_default:
                required.append(field_name)

    result = {
        "type": "object",
        "properties": properties
    }

    if required:
        result["required"] = required

    return result


def _is_scalar_type(field_type) -> bool:
    """Check if a Strawberry field type is a scalar (not an object requiring subfields)."""
    # Unwrap StrawberryOptional/StrawberryList
    while hasattr(field_type, "of_type"):
        field_type = field_type.of_type

    # Scalar types that don't need subfield selection
    scalar_types = {str, int, float, bool, datetime, type(None)}
    type_name = getattr(field_type, "__name__", str(field_type))

    return (
        field_type in scalar_types or
        type_name in {"str", "int", "float", "bool", "ID", "GlobalID", "UUID", "Date", "DateTime"} or
        "Enum" in type_name or
        not hasattr(field_type, "__strawberry_definition__")
    )


def _get_subfields(field_type) -> List[str]:
    """Get minimal subfields for a complex type (id, code, name, email)."""
    # Unwrap StrawberryOptional/StrawberryList
    while hasattr(field_type, "of_type"):
        field_type = field_type.of_type

    strawberry_def = getattr(field_type, "__strawberry_definition__", None)
    if not strawberry_def or not hasattr(strawberry_def, "fields"):
        return ["id"]

    # Priority fields for nested objects
    priority_fields = ["id", "code", "name", "email", "value"]
    subfields = []

    for field in strawberry_def.fields:
        if field.name.startswith("_"):
            continue
        if field.name in EXCLUDED_FIELDS:
            continue
        if field.name in priority_fields and _is_scalar_type(field.type):
            subfields.append(field.name)

    return subfields if subfields else ["id"]


def _get_node_type_from_connection(connection_type) -> type:
    """Extract the node type from a Relay Connection type."""
    strawberry_def = getattr(connection_type, "__strawberry_definition__", None)
    if not strawberry_def or not hasattr(strawberry_def, "fields"):
        return None

    # Find edges field
    for field in strawberry_def.fields:
        if field.name == "edges":
            edge_type = field.type
            # Unwrap List/Optional
            while hasattr(edge_type, "of_type"):
                edge_type = edge_type.of_type

            # Get node from edge
            edge_def = getattr(edge_type, "__strawberry_definition__", None)
            if edge_def and hasattr(edge_def, "fields"):
                for edge_field in edge_def.fields:
                    if edge_field.name == "node":
                        node_type = edge_field.type
                        while hasattr(node_type, "of_type"):
                            node_type = node_type.of_type
                        return node_type
    return None


def extract_return_fields_from_type(return_type) -> str:
    """
    Extract GraphQL return fields from a Strawberry return type.

    Handles both simple Node types and Relay Connection types.

    Args:
        return_type: The Strawberry type (can be Connection, Node, or wrapped type)

    Returns:
        String of GraphQL fields suitable for the query
    """
    # Unwrap StrawberryOptional/StrawberryList
    while hasattr(return_type, "of_type"):
        return_type = return_type.of_type

    type_name = getattr(return_type, "__name__", "")

    # Check if it's a Relay Connection type
    if "Connection" in type_name:
        # Extract node type and get its fields
        node_type = _get_node_type_from_connection(return_type)
        if node_type:
            node_fields = extract_node_fields(node_type)
            if node_fields:
                return f"edges {{ node {{ {' '.join(node_fields)} }} }}"
        return "edges { node { id } }"

    # Simple Node type - extract fields directly
    fields = extract_node_fields(return_type)
    return " ".join(fields) if fields else "id"


def extract_node_fields(node_type: type) -> List[str]:
    """
    Extract field names from a Strawberry node type for GraphQL queries.

    Generates proper GraphQL field selections including subfields for complex types.

    Args:
        node_type: Strawberry node class

    Returns:
        List of field selections (e.g., ["id", "name", "status { id code }"])
    """
    if node_type is None:
        return []

    strawberry_def = getattr(node_type, "__strawberry_definition__", None)
    if not strawberry_def or not hasattr(strawberry_def, "fields"):
        return []

    fields = []
    for field in strawberry_def.fields:
        # Skip private fields and internal fields
        if field.name.startswith("_"):
            continue
        # Skip sensitive fields
        if field.name in EXCLUDED_FIELDS:
            continue

        if _is_scalar_type(field.type):
            fields.append(field.name)
        else:
            # Complex type - add with subfields
            subfields = _get_subfields(field.type)
            fields.append(f"{field.name} {{ {' '.join(subfields)} }}")

    return fields


def extract_tool_from_field(
    field: StrawberryField,
    description: Optional[str] = None,
    node_type: type = None
) -> Dict[str, Any]:
    """
    Extract an LLM tool definition from a Strawberry field.

    This function analyzes a StrawberryField to generate a tool definition
    compatible with LLM function calling APIs (MistralAI, OpenAI, etc.).

    Args:
        field: StrawberryField containing the resolver and type information
        description: Optional description override (uses field description if not provided)

    Returns:
        Tool definition dict in the format:
        {
            "type": "function",
            "function": {
                "name": "function_name",
                "description": "Function description",
                "parameters": {
                    "type": "object",
                    "properties": {...},
                    "required": [...]
                }
            }
        }
    """
    # Get function name
    if hasattr(field, "base_resolver") and field.base_resolver:
        func_name = field.base_resolver.wrapped_func.__name__
        signature = inspect.signature(field.base_resolver.wrapped_func)
    else:
        raise ValueError("Field does not have a resolver")

    # Get description
    tool_description = description
    if not tool_description and hasattr(field, "description"):
        tool_description = field.description
    if not tool_description:
        # Try to get from docstring
        docstring = field.base_resolver.wrapped_func.__doc__
        if docstring:
            # Get first line of docstring
            tool_description = docstring.strip().split("\n")[0]

    # Extract parameters
    properties = {}
    required = []
    input_wrappers = []  # Track flattened input types for GraphQL reconstruction

    for param_name, param in signature.parameters.items():
        # Skip self, info, and obj parameters
        if param_name in ("self", "info", "obj"):
            continue

        # Get type annotation
        if param.annotation is inspect.Parameter.empty:
            continue

        param_type = param.annotation
        param_description = None

        # Handle Annotated types to extract description from strawberry.argument
        origin = get_origin(param_type)
        if origin is Annotated:
            args = get_args(param_type)
            if args:
                # First arg is the actual type
                param_type = args[0]
                # Check remaining args for strawberry.argument with description
                for arg in args[1:]:
                    if hasattr(arg, "description") and arg.description:
                        param_description = arg.description
                        break

        # Check if it's a Strawberry input type
        if hasattr(param_type, "__strawberry_definition__"):
            # Flatten the input type into parameters
            input_schema = extract_strawberry_input_schema(param_type)
            input_field_names = list(input_schema.get("properties", {}).keys())
            for prop_name, prop_schema in input_schema.get("properties", {}).items():
                properties[prop_name] = prop_schema
            required.extend(input_schema.get("required", []))

            # Store metadata for GraphQL input reconstruction
            input_wrappers.append({
                "param_name": param_name,
                "graphql_type": f"{param_type.__name__}!",
                "fields": input_field_names,
            })
        else:
            # Regular parameter
            schema = python_type_to_json_schema(param_type)

            # Add description if found
            if param_description:
                schema["description"] = param_description

            properties[param_name] = schema

            # Check if required
            origin = get_origin(param_type)
            args = get_args(param_type)
            is_optional = origin is Union or isinstance(param_type, types.UnionType)
            if is_optional and args:
                is_optional = type(None) in args
            else:
                is_optional = False
            has_default = param.default is not inspect.Parameter.empty

            if not is_optional and not has_default:
                required.append(param_name)

    # Build final description with return fields
    final_description = tool_description or f"Execute {func_name} operation"

    # Extract return fields from the actual return type of the field
    # This handles both simple Nodes and Relay Connections correctly
    return_fields_str = "id"
    if hasattr(field, "type") and field.type:
        return_fields_str = extract_return_fields_from_type(field.type)
    elif node_type:
        # Fallback to node_type if field.type not available
        fields = extract_node_fields(node_type)
        return_fields_str = " ".join(fields) if fields else "id"

    # Build tool definition
    tool = {
        "type": "function",
        "function": {
            "name": func_name,
            "description": final_description,
            "parameters": {
                "type": "object",
                "properties": properties
            }
        },
        "_graphql": {
            "operation_name": to_camel_case(func_name),
            "return_fields": return_fields_str,
            "node_type": node_type.__name__ if node_type else None,
            "input_wrappers": input_wrappers if input_wrappers else None,
        }
    }

    if required:
        tool["function"]["parameters"]["required"] = required

    return tool


def extract_tool_from_resolver(
    resolver: Any,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract an LLM tool definition from a resolver function.

    This is a convenience function for when you have direct access to the
    resolver function rather than a StrawberryField.

    Args:
        resolver: Resolver function with type annotations
        description: Optional description for the tool

    Returns:
        Tool definition dict
    """
    func_name = resolver.__name__
    signature = inspect.signature(resolver)

    # Get description from docstring if not provided
    tool_description = description
    if not tool_description and resolver.__doc__:
        tool_description = resolver.__doc__.strip().split("\n")[0]

    # Extract parameters
    properties = {}
    required = []
    input_wrappers = []

    for param_name, param in signature.parameters.items():
        # Skip self, info, and obj parameters
        if param_name in ("self", "info", "obj"):
            continue

        # Get type annotation
        if param.annotation is inspect.Parameter.empty:
            continue

        param_type = param.annotation

        # Check if it's a Strawberry input type
        if hasattr(param_type, "__strawberry_definition__"):
            # Flatten the input type into parameters
            input_schema = extract_strawberry_input_schema(param_type)
            input_field_names = list(input_schema.get("properties", {}).keys())
            for prop_name, prop_schema in input_schema.get("properties", {}).items():
                properties[prop_name] = prop_schema
            required.extend(input_schema.get("required", []))

            # Store metadata for GraphQL input reconstruction
            input_wrappers.append({
                "param_name": param_name,
                "graphql_type": f"{param_type.__name__}!",
                "fields": input_field_names,
            })
        else:
            # Regular parameter
            schema = python_type_to_json_schema(param_type)
            properties[param_name] = schema

            # Check if required
            origin = get_origin(param_type)
            args = get_args(param_type)
            is_optional = origin is Union and type(None) in args
            has_default = param.default is not inspect.Parameter.empty

            if not is_optional and not has_default:
                required.append(param_name)

    # Build tool definition
    tool = {
        "type": "function",
        "function": {
            "name": func_name,
            "description": tool_description or f"Execute {func_name} operation",
            "parameters": {
                "type": "object",
                "properties": properties
            }
        },
        "_graphql": {
            "operation_name": to_camel_case(func_name),
            "return_fields": "id",
            "node_type": None,
            "input_wrappers": input_wrappers if input_wrappers else None,
        }
    }

    if required:
        tool["function"]["parameters"]["required"] = required

    return tool