"""
Tool Executor Abstract Base Class.

Defines the interface for tool execution strategies.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from lys.core.utils.strings import to_snake_case

logger = logging.getLogger(__name__)


class ToolExecutor(ABC):
    """
    Base class for tool execution strategies.

    Different implementations handle tool execution in different environments:
    - LocalToolExecutor: Direct resolver execution (monolith mode)
    - GraphQLToolExecutor: Remote execution via GraphQL (microservice mode)
    """

    _page_context: Optional[Any] = None

    def _inject_page_params(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject page context params into tool arguments.

        Rules:
        - Params ending with '_id': Always override (security-critical)
        - Other params: Only inject if LLM didn't provide a value

        Args:
            arguments: Tool arguments from LLM

        Returns:
            Arguments with injected/overridden params
        """
        if not self._page_context:
            logger.debug("[ParamInjection] No page context, skipping injection")
            return arguments

        if not self._page_context.params:
            logger.debug("[ParamInjection] Page context has no params, skipping injection")
            return arguments

        logger.debug(
            f"[ParamInjection] Processing context params: {self._page_context.params}"
        )
        logger.debug(f"[ParamInjection] LLM arguments before injection: {arguments}")

        result = dict(arguments)

        for key, value in self._page_context.params.items():
            if value is None:
                continue

            # Convert camelCase (frontend) to snake_case (backend)
            snake_key = to_snake_case(key)

            if snake_key.endswith("_id"):
                # IDs: always override (security)
                if snake_key in result and result[snake_key] != value:
                    logger.debug(
                        f"[ParamInjection] Security override: {snake_key}={result[snake_key]} -> {value}"
                    )
                else:
                    logger.debug(f"[ParamInjection] Setting ID param: {snake_key}={value}")
                result[snake_key] = value
            elif snake_key not in result:
                # Other params: inject only if absent
                logger.debug(f"[ParamInjection] Injecting missing param: {snake_key}={value}")
                result[snake_key] = value
            else:
                logger.debug(
                    f"[ParamInjection] Keeping LLM value for '{snake_key}': {result[snake_key]} "
                    f"(context had: {value})"
                )

        logger.debug(f"[ParamInjection] Arguments after injection: {result}")
        return result

    async def initialize(self, tools: List[Dict[str, Any]] = None, **kwargs) -> None:
        """
        Initialize the executor with tools and context.

        Args:
            tools: List of tool definitions
            **kwargs: Additional initialization parameters
                - page_context: Page context for param injection
        """
        self._page_context = kwargs.get("page_context")

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