"""
Agent services.

An agent works one task through tools on its own endpoint and returns its analysis — and,
when its definition asks for one, a validated report formatted from it.
Called from code — typically from a special tool of the chatbot, the agent then being a
tool of the chatbot (the orchestrator / specialist pattern) —, it keeps the reading out of
the caller's context: the caller gets the result, the trace stays in ai_agent_run.

The run, in order:
1. Its tools: the definition's webservices the user may call, plus exact arithmetic.
2. A tool loop on the agent's endpoint, under the user's token; the last call is made with
   tool calls refused, so the run ends on a written analysis.
3. When the definition has a report_schema: one structured call turning that analysis into the
   report's schema (two steps — reason, then format —, so the loop's tool history never has to
   cross a structured call), on the definition's report endpoint: formatting decides nothing, a
   fast model does it. It copies the whole analysis, hence costs as long as writing it again: a
   caller that reads prose — another model — may ask for none and take the analysis as written.
Between 2 and 3, the caller's analysis check, when it gives one: it reads the analysis — the
source of truth, not the formatted report —, and what it finds wrong goes back to the agent for
ONE correction round (the evaluator / optimizer pattern); the corrected analysis is checked again,
then formatted. What is still wrong is returned with the result, the caller decides.

The report may instead be written from the READINGS (``report_source``): the structured call
then reads the run's transcript — what the tools returned — on the agent's own endpoint, so the
report's fields come straight from the sources and nothing is written twice. A ``report_check``
then bears on those fields, each value where the report says it was read: what it finds wrong
opens ONE correction round, the report is written again and checked again.

A run may be followed up (``continuation``, then ``run(continuation=...)``): the follow-up is a run
of its own, on the scope of the run it continues, reading its transcript with the tool results
cleared and the new task after it — the caller asks again without the agent reading everything again.

The trace is written in transactions of its own, opened when the run starts and closed when
it ends, whatever the end — a report, a failure, an unexpected error or a cancellation: it
never depends on the caller's transaction, which may roll back.
"""
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

import anyio
from sqlalchemy import update

from lys.apps.ai.errors import AGENT_REQUIRES_USER_TOKEN, AGENT_RUN_NOT_CONTINUABLE, AGENT_RUN_NOT_FOUND
from lys.apps.ai.modules.agent.consts import (
    AGENT_CLEARED_TOOL_RESULT,
    AGENT_CORRECTION_INSTRUCTION,
    AGENT_FINAL_ROUND_INSTRUCTION,
    AGENT_PURE_TOOLS,
    AGENT_REPORT_CORRECTION_INSTRUCTION,
    AGENT_REPORT_FROM_READINGS,
    AGENT_REPORT_FROM_READINGS_INSTRUCTION,
    AGENT_REPORT_INSTRUCTION,
    AGENT_RUN_FAILED,
    AGENT_RUN_RUNNING,
    AGENT_RUN_SUCCEEDED,
    AGENT_ANALYSIS_UNCHECKED,
    AGENT_UNSOURCED_FIGURE,
    AGENT_TRACE_CLOSE_TIMEOUT,
)
from lys.apps.ai.modules.agent.entities import AIAgentRun
from lys.apps.ai.modules.agent.models import (
    AgentContinuation,
    AgentDefinition,
    AgentRunResult,
    AnalysisCheck,
    AnalysisIssue,
    ReportCheck,
    ReportT,
)
from lys.apps.ai.modules.conversation.models import PageContextModel
from lys.apps.ai.modules.core.executors import GraphQLToolExecutor
from lys.apps.ai.modules.core.services import AIToolService
from lys.apps.ai.utils.calculator import CALCULATE_TOOL, build_calculate_handler
from lys.apps.ai.utils.provenance import Provenance, model_result
from lys.apps.ai.utils.sourced_figures import context_of, unsourced_figures
from lys.apps.ai.utils.providers.config import parse_plugin_config
from lys.apps.ai.utils.providers.exceptions import AIError
from lys.apps.ai.utils.tracing import call_totals, traced_call
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import EntityService

