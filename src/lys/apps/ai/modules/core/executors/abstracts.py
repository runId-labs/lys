"""
Tool Executor Abstract Base Class.

Defines the interface for tool execution strategies.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class ToolExecutor(ABC):
    """
    Base class for tool execution strategies.

    Different implementations handle tool execution in different environments:
    - LocalToolExecutor: Direct resolver execution (monolith mode)
    - GraphQLToolExecutor: Remote execution via GraphQL (microservice mode)
    """

    async def initialize(self, tools: List[Dict[str, Any]] = None, **kwargs) -> None:
        """
        Initialize the executor with tools and context.

        Args:
            tools: List of tool definitions
            **kwargs: Additional initialization parameters (e.g., info for local executor)
        """
        pass

    @abstractmethod
    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments from LLM
            context: Execution context containing:
                - session: Database session (for local execution)
                - info: GraphQL info context (for local execution)
                - jwt: User JWT token (for remote execution)
                - user_id: User ID

        Returns:
            Tool execution result as a dictionary
        """
        pass

    @abstractmethod
    async def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get all available tool definitions for LLM.

        Returns:
            List of tool definitions in the format expected by LLM APIs
        """
        pass