"""
Unit tests for AIAgentService: an agent's tools, its loop, its report and its trace.
"""
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from lys.apps.ai.modules.agent.consts import (
    AGENT_CLEARED_TOOL_RESULT,
    AGENT_FINAL_ROUND_INSTRUCTION,
    AGENT_REPORT_CORRECTION_INSTRUCTION,
    AGENT_REPORT_FROM_READINGS,
    AGENT_REPORT_FROM_READINGS_INSTRUCTION,
    AGENT_RUN_FAILED,
    AGENT_RUN_SUCCEEDED,
)
from lys.apps.ai.modules.agent.models import AgentContinuation, AgentDefinition, AnalysisIssue
from lys.apps.ai.modules.agent.services import AIAgentService
from lys.apps.ai.modules.core.executors.abstracts import ToolExecutor
from lys.apps.ai.utils.providers.abstracts import AIJsonResponse, AIResponse
from lys.apps.ai.utils.providers.exceptions import AIError
from lys.core.errors import LysError


class Report(BaseModel):
    verdict: str


TOOLS = {
    "read_plan": {"definition": {"function": {"name": "read_plan"}}, "operation_type": "query"},
    "read_texts": {"definition": {"function": {"name": "read_texts"}}, "operation_type": "query"},
    "delete_plan": {"definition": {"function": {"name": "delete_plan"}}, "operation_type": "mutation"},
    "read_shared": {"definition": {"function": {"name": "read_shared"}}, "operation_type": "query",
                    "consumers": ["plan_review", "chatbot"]},
    "read_reserved": {"definition": {"function": {"name": "read_reserved"}}, "operation_type": "query",
                      "consumers": ["other_agent"]},
}


def _definition(webservices=("read_plan",), max_iterations=5):
    return AgentDefinition(
        purpose="plan_review", webservices=frozenset(webservices), report_schema=Report,
        max_iterations=max_iterations,
    )


def _info(token="token", user=None):
    return SimpleNamespace(context=SimpleNamespace(
        connected_user=user if user is not None else {"sub": "user-1"}, access_token=token,
    ))


def _accessible(names):
    return [{"webservice": name, **TOOLS[name]} for name in names]


def _tool_call(name, arguments=None, call_id="call-1"):
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments or {})}}


class _Harness:
    """AIAgentService wired to a fake model and executor; the trace's writes are recorded."""

    def __init__(self, responses, report=None, accessible=("read_plan",), tool_result=None):
        self.ai_service = MagicMock()
        self.ai_service.chat_with_purpose = AsyncMock(side_effect=responses)
        self.ai_service.chat_json_with_metadata = AsyncMock(
            side_effect=report if isinstance(report, Exception) else None,
            return_value=AIJsonResponse(
                data=report or Report(verdict="ok"), model="m", provider="p",
                usage={"prompt_tokens": 7, "completion_tokens": 3},
            ),
        )
        self.ai_service.get_endpoint.return_value = MagicMock()
        self.executor = MagicMock()
        self.executor.max_parallel_calls = 8
        self.executor.run_together = partial(ToolExecutor.run_together, self.executor)
        self.executor.initialize = AsyncMock()
        self.executor.execute = AsyncMock(
            side_effect=tool_result if isinstance(tool_result, Exception) else None,
            return_value=tool_result if tool_result is not None else {"rows": [1]},
        )
        self.accessible = _accessible(accessible)
        self.get_accessible_tools = AsyncMock(return_value=self.accessible)
        self.opened = None
        self.run_row = None

    async def run(self, definition, info=None, **kwargs):
        app_manager = MagicMock()
        app_manager.get_service.return_value = self.ai_service
        app_manager.settings.get_plugin_config.return_value = {"executor": {"gateway_url": "http://api"}}

        async def open_trace(definition, user_id, client_id, task, transcript, tool_defaults=None,
                             continued_from_id=None):
            self.opened = {"purpose": definition.purpose, "user_id": user_id, "client_id": client_id, "task": task}
            self.opened_scope = {"tool_defaults": tool_defaults, "continued_from_id": continued_from_id}
            return "run-1"

        async def close_trace(state, status, output, error):
            self.run_row = SimpleNamespace(
                status=status, output=output, error=error, transcript=list(state.transcript),
                calls=list(state.calls), provider=state.provider, model=state.model, **state.totals(),
            )

        with (
            patch.object(AIAgentService, "app_manager", app_manager),
            patch.object(AIAgentService, "_open_trace", side_effect=open_trace),
            patch.object(AIAgentService, "_close_trace", side_effect=close_trace),
            patch("lys.apps.ai.modules.agent.services.AIToolService.get_tool",
                  new=AsyncMock(side_effect=lambda name: TOOLS.get(name))),
            patch("lys.apps.ai.modules.agent.services.AIToolService.get_accessible_tools",
                  new=self.get_accessible_tools),
            patch(
                "lys.apps.ai.modules.agent.services.GraphQLToolExecutor", return_value=self.executor,
            ) as executor_class,
        ):
            self.executor_class = executor_class
            return await AIAgentService.run(definition, "Review the plan", info or _info(), **kwargs)