logger = logging.getLogger(__name__)

# The operation type of a webservice tool that only reads (AIToolService metadata).
_QUERY_OPERATION = "query"

# Said to the caller when a run fails: what went wrong, never how — no provider message,
# no stack, nothing a model would repeat to the user.
_RUN_FAILED_MESSAGE = "The analysis could not be completed. Its trace is kept for review."

@dataclass
class _RunState:
    """A run as it goes: what it read and wrote, and each model call it made."""

    id: str
    transcript: List[Dict[str, Any]]
    # Where the figures the run's tools showed come from: read by its calculate, never sent to the model
    provenance: Provenance = field(default_factory=Provenance)
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
        entry = traced_call(kind, latency_ms, usage, self.model, tool_calls, error)
        self.calls.append(entry)
        return entry

    def totals(self) -> Dict[str, Optional[int]]:
        """The trace's columns, added up over the calls; a total no provider reported stays unknown."""
        return call_totals(self.calls, self.tool_calls)


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
        continuation: Optional[AgentContinuation] = None,
        report_check: Optional[ReportCheck] = None,
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
            report_check: Checks the report's fields against its sources (a definition with a
                report_schema); its issues open one correction round, the report is written
                again, and those left after it are returned with the result.
            continuation: The run this one follows up (``continuation``): ``task`` is the
                follow-up, read after that run's transcript, on that run's scope — ``client_id``
                and ``tool_defaults`` are then left out.

        Returns:
            The analysis and, when the definition asks for one, its report — or the error when
            the run failed: a failure is a result, never an exception, so a calling tool can
            hand it to its model.

        Raises:
            LysError: AGENT_REQUIRES_USER_TOKEN when the context carries no user token.
            ValueError: the definition names a webservice that is not a tool, or a mutation; a
                continuation is given with a scope of the caller's.
        """
        if continuation is not None:
            if client_id is not None or tool_defaults is not None:
                raise ValueError("A follow-up runs on the scope of the run it continues, never on the caller's")
            client_id, tool_defaults = continuation.client_id, continuation.tool_defaults
        context = getattr(info, "context", None)
        connected_user = getattr(context, "connected_user", None)
        access_token = getattr(context, "access_token", None)
        if not connected_user or not access_token:
            raise LysError(AGENT_REQUIRES_USER_TOKEN, "An agent runs with the user's own token")

        tools = await cls._tools_for(definition, connected_user)
        provenance = Provenance()
        executor = await cls._executor(tools, access_token, tool_defaults, provenance)
        history = _cleared(continuation.transcript) if continuation is not None else []
        transcript = history + [{"role": "user", "content": task}]
        state = _RunState(
            id=await cls._open_trace(
                definition, connected_user["sub"], client_id, task, transcript, tool_defaults,
                continuation.run_id if continuation is not None else None,
            ),
            transcript=transcript,
            provenance=provenance,
        )

        status, output, error = AGENT_RUN_FAILED, None, None
        try:
            analysis = await cls._tool_loop(definition, state, tools, executor, info, definition.max_iterations, "loop")
            issues, checked = await cls._check(definition, analysis_check, analysis, state)
            if issues and checked:
                state.transcript.append({"role": "user", "content": _correction(issues)})
                analysis = await cls._tool_loop(
                    definition, state, tools, executor, info, definition.revision_iterations, "revision",
                )
                issues, _ = await cls._check(definition, analysis_check, analysis, state)
            # A report is the caller's choice: without a schema, the analysis as written is the result
            report, output = None, None
            if definition.report_schema is not None:
                report = await cls._report(definition, task, analysis, state)
                report_issues, checked = await cls._check_report(report_check, report, state)
                if report_issues and checked:
                    state.transcript.append({"role": "user", "content": _correction(
                        report_issues, AGENT_REPORT_CORRECTION_INSTRUCTION,
                    )})
                    analysis = await cls._tool_loop(
                        definition, state, tools, executor, info, definition.revision_iterations, "revision",
                    )
                    report = await cls._report(definition, task, analysis, state)
                    report_issues, _ = await cls._check_report(report_check, report, state)
                issues = [*issues, *report_issues]
                output = report.model_dump(mode="json")
            status = AGENT_RUN_SUCCEEDED
            return AgentRunResult(run_id=state.id, report=report, issues=tuple(issues), analysis=analysis)
        except AIError as failure:
            error = str(failure)
            logger.error("Agent run %s (%s) failed: %s", state.id, definition.purpose, failure)
            return AgentRunResult(run_id=state.id, report=None, error=_RUN_FAILED_MESSAGE)
        except BaseException as failure:  # an unexpected error or a cancellation: traced, then raised
            error = f"{type(failure).__name__}: {failure}"
            raise
        finally:
            await cls._close_trace(state, status, output, error)

    @classmethod
    async def continuation(
        cls, definition: AgentDefinition, run_id: str, info: Any, client_id: Optional[str] = None,
    ) -> AgentContinuation:
        """
        The run ``run_id`` as a follow-up continues it, checked to be the caller's: the connected
        user's, of ``definition``'s agent, of ``client_id`` (the caller's tenant: a run of another
        client is not continued on this one), succeeded, ended within the definition's
        ``continuation_ttl``.

        Raises:
            LysError: AGENT_REQUIRES_USER_TOKEN when the context carries no user; AGENT_RUN_NOT_FOUND
                for a run that is not the caller's to continue — unknown, malformed, another user's,
                agent's or client's, one answer for all; AGENT_RUN_NOT_CONTINUABLE for the caller's
                run that did not succeed or ended too long ago.
        """
        connected_user = getattr(getattr(info, "context", None), "connected_user", None)
        if not connected_user:
            raise LysError(AGENT_REQUIRES_USER_TOKEN, "A follow-up is the user's own")
        try:
            uuid.UUID(str(run_id))
        except ValueError:
            raise LysError(AGENT_RUN_NOT_FOUND, "No such run to follow up") from None

        async with cls.app_manager.database.get_session() as session:
            agent_run = await session.get(cls.entity_class, str(run_id))
        if (
            agent_run is None
            or agent_run.user_id != connected_user.get("sub")
            or agent_run.purpose != definition.purpose
            or agent_run.client_id != client_id
        ):
            raise LysError(AGENT_RUN_NOT_FOUND, "No such run to follow up")
        if agent_run.status != AGENT_RUN_SUCCEEDED or agent_run.ended_at is None:
            raise LysError(AGENT_RUN_NOT_CONTINUABLE, f"Run {run_id} did not succeed")
        if datetime.now(UTC) - agent_run.ended_at > definition.continuation_ttl:
            raise LysError(AGENT_RUN_NOT_CONTINUABLE, f"Run {run_id} ended too long ago to be followed up")
        return AgentContinuation(
            run_id=agent_run.id, client_id=agent_run.client_id, tool_defaults=agent_run.tool_defaults,
            transcript=tuple(agent_run.transcript or ()),
        )

    # -------------------------------------------------------------------------
    # The run's tools
    # -------------------------------------------------------------------------

    @classmethod
    async def _tools_for(cls, definition: AgentDefinition, connected_user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        The tools of a run: the definition's webservices the user may call — the user's
        rights, read from the token, as for the chatbot —, plus exact arithmetic.

        The definition lists what the agent reads; a tool's audience says who may be offered it.
        The two must agree: a declared tool whose audience leaves the agent out is a definition
        error, raised, never a tool silently dropped from the run.

        Raises:
            ValueError: a declared webservice is not a tool (a misspelt name would silently
                shrink the agent), is a mutation (an agent reads, it never writes: what it
                reads may carry instructions, and a writing agent would act on them), or
                reserves its tool to other purposes.
        """
        for name in sorted(definition.webservices):
            tool = await AIToolService.get_tool(name)
            if tool is None:
                raise ValueError(f"Agent '{definition.purpose}' declares '{name}', which is not a tool")
            if tool.get("operation_type") != _QUERY_OPERATION:
                raise ValueError(f"Agent '{definition.purpose}' declares '{name}', which is not a query")
            if not AIToolService.admits(tool, definition.purpose):
                raise ValueError(
                    f"Agent '{definition.purpose}' declares '{name}', whose tool is reserved to {tool['consumers']}"
                )

        accessible = await AIToolService.get_accessible_tools(connected_user, consumer=definition.purpose)
        tools = [tool for tool in accessible if tool.get("webservice") in definition.webservices]
        return tools + [CALCULATE_TOOL]

    @classmethod
    async def _executor(
        cls, tools: List[Dict[str, Any]], access_token: str, tool_defaults: Optional[Dict[str, Any]],
        provenance: Provenance,
    ) -> GraphQLToolExecutor:
        """
        The run's executor: the API called with the user's token, never a service identity, and
        the caller's defaults pinned — they are the run's scope, not a starting point the model
        may roam from (a model left free invents a client id from another entity's). Its calculate
        reads where the run's figures come from (``provenance``, filled as the tools answer).
        """
        ai_config = parse_plugin_config(cls.app_manager.settings.get_plugin_config("ai"))
        executor = GraphQLToolExecutor(
            gateway_url=ai_config.executor.gateway_url,
            bearer_token=access_token,
            timeout=ai_config.executor.timeout,
            verify_ssl=ai_config.executor.verify_ssl,
            pin_ids=True,
            max_parallel_calls=ai_config.executor.max_parallel_calls,
        )
        # The defaults travel the way page params do for the chatbot: the executor injects them.
        page_context = PageContextModel(page_name="agent", params=tool_defaults) if tool_defaults else None
        await executor.initialize(tools=tools, page_context=page_context)
        for name in AGENT_PURE_TOOLS:
            executor.register_special_tool(name, build_calculate_handler(provenance))
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
            messages.extend(await cls._run_tools(tool_calls, executor, info, state))

        raise AIError("The agent wrote no analysis")  # unreachable: the last call refuses tools

    @classmethod
    async def _run_tools(
        cls, tool_calls: List[Dict[str, Any]], executor: GraphQLToolExecutor, info: Any, state: _RunState,
    ) -> List[Dict[str, Any]]:
        """
        Run the tool calls of one round together, and return their messages in the order they were asked.

        An agent's tools only read (a declared mutation is refused), each call is a request of its own
        under the user's token, and a failing call is already answered as an error the model reads: the
        calls of a round depend on nothing but the model's request, so they wait for one another only as
        long as the slowest — two readings of 40 s take 40 s, not 80 —, as many at once as the executor
        allows (``ToolExecutor.run_together``).
        """
        results: List[Optional[Dict[str, Any]]] = [None] * len(tool_calls)

        async def run(position: int, tool_call: Dict[str, Any]) -> None:
            results[position] = await cls._run_tool(tool_call, executor, info, state)

        await executor.run_together(
            [partial(run, position, tool_call) for position, tool_call in enumerate(tool_calls)])
        return results

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
        # Where its figures come from is kept for calculate, never sent to the model
        state.provenance.add(result)
        result = model_result(result)
        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return {"role": "tool", "tool_call_id": tool_call.get("id", ""), "content": content}

    @classmethod
    async def _report(
        cls, definition: AgentDefinition[ReportT], task: str, analysis: str, state: _RunState,
    ) -> ReportT:
        """
        Write the report in its schema, in one structured call on the definition's report endpoint.

        From the analysis (the default): the call reads the task and the analysis only — the tool
        history stays out of it, so no provider has to accept tool messages beside a response
        schema. From the readings (``report_source``): it reads the run's transcript, what the
        tools returned, and the report is kept in the transcript — it is what a follow-up, or a
        correction round, reads as the agent's answer.

        Raises:
            AIError: no endpoint of the chain produced a valid report.
        """
        ai_service = cls.app_manager.get_service("ai")
        endpoint = ai_service.get_endpoint(definition.report_endpoint).with_cache_key(state.id)
        from_readings = definition.report_source == AGENT_REPORT_FROM_READINGS
        if from_readings:
            # The instruction is the call's own, never kept in the transcript
            messages = state.transcript + [{"role": "user", "content": AGENT_REPORT_FROM_READINGS_INSTRUCTION}]
        else:
            messages = [
                {"role": "user", "content": task},
                {"role": "assistant", "content": analysis},
                {"role": "user", "content": AGENT_REPORT_INSTRUCTION},
            ]
        started = time.perf_counter()
        try:
            response = await ai_service.chat_json_with_metadata(messages, endpoint, definition.report_schema)
        except AIError as failure:
            state.count_call("report", _elapsed_ms(started), None, error=str(failure))
            raise
        state.provider, state.model = response.provider, response.model
        state.count_call("report", _elapsed_ms(started), response.usage)
        if from_readings:
            state.transcript.append({"role": "assistant", "content": response.data.model_dump_json()})
        return response.data

    @classmethod
    async def _check_report(
        cls, report_check: Optional[ReportCheck], report: Any, state: _RunState,
    ) -> Tuple[List[AnalysisIssue], bool]:
        """
        Run the caller's check on a report's fields and trace what it found on the call that wrote
        the report: the issues, and whether the check ran. As for an analysis, a check that cannot
        run leaves the report standing, flagged unchecked — never a failed run, and no correction.
        """
        if report_check is None:
            return [], True
        issues, checked = await cls._checked(report_check, report, state, "report")
        state.calls[-1]["issues"] = [f"{issue.location}: {issue.message}" for issue in issues]
        return issues, checked

    @staticmethod
    async def _checked(check: Any, subject: Any, state: _RunState, location: str) -> Tuple[List[AnalysisIssue], bool]:
        """
        Run a caller's check on what a run wrote (``location``: its analysis, its report).

        Returns:
            The issues it found and True; when the check itself could not run, the one issue saying
            so (AGENT_ANALYSIS_UNCHECKED) and False - what was written stands, the caller's to show.
        """
        try:
            return list(await check(subject)), True
        except Exception as failure:  # noqa: BLE001 - a check that cannot run never fails the run
            logger.error("Agent run %s: %s check failed: %s", state.id, location, failure)
            return [AnalysisIssue(location=location, message=AGENT_ANALYSIS_UNCHECKED)], False

    @classmethod
    async def _check(
        cls, definition: AgentDefinition, analysis_check: Optional[AnalysisCheck], analysis: str,
        state: _RunState,
    ) -> Tuple[List[AnalysisIssue], bool]:
        """
        Run the caller's check on an analysis — and, when the definition asks for it, the check of its
        figures against the run — and trace what they found on the call that wrote it: the issues, and
        whether the caller's check ran. A check that cannot run leaves the analysis standing, flagged
        unchecked — never a failed run, and no correction: nothing to correct.
        """
        issues: List[AnalysisIssue] = cls._unsourced(analysis, state) if definition.figures_check else []
        checked = True
        if analysis_check is not None:
            found, checked = await cls._checked(analysis_check, analysis, state, "analysis")
            issues = issues + found if checked else found
        if issues or analysis_check is not None:
            state.calls[-1]["issues"] = [f"{issue.location}: {issue.message}" for issue in issues]
        return issues, checked

    @staticmethod
    def _unsourced(analysis: str, state: _RunState) -> List[AnalysisIssue]:
        """
        The figures of an analysis found nowhere in the run (utils/sourced_figures.py): what the task and
        the tools gave it, its calculate steps included — never what the agent itself wrote.
        """
        sources = [str(message.get("content") or "") for message in state.transcript
                   if message.get("role") in ("user", "tool")]
        return [
            AnalysisIssue(location=f"« {figure.text} » ({context_of(analysis, figure)})",
                          message=AGENT_UNSOURCED_FIGURE)
            for figure in unsourced_figures(analysis, sources)
        ]

    # -------------------------------------------------------------------------
    # The trace, in transactions of its own
    # -------------------------------------------------------------------------

    @classmethod
    async def record(
        cls, purpose: str, user_id: str, client_id: Optional[str], task: str, calls: List[Dict[str, Any]],
        transcript: Optional[List[Dict[str, Any]]] = None, output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None, provider: Optional[str] = None,
    ) -> None:
        """
        Trace a specialist that runs no agent loop of its own - a single structured call, a loop
        of its own making - in the same table, so what a turn cost reads in one place.

        Written closed, at once (SUCCEEDED, or FAILED with ``error``), in its own transaction:
        shielded and bounded like ``_close_trace``, and logged, never raised, when the store
        does not take it - a trace never fails what it traces.

        Args:
            purpose: The specialist's AI endpoint purpose.
            user_id: The user it ran for.
            client_id: The tenant it was scoped to, if any.
            task: What it was asked.
            calls: Its model calls, each as ``traced_call`` writes them.
            transcript: Its messages, when worth keeping.
            output: What it answered.
            error: Why it failed.
            provider: The provider of its last call.
        """
        now = datetime.now(UTC)
        values = {
            "purpose": purpose, "user_id": user_id, "client_id": client_id, "task": task,
            "status": AGENT_RUN_FAILED if error else AGENT_RUN_SUCCEEDED, "transcript": transcript or [],
            "calls": calls, "output": output, "error": error, "provider": provider,
            "model": calls[-1]["model"] if calls else None, "ended_at": now, **call_totals(calls, 0),
        }
        try:
            with anyio.CancelScope(shield=True), anyio.fail_after(AGENT_TRACE_CLOSE_TIMEOUT):
                async with cls.app_manager.database.get_session() as session:
                    await cls.create(session, **values)
        except Exception as failure:  # noqa: BLE001 - the trace never fails what it traces
            logger.error("Trace of %s not written: %s", purpose, failure)

    @classmethod
    async def _open_trace(
        cls, definition: AgentDefinition, user_id: str, client_id: Optional[str], task: str,
        transcript: List[Dict[str, Any]], tool_defaults: Optional[Dict[str, Any]] = None,
        continued_from_id: Optional[str] = None,
    ) -> str:
        """Write the run, RUNNING, with its scope, in its own transaction, and return its id."""
        async with cls.app_manager.database.get_session() as session:
            agent_run = await cls.create(
                session, purpose=definition.purpose, user_id=user_id, client_id=client_id,
                tool_defaults=tool_defaults, continued_from_id=continued_from_id,
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


def _cleared(transcript) -> List[Dict[str, Any]]:
    """
    A run's transcript as a follow-up reads it: every message kept — the tasks, the calls, the
    analyses —, each tool result replaced by AGENT_CLEARED_TOOL_RESULT (its call id kept, so the
    history stays well-formed for the provider).
    """
    return [
        {**message, "content": AGENT_CLEARED_TOOL_RESULT} if message.get("role") == "tool" else dict(message)
        for message in transcript
    ]


def _correction(issues: List[AnalysisIssue], instruction: str = AGENT_CORRECTION_INSTRUCTION) -> str:
    """A correction round's message: the instruction, then each issue where it is."""
    return instruction + "\n" + "\n".join(f"- {issue.location} : {issue.message}" for issue in issues)
