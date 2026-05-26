"""
Unit tests for the LLM message sanitizer.

Covers the contract enforced by `sanitize_llm_messages`: provider-agnostic
guarantees that the resulting message list satisfies Mistral / OpenAI /
Anthropic ordering rules.
"""

import json

from lys.apps.ai.utils.message_sanitizer import sanitize_llm_messages


class TestSystemPositioning:
    def test_empty_list_passes_through(self):
        assert sanitize_llm_messages([]) == []

    def test_single_system_at_index_zero_unchanged(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
        ]
        assert sanitize_llm_messages(messages) == messages

    def test_duplicate_system_keeps_only_first(self):
        messages = [
            {"role": "system", "content": "sys1"},
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "sys2"},
        ]
        result = sanitize_llm_messages(messages)
        assert [m["role"] for m in result] == ["system", "user"]
        assert result[0]["content"] == "sys1"

    def test_system_not_first_is_moved_to_index_zero(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "sys"},
        ]
        result = sanitize_llm_messages(messages)
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"


class TestToolReattachment:
    def test_tool_after_system_is_reattached_after_assistant(self):
        # Reproduces the Mistral "Unexpected role 'tool' after role 'system'" bug:
        # DB returns rows in non-deterministic order, placing tool right after system.
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "tool", "tool_call_id": "call_1", "content": '{"result": "ok"}'},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "f", "arguments": "{}"}},
            ]},
            {"role": "assistant", "content": "done"},
        ]
        result = sanitize_llm_messages(messages)
        roles = [m["role"] for m in result]
        assert roles == ["system", "user", "assistant", "tool", "assistant"]
        # tool must follow its assistant parent
        assert result[3]["tool_call_id"] == "call_1"

    def test_orphan_tool_is_dropped(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "tool", "tool_call_id": "ghost", "content": '{"x": 1}'},
            {"role": "assistant", "content": "ok"},
        ]
        result = sanitize_llm_messages(messages)
        assert [m["role"] for m in result] == ["system", "user", "assistant"]

    def test_unmatched_assistant_tool_call_gets_synthetic_response(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "call_X", "type": "function",
                 "function": {"name": "f", "arguments": "{}"}},
            ]},
            # no tool response for call_X — e.g. exception during tool execution
        ]
        result = sanitize_llm_messages(messages)
        assert [m["role"] for m in result] == ["user", "assistant", "tool"]
        assert result[2]["tool_call_id"] == "call_X"
        assert "interrupted" in json.loads(result[2]["content"])["error"]

    def test_multiple_parallel_tool_calls_are_all_paired(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "a", "type": "function", "function": {"name": "f", "arguments": "{}"}},
                {"id": "b", "type": "function", "function": {"name": "g", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "a", "content": "ra"},
            {"role": "tool", "tool_call_id": "b", "content": "rb"},
        ]
        result = sanitize_llm_messages(messages)
        assert [m["role"] for m in result] == ["user", "assistant", "tool", "tool"]
        # Order matches assistant.tool_calls[] order
        assert result[2]["tool_call_id"] == "a"
        assert result[3]["tool_call_id"] == "b"

    def test_shuffled_history_with_two_turns_is_repaired(self):
        # Simulates DB returning all rows with same created_at in a random order
        # spanning two assistant→tool turns. The sanitizer must regroup each
        # assistant with its tools.
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "tool", "tool_call_id": "t2", "content": "r2"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "t1", "type": "function", "function": {"name": "f", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "t1", "content": "r1"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "t2", "type": "function", "function": {"name": "g", "arguments": "{}"}},
            ]},
            {"role": "assistant", "content": "final"},
        ]
        result = sanitize_llm_messages(messages)
        roles = [m["role"] for m in result]
        assert roles == [
            "system", "user",
            "assistant", "tool",   # turn 1
            "assistant", "tool",   # turn 2
            "assistant",           # final
        ]
        assert result[3]["tool_call_id"] == "t1"
        assert result[5]["tool_call_id"] == "t2"


class TestPreservation:
    def test_assistant_without_tool_calls_unchanged(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "again"},
        ]
        assert sanitize_llm_messages(messages) == messages

    def test_tool_calls_without_id_are_skipped_without_crashing(self):
        # Defensive: if a tool_call lacks an id, we don't try to pair it.
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"type": "function", "function": {"name": "f", "arguments": "{}"}},
            ]},
        ]
        result = sanitize_llm_messages(messages)
        assert [m["role"] for m in result] == ["user", "assistant"]