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

    def _inject_page_params(self, arguments: Dict[str, Any], force_ids: bool = True) -> Dict[str, Any]:
        """
        Inject page-context params as defaults into tool arguments.

        Every param defaults to the page focus only when the LLM omitted it. ``*_id`` params
        are additionally PINNED to the focus (overriding the LLM) when ``force_ids`` is True.
        Pin them on the **service-auth** path — there the gateway applies no per-user access
        filtering, so an LLM-chosen id must not be trusted. With a **user bearer**
        (``force_ids=False``) ids may be overridden by the LLM to roam (e.g. a sister company
        / another year): access is then enforced by the user token at the gateway, and writes
        by a user review step. The pin is therefore a safeguard for the unfiltered path, not
        the security boundary itself.

        Args:
            arguments: Tool arguments from LLM
            force_ids: Pin ``*_id`` params to the focus (True for service auth — the safe
                default; False for a user-authed executor where the gateway enforces access).

        Returns:
            Arguments with page-focus defaults filled in (and ids pinned when force_ids)
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

            if snake_key.endswith("_id") and force_ids:
                # Service-auth path: pin ids to the focus (no per-user gateway filtering).
                logger.debug(f"[ParamInjection] Pinned id (service auth): {snake_key}={value}")
                result[snake_key] = value
            elif snake_key not in result:
                # Default to the page focus only when the LLM omitted the param.
                logger.debug(f"[ParamInjection] Defaulting missing param: {snake_key}={value}")
                result[snake_key] = value
            else:
                # The LLM provided a value — keep it (may be roaming to another entity/year).
                logger.debug(
                    f"[ParamInjection] Keeping LLM value for '{snake_key}': {result[snake_key]} "
                    f"(context default: {value})"
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