def _answer(content="Analysis: the plan holds.", usage=None):
    return AIResponse(content=content, usage=usage or {"prompt_tokens": 100, "completion_tokens": 10},
                      model="m", provider="p")


def _calls(*tool_calls):
    return AIResponse(content="", tool_calls=list(tool_calls),
                      usage={"prompt_tokens": 50, "completion_tokens": 5, "cache_read_tokens": 40},
                      model="m", provider="p")


class TestRights:
    """An agent reads with the user's token and rights, never more than declared."""

    @pytest.mark.asyncio
    async def test_a_run_without_the_users_token_is_refused(self):
        with pytest.raises(LysError, match="AGENT_REQUIRES_USER_TOKEN"):
            await _Harness([_answer()]).run(_definition(), info=_info(token=None))

    @pytest.mark.asyncio
    async def test_the_tools_are_the_declared_ones_the_user_may_call_plus_arithmetic(self):
        harness = _Harness([_answer()], accessible=("read_plan",))
        await harness.run(_definition(webservices=("read_plan", "read_texts")))
        tools = harness.executor.initialize.call_args.kwargs["tools"]
        names = [(tool.get("definition") or tool)["function"]["name"] for tool in tools]
        assert names == ["read_plan", "calculate"]

    @pytest.mark.asyncio
    async def test_a_declared_name_that_is_no_tool_is_refused(self):
        with pytest.raises(ValueError, match="not a tool"):
            await _Harness([_answer()]).run(_definition(webservices=("read_plna",)))

    @pytest.mark.asyncio
    async def test_a_declared_mutation_is_refused(self):
        with pytest.raises(ValueError, match="not a query"):
            await _Harness([_answer()]).run(_definition(webservices=("read_plan", "delete_plan")))

    @pytest.mark.asyncio
    async def test_a_declared_tool_reserved_to_others_is_refused(self):
        """The definition and the tool's audience must agree: no tool silently dropped from the run."""
        with pytest.raises(ValueError, match="reserved to"):
            await _Harness([_answer()]).run(_definition(webservices=("read_plan", "read_reserved")))

    @pytest.mark.asyncio
    async def test_the_tools_are_read_as_the_agents_own(self):
        """A tool whose audience names the agent is its, and the agent asks for its own audience."""
        harness = _Harness([_answer()], accessible=("read_plan", "read_shared"))
        await harness.run(_definition(webservices=("read_plan", "read_shared")))
        assert harness.get_accessible_tools.await_args.kwargs["consumer"] == "plan_review"
        tools = harness.executor.initialize.call_args.kwargs["tools"]
        names = [(tool.get("definition") or tool)["function"]["name"] for tool in tools]
        assert names == ["read_plan", "read_shared", "calculate"]

    @pytest.mark.asyncio
    async def test_the_callers_defaults_reach_the_tools_as_page_params(self):
        harness = _Harness([_answer()])
        await harness.run(_definition(), tool_defaults={"clientId": "Q2xpZW50"})
        assert harness.executor.initialize.call_args.kwargs["page_context"].params == {"clientId": "Q2xpZW50"}


