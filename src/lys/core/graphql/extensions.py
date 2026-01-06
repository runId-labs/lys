"""
GraphQL extensions for Strawberry.

This module provides custom Strawberry extensions for the lys framework,
including database session management for GraphQL operations.
"""
import asyncio
from typing import Any, List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.extensions import SchemaExtension

from lys.apps.ai.utils.guardrails import CONFIRM_ACTION_TOOL
from lys.core.utils.routes import filter_routes_by_permissions, build_navigate_tool


class ThreadSafeSessionProxy:
    """
    Proxy that serializes all access to an AsyncSession.

    SQLAlchemy's AsyncSession is not thread-safe and cannot be used concurrently
    by multiple coroutines. In GraphQL, multiple root field resolvers may execute
    in parallel, all sharing the same session from the context.

    This proxy wraps the session and uses an asyncio.Lock to ensure only one
    coroutine accesses the session at a time, preventing race conditions.

    Usage:
        The proxy is transparent to resolvers - they continue using
        info.context.session as before, but all operations are now serialized.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._lock = asyncio.Lock()

    async def execute(self, *args, **kwargs):
        async with self._lock:
            return await self._session.execute(*args, **kwargs)

    async def scalar(self, *args, **kwargs):
        async with self._lock:
            return await self._session.scalar(*args, **kwargs)

    async def scalars(self, *args, **kwargs):
        async with self._lock:
            return await self._session.scalars(*args, **kwargs)

    async def stream(self, *args, **kwargs):
        async with self._lock:
            return await self._session.stream(*args, **kwargs)

    async def stream_scalars(self, *args, **kwargs):
        async with self._lock:
            return await self._session.stream_scalars(*args, **kwargs)

    async def flush(self, *args, **kwargs):
        async with self._lock:
            return await self._session.flush(*args, **kwargs)

    async def refresh(self, *args, **kwargs):
        async with self._lock:
            return await self._session.refresh(*args, **kwargs)

    async def get(self, *args, **kwargs):
        async with self._lock:
            return await self._session.get(*args, **kwargs)

    def add(self, instance, _warn=True):
        # add is synchronous but we still protect state consistency
        return self._session.add(instance, _warn=_warn)

    def add_all(self, instances):
        return self._session.add_all(instances)

    async def delete(self, instance):
        async with self._lock:
            return await self._session.delete(instance)

    async def merge(self, instance, *args, **kwargs):
        async with self._lock:
            return await self._session.merge(instance, *args, **kwargs)

    def expunge(self, instance):
        return self._session.expunge(instance)

    def expunge_all(self):
        return self._session.expunge_all()

    @property
    def is_active(self):
        return self._session.is_active

    @property
    def dirty(self):
        return self._session.dirty

    @property
    def new(self):
        return self._session.new

    @property
    def deleted(self):
        return self._session.deleted

    def __getattr__(self, name):
        # Fallback for any other attributes/methods not explicitly wrapped
        return getattr(self._session, name)


class DatabaseSessionExtension(SchemaExtension):
    """
    Strawberry extension that manages database session lifecycle for GraphQL operations.

    This extension opens a database session at the start of a GraphQL request and keeps it
    open for the entire duration of the GraphQL resolution (including nested field resolvers).
    The session is automatically closed when the GraphQL operation completes.

    Benefits:
    - Eliminates DetachedInstanceError by keeping entities attached during resolution
    - Allows lazy loading of relationships without explicit eager loading
    - Follows standard GraphQL/Strawberry patterns for database session management
    - Simplifies resolver code by removing need for manual session management

    Trade-offs:
    - Sessions remain open longer (entire GraphQL operation vs. per-resolver)
    - Potential N+1 query problem if lazy loading is used extensively
    - Recommend using dataloaders for frequently accessed relationships

    Usage:
        The extension is automatically configured in the schema and requires no
        changes to resolver code. Resolvers access the session via info.context.session.
    """

    async def on_execute(self):
        """
        Hook called at the start of GraphQL execution.

        Opens a database session, stores it in the GraphQL context, executes the
        entire GraphQL operation (including all nested resolvers), and then closes
        the session.

        Yields control to allow the GraphQL operation to execute, then cleans up.
        """
        # Get app_manager from context (set by get_context or resolver)
        app_manager = getattr(self.execution_context.context, "app_manager", None)

        # If no app_manager in context yet, we'll let individual resolvers handle sessions
        # This can happen for introspection queries or before resolvers set app_manager
        if app_manager is None:
            yield

        else:
            # Open database session for the entire GraphQL operation
            async with app_manager.database.get_session() as session:
                # Wrap session in thread-safe proxy to handle concurrent resolver access
                # Multiple root field resolvers may execute in parallel, and AsyncSession
                # is not safe for concurrent use. The proxy serializes all access.
                self.execution_context.context.session = ThreadSafeSessionProxy(session)

                # Yield to allow the GraphQL operation to execute with session open
                # This includes the main resolver and all nested field resolvers
                yield

                # Session automatically closes here when exiting async with block


class AIContextExtension(SchemaExtension):
    """
    Strawberry extension that prepares AI-related context for LLM tool calling.

    This extension filters tools based on user permissions and builds a system prompt
    with user context. The filtered tools and system prompt are made available in the
    GraphQL context for use by AI-related operations.

    Context attributes set:
    - ai_tools: List of tool definitions the user can access
    - ai_system_prompt: Pre-formatted system prompt with user context and permissions
    """

    async def on_execute(self):
        """
        Hook called at the start of GraphQL execution.

        Prepares AI context including filtered tools and system prompt based on
        the connected user's permissions.
        """
        context = self.execution_context.context
        app_manager = getattr(context, "app_manager", None)

        if app_manager is None:
            yield
            return

        # Get connected user from context
        connected_user = context.connected_user

        # Get webservice service (may be extended by user_auth or user_role apps)
        webservice_service = app_manager.get_service("webservice")

        # Get database session (set by DatabaseSessionExtension)
        session = getattr(context, "session", None)

        if session is None:
            # No session available, set empty context
            context.ai_tools = []
            context.ai_system_prompt = ""
            yield
            return

        # Get accessible webservices for the user
        stmt = await webservice_service.accessible_webservices(connected_user)
        result = await session.execute(stmt)
        accessible_webservices = list(result.scalars().all())
        accessible_webservice_ids = {ws.id for ws in accessible_webservices}
        # Map webservice id to operation_type from DB
        webservice_operation_types = {ws.id: ws.operation_type for ws in accessible_webservices}

        # Filter tools based on accessible webservices
        all_tools = app_manager.registry.tools
        filtered_tools: List[Dict[str, Any]] = []

        for tool_name, tool_data in all_tools.items():
            if tool_name in accessible_webservice_ids:
                filtered_tools.append({
                    "definition": tool_data["definition"],
                    "operation_type": webservice_operation_types.get(tool_name, "mutation"),
                })

        # Add confirm_action tool for guardrail confirmations
        filtered_tools.append({
            "definition": CONFIRM_ACTION_TOOL,
            "operation_type": "mutation",
        })

        context.ai_tools = filtered_tools

        # Load and filter navigation routes based on user permissions
        # Try plugin config first, fallback to old settings.ai
        ai_plugin_config = app_manager.settings.get_plugin_config("ai")
        routes_manifest_path = None

        # Check chatbot options for routes_manifest_path (plugin system)
        chatbot_config = ai_plugin_config.get("chatbot", {})
        if isinstance(chatbot_config, dict):
            routes_manifest_path = chatbot_config.get("options", {}).get("routes_manifest_path")

        manifest = None
        if routes_manifest_path:
            from lys.core.utils.routes import load_routes_manifest
            manifest = load_routes_manifest(routes_manifest_path)
        if manifest and "routes" in manifest:
            context.ai_accessible_routes = filter_routes_by_permissions(
                manifest["routes"],
                accessible_webservice_ids
            )
            # Add navigate tool with accessible routes as enum
            if context.ai_accessible_routes:
                navigate_tool = build_navigate_tool(context.ai_accessible_routes)
                filtered_tools.append({
                    "definition": navigate_tool,
                    "operation_type": "mutation",
                })
        else:
            context.ai_accessible_routes = []

        # Build system prompt with user context
        system_prompt_parts = []

        # Add custom application system prompt if configured (from plugin config)
        custom_system_prompt = chatbot_config.get("system_prompt") if isinstance(chatbot_config, dict) else None

        if custom_system_prompt:
            system_prompt_parts.append(custom_system_prompt)
            system_prompt_parts.append("")  # Empty line separator

        if connected_user:
            # User info from JWT
            user_id = connected_user.get("sub", "unknown")
            is_super_user = connected_user.get("is_super_user", False)

            # Load full user details from database
            user_details = await self._get_user_details(app_manager, session, user_id)

            system_prompt_parts.append("## User Context")
            if user_details:
                if user_details.get("email"):
                    system_prompt_parts.append(f"- Email: {user_details['email']}")
                if user_details.get("first_name") or user_details.get("last_name"):
                    name = f"{user_details.get('first_name', '')} {user_details.get('last_name', '')}".strip()
                    system_prompt_parts.append(f"- Name: {name}")
                if user_details.get("status"):
                    system_prompt_parts.append(f"- Status: {user_details['status']}")
                if user_details.get("language_code"):
                    system_prompt_parts.append(f"- Language: {user_details['language_code']}")
            system_prompt_parts.append(f"- Super User: {'Yes' if is_super_user else 'No'}")

            # Add User ID for tool calls that need to reference the current user
            system_prompt_parts.append(f"- User ID: {user_id}")

            # Add language instruction if user has a preferred language
            if user_details and user_details.get("language_code"):
                system_prompt_parts.append(f"\n**Important: Always respond in the user's language ({user_details['language_code']}).**")

            # Get user roles with descriptions if available
            if not is_super_user:
                roles_info = await self._get_user_roles_info(app_manager, session, user_id)
                if roles_info:
                    system_prompt_parts.append("\n## User Roles")
                    for role in roles_info:
                        role_line = f"- {role['code']}"
                        if role.get("description"):
                            role_line += f": {role['description']}"
                        system_prompt_parts.append(role_line)

            # Available tools summary
            system_prompt_parts.append(f"\n## Available Tools: {len(filtered_tools)}")
        else:
            system_prompt_parts.append("## User Context")
            system_prompt_parts.append("- Anonymous user (not authenticated)")
            system_prompt_parts.append(f"\n## Available Tools: {len(filtered_tools)} (public only)")

        context.ai_system_prompt = "\n".join(system_prompt_parts)

        yield

    async def _get_user_roles_info(
        self,
        app_manager,
        session,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get user roles with their descriptions.

        Args:
            app_manager: Application manager instance
            session: Database session
            user_id: User ID to get roles for

        Returns:
            List of role dictionaries with code and description
        """
        try:
            # Get role entity
            role_entity = app_manager.get_entity("role")
            user_entity = app_manager.get_entity("user")

            # Query roles for the user
            from sqlalchemy import select
            stmt = (
                select(role_entity)
                .where(role_entity.users.any(user_entity.id == user_id))
                .where(role_entity.enabled == True)
            )

            result = await session.execute(stmt)
            roles = result.scalars().all()

            return [
                {
                    "code": role.code,
                    "description": getattr(role, "description", None)
                }
                for role in roles
            ]
        except Exception:
            # Role service may not be available (user_role app not installed)
            return []

    async def _get_user_details(
        self,
        app_manager,
        session,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get user details from database.

        Args:
            app_manager: Application manager instance
            session: Database session
            user_id: User ID to get details for

        Returns:
            Dictionary with user details (email, first_name, last_name, status)
        """
        try:
            user_entity = app_manager.get_entity("user")

            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            # Query user with private_data loaded
            stmt = (
                select(user_entity)
                .where(user_entity.id == user_id)
                .options(selectinload(user_entity.private_data))
            )

            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return {}

            details = {
                "email": getattr(user, "email", None),
                "status": getattr(user, "status", None),
            }

            # Get name and language from private_data if available
            if hasattr(user, "private_data") and user.private_data:
                details["first_name"] = getattr(user.private_data, "first_name", None)
                details["last_name"] = getattr(user.private_data, "last_name", None)
                details["language_code"] = getattr(user.private_data, "language_code", None)

            # Convert status to string if needed
            if details["status"]:
                if hasattr(details["status"], "code"):
                    # ParametricItem from register
                    details["status"] = details["status"].code
                elif hasattr(details["status"], "value"):
                    # Standard enum
                    details["status"] = details["status"].value

            return details

        except Exception:
            # User entity may not have expected fields
            return {}