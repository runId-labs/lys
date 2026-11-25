"""
Agent definition and run result.
"""
from dataclasses import dataclass
from typing import Awaitable, Callable, FrozenSet, Generic, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

from lys.apps.ai.modules.agent.consts import DEFAULT_AGENT_MAX_ITERATIONS, DEFAULT_AGENT_REVISION_ITERATIONS

ReportT = TypeVar("ReportT", bound=BaseModel)


@dataclass(frozen=True)
class AgentDefinition(Generic[ReportT]):
    """
    What an agent is: the endpoint it runs on, what it may read, what it returns.

    Attributes:
        purpose: The endpoint (AIConfig.endpoints key). Its system_prompt is the agent's
            instructions; its model, options and fallback chain are the agent's.
        webservices: The webservices the agent may call as tools. A run holds those of them
            the user may call — never more than the user, never more than declared —, plus
            exact arithmetic. Queries only: an agent reads, it never writes.
        report_schema: The report the run returns, validated.
        max_iterations: Model calls of the tool loop, the last with tool calls refused.
        report_purpose: The endpoint turning the analysis into the report. Formatting decides
            nothing — it copies the analysis into the schema —, so a fast model without
            reasoning does it; None: the agent's own endpoint.
        revision_iterations: Model calls of the correction round an analysis check opens, the
            last with tool calls refused.
    """

    purpose: str
    webservices: FrozenSet[str]
    report_schema: Type[ReportT]
    max_iterations: int = DEFAULT_AGENT_MAX_ITERATIONS
    report_purpose: Optional[str] = None
    revision_iterations: int = DEFAULT_AGENT_REVISION_ITERATIONS

    @property
    def report_endpoint(self) -> str:
        """The endpoint the report is formatted on."""
        return self.report_purpose or self.purpose

    def __post_init__(self):
        if not self.purpose:
            raise ValueError("An agent needs an endpoint purpose")
        if self.max_iterations < 1:
            raise ValueError(f"max_iterations must be a positive integer, got {self.max_iterations!r}")
        if self.revision_iterations < 1:
            raise ValueError(f"revision_iterations must be a positive integer, got {self.revision_iterations!r}")


@dataclass(frozen=True)
class AnalysisIssue:
    """
    What a check found wrong in an agent's analysis, in words the agent reads.

    Attributes:
        location: What in the analysis (e.g. the citation « Hypothèses » E35 = 25 %).
        message: What is wrong and what the source says instead — the agent corrects from it.
    """

    location: str
    message: str


# A check of an analysis against its sources, by the caller who knows them: the issues it finds,
# none when the analysis holds. It reads the analysis itself — the source of truth —, never the
# formatted report, so a formatter dropping a field can never look like an analysis error.
AnalysisCheck = Callable[[str], Awaitable[List[AnalysisIssue]]]


@dataclass(frozen=True)
class AgentRunResult(Generic[ReportT]):
    """
    What a run returned: the report, and the run's id to read its trace.

    ``report`` is None when the run failed; ``error`` then says why, in words a caller may
    hand to a model (no internals). ``issues``: what the analysis check still found wrong after
    the correction round — the caller decides what to show of those parts.
    """

    run_id: str
    report: Optional[ReportT]
    error: Optional[str] = None
    issues: Tuple[AnalysisIssue, ...] = ()