class TestParallelTools:
    """The tool calls of one round run together: the round waits for the slowest, not for their sum."""

    @pytest.mark.asyncio
    async def test_a_rounds_calls_run_together_and_answer_in_the_order_asked(self):
        import anyio

        harness = _Harness([_calls(_tool_call("read_plan", {"n": 1}, "call-1"),
                                   _tool_call("read_texts", {"n": 2}, "call-2")), _answer()],
                           accessible=("read_plan", "read_texts"))
        running, overlap = 0, []

        async def execute(tool_name, arguments, context):
            nonlocal running
            running += 1
            overlap.append(running)
            # The first asked answers last: the order kept is the request's, not the arrival's
            await anyio.sleep(0.05 if arguments["n"] == 1 else 0.01)
            running -= 1
            return {"tool": tool_name}

        harness.executor.execute = AsyncMock(side_effect=execute)
        await harness.run(_definition(webservices=("read_plan", "read_texts")))

        assert max(overlap) == 2
        tools = [message for message in harness.run_row.transcript if message["role"] == "tool"]
        assert [message["tool_call_id"] for message in tools] == ["call-1", "call-2"]
        assert json.loads(tools[0]["content"]) == {"tool": "read_plan"}
        assert harness.run_row.tool_calls == 2

    @pytest.mark.asyncio
    async def test_a_failing_call_fails_alone(self):
        harness = _Harness([_calls(_tool_call("read_plan", {"n": 1}, "call-1"),
                                   _tool_call("read_texts", {"n": 2}, "call-2")), _answer()],
                           accessible=("read_plan", "read_texts"))

        async def execute(tool_name, arguments, context):
            if arguments["n"] == 1:
                raise RuntimeError("down")
            return {"rows": [2]}

        harness.executor.execute = AsyncMock(side_effect=execute)
        result = await harness.run(_definition(webservices=("read_plan", "read_texts")))

        assert result.error is None
        tools = [message for message in harness.run_row.transcript if message["role"] == "tool"]
        assert "failed" in tools[0]["content"] and json.loads(tools[1]["content"]) == {"rows": [2]}


class TestScopePinning:
    """The caller's defaults are the run's scope: pinned over whatever id the model passes."""

    @pytest.mark.asyncio
    async def test_the_run_pins_the_callers_ids(self):
        harness = _Harness([_answer()])
        await harness.run(_definition(), tool_defaults={"clientId": "Q2xpZW50"})
        assert harness.executor_class.call_args.kwargs["pin_ids"] is True

    def test_an_executor_pins_ids_on_service_auth_or_when_asked(self):
        from lys.apps.ai.modules.core.executors.graphql import GraphQLToolExecutor

        user = GraphQLToolExecutor(gateway_url="http://api", bearer_token="t")
        pinned = GraphQLToolExecutor(gateway_url="http://api", bearer_token="t", pin_ids=True)
        service = GraphQLToolExecutor(gateway_url="http://api", secret_key="k", service_name="s")
        assert (user._pins_ids, pinned._pins_ids, service._pins_ids) == (False, True, True)


class TestLoop:
    """The model reads through its tools, then writes its analysis, turned into the report."""

    @pytest.mark.asyncio
    async def test_a_run_reads_then_reports(self):
        harness = _Harness([_calls(_tool_call("read_plan")), _answer()], report=Report(verdict="fragile"))
        result = await harness.run(_definition())

        assert result.report == Report(verdict="fragile") and result.error is None
        run = harness.run_row
        assert (run.status, run.output) == (AGENT_RUN_SUCCEEDED, {"verdict": "fragile"})
        assert [message["role"] for message in run.transcript] == ["user", "assistant", "tool", "assistant"]
        assert (run.model_calls, run.tool_calls) == (3, 1)  # two loop calls and the report
        # The report's own tokens are counted with the loop's
        assert (run.tokens_in, run.tokens_out, run.cache_read_tokens) == (157, 18, 40)
        assert [call["kind"] for call in run.calls] == ["loop", "loop", "report"]
        assert (run.calls[-1]["tokens_in"], run.calls[-1]["tokens_out"]) == (7, 3)
        assert [call["tool_calls"] for call in run.calls] == [1, 0, 0]

    @pytest.mark.asyncio
    async def test_a_run_returns_its_analysis_with_the_report(self):
        harness = _Harness([_calls(_tool_call("read_plan")), _answer("The analysis.")])
        result = await harness.run(_definition())
        assert result.analysis == "The analysis." and result.succeeded

    @pytest.mark.asyncio
    async def test_a_definition_without_a_report_returns_the_analysis_as_written(self):
        """A report is the caller's choice: none asked, no formatting call, the analysis is the result."""
        harness = _Harness([_calls(_tool_call("read_plan")), _answer("The analysis.")])
        definition = AgentDefinition(purpose="plan_review", webservices=frozenset({"read_plan"}))
        result = await harness.run(definition)

        assert (result.analysis, result.report, result.error) == ("The analysis.", None, None)
        assert result.succeeded
        harness.ai_service.chat_json_with_metadata.assert_not_awaited()
        run = harness.run_row
        assert (run.status, run.output) == (AGENT_RUN_SUCCEEDED, None)
        assert [call["kind"] for call in run.calls] == ["loop", "loop"]
        assert run.transcript[-1] == {"role": "assistant", "content": "The analysis."}

    @pytest.mark.asyncio
    async def test_the_report_reads_the_task_and_the_analysis_only(self):
        harness = _Harness([_calls(_tool_call("read_plan")), _answer("The analysis.")])
        await harness.run(_definition())
        messages = harness.ai_service.chat_json_with_metadata.call_args.args[0]
        assert [message["role"] for message in messages] == ["user", "assistant", "user"]
        assert messages[1]["content"] == "The analysis."

    @pytest.mark.asyncio
    async def test_the_last_call_refuses_tools_and_asks_for_the_analysis(self):
        harness = _Harness([_calls(_tool_call("read_plan")), _answer()])
        await harness.run(_definition(max_iterations=2))
        last = harness.ai_service.chat_with_purpose.call_args_list[-1]
        assert last.kwargs["tool_calls_allowed"] is False
        assert last.args[0][-1] == {"role": "system", "content": AGENT_FINAL_ROUND_INSTRUCTION}
        # The instruction is the call's own, never kept in the trace
        assert all(message.get("content") != AGENT_FINAL_ROUND_INSTRUCTION for message in harness.run_row.transcript)

    @pytest.mark.asyncio
    async def test_a_failing_tool_is_the_models_to_read(self):
        harness = _Harness([_calls(_tool_call("read_plan")), _answer()], tool_result=RuntimeError("boom"))
        result = await harness.run(_definition())
        tool_message = harness.run_row.transcript[2]
        assert json.loads(tool_message["content"]) == {"error": "Tool 'read_plan' failed to execute."}
        assert result.report is not None

    @pytest.mark.asyncio
    async def test_arithmetic_runs_locally(self):
        harness = _Harness([_answer()])
        await harness.run(_definition())
        registered = [call.args[0] for call in harness.executor.register_special_tool.call_args_list]
        assert registered == ["calculate"]


