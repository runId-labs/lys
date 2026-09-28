"""
Routes manifest utilities for AI navigation.

This module provides functions to load and filter frontend routes
based on user permissions for AI-assisted navigation.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def camel_to_snake(name: str) -> str:
    """
    Convert camelCase to snake_case.

    Args:
        name: camelCase string (e.g., "allClients", "allClientUsers")

    Returns:
        snake_case string (e.g., "all_clients", "all_client_users")
    """
    # Insert underscore before uppercase letters and convert to lowercase
    result = re.sub(r"([A-Z])", r"_\1", name).lower()
    # Remove leading underscore if present
    return result.lstrip("_")


def route_page_params(route: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    The params a routes-manifest entry declares, or None when it declares none.

    One accessor for the one source of truth: the manifest entry. Both readers
    of a schema go through it — the AI service resolving a page by name, and
    the navigate tool resolving the TARGET route by path — so a route whose
    ``params`` is missing or malformed reads the same way on both paths.
    """
    if not isinstance(route, dict):
        return None
    params = route.get("params")
    return params if isinstance(params, dict) else None


def writable_param_names(schema: Optional[Dict[str, Any]]) -> List[str]:
    """The params a page marks writable, sorted — what the model may set."""
    if not isinstance(schema, dict):
        return []
    return sorted(
        key for key, spec in schema.items() if isinstance(spec, dict) and spec.get("writable")
    )


def load_routes_manifest(path: str) -> Optional[Dict[str, Any]]:
    """
    Load routes manifest from a JSON file.

    Args:
        path: Path to the routes-manifest.json file

    Returns:
        Parsed manifest dict or None if file not found/invalid
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            logger.debug(f"Loaded routes manifest from {path}: {len(manifest.get('routes', []))} routes")
            return manifest
    except FileNotFoundError:
        logger.warning(f"Routes manifest not found at {path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in routes manifest {path}: {e}")
        return None


def filter_routes_by_permissions(
    routes: List[Dict[str, Any]],
    accessible_webservice_ids: Set[str]
) -> List[Dict[str, Any]]:
    """
    Filter routes based on user's accessible webservices.

    Routes are included if:
    - webservice is null (public page, no permission required)
    - webservice (converted to snake_case) is in accessible_webservice_ids

    Args:
        routes: List of route dicts from the manifest
        accessible_webservice_ids: Set of webservice IDs the user can access

    Returns:
        Filtered list of routes the user can navigate to
    """
    filtered = []

    for route in routes:
        webservice = route.get("webservice")

        if webservice is None:
            # Public page, no permission required
            filtered.append(route)
        else:
            # Convert camelCase to snake_case and check permission
            webservice_snake = camel_to_snake(webservice)
            if webservice_snake in accessible_webservice_ids:
                filtered.append(route)

    logger.debug(
        f"Filtered routes: {len(filtered)}/{len(routes)} "
        f"(accessible webservices: {len(accessible_webservice_ids)})"
    )

    return filtered


def build_navigate_tool(accessible_routes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build the navigate tool definition with accessible paths as enum.

    Routes declaring writable params carry them in the description: the model
    needs to know WHICH filters it may set on arrival, and only the writable
    ones are its to set.
    """
    # Build path enum from accessible routes
    path_enum = [route["path"] for route in accessible_routes]

    # Build description with available pages, and the writable params each
    # accepts on arrival
    def _writable_note(route: Dict[str, Any]) -> str:
        writable = writable_param_names(route_page_params(route))
        return f" (writable params: {', '.join(writable)})" if writable else ""

    routes_description = "\n".join(
        f"- {route['path']}: {route.get('description', 'No description')}{_writable_note(route)}"
        for route in accessible_routes
    )

    return {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": (
                "Navigate the user to a specific page in the application. "
                "Use this when the user asks to go to a page or section. "
                "A route listing 'writable params' accepts them on arrival, in the "
                "same shapes as the 'Page params' JSON section — pass them to land "
                "the user directly on the state you described (never invent a value).\n\n"
                f"Available pages:\n{routes_description}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "enum": path_enum,
                        "description": "The URL path to navigate to"
                    },
                    "params": {
                        "type": "object",
                        "description": (
                            "Optional filters to apply on arrival — only the keys the "
                            "target route lists as writable params, values exactly as "
                            "the 'Page params' section carries them. Omit to open the "
                            "page with its defaults."
                        ),
                    },
                    "continue_action": {
                        "type": "boolean",
                        "description": "Set to true if navigating to execute a pending action (implicit navigation). Set to false for explicit navigation requests.",
                        "default": False
                    }
                },
                "required": ["path"]
            }
        }
    }
