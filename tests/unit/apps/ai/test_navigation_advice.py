"""The navigation adviser: what it reads of the pages, and how its advice is checked (utils/navigation_advice.py)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from lys.apps.ai.utils.providers.abstracts import AIJsonResponse

from lys.apps.ai.utils.navigation_advice import (
    NAVIGATION_ADVICE_PURPOSE,
    QUESTION_MAX_LENGTH,
    NavigationAdvice,
    build_navigation_advice_handler,
    checked_advice,
    pages_context,
    prompt_sections,
)

PROMPT = """## Page
What the page is for.

## Screen
- A table of orders, a « New order » button.

### Columns
Date, amount.

## Behaviour
Never read by the adviser.
"""

ROUTES = [
    {
        "name": "OrderListPage",
        "path": "/orders",
        "description": "The orders of a shop",
        "params": {
            "shopId": {"type": "global_id"},
            "year": {"type": "int", "writable": True},
        },
        "chatbot_behaviour": {"prompt": PROMPT},
    },
    {"name": "HomePage", "path": "/home", "description": "The home page"},
]


def _advice(**fields):
    return NavigationAdvice(**{"message": "The orders table answers.", **fields})


class TestPromptSections:

    def test_only_the_headings_asked_are_kept_with_their_subsections(self):
        sections = prompt_sections(PROMPT, ["Page", "screen"])
        assert "What the page is for." in sections
        assert "### Columns" in sections
        assert "Never read" not in sections

    def test_no_heading_keeps_the_whole_prompt_and_an_absent_one_nothing(self):
        assert prompt_sections(PROMPT, None) == PROMPT.strip()
        assert prompt_sections(PROMPT, ["Elsewhere"]) == ""


class TestPagesContext:

    def test_each_page_states_its_path_description_writable_filters_and_screen(self):
        context = pages_context(ROUTES, ["Page", "Screen"])
        assert "### /orders\nThe orders of a shop" in context
        assert "Writable filters: year (int)" in context
        assert "shopId" not in context
        assert "« New order »" in context
        assert "### /home\nThe home page" in context


class TestCheckedAdvice:

    def test_a_page_the_user_may_open_with_its_writable_filters_is_kept(self):
        answer = checked_advice(_advice(page="/orders", params={"year": 2026}), ROUTES, "/home")
        assert answer == {
            "page": "/orders", "params": {"year": 2026}, "message": "The orders table answers.", "current": False,
        }

    def test_the_page_the_user_is_on_is_current(self):
        assert checked_advice(_advice(page="/orders"), ROUTES, "/orders")["current"] is True

    def test_a_page_outside_the_routes_is_dropped_with_its_filters(self):
        answer = checked_advice(_advice(page="/admin", params={"year": 2026}), ROUTES, "/home")
        assert answer["page"] is None and answer["params"] is None
        assert answer["dropped"] == ["page /admin: not a page the user may open", "params: no page to apply them to"]

    def test_a_filter_read_only_undeclared_or_invalid_is_dropped_and_said(self):
        answer = checked_advice(
            _advice(page="/orders", params={"shopId": "x", "status": "OPEN", "year": "last"}), ROUTES, None,
        )
        assert answer["page"] == "/orders" and answer["params"] is None
        assert answer["dropped"] == [
            "param shopId: not_writable", "param status: undeclared", "param year: invalid_value",
        ]

    def test_no_page_is_an_answer(self):
        answer = checked_advice(_advice(message="No page shows the stock."), ROUTES, "/home")
        assert answer == {"page": None, "params": None, "message": "No page shows the stock.", "current": False}


class TestHandler:

    USAGE = {"prompt_tokens": 120, "completion_tokens": 30, "cache_read_tokens": 4000}

    @classmethod
    def _service(cls, result=None, error=None):
        service = MagicMock()
        endpoint = MagicMock()
        service.get_endpoint.return_value.with_cache_key.return_value = endpoint
        response = AIJsonResponse(data=result, model="flash", provider="mistral", usage=cls.USAGE)
        service.chat_json_with_metadata = AsyncMock(return_value=response, side_effect=error)
        return service, endpoint

    def test_the_question_is_asked_with_the_pages_and_the_advice_checked(self):
        service, endpoint = self._service(_advice(page="/orders"))
        handler = build_navigation_advice_handler(service, ROUTES, "OrderListPage", ["Page"])
        answer = asyncio.run(handler({"question": "Where are my orders?"}, {}))
        assert answer["page"] == "/orders" and answer["current"] is True
        service.get_endpoint.assert_called_once_with(NAVIGATION_ADVICE_PURPOSE)
        messages, used_endpoint, schema = service.chat_json_with_metadata.call_args.args
        assert used_endpoint is endpoint and schema is NavigationAdvice
        content = messages[0]["content"]
        assert content.startswith("Pages the user may open:\n\n### /orders")
        assert content.endswith("Page the user is on: /orders\n\nQuestion: Where are my orders?")

    def test_what_surrounds_every_page_is_read_after_the_pages(self):
        service, _ = self._service(_advice())
        handler = build_navigation_advice_handler(service, ROUTES, None, None, interface="The whiteboard menu.")
        asyncio.run(handler({"question": "Where do I export?"}, {}))
        content = service.chat_json_with_metadata.call_args.args[0][0]["content"]
        assert "\n\nAround every page:\nThe whiteboard menu.\n\nPage the user is on: unknown" in content

    def test_the_same_pages_share_one_cache_entry_whatever_their_order(self):
        service, _ = self._service(_advice())
        for routes in (ROUTES, list(reversed(ROUTES))):
            asyncio.run(build_navigation_advice_handler(service, routes, None, None)({"question": "?"}, {}))
        keys = [call.args[0] for call in service.get_endpoint.return_value.with_cache_key.call_args_list]
        assert keys[0] == keys[1] and keys[0].startswith("navigation-")

    def test_an_empty_or_overlong_question_is_refused_before_any_call(self):
        service, _ = self._service(_advice())
        handler = build_navigation_advice_handler(service, ROUTES, None, None)
        for question in ("  ", "x" * (QUESTION_MAX_LENGTH + 1)):
            assert "error" in asyncio.run(handler({"question": question}, {}))
        service.chat_json_with_metadata.assert_not_called()

    def test_a_failed_advice_is_an_error_for_the_chatbot_never_a_raise(self):
        service, _ = self._service(error=RuntimeError("provider down"))
        handler = build_navigation_advice_handler(service, ROUTES, None, None)
        assert asyncio.run(handler({"question": "Where?"}, {})) == {
            "error": "The navigation advice could not be given; use the pages of navigate.",
        }


class TestTrace:
    """Each advice asked is traced with its tokens - or its failure."""

    def test_an_advice_is_traced_with_its_question_tokens_and_answer(self):
        service, _ = TestHandler._service(_advice(page="/orders"))
        trace = AsyncMock()
        handler = build_navigation_advice_handler(service, ROUTES, None, None, trace=trace)
        answer = asyncio.run(handler({"question": "Where are my orders?"}, {}))
        kwargs = trace.call_args.kwargs
        assert kwargs["task"] == "Where are my orders?" and kwargs["output"] == answer and kwargs["error"] is None
        assert kwargs["provider"] == "mistral"
        [call] = kwargs["calls"]
        assert call["kind"] == "advice" and call["model"] == "flash"
        assert (call["tokens_in"], call["tokens_out"], call["cache_read_tokens"]) == (120, 30, 4000)

    def test_a_failed_advice_is_traced_as_a_failure(self):
        service, _ = TestHandler._service(error=RuntimeError("provider down"))
        trace = AsyncMock()
        asyncio.run(build_navigation_advice_handler(service, ROUTES, None, None, trace=trace)({"question": "?"}, {}))
        assert trace.call_args.kwargs["error"] == "provider down" and trace.call_args.kwargs["calls"] == []