class TestFailure:
    """A failed run is a result the caller hands on, and a trace kept FAILED."""

    @pytest.mark.asyncio
    async def test_a_provider_failure_fails_the_run_without_leaking_it(self):
        harness = _Harness([AIError("Mistral rate limit exceeded")])
        result = await harness.run(_definition())
        assert result.report is None and result.analysis is None and not result.succeeded
        assert "rate limit" not in result.error
        assert (harness.run_row.status, harness.run_row.error) == (AGENT_RUN_FAILED, "Mistral rate limit exceeded")

    @pytest.mark.asyncio
    async def test_a_report_that_does_not_validate_fails_the_run(self):
        harness = _Harness([_answer()], report=AIError("schema mismatch"))
        result = await harness.run(_definition())
        assert result.report is None and harness.run_row.status == AGENT_RUN_FAILED

    @pytest.mark.asyncio
    async def test_an_empty_analysis_fails_the_run(self):
        harness = _Harness([_answer(content="  ")])
        result = await harness.run(_definition())
        assert result.report is None and harness.run_row.status == AGENT_RUN_FAILED


class TestTrace:
    """The trace lives in its own transactions and outlives any end of the run."""

    @pytest.mark.asyncio
    async def test_an_unexpected_error_is_traced_then_raised(self):
        harness = _Harness([RuntimeError("bug")])
        with pytest.raises(RuntimeError):
            await harness.run(_definition())
        assert (harness.run_row.status, harness.run_row.error) == (AGENT_RUN_FAILED, "RuntimeError: bug")

    @pytest.mark.asyncio
    async def test_the_run_is_opened_with_its_scope(self):
        harness = _Harness([_answer()])
        await harness.run(_definition(), client_id="client-1")
        assert harness.opened == {
            "purpose": "plan_review", "user_id": "user-1", "client_id": "client-1", "task": "Review the plan",
        }

    @pytest.mark.asyncio
    async def test_the_report_is_formatted_on_the_report_endpoint(self):
        harness = _Harness([_answer()])
        definition = AgentDefinition(
            purpose="plan_review", webservices=frozenset({"read_plan"}), report_schema=Report,
            report_purpose="plan_review_report",
        )
        await harness.run(definition)
        harness.ai_service.get_endpoint.assert_called_once_with("plan_review_report")

    @pytest.mark.asyncio
    async def test_closing_writes_in_its_own_session_and_never_raises(self):
        from contextlib import asynccontextmanager
        from lys.apps.ai.modules.agent.services import _RunState

        sessions = []

        @asynccontextmanager
        async def get_session():
            session = MagicMock(execute=AsyncMock(side_effect=RuntimeError("store down")))
            sessions.append(session)
            yield session

        app_manager = MagicMock()
        app_manager.database.get_session = get_session
        # Entities are mapped at app boot only: the statement itself is not what this test checks
        with (
            patch.object(AIAgentService, "app_manager", app_manager),
            patch("lys.apps.ai.modules.agent.services.update", MagicMock()),
        ):
            await AIAgentService._close_trace(_RunState(id="run-1", transcript=[]), AGENT_RUN_FAILED, None, "e")
        assert len(sessions) == 1 and sessions[0].execute.await_count == 1


