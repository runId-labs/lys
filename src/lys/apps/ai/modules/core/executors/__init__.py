"""
Tool executors for AI module.

Executes tools via GraphQL calls to Apollo Gateway (microservice mode).
"""

from lys.apps.ai.modules.core.executors.abstracts import ToolExecutor
from lys.apps.ai.modules.core.executors.graphql import GraphQLToolExecutor

__all__ = ["ToolExecutor", "GraphQLToolExecutor"]