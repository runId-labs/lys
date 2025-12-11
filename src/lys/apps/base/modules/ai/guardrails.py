"""
AI Guardrails - Safety middleware for AI tool execution.

This module provides a confirmation system for risky AI operations (CREATE, UPDATE, DELETE).
It intercepts tool calls, generates previews, and requires explicit user confirmation
before executing modifications.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from strawberry import relay

from lys.core.consts.ai import ToolRiskLevel
from lys.core.utils.tool_generator import node_to_dict

logger = logging.getLogger(__name__)

# In-memory store for pending actions (use Redis in production for multi-instance)
_pending_actions: Dict[str, Dict[str, Any]] = {}

# Risk levels that require confirmation
CONFIRMATION_REQUIRED_LEVELS = {ToolRiskLevel.CREATE, ToolRiskLevel.UPDATE, ToolRiskLevel.DELETE}


class AIGuardrailService:
    """Middleware for AI tool execution safety."""

    @classmethod
    async def process_tool_call(
        cls,
        tool_name: str,
        tool_data: Dict[str, Any],
        tool_args: Dict[str, Any],
        info: Any
    ) -> Dict[str, Any]:
        """
        Process a tool call with optional confirmation requirement.

        Args:
            tool_name: Name of the tool
            tool_data: Tool data from registry (includes risk_level, confirmation_fields)
            tool_args: Converted arguments for the tool
            info: GraphQL info context

        Returns:
            Either a confirmation request or signals to proceed with execution
        """
        risk_level = tool_data.get("risk_level", ToolRiskLevel.READ)

        # Safe operation - signal to execute directly
        if risk_level not in CONFIRMATION_REQUIRED_LEVELS:
            return {"status": "execute", "tool_args": tool_args}

        # Risky operation - generate preview and request confirmation
        preview = await cls._generate_preview(tool_data, tool_args, info)

        # Store pending action
        action_id = str(uuid.uuid4())
        user_id = str(info.context.connected_user.get("sub", ""))

        _pending_actions[action_id] = {
            "tool_name": tool_name,
            "tool_data": tool_data,
            "tool_args": tool_args,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=5),
            "preview": preview
        }

        logger.info(f"Created pending action {action_id} for tool {tool_name} (risk: {risk_level.value})")

        return {
            "status": "confirmation_required",
            "action_id": action_id,
            "preview": preview,
            "message": cls._get_confirmation_message(risk_level, tool_name)
        }

    @classmethod
    async def confirm_action(
        cls,
        action_id: str,
        confirmed: bool,
        info: Any
    ) -> Dict[str, Any]:
        """
        Confirm or cancel a pending action.

        Args:
            action_id: ID of the pending action
            confirmed: True to execute, False to cancel
            info: GraphQL info context

        Returns:
            Result dict with status and either execution signal or cancellation
        """
        action = _pending_actions.get(action_id)

        if not action:
            return {
                "status": "error",
                "message": "Action not found or expired. Please retry the operation."
            }

        # Verify user owns this action
        user_id = str(info.context.connected_user.get("sub", ""))
        if action["user_id"] != user_id:
            return {
                "status": "error",
                "message": "Unauthorized: This action belongs to another user."
            }

        # Check expiration
        if datetime.utcnow() > action["expires_at"]:
            del _pending_actions[action_id]
            return {
                "status": "error",
                "message": "Action expired. Please retry the operation."
            }

        # Handle cancellation
        if not confirmed:
            del _pending_actions[action_id]
            logger.info(f"Action {action_id} cancelled by user")
            return {
                "status": "cancelled",
                "message": "Action cancelled."
            }

        # Return signal to execute
        tool_name = action["tool_name"]
        tool_args = action["tool_args"]
        del _pending_actions[action_id]

        logger.info(f"Action {action_id} confirmed, executing {tool_name}")

        return {
            "status": "execute",
            "tool_name": tool_name,
            "tool_data": action["tool_data"],
            "tool_args": tool_args
        }

    @classmethod
    async def _generate_preview(
        cls,
        tool_data: Dict[str, Any],
        tool_args: Dict[str, Any],
        info: Any
    ) -> Dict[str, Any]:
        """
        Generate a preview of the object to be modified.

        Args:
            tool_data: Tool data with confirmation_fields
            tool_args: Tool arguments including object ID
            info: GraphQL info context

        Returns:
            Preview dict with current state and planned changes
        """
        confirmation_fields = tool_data.get("confirmation_fields", [])
        obj_id = tool_args.get("id")

        # Build changes dict (exclude 'id' from changes)
        # Serialize Strawberry input objects to dict
        changes = {}
        for k, v in tool_args.items():
            if k == "id":
                continue
            # Handle Strawberry input objects
            if hasattr(v, "__strawberry_definition__"):
                import strawberry
                changes[k] = strawberry.asdict(v)
            else:
                changes[k] = v

        # If no ID or no confirmation fields, return just the changes
        if not obj_id or not confirmation_fields:
            return {"changes": changes}

        # Fetch current object state
        node_type = tool_data.get("node_type")
        if not node_type:
            return {"changes": changes}

        try:
            current = await cls._fetch_object(node_type, obj_id, info)

            # Extract only confirmation fields
            current_values = {}
            for field in confirmation_fields:
                value = cls._get_nested_value(current, field)
                if value is not None:
                    current_values[field] = value

            return {
                "current": current_values,
                "changes": changes
            }
        except Exception as e:
            logger.warning(f"Could not fetch object for preview: {e}")
            return {
                "error": f"Could not fetch current state: {str(e)}",
                "changes": changes
            }

    @classmethod
    async def _fetch_object(
        cls,
        node_type: type,
        obj_id: Any,
        info: Any
    ) -> Dict[str, Any]:
        """
        Fetch an object by its GlobalID for preview.

        Args:
            node_type: Strawberry node type
            obj_id: GlobalID or string ID
            info: GraphQL info context

        Returns:
            Object serialized as dict
        """
        # Handle GlobalID objects
        if isinstance(obj_id, relay.GlobalID):
            global_id = obj_id
        elif isinstance(obj_id, str):
            # Create GlobalID from string
            global_id = relay.GlobalID(node_type.__name__, obj_id)
        else:
            raise ValueError(f"Invalid ID type: {type(obj_id)}")

        # Resolve the node
        node = await node_type.resolve_node(
            global_id.node_id,
            info=info,
            required=True
        )

        return node_to_dict(node)

    @classmethod
    def _get_nested_value(cls, obj: Dict[str, Any], field_path: str) -> Any:
        """
        Get a nested value from a dict using dot notation.

        Example: _get_nested_value({"client": {"name": "Test"}}, "client.name") -> "Test"

        Args:
            obj: Dict to extract from
            field_path: Dot-separated field path

        Returns:
            Value or None if not found
        """
        parts = field_path.split(".")
        value = obj
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    @classmethod
    def _get_confirmation_message(cls, risk_level: ToolRiskLevel, tool_name: str) -> str:
        """
        Get appropriate confirmation message based on risk level.

        Args:
            risk_level: Operation risk level
            tool_name: Name of the tool

        Returns:
            Human-readable confirmation message
        """
        messages = {
            ToolRiskLevel.CREATE: f"Please confirm this creation ({tool_name})",
            ToolRiskLevel.UPDATE: f"Please confirm this modification ({tool_name})",
            ToolRiskLevel.DELETE: f"Please confirm this deletion ({tool_name}) - this may be irreversible"
        }
        return messages.get(risk_level, f"Please confirm this action ({tool_name})")


# Tool definition for confirm_action
CONFIRM_ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "confirm_action",
        "description": "Confirm or cancel a pending action that requires user approval. "
                       "Use this after receiving a 'confirmation_required' response from a previous tool call.",
        "parameters": {
            "type": "object",
            "properties": {
                "action_id": {
                    "type": "string",
                    "description": "The action_id returned by the previous tool call that requires confirmation"
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Set to true to execute the action, false to cancel it"
                }
            },
            "required": ["action_id", "confirmed"]
        }
    }
}