class TestAnalysisCheck:
    """A check reads the analysis; its issues go back to the agent once, before formatting."""

    @pytest.mark.asyncio
    async def test_an_analysis_that_holds_opens_no_correction(self):
        harness = _Harness([_answer("Analysis.")])
        check = AsyncMock(return_value=[])
        result = await harness.run(_definition(), analysis_check=check)
        check.assert_awaited_once_with("Analysis.")
        assert result.issues == () and harness.ai_service.chat_with_purpose.await_count == 1
        assert harness.run_row.calls[0]["issues"] == []

    @pytest.mark.asyncio
    async def test_issues_open_one_correction_round_then_one_report(self):
        issue = AnalysisIssue(location="« Hypothèses » E35 = 25 %", message="E35 holds 'Régime'")
        harness = _Harness([_answer("First."), _calls(_tool_call("read_plan")), _answer("Corrected.")])
        check = AsyncMock(side_effect=[[issue], []])
        result = await harness.run(_definition(), analysis_check=check)

        assert result.issues == () and [call.args[0] for call in check.await_args_list] == ["First.", "Corrected."]
        correction = harness.run_row.transcript[2]
        assert correction["role"] == "user" and "E35 holds 'Régime'" in correction["content"]
        assert [call["kind"] for call in harness.run_row.calls] == ["loop", "revision", "revision", "report"]
        # One formatting only, of the corrected analysis
        [report_call] = harness.ai_service.chat_json_with_metadata.call_args_list
        assert report_call.args[0][1]["content"] == "Corrected."

    @pytest.mark.asyncio
    async def test_issues_left_after_the_correction_are_returned(self):
        issue = AnalysisIssue(location="citation", message="still wrong")
        harness = _Harness([_answer("First."), _answer("Second.")])
        result = await harness.run(_definition(), analysis_check=AsyncMock(return_value=[issue]))
        assert result.report is not None and result.issues == (issue,)
        assert result.analysis == "Second."  # the corrected analysis, not the first one
        assert harness.run_row.status == AGENT_RUN_SUCCEEDED

    @pytest.mark.asyncio
    async def test_a_check_that_cannot_run_leaves_the_analysis_unchecked_without_correction(self):
        harness = _Harness([_answer("First."), _answer("Second.")])
        result = await harness.run(_definition(), analysis_check=AsyncMock(side_effect=RuntimeError("api down")))
        assert result.report is not None
        assert [issue.location for issue in result.issues] == ["analysis"]
        assert harness.ai_service.chat_with_purpose.await_count == 1  # nothing to correct

    @pytest.mark.asyncio
    async def test_a_call_that_fails_is_traced_with_its_error(self):
        harness = _Harness([_calls(_tool_call("read_plan")), AIError("Request timed out after 180s")])
        await harness.run(_definition())
        assert harness.run_row.calls[-1]["error"] == "Request timed out after 180s"
        assert [call["kind"] for call in harness.run_row.calls] == ["loop", "loop"]


def _from_readings(max_iterations=5):
    return AgentDefinition(
        purpose="plan_review", webservices=frozenset({"read_plan"}), report_schema=Report,
        report_source=AGENT_REPORT_FROM_READINGS, max_iterations=max_iterations,
    )


