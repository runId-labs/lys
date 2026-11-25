"""
Agent services.

An agent works one task through tools on its own endpoint and returns a validated report.
Called from code — typically from a special tool of the chatbot, the agent then being a
tool of the chatbot (the orchestrator / specialist pattern) —, it keeps the reading out of
the caller's context: the caller gets the report, the trace stays in ai_agent_run.

The run, in order:
1. Its tools: the definition's webservices the user may call, plus exact arithmetic.
2. A tool loop on the agent's endpoint, under the user's token; the last call is made with
   tool calls refused, so the run ends on a written analysis.
3. One structured call turning that analysis into the report's schema (two steps — reason,
   then format —, so the loop's tool history never has to cross a structured call), on the
   definition's report endpoint: formatting decides nothing, a fast model does it.
Between 2 and 3, the caller's analysis check, when it gives one: it reads the analysis — the
source of truth, not the formatted report —, and what it finds wrong goes back to the agent for
ONE correction round (the evaluator / optimizer pattern); the corrected analysis is checked again,
then formatted. What is still wrong is returned with the report, the caller decides.

The trace is written in transactions of its own, opened when the run starts and closed when
it ends, whatever the end — a report, a failure, an unexpected error or a cancellation: it
never depends on the caller's transaction, which may roll back.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

import anyio
from sqlalchemy import update

from lys.apps.ai.errors import AGENT_REQUIRES_USER_TOKEN
from lys.apps.ai.modules.agent.consts import (
    AGENT_CORRECTION_INSTRUCTION,
    AGENT_FINAL_ROUND_INSTRUCTION,
    AGENT_PURE_TOOLS,
    AGENT_REPORT_INSTRUCTION,
    AGENT_RUN_FAILED,
    AGENT_RUN_RUNNING,
    AGENT_RUN_SUCCEEDED,
    AGENT_ANALYSIS_UNCHECKED,
    AGENT_TRACE_CLOSE_TIMEOUT,
)
from lys.apps.ai.modules.agent.entities import AIAgentRun
from lys.apps.ai.modules.agent.models import AgentDefinition, AgentRunResult, AnalysisCheck, AnalysisIssue, ReportT
from lys.apps.ai.modules.conversation.models import PageContextModel
from lys.apps.ai.modules.core.executors import GraphQLToolExecutor
from lys.apps.ai.modules.core.services import AIToolService
from lys.apps.ai.utils.calculator import CALCULATE_TOOL, handle_calculate
from lys.apps.ai.utils.providers.config import parse_plugin_config
from lys.apps.ai.utils.providers.exceptions import AIError
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import EntityService

logger = logging.getLogger(__name__)

# The operation type of a webservice tool that only reads (AIToolService metadata).
_QUERY_OPERATION = "query"

# Said to the caller when a run fails: what went wrong, never how — no provider message,
# no stack, nothing a model would repeat to the user.
_RUN_FAILED_MESSAGE = "The analysis could not be completed. Its trace is kept for review."

# Provider usage keys -> trace columns.
_USAGE_COLUMNS = (
    ("tokens_in", "prompt_tokens"),
    ("tokens_out", "completion_tokens"),
    ("cache_read_tokens", "cache_read_tokens"),
    ("cache_write_tokens", "cache_write_tokens"),
)


@dataclass
class _RunState:
    """A run as it goes: what it read and wrote, and each model call it made."""

    id: str
    transcript: List[Dict[str, Any]]
    calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: int = 0
    provider: Optional[str] = None
    model: Optional[str] = None

    def count_call(
        self, kind: str, latency_ms: int, usage: Optional[Dict[str, Any]], tool_calls: int = 0,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        One model call: its kind (loop, revision, report), its latency, its tokens, the tools it
        asked for — and its error when it failed, so a call that never answered is traced too.
        """
        entry = {"kind": kind, "latency_ms": latency_ms, "tool_calls": tool_calls, "model": self.model}
        entry.update({column: (usage or {}).get(key) for column, key in _USAGE_COLUMNS})
        if error is not None:
            entry["error"] = error
        self.calls.append(entry)
        return entry

    def totals(self) -> Dict[str, Optional[int]]:
        """The trace's columns, added up over the calls; a total no provider reported stays unknown."""
        totals: Dict[str, Optional[int]] = {
            "model_calls": len(self.calls),
            "tool_calls": self.tool_calls,
            "latency_ms": sum(call["latency_ms"] for call in self.calls),
        }
        for column, _ in _USAGE_COLUMNS:
            values = [call[column] for call in self.calls if call[column] is not None]
            totals[column] = sum(values) if values else None
        return totals


