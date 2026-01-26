"""
GraphQL Tool Executor.

Executes tools via GraphQL calls to Apollo Gateway (microservice mode).
"""

import base64
import logging
from typing import Dict, Any, List, Optional

import httpx

from lys.apps.ai.modules.core.executors.abstracts import ToolExecutor
from lys.core.graphql.client import GraphQLClient
from lys.core.utils.strings import to_camel_case, to_snake_case

logger = logging.getLogger(__name__)


class GraphQLToolExecutor(ToolExecutor):
    """
    Executes tools via GraphQL calls to Apollo Gateway (microservice mode).

    In microservice architecture:
    - Tools are defined on child services (Orders, Inventory, etc.)
    - Tool definitions are fetched via gateway GraphQL query
    - Execution happens via GraphQL calls through the gateway

    Supports two authentication modes:
    - Service JWT: For inter-service calls (requires secret_key and service_name)
    - Bearer JWT: For user-authenticated calls (requires bearer_token)
    """

    def __init__(
        self,
        gateway_url: str,
        secret_key: str = None,
        service_name: str = None,
        bearer_token: str = None,
        timeout: int = 30,
    ):
        """
        Initialize the GraphQL tool executor.

        Either provide (secret_key + service_name) for Service auth,
        or bearer_token for Bearer auth.

        Args:
            gateway_url: URL of the Apollo Gateway
            secret_key: Secret key for service JWT generation (Service auth)
            service_name: Name of the calling service (Service auth)
            bearer_token: User JWT token (Bearer auth)
            timeout: HTTP request timeout in seconds
        """
        self.gateway_url = gateway_url
        self.timeout = timeout
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self._accessible_routes = []
        self._client = GraphQLClient(
            url=gateway_url,
            secret_key=secret_key,
            service_name=service_name,
            bearer_token=bearer_token,
            timeout=timeout,
        )

    async def initialize(self, tools: Optional[List[Dict[str, Any]]] = None, **kwargs):
        """
        Initialize the executor with tools.

        Can be initialized either by passing tools directly or by fetching
        from gateway.

        Args:
            tools: Optional list of tool definitions to use directly
            **kwargs: Additional initialization parameters
                - accessible_routes: List of routes accessible to the user for navigation
                - page_context: Page context for param injection
        """
        await super().initialize(tools, **kwargs)
        self._accessible_routes = kwargs.get("accessible_routes") or []

        if tools is not None:
            # Use provided tools
            for tool in tools:
                tool_def = tool.get("ai_tool") or tool.get("definition") or tool
                if tool_def:
                    name = tool_def.get("function", {}).get("name") or tool.get("name")
                    if name:
                        self._tools[name] = {
                            "definition": tool_def,
                            "operation_type": tool.get("operation_type") or "mutation",
                        }
            self._initialized = True
            return

        # Fetch from gateway via GraphQL
        await self._fetch_tools_from_gateway()
        self._initialized = True

    async def _fetch_tools_from_gateway(self):
        """Fetch AI tools from gateway via GraphQL query."""
        query = """
        query GetAITools {
            allWebservices(isAiTool: true) {
                edges {
                    node {
                        id
                        code
                        operationType
                        aiTool
                    }
                }
            }
        }
        """

        try:
            data = await self._client.execute(query)

            if "errors" in data:
                logger.error(f"GraphQL errors fetching tools: {data['errors']}")
                return

            edges = data.get("data", {}).get("allWebservices", {}).get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                ai_tool = node.get("aiTool")
                if ai_tool:
                    name = ai_tool.get("function", {}).get("name") or node.get("code")
                    self._tools[name] = {
                        "definition": ai_tool,
                        "operation_type": node.get("operationType") or "mutation",
                    }

            logger.info(f"Loaded {len(self._tools)} AI tools from gateway")

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch tools from gateway: {e}")
            raise

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool via GraphQL call to the gateway.

        Uses service JWT for authentication (user context is passed via arguments).

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments from LLM
            context: Execution context (contains info for special tools)

        Returns:
            Tool execution result
        """
        if not self._initialized:
            raise RuntimeError("GraphQLToolExecutor not initialized. Call initialize() first.")

        # Handle special tools that don't go through GraphQL
        if tool_name == "navigate":
            return self._handle_navigate(arguments, context)

        if tool_name == "confirm_action":
            return await self._handle_confirm_action(arguments, context)

        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' not found")

        tool = self._tools[tool_name]
        definition = tool["definition"]
        operation_type = tool["operation_type"]
        gql_meta = definition.get("_graphql", {})

        operation_name = gql_meta.get("operation_name", to_camel_case(tool_name))
        raw_return_fields = gql_meta.get("return_fields", "id")
        # Convert return fields to camelCase
        return_fields = " ".join(to_camel_case(f) for f in raw_return_fields.split())

        # Get parameter types from definition
        parameters = definition.get("function", {}).get("parameters", {})
        properties = parameters.get("properties", {})

        # Inject page context params into arguments
        arguments = self._inject_page_params(arguments)

        # Filter arguments by those the tool accepts (ignore unknown params like dStack)
        filtered_out = {k: v for k, v in arguments.items() if k not in properties}
        if filtered_out:
            logger.debug(
                f"[ParamFiltering] Tool '{tool_name}' - filtered out unknown params: {filtered_out}"
            )
        arguments = {k: v for k, v in arguments.items() if k in properties}

        # Filter orderBy fields to only include valid fields from the schema
        if "order_by" in arguments and isinstance(arguments["order_by"], dict):
            order_by_schema = properties.get("order_by", {})
            valid_fields = set(order_by_schema.get("properties", {}).keys())
            # Also accept snake_case versions of camelCase fields
            valid_fields_snake = {to_snake_case(f) for f in valid_fields}
            all_valid = valid_fields | valid_fields_snake

            original_order_by = arguments["order_by"]
            filtered_order_by = {k: v for k, v in original_order_by.items() if k in all_valid}
            if filtered_order_by != original_order_by:
                invalid_fields = set(original_order_by.keys()) - set(filtered_order_by.keys())
                logger.debug(
                    f"[ParamFiltering] Tool '{tool_name}' - filtered out invalid orderBy fields: {invalid_fields}"
                )
            arguments["order_by"] = filtered_order_by if filtered_order_by else None
            # Remove orderBy entirely if empty
            if not arguments["order_by"]:
                del arguments["order_by"]

        logger.debug(f"[ParamFiltering] Tool '{tool_name}' - final arguments: {arguments}")

        # Build GraphQL operation
        node_type = gql_meta.get("node_type")
        input_wrappers = gql_meta.get("input_wrappers")
        query, variables = self._build_operation(
            operation_type=operation_type,
            operation_name=operation_name,
            arguments=arguments,
            return_fields=return_fields,
            properties=properties,
            node_type=node_type,
            input_wrappers=input_wrappers,
        )

        logger.info(f"Executing tool {tool_name} via GraphQL: {operation_name}")
        logger.debug(f"Query: {query}")
        logger.debug(f"Variables: {variables}")

        try:
            data = await self._client.execute(query, variables)

            if "errors" in data:
                errors = data["errors"]
                error_messages = [e.get("message", str(e)) for e in errors]
                logger.error(f"GraphQL errors: {error_messages}")
                return {
                    "status": "error",
                    "message": "; ".join(error_messages),
                }

            result = data.get("data", {}).get(operation_name)
            if result is None:
                return {
                    "status": "error",
                    "message": f"No result returned from {operation_name}",
                }

            return result

        except httpx.HTTPError as e:
            logger.error(f"HTTP error executing tool {tool_name}: {e}")
            return {
                "status": "error",
                "message": f"HTTP error: {str(e)}",
            }

    def _build_operation(
        self,
        operation_type: str,
        operation_name: str,
        arguments: Dict[str, Any],
        return_fields: str,
        properties: Dict[str, Any],
        node_type: str = None,
        input_wrappers: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build GraphQL operation string and variables.

        Args:
            operation_type: "query" or "mutation"
            operation_name: GraphQL operation name (camelCase)
            arguments: Arguments from LLM (snake_case keys)
            return_fields: Fields to return (space-separated)
            properties: Parameter schema from tool definition
            node_type: GraphQL node type name for GlobalID conversion
            input_wrappers: Metadata for reconstructing flattened input types

        Returns:
            Tuple of (query_string, variables_dict)
        """
        # Build set of fields that belong to input wrappers
        wrapped_fields = set()
        if input_wrappers:
            for wrapper in input_wrappers:
                wrapped_fields.update(wrapper.get("fields", []))

        # Convert argument keys to camelCase and IDs to GlobalID for GraphQL
        # Also separate wrapped vs non-wrapped arguments
        variables = {}
        non_wrapped_args = {}

        for key, value in arguments.items():
            camel_key = to_camel_case(key)
            prop_schema = properties.get(key, {})
            graphql_type = prop_schema.get("_graphql_type", "")

            # Convert raw UUIDs to GlobalID for ID! types
            if "ID" in graphql_type and isinstance(value, str):
                value = self._to_global_id(key, value, node_type)

            if key not in wrapped_fields:
                # Non-wrapped argument - add directly to variables
                variables[camel_key] = value
                non_wrapped_args[key] = value
            # Wrapped fields will be handled below

        # Reconstruct input wrappers from flattened arguments
        if input_wrappers:
            for wrapper in input_wrappers:
                param_name = wrapper["param_name"]
                camel_param = to_camel_case(param_name)
                fields = wrapper.get("fields", [])

                # Build the input object from flattened fields
                input_obj = {}
                for field_name in fields:
                    if field_name in arguments:
                        camel_field = to_camel_case(field_name)
                        value = arguments[field_name]

                        # Check for ID conversion on nested fields
                        prop_schema = properties.get(field_name, {})
                        graphql_type = prop_schema.get("_graphql_type", "")
                        if "ID" in graphql_type and isinstance(value, str):
                            value = self._to_global_id(field_name, value, node_type)

                        input_obj[camel_field] = value

                if input_obj:
                    variables[camel_param] = input_obj

        # Build variables declaration
        vars_parts = []
        args_parts = []

        # Add non-wrapped arguments
        for key in non_wrapped_args:
            camel_key = to_camel_case(key)
            prop_schema = properties.get(key, {})
            logger.debug(f"[QueryBuild] key={key}, prop_schema keys={list(prop_schema.keys())}, _graphql_type={prop_schema.get('_graphql_type', 'NOT FOUND')}")
            graphql_type = self._json_type_to_graphql(prop_schema)
            vars_parts.append(f"${camel_key}: {graphql_type}")
            args_parts.append(f"{camel_key}: ${camel_key}")

        # Add input wrapper arguments
        if input_wrappers:
            for wrapper in input_wrappers:
                param_name = wrapper["param_name"]
                camel_param = to_camel_case(param_name)
                graphql_type = wrapper["graphql_type"]
                vars_parts.append(f"${camel_param}: {graphql_type}")
                args_parts.append(f"{camel_param}: ${camel_param}")

        vars_str = ", ".join(vars_parts)
        args_str = ", ".join(args_parts)

        # Build query - handle case with no arguments
        if vars_str:
            query = f"""
            {operation_type} ToolExecution({vars_str}) {{
                {operation_name}({args_str}) {{
                    {return_fields}
                }}
            }}
            """
        else:
            query = f"""
            {operation_type} {{
                {operation_name} {{
                    {return_fields}
                }}
            }}
            """

        return query.strip(), variables

    def _json_type_to_graphql(self, prop_schema: Dict[str, Any]) -> str:
        """
        Convert JSON Schema type to GraphQL type.

        Args:
            prop_schema: JSON Schema property definition

        Returns:
            GraphQL type string
        """
        # Use explicit GraphQL type if available
        if "_graphql_type" in prop_schema:
            return prop_schema["_graphql_type"]

        json_type = prop_schema.get("type", "string")

        type_mapping = {
            "string": "String",
            "integer": "Int",
            "number": "Float",
            "boolean": "Boolean",
            "array": "[String]",
        }

        return type_mapping.get(json_type, "String")

    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get all available tool definitions for LLM."""
        return [tool["definition"] for tool in self._tools.values()]

    def add_tool(self, name: str, definition: Dict[str, Any], operation_type: str = "mutation"):
        """
        Manually add a tool definition.

        Args:
            name: Tool name
            definition: Tool definition in LLM format
            operation_type: "query" or "mutation"
        """
        self._tools[name] = {
            "definition": definition,
            "operation_type": operation_type,
        }

    def _to_global_id(self, param_name: str, value: str, node_type: str = None) -> str:
        """
        Convert a raw UUID to Relay GlobalID format (base64 encoded).

        If the value is already a valid GlobalID, returns it unchanged.

        Args:
            param_name: Parameter name (e.g., "id", "user_id")
            value: Raw UUID string or existing GlobalID
            node_type: GraphQL node type name (e.g., "UserNode")

        Returns:
            Base64 encoded GlobalID string
        """
        # Check if value is already a GlobalID (base64 encoded TypeName:uuid)
        try:
            decoded = base64.b64decode(value).decode()
            if ":" in decoded and "Node" in decoded:
                # Already a valid GlobalID, return as-is
                logger.debug(f"Value {param_name}={value} is already a GlobalID, skipping encoding")
                return value
        except Exception:
            # Not a valid base64 string, proceed with encoding
            pass

        type_name = node_type
        if not type_name:
            # Fallback: derive from param name (e.g., "user_id" -> "UserNode")
            base_name = param_name.replace("_id", "") if param_name != "id" else "unknown"
            parts = base_name.split("_")
            pascal_name = "".join(part.capitalize() for part in parts)
            type_name = f"{pascal_name}Node"

        # Encode as GlobalID: base64("TypeName:uuid")
        global_id_str = f"{type_name}:{value}"
        encoded = base64.b64encode(global_id_str.encode()).decode()
        logger.debug(f"Converted {param_name}={value} to GlobalID({type_name}): {encoded}")
        return encoded

    def _handle_navigate(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle navigate frontend passthrough tool."""
        import uuid
        from datetime import datetime, timedelta

        path = arguments.get("path", "")
        continue_action = arguments.get("continue_action", False)
        info = context.get("info")

        if not info:
            return {
                "status": "error",
                "message": "Missing context info for navigate",
            }

        # Validate path against accessible routes
        valid_paths = [route["path"] for route in self._accessible_routes]

        if path not in valid_paths:
            return {
                "status": "error",
                "message": f"Path '{path}' is not accessible. Available paths: {', '.join(valid_paths)}",
            }

        # If continue_action is True, require confirmation via guardrail
        if continue_action:
            from lys.apps.ai.utils.guardrails import _pending_actions

            # Find route name for better UX
            route_name = path
            for route in self._accessible_routes:
                if route["path"] == path:
                    route_name = route.get("name", path)
                    break

            # Store pending navigation action
            action_id = str(uuid.uuid4())
            user_id = str(info.context.connected_user.get("sub", ""))

            _pending_actions[action_id] = {
                "tool_name": "navigate",
                "tool_data": {"is_navigate": True},
                "tool_args": {"path": path, "continue_action": True},
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(minutes=5),
                "preview": {"path": path, "page_name": route_name}
            }

            return {
                "status": "confirmation_required",
                "action_id": action_id,
                "preview": {"path": path, "page_name": route_name},
                "message": f"Voulez-vous naviguer vers {route_name} pour effectuer cette action ?"
            }

        # Direct navigation (explicit request) - no confirmation needed
        if not hasattr(info.context, "frontend_actions"):
            info.context.frontend_actions = []

        info.context.frontend_actions.append({
            "type": "navigate",
            "path": path,
            "continueAction": False,
        })

        return {
            "status": "navigation_scheduled",
            "message": f"Navigation to '{path}' has been scheduled. The user will be redirected.",
        }

    async def _handle_confirm_action(self, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle confirm_action special tool."""
        from lys.apps.ai.utils.guardrails import AIGuardrailService

        action_id = arguments.get("action_id", "")
        confirmed = arguments.get("confirmed", False)
        info = context.get("info")
        session = context.get("session")

        if not info:
            return {
                "status": "error",
                "message": "Missing context info for confirm_action",
            }

        result = await AIGuardrailService.confirm_action(action_id, confirmed, info)

        # If confirmed and status is "execute", execute the actual tool
        if result.get("status") == "execute":
            tool_name = result["tool_name"]
            tool_args = result["tool_args"]
            tool_data = result.get("tool_data", {})

            # Special handling for navigate tool
            if tool_name == "navigate" and tool_data.get("is_navigate"):
                path = tool_args.get("path", "")

                # Store frontend action
                if not hasattr(info.context, "frontend_actions"):
                    info.context.frontend_actions = []

                info.context.frontend_actions.append({
                    "type": "navigate",
                    "path": path,
                    "continueAction": True,  # Trigger "Continue" on frontend after navigation
                })

                return {
                    "status": "navigation_scheduled",
                    "message": f"Navigation to '{path}' confirmed. You will be redirected.",
                }

            # Execute the tool via GraphQL
            executed_result = await self.execute(
                tool_name=tool_name,
                arguments=tool_args,
                context=context,
            )

            return executed_result

        return result