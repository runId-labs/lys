"""
Unit tests for AIAgentService: an agent's tools, its loop, its report and its trace.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from lys.apps.ai.modules.agent.consts import (
    AGENT_FINAL_ROUND_INSTRUCTION,
    AGENT_RUN_FAILED,
    AGENT_RUN_SUCCEEDED,
)
from lys.apps.ai.modules.agent.models import AgentDefinition, AnalysisIssue
from lys.apps.ai.modules.agent.services import AIAgentService
from lys.apps.ai.utils.providers.abstracts import AIJsonResponse, AIResponse
from lys.apps.ai.utils.providers.exceptions import AIError
from lys.core.errors import LysError


class Report(BaseModel):
    verdict: str


TOOLS = {
    "read_plan": {"definition": {"function": {"name": "read_plan"}}, "operation_type": "query"},
    "read_texts": {"definition": {"function": {"name": "read_texts"}}, "operation_type": "query"},
    "delete_plan": {"definition": {"function": {"name": "delete_plan"}}, "operation_type": "mutation"},
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
            return_value=AIJsonResponse(data=report or Report(verdict="ok"), model="m", provider="p"),
        )
        self.ai_service.get_endpoint.return_value = MagicMock()
        self.executor = MagicMock()
        self.executor.initialize = AsyncMock()
        self.executor.execute = AsyncMock(
            side_effect=tool_result if isinstance(tool_result, Exception) else None,
            return_value=tool_result if tool_result is not None else {"rows": [1]},
        )
        self.accessible = _accessible(accessible)
        self.opened = None
        self.run_row = None

    async def run(self, definition, info=None, **kwargs):
        app_manager = MagicMock()
        app_manager.get_service.return_value = self.ai_service
        app_manager.settings.get_plugin_config.return_value = {"executor": {"gateway_url": "http://api"}}

        async def open_trace(definition, user_id, client_id, task, transcript):
            self.opened = {"purpose": definition.purpose, "user_id": user_id, "client_id": client_id, "task": task}
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
                  new=AsyncMock(return_value=self.accessible)),
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
    async def test_the_callers_defaults_reach_the_tools_as_page_params(self):
        harness = _Harness([_answer()])
        await harness.run(_definition(), tool_defaults={"clientId": "Q2xpZW50"})
        assert harness.executor.initialize.call_args.kwargs["page_context"].params == {"clientId": "Q2xpZW50"}


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
        assert (run.tokens_in, run.tokens_out, run.cache_read_tokens) == (150, 15, 40)
        assert [call["kind"] for call in run.calls] == ["loop", "loop", "report"]
        assert [call["tool_calls"] for call in run.calls] == [1, 0, 0]

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
        assert result.report is None and "rate limit" not in result.error
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


class TestDefinition:
    def test_a_definition_needs_an_endpoint_and_a_positive_budget(self):
        with pytest.raises(ValueError):
            AgentDefinition(purpose="", webservices=frozenset(), report_schema=Report)
        with pytest.raises(ValueError):
            AgentDefinition(purpose="p", webservices=frozenset(), report_schema=Report, max_iterations=0)
