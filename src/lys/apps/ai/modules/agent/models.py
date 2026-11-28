"""
Agent definition and run result.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, FrozenSet, Generic, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

from lys.apps.ai.modules.agent.consts import (
    AGENT_REPORT_FROM_ANALYSIS,
    AGENT_REPORT_FROM_READINGS,
    AGENT_REPORT_SOURCES,
    DEFAULT_AGENT_CONTINUATION_TTL,
    DEFAULT_AGENT_MAX_ITERATIONS,
    DEFAULT_AGENT_REVISION_ITERATIONS,
)

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
        report_schema: The report the analysis is formatted into, validated, when the caller
            wants one — a structured report is one more model call, copying the whole analysis.
            None: the run returns its analysis as written, and no report.
        max_iterations: Model calls of the tool loop, the last with tool calls refused.
        report_purpose: The endpoint turning the analysis into the report. Formatting decides
            nothing — it copies the analysis into the schema —, so a fast model without
            reasoning does it; None: the agent's own endpoint. Given without a report_schema,
            it raises: an endpoint with nothing to format is a definition error.
        report_source: What the report is written from. AGENT_REPORT_FROM_ANALYSIS (default):
            copied from the analysis the agent wrote, the tool history left out of the structured
            call — any provider takes it. AGENT_REPORT_FROM_READINGS: written from the run's
            transcript, what the tools returned, on the agent's own endpoint and instructions —
            its fields come straight from the sources, so a report check can bear on them, and
            nothing is written twice; the provider must accept tool messages beside a response
            schema. It needs a report_schema, and no report_purpose: the agent writes it.
        revision_iterations: Model calls of the correction round a check opens, the last with
            tool calls refused.
        continuation_ttl: How long a run may be followed up once it ended.
        figures_check: Whether every figure the analysis writes must be found in the run — the task,
            the tools' results, the calculate steps (utils/sourced_figures.py) —, beside the caller's
            own check: a figure found nowhere opens the correction round like any issue.
    """

    purpose: str
    webservices: FrozenSet[str]
    report_schema: Optional[Type[ReportT]] = None
    max_iterations: int = DEFAULT_AGENT_MAX_ITERATIONS
    report_purpose: Optional[str] = None
    report_source: str = AGENT_REPORT_FROM_ANALYSIS
    revision_iterations: int = DEFAULT_AGENT_REVISION_ITERATIONS
    continuation_ttl: timedelta = DEFAULT_AGENT_CONTINUATION_TTL
    figures_check: bool = False

    @property
    def report_endpoint(self) -> str:
        """The endpoint the report is formatted on."""
        return self.report_purpose or self.purpose

    def __post_init__(self):
        if not self.purpose:
            raise ValueError("An agent needs an endpoint purpose")
        if self.report_purpose and self.report_schema is None:
            raise ValueError("report_purpose formats a report: it needs a report_schema")
        if self.report_source not in AGENT_REPORT_SOURCES:
            raise ValueError(f"report_source is one of {AGENT_REPORT_SOURCES}, got {self.report_source!r}")
        if self.report_source == AGENT_REPORT_FROM_READINGS and (self.report_schema is None or self.report_purpose):
            raise ValueError(
                "A report written from the readings needs a report_schema and no report_purpose: "
                "the agent writes it on its own endpoint"
            )
        if self.max_iterations < 1:
            raise ValueError(f"max_iterations must be a positive integer, got {self.max_iterations!r}")
        if self.revision_iterations < 1:
            raise ValueError(f"revision_iterations must be a positive integer, got {self.revision_iterations!r}")
        if self.continuation_ttl <= timedelta(0):
            raise ValueError(f"continuation_ttl must be a positive duration, got {self.continuation_ttl!r}")


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


@dataclass(frozen=True)
class AgentContinuation:
    """
    A run a follow-up continues, checked to be the caller's (AIAgentService.continuation).

    Attributes:
        run_id: The run followed up.
        client_id: Its tenant: the follow-up's, never the caller's.
        tool_defaults: Its scope, pinned in the tools: the follow-up's, never the caller's — the
            caller reads it to build what depends on the scope (an analysis check).
        transcript: What the run read and wrote, as stored.
    """

    run_id: str
    client_id: Optional[str]
    tool_defaults: Optional[Dict[str, Any]]
    transcript: Tuple[Dict[str, Any], ...]


# A check of an analysis against its sources, by the caller who knows them: the issues it finds,
# none when the analysis holds. It reads the analysis itself — the source of truth —, never the
# formatted report, so a formatter dropping a field can never look like an analysis error.
AnalysisCheck = Callable[[str], Awaitable[List[AnalysisIssue]]]

# A check of a report's FIELDS against its sources, by the caller who knows them: each value where
# the report says it was read. A field is either checked or it is not in the report — unlike a
# citation searched in prose, which a different wording hides from the check.
ReportCheck = Callable[[Any], Awaitable[List[AnalysisIssue]]]


@dataclass(frozen=True)
class AgentRunResult(Generic[ReportT]):
    """
    What a run returned, and the run's id to read its trace or follow it up.

    A run that succeeded returns its ``analysis`` — what the agent wrote, checked and corrected —
    and, when the definition asks for one, the ``report`` formatted from it. A run that failed
    returns neither: ``error`` then says why, in words a caller may hand to a model (no
    internals). ``report`` alone does not tell a failure — it is also None for a definition
    without a report_schema —: read ``succeeded``. ``issues``: what the checks (of the analysis,
    of the report) still found wrong after their correction round — the caller decides what to
    show of those parts.
    """

    run_id: str
    report: Optional[ReportT]
    error: Optional[str] = None
    issues: Tuple[AnalysisIssue, ...] = ()
    analysis: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        """Whether the run ended on an analysis (and its report, when one was asked)."""
        return self.error is None