class TestReportFromReadings:
    """The report written from what the tools returned, and checked field by field."""

    @pytest.mark.asyncio
    async def test_the_report_reads_the_transcript_on_the_agents_own_endpoint(self):
        harness = _Harness([_calls(_tool_call("read_plan")), _answer("Read.")], report=Report(verdict="fragile"))
        result = await harness.run(_from_readings())

        messages = harness.ai_service.chat_json_with_metadata.call_args.args[0]
        assert [message["role"] for message in messages] == ["user", "assistant", "tool", "assistant", "user"]
        assert messages[-1]["content"] == AGENT_REPORT_FROM_READINGS_INSTRUCTION
        harness.ai_service.get_endpoint.assert_called_with("plan_review")
        assert result.report == Report(verdict="fragile")

    @pytest.mark.asyncio
    async def test_the_report_is_kept_in_the_transcript_and_its_instruction_is_not(self):
        """What a follow-up reads as the agent's answer is the report, never the call's own instruction."""
        harness = _Harness([_answer("Read.")], report=Report(verdict="fragile"))
        await harness.run(_from_readings())
        transcript = harness.run_row.transcript
        assert transcript[-1] == {"role": "assistant", "content": Report(verdict="fragile").model_dump_json()}
        assert all(message["content"] != AGENT_REPORT_FROM_READINGS_INSTRUCTION for message in transcript)

    @pytest.mark.asyncio
    async def test_a_report_that_holds_opens_no_correction(self):
        harness = _Harness([_answer("Read.")])
        check = AsyncMock(return_value=[])
        result = await harness.run(_from_readings(), report_check=check)
        check.assert_awaited_once_with(Report(verdict="ok"))
        assert result.issues == () and [call["kind"] for call in harness.run_row.calls] == ["loop", "report"]

    @pytest.mark.asyncio
    async def test_issues_in_the_reports_fields_open_one_correction_then_the_report_again(self):
        issue = AnalysisIssue(location="figures[0]", message="the cell holds another value")
        harness = _Harness([_answer("Read."), _calls(_tool_call("read_plan")), _answer("Read again.")])
        harness.ai_service.chat_json_with_metadata.side_effect = [
            AIJsonResponse(data=Report(verdict="wrong"), model="m", provider="p"),
            AIJsonResponse(data=Report(verdict="right"), model="m", provider="p"),
        ]
        check = AsyncMock(side_effect=[[issue], []])
        result = await harness.run(_from_readings(), report_check=check)

        assert result.report == Report(verdict="right") and result.issues == ()
        run = harness.run_row
        assert [call["kind"] for call in run.calls] == ["loop", "report", "revision", "revision", "report"]
        assert run.calls[1]["issues"] == ["figures[0]: the cell holds another value"]
        correction = next(m for m in run.transcript if m["role"] == "user" and "figures[0]" in m["content"])
        assert correction["content"].startswith(AGENT_REPORT_CORRECTION_INSTRUCTION)
        assert run.output == {"verdict": "right"}

    @pytest.mark.asyncio
    async def test_issues_left_in_the_report_are_returned_after_the_analysis_ones(self):
        analysis_issue = AnalysisIssue(location="citation", message="still wrong")
        report_issue = AnalysisIssue(location="figures[0]", message="still wrong")
        harness = _Harness([_answer("First."), _answer("Second."), _answer("Third.")])
        result = await harness.run(
            _definition(), analysis_check=AsyncMock(return_value=[analysis_issue]),
            report_check=AsyncMock(return_value=[report_issue]),
        )
        assert result.issues == (analysis_issue, report_issue) and result.succeeded

    @pytest.mark.asyncio
    async def test_a_report_check_that_cannot_run_leaves_the_report_unchecked_without_correction(self):
        harness = _Harness([_answer("Read.")])
        result = await harness.run(_from_readings(), report_check=AsyncMock(side_effect=RuntimeError("down")))
        assert [issue.location for issue in result.issues] == ["report"]
        assert [call["kind"] for call in harness.run_row.calls] == ["loop", "report"]

    @pytest.mark.parametrize("fields", [
        {"report_source": "elsewhere", "report_schema": Report},
        {"report_source": AGENT_REPORT_FROM_READINGS},
        {"report_source": AGENT_REPORT_FROM_READINGS, "report_schema": Report, "report_purpose": "p_report"},
    ])
    def test_a_report_from_the_readings_is_the_agents_own_and_needs_a_schema(self, fields):
        with pytest.raises(ValueError):
            AgentDefinition(purpose="p", webservices=frozenset(), **fields)


class TestDefinition:
    def test_a_report_endpoint_needs_a_report_to_format(self):
        with pytest.raises(ValueError, match="report_schema"):
            AgentDefinition(purpose="p", webservices=frozenset(), report_purpose="p_report")

    def test_a_definition_needs_an_endpoint_and_a_positive_budget(self):
        with pytest.raises(ValueError):
            AgentDefinition(purpose="", webservices=frozenset(), report_schema=Report)
        with pytest.raises(ValueError):
            AgentDefinition(purpose="p", webservices=frozenset(), report_schema=Report, max_iterations=0)


RUN_ID = "0b3c5f4e-8d2a-4c1e-9f6b-2a7d1e5c9b30"

HISTORY = (
    {"role": "user", "content": "Review the plan"},
    {"role": "assistant", "content": "", "tool_calls": [_tool_call("read_plan")]},
    {"role": "tool", "tool_call_id": "call-1", "content": json.dumps({"rows": ["a" * 1000]})},
    {"role": "assistant", "content": "Analysis: the plan holds."},
)


def _continuation(client_id="client-1", tool_defaults=None):
    return AgentContinuation(
        run_id=RUN_ID, client_id=client_id, tool_defaults=tool_defaults or {"clientId": "Q2xpZW50"},
        transcript=HISTORY,
    )


