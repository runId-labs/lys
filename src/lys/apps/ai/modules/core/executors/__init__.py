"""
Tool executors for AI module.

Provides different strategies for executing tools:
- LocalToolExecutor: Execute tools via local resolvers (monolith mode)
- GraphQLToolExecutor: Execute tools via GraphQL calls (microservice mode)
"""

from lys.apps.ai.modules.core.executors.abstracts import ToolExecutor
from lys.apps.ai.modules.core.executors.local import LocalToolExecutor
from lys.apps.ai.modules.core.executors.graphql import GraphQLToolExecutor

__all__ = ["ToolExecutor", "LocalToolExecutor", "GraphQLToolExecutor"]