@register_service()
class AIAgentService(EntityService[AIAgentRun]):
    """Runs agents and keeps their trace."""

    @classmethod
    async def run(
        cls,
        definition: AgentDefinition[ReportT],
        task: str,
        info: Any,
        client_id: Optional[str] = None,
        tool_defaults: Optional[Dict[str, Any]] = None,
        analysis_check: Optional[AnalysisCheck] = None,
    ) -> AgentRunResult[ReportT]:
        """
        Run ``definition`` on ``task`` for the connected user.

        Args:
            definition: The agent.
            task: What it is asked, as the caller words it: the agent's only user message.
            info: GraphQL info of the caller; its context carries the connected user and the
                access token the agent calls the API with.
            client_id: The tenant the run is scoped to, stored on the trace.
            tool_defaults: The run's scope, as page params are for the chatbot (``clientId`` ->
                ``client_id``): injected in its tools and pinned over the model's ids.
            analysis_check: Checks the analysis against its sources; its issues open one
                correction round, and those left after it are returned with the report.

        Returns:
            The report, or the error when the run failed — a failure is a result, never an
            exception, so a calling tool can hand it to its model.

        Raises:
            LysError: AGENT_REQUIRES_USER_TOKEN when the context carries no user token.
            ValueError: the definition names a webservice that is not a tool, or a mutation.
        """
        context = getattr(info, "context", None)
        connected_user = getattr(context, "connected_user", None)
        access_token = getattr(context, "access_token", None)
        if not connected_user or not access_token:
            raise LysError(AGENT_REQUIRES_USER_TOKEN, "An agent runs with the user's own token")

        tools = await cls._tools_for(definition, connected_user)
        executor = await cls._executor(tools, access_token, tool_defaults)
        transcript = [{"role": "user", "content": task}]
        state = _RunState(
            id=await cls._open_trace(definition, connected_user["sub"], client_id, task, transcript),
            transcript=transcript,
        )

        status, output, error = AGENT_RUN_FAILED, None, None
        try:
            analysis = await cls._tool_loop(definition, state, tools, executor, info, definition.max_iterations, "loop")
            issues, checked = await cls._check(analysis_check, analysis, state)
            if issues and checked:
                state.transcript.append({"role": "user", "content": _correction(issues)})
                analysis = await cls._tool_loop(
                    definition, state, tools, executor, info, definition.revision_iterations, "revision",
                )
                issues, _ = await cls._check(analysis_check, analysis, state)
            report = await cls._report(definition, task, analysis, state)
            status, output = AGENT_RUN_SUCCEEDED, report.model_dump(mode="json")
            return AgentRunResult(run_id=state.id, report=report, issues=tuple(issues))
        except AIError as failure:
            error = str(failure)
            logger.error("Agent run %s (%s) failed: %s", state.id, definition.purpose, failure)
            return AgentRunResult(run_id=state.id, report=None, error=_RUN_FAILED_MESSAGE)
        except BaseException as failure:  # an unexpected error or a cancellation: traced, then raised
            error = f"{type(failure).__name__}: {failure}"
            raise
        finally:
            await cls._close_trace(state, status, output, error)

    # -------------------------------------------------------------------------
    # The run's tools
    # -------------------------------------------------------------------------

    @classmethod
    async def _tools_for(cls, definition: AgentDefinition, connected_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        The tools of a run: the definition's webservices the user may call — the user's
        rights, read from the token, as for the chatbot —, plus exact arithmetic.

        Raises:
            ValueError: a declared webservice is not a tool (a misspelt name would silently
                shrink the agent), or is a mutation (an agent reads, it never writes: what it
                reads may carry instructions, and a writing agent would act on them).
        """
        for name in sorted(definition.webservices):
            tool = await AIToolService.get_tool(name)
            if tool is None:
                raise ValueError(f"Agent '{definition.purpose}' declares '{name}', which is not a tool")
            if tool.get("operation_type") != _QUERY_OPERATION:
                raise ValueError(f"Agent '{definition.purpose}' declares '{name}', which is not a query")

        accessible = await AIToolService.get_accessible_tools(connected_user)
        tools = [tool for tool in accessible if tool.get("webservice") in definition.webservices]
        return tools + [CALCULATE_TOOL]

    @classmethod
    async def _executor(
        cls, tools: List[Dict[str, Any]], access_token: str, tool_defaults: Optional[Dict[str, Any]],
    ) -> GraphQLToolExecutor:
        """
        The run's executor: the API called with the user's token, never a service identity, and
        the caller's defaults pinned — they are the run's scope, not a starting point the model
        may roam from (a model left free invents a client id from another entity's).
        """
        ai_config = parse_plugin_config(cls.app_manager.settings.get_plugin_config("ai"))
        executor = GraphQLToolExecutor(
            gateway_url=ai_config.executor.gateway_url,
            bearer_token=access_token,
            timeout=ai_config.executor.timeout,
            verify_ssl=ai_config.executor.verify_ssl,
            pin_ids=True,
        )
        # The defaults travel the way page params do for the chatbot: the executor injects them.
        page_context = PageContextModel(page_name="agent", params=tool_defaults) if tool_defaults else None
        await executor.initialize(tools=tools, page_context=page_context)
        for name in AGENT_PURE_TOOLS:
            executor.register_special_tool(name, handle_calculate)
        return executor

    # -------------------------------------------------------------------------
    # The loop and the report
    # -------------------------------------------------------------------------

    @classmethod
    async def _tool_loop(
        cls,
        definition: AgentDefinition,
        state: _RunState,
        tools: List[Dict[str, Any]],
        executor: GraphQLToolExecutor,
        info: Any,
        iterations: int,
        kind: str,
    ) -> str:
        """
        Call the model, run the tools it asks for, until it writes its analysis: ``iterations``
        calls at most, the last made with tool calls refused and AGENT_FINAL_ROUND_INSTRUCTION,
        never kept. ``kind`` names the calls in the trace (loop, or revision after a check).

        Returns:
            The analysis the model wrote.

        Raises:
            AIError: the endpoint's whole fallback chain failed, or the model wrote nothing.
        """
        ai_service = cls.app_manager.get_service("ai")
        llm_tools = [tool.get("definition", tool) for tool in tools]
        messages = state.transcript

        for iteration in range(iterations):
            last_call = iteration == iterations - 1
            final_round = [{"role": "system", "content": AGENT_FINAL_ROUND_INSTRUCTION}] if last_call else []
            started = time.perf_counter()
            try:
                response = await ai_service.chat_with_purpose(
                    messages + final_round, definition.purpose, llm_tools,
                    # The run names its own cache bucket: what the provider reuses is this run's prefix.
                    cache_key=state.id, tool_calls_allowed=not last_call,
                )
            except AIError as failure:
                state.count_call(kind, _elapsed_ms(started), None, error=str(failure))
                raise
            tool_calls = [] if last_call else (response.tool_calls or [])
            state.provider, state.model = response.provider, response.model
            state.count_call(kind, _elapsed_ms(started), response.usage, len(tool_calls))

            if not tool_calls:
                analysis = (response.content or "").strip()
                if not analysis:
                    raise AIError("The agent wrote no analysis")
                messages.append({"role": "assistant", "content": analysis})
                return analysis

            messages.append({"role": "assistant", "content": response.content, "tool_calls": tool_calls})
            for tool_call in tool_calls:
                messages.append(await cls._run_tool(tool_call, executor, info, state))

        raise AIError("The agent wrote no analysis")  # unreachable: the last call refuses tools

    @classmethod
    async def _run_tool(
        cls, tool_call: Dict[str, Any], executor: GraphQLToolExecutor, info: Any, state: _RunState,
    ) -> Dict[str, Any]:
        """
        Run one tool call and return its message. A tool that fails is the model's to read
        (as for the chatbot): it gets a generic error and may call again, the run goes on.
        """
        function = tool_call.get("function") or {}
        name = function.get("name", "")
        state.tool_calls += 1
        try:
            raw = function.get("arguments") or "{}"
            arguments = json.loads(raw) if isinstance(raw, str) else raw
            result = await executor.execute(
                tool_name=name, arguments=arguments,
                context={"session": None, "info": info, "conversation_id": None},
            )
        except Exception as error:  # noqa: BLE001 - any tool failure is the model's to read
            logger.error("Agent run %s: tool '%s' failed: %s", state.id, name, error)
            result = {"error": f"Tool '{name}' failed to execute."}
        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return {"role": "tool", "tool_call_id": tool_call.get("id", ""), "content": content}

    @classmethod
    async def _report(
        cls, definition: AgentDefinition[ReportT], task: str, analysis: str, state: _RunState,
    ) -> ReportT:
        """
        Turn the analysis into the report's schema, on the definition's report endpoint: one
        structured call that reads the task and the analysis only — the tool history stays out
        of it, so no provider has to accept tool messages beside a response schema.

        Raises:
            AIError: no endpoint of the chain produced a valid report.
        """
        ai_service = cls.app_manager.get_service("ai")
        endpoint = ai_service.get_endpoint(definition.report_endpoint).with_cache_key(state.id)
        started = time.perf_counter()
        try:
            response = await ai_service.chat_json_with_metadata(
                [
                    {"role": "user", "content": task},
                    {"role": "assistant", "content": analysis},
                    {"role": "user", "content": AGENT_REPORT_INSTRUCTION},
                ],
                endpoint,
                definition.report_schema,
            )
        except AIError as failure:
            state.count_call("report", _elapsed_ms(started), None, error=str(failure))
            raise
        # The structured call reports no usage: its latency and model are what the trace keeps.
        state.provider, state.model = response.provider, response.model
        state.count_call("report", _elapsed_ms(started), None)
        return response.data

    @classmethod
    async def _check(
        cls, analysis_check: Optional[AnalysisCheck], analysis: str, state: _RunState,
    ) -> Tuple[List[AnalysisIssue], bool]:
        """
        Run the caller's check on an analysis and trace what it found on the call that wrote it:
        the issues, and whether the check ran. A check that cannot run leaves the analysis
        standing, flagged unchecked — never a failed run, and no correction: nothing to correct.
        """
        if analysis_check is None:
            return [], True
        try:
            issues, checked = list(await analysis_check(analysis)), True
        except Exception as failure:  # noqa: BLE001 - an unchecked analysis is the caller's to show
            logger.error("Agent run %s: analysis check failed: %s", state.id, failure)
            issues, checked = [AnalysisIssue(location="analysis", message=AGENT_ANALYSIS_UNCHECKED)], False
        state.calls[-1]["issues"] = [f"{issue.location}: {issue.message}" for issue in issues]
        return issues, checked

    # -------------------------------------------------------------------------
    # The trace, in transactions of its own
    # -------------------------------------------------------------------------

    @classmethod
    async def _open_trace(
        cls, definition: AgentDefinition, user_id: str, client_id: Optional[str], task: str,
        transcript: List[Dict[str, Any]],
    ) -> str:
        """Write the run, RUNNING, in its own transaction, and return its id."""
        async with cls.app_manager.database.get_session() as session:
            agent_run = await cls.create(
                session, purpose=definition.purpose, user_id=user_id, client_id=client_id,
                status=AGENT_RUN_RUNNING, task=task, transcript=transcript, calls=[], model_calls=0, tool_calls=0,
            )
            return agent_run.id

    @classmethod
    async def _close_trace(
        cls, state: _RunState, status: str, output: Optional[Dict[str, Any]], error: Optional[str],
    ) -> None:
        """
        Close the run in its own transaction: its end, its transcript and calls, the report or
        the error. Shielded and bounded: a cancelled caller still leaves the trace, and a store
        that stops answering does not hold the caller. A trace that cannot be written is logged,
        never raised — it must not turn a run's result into a failure.
        """
        entity = cls.entity_class
        values = {
            "status": status, "ended_at": datetime.now(UTC), "transcript": state.transcript, "calls": state.calls,
            "output": output, "error": error, "provider": state.provider, "model": state.model, **state.totals(),
        }
        try:
            with anyio.CancelScope(shield=True), anyio.fail_after(AGENT_TRACE_CLOSE_TIMEOUT):
                async with cls.app_manager.database.get_session() as session:
                    await session.execute(update(entity).where(entity.id == state.id).values(**values))
        except Exception as failure:  # noqa: BLE001 - the trace never fails the run
            logger.error("Agent run %s: trace not closed: %s", state.id, failure)


def _elapsed_ms(started: float) -> int:
    """Milliseconds since ``started`` (a perf_counter reading)."""
    return int((time.perf_counter() - started) * 1000)


def _correction(issues: List[AnalysisIssue]) -> str:
    """The correction round's message: the instruction, then each issue where it is."""
    return AGENT_CORRECTION_INSTRUCTION + "\n" + "\n".join(f"- {issue.location} : {issue.message}" for issue in issues)