class TestFollowUp:
    """A follow-up is a run of its own, on its run's scope, reading its transcript with the results cleared."""

    @pytest.mark.asyncio
    async def test_the_follow_up_reads_the_run_cleared_then_its_task(self):
        harness = _Harness([_answer()])
        await harness.run(_definition(), continuation=_continuation())
        sent = harness.ai_service.chat_with_purpose.await_args_list[0].args[0]
        assert [message["role"] for message in sent] == ["user", "assistant", "tool", "assistant", "user"]
        assert sent[2] == {"role": "tool", "tool_call_id": "call-1", "content": AGENT_CLEARED_TOOL_RESULT}
        assert sent[1]["tool_calls"] == HISTORY[1]["tool_calls"] and sent[3] == HISTORY[3]
        assert sent[-1] == {"role": "user", "content": "Review the plan"}

    @pytest.mark.asyncio
    async def test_the_run_followed_up_is_left_as_it_was(self):
        await _Harness([_answer()]).run(_definition(), continuation=_continuation())
        assert HISTORY[2]["content"] != AGENT_CLEARED_TOOL_RESULT

    @pytest.mark.asyncio
    async def test_the_follow_up_runs_on_its_runs_scope_and_points_at_it(self):
        harness = _Harness([_answer()])
        await harness.run(_definition(), continuation=_continuation(tool_defaults={"clientId": "Q2xpZW50"}))
        assert harness.executor.initialize.call_args.kwargs["page_context"].params == {"clientId": "Q2xpZW50"}
        assert harness.opened["client_id"] == "client-1"
        assert harness.opened_scope == {"tool_defaults": {"clientId": "Q2xpZW50"}, "continued_from_id": RUN_ID}

    @pytest.mark.parametrize("scope", [{"client_id": "client-2"}, {"tool_defaults": {"clientId": "other"}}])
    @pytest.mark.asyncio
    async def test_a_follow_up_with_a_scope_of_the_callers_is_refused(self, scope):
        with pytest.raises(ValueError, match="scope of the run it continues"):
            await _Harness([_answer()]).run(_definition(), continuation=_continuation(), **scope)

    @pytest.mark.asyncio
    async def test_a_new_run_keeps_its_scope_for_a_follow_up(self):
        harness = _Harness([_answer()])
        await harness.run(_definition(), client_id="client-1", tool_defaults={"clientId": "Q2xpZW50"})
        assert harness.opened_scope == {"tool_defaults": {"clientId": "Q2xpZW50"}, "continued_from_id": None}


def _stored_run(**overrides):
    values = {
        "id": RUN_ID, "user_id": "user-1", "purpose": "plan_review", "client_id": "client-1",
        "status": AGENT_RUN_SUCCEEDED, "ended_at": datetime.now(UTC) - timedelta(hours=1),
        "tool_defaults": {"clientId": "Q2xpZW50"}, "transcript": list(HISTORY),
    }
    return SimpleNamespace(**{**values, **overrides})


async def _continue(stored, run_id=RUN_ID, client_id="client-1", info=None, definition=None):
    session = MagicMock(get=AsyncMock(return_value=stored))

    @asynccontextmanager
    async def get_session():
        yield session

    app_manager = MagicMock()
    app_manager.database.get_session = get_session
    with patch.object(AIAgentService, "app_manager", app_manager):
        return await AIAgentService.continuation(definition or _definition(), run_id, info or _info(), client_id)


