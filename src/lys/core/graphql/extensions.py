"""
GraphQL extensions for Strawberry.

This module provides custom Strawberry extensions for the lys framework,
including database session management for GraphQL operations.
"""
from typing import Any

from strawberry.extensions import SchemaExtension


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
                # Store session in GraphQL context so all resolvers can access it
                self.execution_context.context.session = session

                # Yield to allow the GraphQL operation to execute with session open
                # This includes the main resolver and all nested field resolvers
                yield

                # Session automatically closes here when exiting async with block