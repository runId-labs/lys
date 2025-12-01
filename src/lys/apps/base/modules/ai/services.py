import inspect
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, get_origin, get_args
from uuid import uuid4

import httpx
from strawberry import relay
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select as SQLSelect

from lys.apps.base.modules.ai.entities import AIConversation
from lys.apps.base.modules.ai.guardrails import AIGuardrailService, CONFIRM_ACTION_TOOL
from lys.core.configs import LysAppSettings
from lys.core.registries import register_service
from lys.core.services import EntityService, Service
from lys.core.utils.tool_generator import entity_to_dict, node_to_dict

logger = logging.getLogger(__name__)


@register_service()
class AIConversationService(EntityService[AIConversation]):
    """Service for managing AI conversation history."""

    @classmethod
    async def get_or_create_conversation(
        cls,
        session: AsyncSession,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> AIConversation:
        """
        Get an existing conversation or create a new one.

        Args:
            session: Database session
            user_id: User ID who owns the conversation
            conversation_id: Optional existing conversation ID

        Returns:
            AIConversation entity
        """
        if conversation_id:
            # Try to get existing conversation
            stmt = select(cls.entity_class).where(
                cls.entity_class.id == conversation_id,
                cls.entity_class.user_id == user_id
            )
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()

            if conversation:
                return conversation

        # Create new conversation
        conversation = cls.entity_class(
            id=conversation_id or str(uuid4()),
            user_id=user_id,
            messages=[],
            message_count=0
        )
        session.add(conversation)
        await session.flush()

        return conversation

    @classmethod
    async def add_messages(
        cls,
        session: AsyncSession,
        conversation: Any,
        messages: List[Dict[str, Any]]
    ) -> None:
        """
        Add messages to a conversation.

        Args:
            session: Database session
            conversation: AIConversation entity
            messages: List of messages to add
        """
        # Append new messages to existing history
        # Create a new list to ensure SQLAlchemy detects the change
        current_messages = list(conversation.messages or [])
        current_messages.extend(messages)

        conversation.messages = current_messages
        conversation.message_count = len(current_messages)
        conversation.last_message_at = datetime.utcnow()

        # Generate title from first user message if not set
        if not conversation.title and messages:
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    conversation.title = content[:100] + ("..." if len(content) > 100 else "")
                    break

        await session.flush()

    @classmethod
    async def get_conversation_history(
        cls,
        conversation: Any
    ) -> List[Dict[str, Any]]:
        """
        Get the message history from a conversation.

        Args:
            conversation: AIConversation entity

        Returns:
            List of messages
        """
        return conversation.messages or []

    @classmethod
    async def delete_old_conversations(
        cls,
        session: AsyncSession,
        hours: int = 24
    ) -> int:
        """
        Delete conversations older than specified hours.

        Args:
            session: Database session
            hours: Age threshold in hours

        Returns:
            Number of deleted conversations
        """
        from sqlalchemy import delete
        from datetime import timedelta

        entity_class = cls.entity_class
        threshold = datetime.utcnow() - timedelta(hours=hours)

        stmt = delete(entity_class).where(
            entity_class.last_message_at < threshold
        )
        result = await session.execute(stmt)
        await session.flush()

        return result.rowcount


@register_service()
class AIService(Service):
    """Service for AI/LLM integration and tool execution."""

    service_name = "ai"

    @classmethod
    async def chat(
        cls,
        message: str,
        tools: List[Dict[str, Any]],
        system_prompt: str,
        session: AsyncSession,
        info: Any,
        conversation_id: Optional[str] = None,
        max_tool_iterations: int = 10
    ) -> Dict[str, Any]:
        """
        Send a message to the LLM and process tool calls.

        Args:
            message: User message
            tools: List of available tool definitions
            system_prompt: System prompt with user context
            session: Database session for tool execution
            info: GraphQL info context
            conversation_id: Optional conversation ID for context
            max_tool_iterations: Maximum number of tool call iterations

        Returns:
            Dict with 'content', 'tool_calls_count', and 'tool_results'
        """
        settings = LysAppSettings()

        if not settings.ai.configured():
            raise ValueError("AI is not configured. Set AI_ENABLED=true and AI_API_KEY in environment.")

        # Get user ID from context
        user_id = info.context.connected_user.get("id") if info.context.connected_user else None

        if not user_id:
            raise ValueError("User must be authenticated to use AI chat.")

        # Get or create conversation
        conversation_service = cls.app_manager.get_service("ai_conversations")
        conversation = await conversation_service.get_or_create_conversation(
            session=session,
            user_id=user_id,
            conversation_id=conversation_id
        )

        # Load conversation history
        history = await conversation_service.get_conversation_history(conversation)

        # Build messages with system prompt and history
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (filter out system messages from history)
        for msg in history:
            if msg.get("role") != "system":
                messages.append(msg)

        # Add new user message
        messages.append({"role": "user", "content": message})

        tool_results = []
        tool_calls_count = 0
        new_messages = [{"role": "user", "content": message}]  # Track new messages to save

        # Initialize frontend_actions in context for collection during tool execution
        info.context.frontend_actions = []

        # Agent loop: call LLM, execute tools, repeat until no more tool calls
        for iteration in range(max_tool_iterations):
            response = await cls._call_llm(
                messages=messages,
                tools=tools if tools else None,
                settings=settings
            )

            # Check if LLM wants to call tools
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                # No tool calls, save conversation and return the response
                assistant_message = {"role": "assistant", "content": response.get("content", "")}
                new_messages.append(assistant_message)

                # Save new messages to conversation
                await conversation_service.add_messages(session, conversation, new_messages)

                # Collect frontend_actions from context
                frontend_actions = getattr(info.context, "frontend_actions", [])

                return {
                    "content": response.get("content", ""),
                    "conversation_id": conversation.id,
                    "tool_calls_count": tool_calls_count,
                    "tool_results": tool_results,
                    "frontend_actions": frontend_actions if frontend_actions else None
                }

            # Execute tool calls
            tool_calls_count += len(tool_calls)

            # Add assistant message with tool calls to history
            assistant_msg = {
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": tool_calls
            }
            messages.append(assistant_msg)
            new_messages.append(assistant_msg)

            # Execute each tool and collect results
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                tool_call_id = tool_call.get("id", "")

                try:
                    tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    result = await cls._execute_tool(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        session=session,
                        info=info
                    )
                    tool_results.append({
                        "tool_name": tool_name,
                        "result": str(result),
                        "success": True
                    })

                    # Add tool result to messages
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result) if not isinstance(result, str) else result
                    }
                    messages.append(tool_msg)
                    new_messages.append(tool_msg)

                except Exception as e:
                    error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                    logger.error(error_msg)
                    tool_results.append({
                        "tool_name": tool_name,
                        "result": error_msg,
                        "success": False
                    })

                    # Add error to messages so LLM knows
                    error_tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps({"error": error_msg})
                    }
                    messages.append(error_tool_msg)
                    new_messages.append(error_tool_msg)

        # Max iterations reached - save what we have
        await conversation_service.add_messages(session, conversation, new_messages)

        # Collect frontend_actions from context
        frontend_actions = getattr(info.context, "frontend_actions", [])

        return {
            "content": "Maximum tool iterations reached. Please try a simpler request.",
            "conversation_id": conversation.id,
            "tool_calls_count": tool_calls_count,
            "tool_results": tool_results,
            "frontend_actions": frontend_actions if frontend_actions else None
        }

    @classmethod
    async def _call_llm(
        cls,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        settings: LysAppSettings
    ) -> Dict[str, Any]:
        """
        Call the LLM API.

        Args:
            messages: Conversation history
            tools: Available tools
            settings: App settings with AI configuration

        Returns:
            LLM response with content and optional tool_calls
        """
        provider = settings.ai.provider or "mistral"

        if provider == "mistral":
            return await cls._call_mistral(messages, tools, settings)
        elif provider == "openai":
            return await cls._call_openai(messages, tools, settings)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

    @classmethod
    async def _call_mistral(
        cls,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        settings: LysAppSettings
    ) -> Dict[str, Any]:
        """Call Mistral API."""
        base_url = settings.ai.base_url or "https://api.mistral.ai/v1"
        model = settings.ai.model or "mistral-large-latest"

        payload = {
            "model": model,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.info(f"Calling Mistral API: model={model}, messages_count={len(messages)}, tools_count={len(tools) if tools else 0}")
        # Log messages only (tools are too verbose)
        logger.debug(f"Mistral messages: {json.dumps(messages, indent=2, default=str)}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.ai.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60.0
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Mistral API error: {response.status_code} - {error_text}")
                raise ValueError(f"Mistral API error: {response.status_code}")

            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})

            # Handle both string and structured content formats
            content = message.get("content", "")
            if isinstance(content, list):
                # Structured content: extract text from each part
                content = "".join(
                    part.get("text", "") for part in content if part.get("type") == "text"
                )

            return {
                "content": content,
                "tool_calls": message.get("tool_calls", [])
            }

    @classmethod
    async def _call_openai(
        cls,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        settings: LysAppSettings
    ) -> Dict[str, Any]:
        """Call OpenAI API."""
        base_url = settings.ai.base_url or "https://api.openai.com/v1"
        model = settings.ai.model or "gpt-4"

        payload = {
            "model": model,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.info(f"Calling OpenAI API: model={model}, messages_count={len(messages)}, tools_count={len(tools) if tools else 0}")
        # Log messages only (tools are too verbose)
        logger.debug(f"OpenAI messages: {json.dumps(messages, indent=2, default=str)}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.ai.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60.0
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"OpenAI API error: {response.status_code} - {error_text}")
                raise ValueError(f"OpenAI API error: {response.status_code}")

            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})

            return {
                "content": message.get("content", ""),
                "tool_calls": message.get("tool_calls", [])
            }

    @classmethod
    async def _execute_tool(
        cls,
        tool_name: str,
        tool_args: Dict[str, Any],
        session: AsyncSession,
        info: Any
    ) -> Any:
        """
        Execute a tool by calling its registered resolver.

        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
            session: Database session
            info: GraphQL info context

        Returns:
            Tool execution result
        """
        app_manager = info.context.app_manager

        # Handle confirm_action as a special tool
        if tool_name == "confirm_action":
            action_id = tool_args.get("action_id", "")
            confirmed = tool_args.get("confirmed", False)

            result = await AIGuardrailService.confirm_action(action_id, confirmed, info)

            # If confirmed and status is "execute", execute the actual tool
            if result.get("status") == "execute":
                executed_result = await cls._execute_tool_internal(
                    result["tool_name"],
                    result["tool_data"],
                    result["tool_args"],
                    session,
                    info
                )

                # Add refresh action for frontend to reload data
                tool_data = result.get("tool_data", {})
                node_type = tool_data.get("node_type")
                logger.debug(f"confirm_action executed: tool_name={result.get('tool_name')}, node_type={node_type}")
                if node_type:
                    if not hasattr(info.context, "frontend_actions"):
                        info.context.frontend_actions = []
                    info.context.frontend_actions.append({
                        "type": "refresh",
                        "nodes": [node_type.__name__]
                    })
                    logger.info(f"Added refresh action for nodes: {[node_type.__name__]}")
                else:
                    logger.warning(f"No node_type found for tool: {result.get('tool_name')}")

                return executed_result

            return result

        # Handle navigate as a frontend passthrough tool
        if tool_name == "navigate":
            path = tool_args.get("path", "")

            # Validate path against accessible routes
            accessible_routes = getattr(info.context, "ai_accessible_routes", [])
            valid_paths = [route["path"] for route in accessible_routes]

            if path not in valid_paths:
                return {
                    "status": "error",
                    "message": f"Path '{path}' is not accessible. Available paths: {', '.join(valid_paths)}"
                }

            # Store frontend action in context for later collection
            if not hasattr(info.context, "frontend_actions"):
                info.context.frontend_actions = []

            info.context.frontend_actions.append({
                "type": "navigate",
                "path": path
            })

            return {
                "status": "navigation_scheduled",
                "message": f"Navigation to '{path}' has been scheduled. The user will be redirected."
            }

        # Get the tool from registry
        try:
            tool_data = app_manager.registry.get_tool(tool_name)
        except KeyError:
            raise ValueError(f"Tool '{tool_name}' not found in registry")

        # Get resolver info for argument conversion
        resolver = tool_data["resolver"]
        node_type = tool_data.get("node_type")

        # Get the actual callable from the resolver
        if hasattr(resolver, 'wrapped_func'):
            actual_resolver = resolver.wrapped_func
        else:
            actual_resolver = resolver

        sig = inspect.signature(actual_resolver)

        # Convert string arguments to GlobalID where needed
        converted_args = cls._convert_tool_args(sig, tool_args, node_type)

        # Reconstruct Strawberry input objects from flattened arguments
        converted_args = cls._reconstruct_input_args(sig, converted_args)

        # Pass through guardrail
        guardrail_result = await AIGuardrailService.process_tool_call(
            tool_name,
            tool_data,
            converted_args,
            info
        )

        # If confirmation is required, return that to the LLM
        if guardrail_result.get("status") == "confirmation_required":
            return guardrail_result

        # Execute the tool
        return await cls._execute_tool_internal(
            tool_name,
            tool_data,
            converted_args,
            session,
            info
        )

    @classmethod
    async def _execute_tool_internal(
        cls,
        tool_name: str,
        tool_data: Dict[str, Any],
        converted_args: Dict[str, Any],
        session: AsyncSession,
        info: Any
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
        if hasattr(resolver, 'wrapped_func'):
            actual_resolver = resolver.wrapped_func
        else:
            actual_resolver = resolver

        # Check if resolver needs 'self' parameter (mutations vs queries)
        sig = inspect.signature(actual_resolver)
        params = list(sig.parameters.keys())

        if params and params[0] == 'self':
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
            if node_type and hasattr(node_type, 'from_entity'):
                items = [node_to_dict(node_type.from_entity(entity)) for entity in entities]
            else:
                items = [entity_to_dict(entity, include_relations=True, max_depth=2) for entity in entities]

            return {
                "items": items,
                "total": len(entities)
            }

        # Serialize the result
        return cls._serialize_result(result)

    @classmethod
    def _convert_tool_args(
        cls,
        sig: inspect.Signature,
        tool_args: Dict[str, Any],
        node_type: type = None
    ) -> Dict[str, Any]:
        """
        Convert tool arguments to the expected types.

        Handles conversion of string UUIDs to relay.GlobalID objects.
        The GlobalID type name is determined from:
        1. The node_type of the tool (for 'id' parameter from lys_edition/lys_getter)
        2. The parameter name (for explicit parameters like 'user_id', 'client_id')

        Args:
            sig: Function signature
            tool_args: Raw arguments from LLM (contains UUIDs as strings)
            node_type: The Strawberry node type associated with the tool

        Returns:
            Converted arguments with GlobalID objects where needed
        """
        from typing import Union

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
                    # For 'id' parameter (from lys_edition/lys_getter), use the tool's node_type
                    gid_type_name = node_type.__name__
                else:
                    # For explicit parameters like 'user_id', 'client_id', derive from param name
                    # user_id → UserNode, client_id → ClientNode
                    base_name = param_name.replace("_id", "")
                    # Convert snake_case to PascalCase and add Node suffix
                    parts = base_name.split("_")
                    pascal_name = "".join(part.capitalize() for part in parts)
                    gid_type_name = f"{pascal_name}Node"

                # Create GlobalID with the type name and UUID
                converted[param_name] = relay.GlobalID(gid_type_name, value)
                logger.debug(f"Converted {param_name}={value} to GlobalID({gid_type_name}, {value})")
            else:
                converted[param_name] = value

        return converted

    @classmethod
    def _reconstruct_input_args(
        cls,
        sig: inspect.Signature,
        tool_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Reconstruct Strawberry input objects from flattened arguments.

        When tools are generated, Strawberry input types are flattened into
        individual parameters. This method reconstructs the input objects
        from those flattened arguments.

        Args:
            sig: Function signature
            tool_args: Flattened arguments from LLM

        Returns:
            Arguments with reconstructed input objects
        """
        from typing import Union, Annotated

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
                # Remove the flattened fields from result
                for field_name in fields_to_remove:
                    del result[field_name]

                # Create the input object
                # Strawberry inputs can be instantiated directly with kwargs
                try:
                    input_obj = param_type(**input_args)
                    result[param_name] = input_obj
                    logger.debug(f"Reconstructed {param_name} input with fields: {list(input_args.keys())}")
                except Exception as e:
                    logger.error(f"Failed to reconstruct input {param_name}: {e}")
                    # Put the fields back and let the error propagate naturally
                    for field_name in fields_to_remove:
                        result[field_name] = input_args.get(field_name)

        return result

    @classmethod
    def _serialize_result(cls, result: Any) -> Any:
        """
        Serialize a tool result for the LLM.

        Handles SQLAlchemy objects, Pydantic models, and basic types.
        """
        if result is None:
            return None

        # Handle datetime
        if hasattr(result, 'isoformat'):
            return result.isoformat()

        # Handle UUID
        if hasattr(result, 'hex') and hasattr(result, 'int'):
            return str(result)

        # Handle lists
        if isinstance(result, list):
            return [cls._serialize_result(item) for item in result]

        # Handle dicts
        if isinstance(result, dict):
            return {k: cls._serialize_result(v) for k, v in result.items()}

        # Handle Relay Connection objects (pagination results)
        if hasattr(result, 'edges'):
            edges = getattr(result, 'edges', [])
            if not edges:
                return {"items": [], "message": "No results found"}
            return {
                "items": [cls._serialize_result(edge.node) for edge in edges if hasattr(edge, 'node')],
                "total": len(edges)
            }

        # Handle Strawberry nodes (EntityNode, ServiceNode)
        if hasattr(result, '_entity') or hasattr(result, '__strawberry_definition__'):
            return node_to_dict(result)

        # Handle SQLAlchemy entities
        if hasattr(result, '__table__'):
            # Use entity_to_dict for proper serialization with all columns
            return entity_to_dict(result, include_relations=True, max_depth=2)

        # Handle Pydantic models
        if hasattr(result, 'model_dump'):
            return result.model_dump()

        # Handle objects with __dict__
        if hasattr(result, '__dict__') and not isinstance(result, type):
            # Filter out private attributes and SQLAlchemy internals
            return {
                k: cls._serialize_result(v)
                for k, v in result.__dict__.items()
                if not k.startswith('_')
            }

        # Basic types
        return result