class TestContinuation:
    """Only the caller's own run, of the same agent and client, succeeded and recent, is followed up."""

    @pytest.mark.asyncio
    async def test_the_callers_run_is_returned_with_its_scope_and_transcript(self):
        continuation = await _continue(_stored_run())
        assert continuation == AgentContinuation(
            run_id=RUN_ID, client_id="client-1", tool_defaults={"clientId": "Q2xpZW50"}, transcript=HISTORY,
        )

    @pytest.mark.parametrize("stored, run_id, client_id", [
        (None, RUN_ID, "client-1"),
        (_stored_run(), "not-a-uuid", "client-1"),
        (_stored_run(user_id="user-2"), RUN_ID, "client-1"),
        (_stored_run(purpose="other_agent"), RUN_ID, "client-1"),
        (_stored_run(), RUN_ID, "client-2"),
        (_stored_run(), RUN_ID, None),
    ])
    @pytest.mark.asyncio
    async def test_a_run_not_the_callers_to_continue_is_not_found(self, stored, run_id, client_id):
        with pytest.raises(LysError, match="AGENT_RUN_NOT_FOUND"):
            await _continue(stored, run_id=run_id, client_id=client_id)

    @pytest.mark.parametrize("stored", [
        _stored_run(status=AGENT_RUN_FAILED),
        _stored_run(status="RUNNING", ended_at=None),
        _stored_run(ended_at=datetime.now(UTC) - timedelta(hours=25)),
    ])
    @pytest.mark.asyncio
    async def test_a_run_failed_running_or_too_old_is_not_continuable(self, stored):
        with pytest.raises(LysError, match="AGENT_RUN_NOT_CONTINUABLE"):
            await _continue(stored)

    @pytest.mark.asyncio
    async def test_the_definition_sets_how_long_a_run_may_be_followed_up(self):
        definition = AgentDefinition(
            purpose="plan_review", webservices=frozenset({"read_plan"}), report_schema=Report,
            continuation_ttl=timedelta(hours=2),
        )
        with pytest.raises(LysError, match="AGENT_RUN_NOT_CONTINUABLE"):
            await _continue(_stored_run(ended_at=datetime.now(UTC) - timedelta(hours=3)), definition=definition)

    @pytest.mark.asyncio
    async def test_a_follow_up_needs_the_connected_user(self):
        with pytest.raises(LysError, match="AGENT_REQUIRES_USER_TOKEN"):
            await _continue(_stored_run(), info=_info(user={}))

    def test_a_continuation_ttl_must_be_positive(self):
        with pytest.raises(ValueError, match="continuation_ttl"):
            AgentDefinition(
                purpose="plan_review", webservices=frozenset({"read_plan"}), report_schema=Report,
                continuation_ttl=timedelta(0),
            )


class TestRunProvenance:
    """An agent's tools state where their figures come from: kept for its calculate, never sent to the model."""

    @pytest.mark.asyncio
    async def test_a_tool_result_feeds_the_provenance_and_reaches_the_model_without_it(self):
        from lys.apps.ai.modules.agent.services import _RunState
        from lys.apps.ai.utils.calculator import build_calculate_handler
        from lys.apps.ai.utils.provenance import PROVENANCE_KEY, figure

        state = _RunState(id="run-1", transcript=[])
        executor = MagicMock(execute=AsyncMock(return_value={"content": "table", PROVENANCE_KEY: [
            figure(1250000, "loaded_cost", "loaded cost", "ledger", "EUR"),
            figure(1000000, "gross_payroll", "gross payroll", "payroll", "EUR"),
        ]}))
        message = await AIAgentService._run_tool(
            {"id": "c1", "function": {"name": "reading", "arguments": "{}"}}, executor, MagicMock(), state)

        assert json.loads(message["content"]) == {"content": "table"}
        answer = build_calculate_handler(state.provenance)(
            {"steps": [{"name": "rate", "expression": "(1250000 - 1000000) / 1000000"}]}, {})
        assert "ledger" in answer["warnings"][0] and "payroll" in answer["warnings"][0]


class TestRecord:
    """A specialist without an agent loop is traced in the same table, closed at once, never raising."""

    @staticmethod
    async def _record(create, **overrides):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def get_session():
            yield MagicMock()

        app_manager = MagicMock()
        app_manager.database.get_session = get_session
        from lys.apps.ai.utils.tracing import traced_call
        values = {
            "calls": [traced_call("draft", 40, {"prompt_tokens": 10, "completion_tokens": 5}, "flash", 1),
                      traced_call("draft", 60, {"prompt_tokens": 20, "cache_read_tokens": 900}, "flash")],
            "output": {"note": "done"}, "provider": "mistral", **overrides,
        }
        with patch.object(AIAgentService, "app_manager", app_manager), patch.object(AIAgentService, "create", create):
            await AIAgentService.record("whiteboard_drafting", "user-1", "client-1", "Draw A", **values)

    @pytest.mark.asyncio
    async def test_a_run_is_written_closed_with_its_calls_added_up(self):
        create = AsyncMock()
        await self._record(create)
        row = create.await_args.kwargs
        assert row["status"] == AGENT_RUN_SUCCEEDED and row["model"] == "flash" and row["ended_at"] is not None
        assert (row["model_calls"], row["latency_ms"], row["tokens_in"], row["tokens_out"]) == (2, 100, 30, 5)
        assert row["cache_read_tokens"] == 900 and row["cache_write_tokens"] is None

    @pytest.mark.asyncio
    async def test_a_failure_is_traced_failed_and_a_store_down_never_raises(self):
        create = AsyncMock(side_effect=RuntimeError("store down"))
        await self._record(create, error="provider down", output=None)
        assert create.await_args.kwargs["status"] == AGENT_RUN_FAILED
