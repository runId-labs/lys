"""
Local Tool Executor.

Executes tools via local resolvers in monolith mode.
"""

import inspect
import logging
from typing import Dict, Any, List, Optional, get_origin, get_args, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select as SQLSelect
from strawberry import relay

from lys.apps.ai.modules.core.executors.abstracts import ToolExecutor
from lys.apps.ai.modules.core.services import AIToolService
from lys.apps.ai.utils.guardrails import AIGuardrailService
from lys.core.utils.tool_generator import entity_to_dict, node_to_dict

logger = logging.getLogger(__name__)


class LocalToolExecutor(ToolExecutor):
    """
    Executes tools via local resolvers (monolith mode).

    Handles:
    - Tool lookup from app registry
    - Argument conversion (GlobalID, input reconstruction)
    - Guardrail processing (confirmation required for mutations)
    - Result serialization
    """

    def __init__(self, app_manager=None):
        """
        Initialize the local tool executor.

        Args:
            app_manager: Application manager with registry (optional, can be passed in context)
        """
        self._app_manager = app_manager
        self._tools = []
        self._info = None
        self._accessible_routes = []

    async def initialize(self, tools: List[Dict[str, Any]] = None, **kwargs) -> None:
        """
        Initialize the executor with tools and context.

        Args:
            tools: List of tool definitions
            **kwargs: Additional initialization parameters
                - info: GraphQL context
                - accessible_routes: List of routes accessible to the user for navigation
        """
        if tools:
            self._tools = tools
        self._info = kwargs.get("info")
        self._accessible_routes = kwargs.get("accessible_routes") or []

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool by calling its registered resolver.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments for the tool
            context: Execution context with session and info

        Returns:
            Tool execution result
        """
        session: AsyncSession = context.get("session")
        info = context.get("info")

        if info is None:
            raise ValueError("GraphQL info context is required for local tool execution")

        app_manager = self._app_manager or info.context.app_manager

        # Handle confirm_action as a special tool
        if tool_name == "confirm_action":
            return await self._handle_confirm_action(arguments, session, info)

        # Handle navigate as a frontend passthrough tool
        if tool_name == "navigate":
            return self._handle_navigate(arguments, info)

        # Get the tool from AIToolService
        tool_data = await AIToolService.get_tool(tool_name)
        if not tool_data:
            raise ValueError(f"Tool '{tool_name}' not found")

        # Get resolver info for argument conversion
        resolver = tool_data["resolver"]
        node_type = tool_data.get("node_type")

        # Get the actual callable from the resolver
        if hasattr(resolver, "wrapped_func"):
            actual_resolver = resolver.wrapped_func
        else:
            actual_resolver = resolver

        sig = inspect.signature(actual_resolver)

        # Convert string arguments to GlobalID where needed
        converted_args = self._convert_tool_args(sig, arguments, node_type)

        # Reconstruct Strawberry input objects from flattened arguments
        converted_args = self._reconstruct_input_args(sig, converted_args)

        # Pass through guardrail
        guardrail_result = await self._process_guardrail(
            tool_name, tool_data, converted_args, info
        )

        # If confirmation is required, return that to the LLM
        if guardrail_result and guardrail_result.get("status") == "confirmation_required":
            return guardrail_result

        # Execute the tool
        return await self._execute_internal(
            tool_name, tool_data, converted_args, session, info
        )

    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get all available tool definitions from registry."""
        if self._app_manager is None:
            return []
        return self._app_manager.registry.get_tools()

    async def _handle_confirm_action(
        self,
        tool_args: Dict[str, Any],
        session: AsyncSession,
        info: Any,
    ) -> Any:
        """Handle confirm_action special tool."""
        action_id = tool_args.get("action_id", "")
        confirmed = tool_args.get("confirmed", False)

        result = await AIGuardrailService.confirm_action(action_id, confirmed, info)

        # If confirmed and status is "execute", execute the actual tool
        if result.get("status") == "execute":
            executed_result = await self._execute_internal(
                result["tool_name"],
                result["tool_data"],
                result["tool_args"],
                session,
                info,
            )

            # Add refresh action for frontend to reload data
            tool_data = result.get("tool_data", {})
            node_type = tool_data.get("node_type")
            if node_type:
                if not hasattr(info.context, "frontend_actions"):
                    info.context.frontend_actions = []
                info.context.frontend_actions.append({
                    "type": "refresh",
                    "nodes": [node_type.__name__],
                })

            return executed_result

        return result

    def _handle_navigate(self, tool_args: Dict[str, Any], info: Any) -> Dict[str, Any]:
        """Handle navigate frontend passthrough tool."""
        path = tool_args.get("path", "")

        # Validate path against accessible routes
        valid_paths = [route["path"] for route in self._accessible_routes]

        if path not in valid_paths:
            return {
                "status": "error",
                "message": f"Path '{path}' is not accessible. Available paths: {', '.join(valid_paths)}",
            }

        # Store frontend action in context for later collection
        if not hasattr(info.context, "frontend_actions"):
            info.context.frontend_actions = []

        info.context.frontend_actions.append({
            "type": "navigate",
            "path": path,
        })

        return {
            "status": "navigation_scheduled",
            "message": f"Navigation to '{path}' has been scheduled. The user will be redirected.",
        }

    async def _process_guardrail(
        self,
        tool_name: str,
        tool_data: Dict[str, Any],
        converted_args: Dict[str, Any],
        info: Any,
    ) -> Optional[Dict[str, Any]]:
        """Process tool call through guardrail."""
        return await AIGuardrailService.process_tool_call(
            tool_name, tool_data, converted_args, info
        )

    async def _execute_internal(
        self,
        tool_name: str,
        tool_data: Dict[str, Any],
        converted_args: Dict[str, Any],
        session: AsyncSession,
        info: Any,
    ) -> Any:
        """
        Internal method to execute a tool after guardrail approval.

        Args:
            tool_name: Name of the tool
            tool_data: Tool data from registry
            converted_args: Already converted and reconstructed arguments
            session: Database session
            info: GraphQL info context

        Returns:
            Tool execution result
        """
        resolver = tool_data["resolver"]
        node_type = tool_data.get("node_type")

        logger.info(f"Executing tool: {tool_name} with args: {converted_args}")

        # Get the actual callable from the resolver
        if hasattr(resolver, "wrapped_func"):
            actual_resolver = resolver.wrapped_func
        else:
            actual_resolver = resolver

        # Check if resolver needs 'self' parameter (mutations vs queries)
        sig = inspect.signature(actual_resolver)
        params = list(sig.parameters.keys())

        if params and params[0] == "self":
            # Mutation - pass None as self
            result = await actual_resolver(None, info=info, **converted_args)
        else:
            # Query/getter - no self needed
            result = await actual_resolver(info=info, **converted_args)

        # Handle SQLAlchemy Select objects (from @lys_connection resolvers)
        if isinstance(result, SQLSelect):
            # Execute the query and get results
            db_result = await session.execute(result)
            entities = db_result.scalars().all()
            if not entities:
                return {"items": [], "message": "No results found"}

            # Convert entities to nodes if node_type is available
            if node_type and hasattr(node_type, "from_entity"):
                items = [node_to_dict(node_type.from_entity(entity)) for entity in entities]
            else:
                items = [entity_to_dict(entity, include_relations=True, max_depth=2) for entity in entities]

            return {
                "items": items,
                "total": len(entities),
            }

        # Serialize the result
        return self._serialize_result(result)

    def _convert_tool_args(
        self,
        sig: inspect.Signature,
        tool_args: Dict[str, Any],
        node_type: type = None,
    ) -> Dict[str, Any]:
        """
        Convert tool arguments to the expected types.

        Handles conversion of string UUIDs to relay.GlobalID objects.
        """
        converted = {}

        for param_name, value in tool_args.items():
            if param_name not in sig.parameters:
                converted[param_name] = value
                continue

            param = sig.parameters[param_name]
            param_type = param.annotation

            # Handle Optional[GlobalID] - unwrap the Union
            actual_type = param_type
            origin = get_origin(param_type)
            if origin is Union:
                args = get_args(param_type)
                non_none_args = [a for a in args if a is not type(None)]
                if non_none_args:
                    actual_type = non_none_args[0]

            # Check if parameter expects GlobalID
            type_name = getattr(actual_type, "__name__", str(actual_type))
            if "GlobalID" in type_name and isinstance(value, str):
                # Determine the GraphQL type name for the GlobalID
                if param_name == "id" and node_type:
                    gid_type_name = node_type.__name__
                else:
                    # For explicit parameters like 'user_id', 'client_id', derive from param name
                    base_name = param_name.replace("_id", "")
                    parts = base_name.split("_")
                    pascal_name = "".join(part.capitalize() for part in parts)
                    gid_type_name = f"{pascal_name}Node"

                converted[param_name] = relay.GlobalID(gid_type_name, value)
                logger.debug(f"Converted {param_name}={value} to GlobalID({gid_type_name}, {value})")
            else:
                converted[param_name] = value

        return converted

    def _reconstruct_input_args(
        self,
        sig: inspect.Signature,
        tool_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Reconstruct Strawberry input objects from flattened arguments.
        """
        from typing import Annotated

        result = dict(tool_args)

        for param_name, param in sig.parameters.items():
            # Skip non-input parameters
            if param_name in ("self", "info", "obj"):
                continue

            param_type = param.annotation
            if param_type is inspect.Parameter.empty:
                continue

            # Handle Annotated types
            origin = get_origin(param_type)
            if origin is Annotated:
                args = get_args(param_type)
                if args:
                    param_type = args[0]

            # Handle Optional types
            origin = get_origin(param_type)
            if origin is Union:
                args = get_args(param_type)
                non_none_args = [a for a in args if a is not type(None)]
                if non_none_args:
                    param_type = non_none_args[0]

            # Check if it's a Strawberry input type
            if not hasattr(param_type, "__strawberry_definition__"):
                continue

            # Get the field names from the Strawberry input
            strawberry_def = param_type.__strawberry_definition__
            if not hasattr(strawberry_def, "fields"):
                continue

            # Collect arguments that belong to this input
            input_args = {}
            fields_to_remove = []

            for field in strawberry_def.fields:
                field_name = field.name
                if field_name in result:
                    input_args[field_name] = result[field_name]
                    fields_to_remove.append(field_name)

            # If we found any fields for this input, create the input object
            if input_args:
                for field_name in fields_to_remove:
                    del result[field_name]

                try:
                    input_obj = param_type(**input_args)
                    result[param_name] = input_obj
                    logger.debug(f"Reconstructed {param_name} input with fields: {list(input_args.keys())}")
                except Exception as e:
                    logger.error(f"Failed to reconstruct input {param_name}: {e}")
                    for field_name in fields_to_remove:
                        result[field_name] = input_args.get(field_name)

        return result

    def _serialize_result(self, result: Any) -> Any:
        """
        Serialize a tool result for the LLM.

        Handles SQLAlchemy objects, Pydantic models, and basic types.
        """
        if result is None:
            return None

        # Handle datetime
        if hasattr(result, "isoformat"):
            return result.isoformat()

        # Handle UUID
        if hasattr(result, "hex") and hasattr(result, "int"):
            return str(result)

        # Handle lists
        if isinstance(result, list):
            return [self._serialize_result(item) for item in result]

        # Handle dicts
        if isinstance(result, dict):
            return {k: self._serialize_result(v) for k, v in result.items()}

        # Handle Relay Connection objects (pagination results)
        if hasattr(result, "edges"):
            edges = getattr(result, "edges", [])
            if not edges:
                return {"items": [], "message": "No results found"}
            return {
                "items": [self._serialize_result(edge.node) for edge in edges if hasattr(edge, "node")],
                "total": len(edges),
            }

        # Handle Strawberry nodes (EntityNode, ServiceNode)
        if hasattr(result, "_entity") or hasattr(result, "__strawberry_definition__"):
            return node_to_dict(result)

        # Handle SQLAlchemy entities
        if hasattr(result, "__table__"):
            return entity_to_dict(result, include_relations=True, max_depth=2)

        # Handle Pydantic models
        if hasattr(result, "model_dump"):
            return result.model_dump()

        # Handle objects with __dict__
        if hasattr(result, "__dict__") and not isinstance(result, type):
            return {
                k: self._serialize_result(v)
                for k, v in result.__dict__.items()
                if not k.startswith("_")
            }

        # Basic types
        return result