"""
Where in the application something is: the ``advise_navigation`` special tool.

The chatbot knows each page it may open by one line (the ``navigate`` tool) and the screen of the
page it is on (that page's prompt). Asked where something is or how to do it elsewhere, it guessed
from a line. This tool reads, for the chatbot, the pages the user may open — their description,
their filters and the sections of their prompt that describe the screen (``sections``, the
consumer's headings) — and answers on a model of its own (``navigation_advice`` endpoint): the page
that answers, the filters to land on, and a message on how to do it there.

The model designates, the code checks: the page must be one the user may open, the filters must be
the page's writable ones, valid in their declared shape (``writable_page_params``). What does not
pass is dropped and said, never forwarded. The chatbot still navigates itself (``navigate``): this
tool only advises.
"""

import hashlib
import logging
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from lys.apps.ai.utils.page_params import writable_page_params
from lys.apps.ai.utils.tracing import traced_call
from lys.core.utils.routes import route_page_params, writable_param_names

logger = logging.getLogger(__name__)

#: The AI endpoint purpose the advice is asked on (the consumer configures it: model, prompt)
NAVIGATION_ADVICE_PURPOSE = "navigation_advice"

#: How long the question asked may be: a question, not a document
QUESTION_MAX_LENGTH = 1000

#: How long the message of an advice may be: a few sentences for the chatbot to say
MESSAGE_MAX_LENGTH = 1500


class NavigationAdvice(BaseModel):
    """The advice of a model: the page that answers, the filters to land on it, and how."""

    page: Optional[str] = Field(
        None, description="The path of the page that answers, exactly as listed; null when no listed page does",
    )
    params: Optional[Dict[str, Any]] = Field(
        None, description="The filters to apply on arrival: only the writable params the page lists, in their "
                          "shape; null when none is needed",
    )
    message: str = Field(
        ..., min_length=1, max_length=MESSAGE_MAX_LENGTH,
        description="For the assistant, in two or three sentences: what the page shows that answers, where on "
                    "it, what to do there — or why no page does",
    )


def prompt_sections(prompt: str, headings: Optional[List[str]]) -> str:
    """
    The sections of a page's prompt titled with one of ``headings`` (a ``## Heading`` line and what
    follows up to the next heading of the same or a higher level); the whole prompt when no heading
    is given, nothing when none of them is there.
    """
    if not headings:
        return prompt.strip()
    wanted = {heading.strip().lower() for heading in headings}
    kept, keep = [], False
    for line in prompt.splitlines():
        match = re.match(r"^(#{1,2})\s+(.+?)\s*$", line)
        if match:
            keep = match.group(2).strip().lower() in wanted
        if keep:
            kept.append(line)
    return "\n".join(kept).strip()


def pages_context(routes: List[Dict[str, Any]], headings: Optional[List[str]]) -> str:
    """What the model reads of each page the user may open: its path, its description, its writable
    filters and the screen sections of its prompt."""
    blocks = []
    for route in routes:
        schema = route_page_params(route) or {}
        writable = writable_param_names(schema)
        screen = prompt_sections((route.get("chatbot_behaviour") or {}).get("prompt") or "", headings)
        block = f"### {route['path']}\n{route.get('description') or ''}"
        if writable:
            filters = ", ".join(f"{key} ({(schema.get(key) or {}).get('type', '?')})" for key in writable)
            block += f"\nWritable filters: {filters}"
        if screen:
            block += f"\n{screen}"
        blocks.append(block)
    return "\n\n".join(blocks)


def checked_advice(
    advice: NavigationAdvice, routes: List[Dict[str, Any]], current_path: Optional[str],
) -> Dict[str, Any]:
    """
    The advice as the chatbot gets it, checked against what the user may open: a page not among the
    routes is dropped, the filters are only the page's writable ones that validate. What was dropped
    is said (``dropped``), so the chatbot never repeats it.
    """
    by_path = {route["path"]: route for route in routes}
    answer: Dict[str, Any] = {"page": None, "params": None, "message": advice.message, "current": False}
    dropped: List[str] = []
    route = by_path.get(advice.page) if advice.page else None
    if advice.page and route is None:
        dropped.append(f"page {advice.page}: not a page the user may open")
    if route is not None:
        answer["page"] = route["path"]
        answer["current"] = route["path"] == current_path
        accepted, refusals = writable_page_params(advice.params, route_page_params(route), route.get("name", ""))
        answer["params"] = accepted or None
        dropped += [f"param {key}: {reason}" for key, reason in refusals.items()]
    elif advice.params:
        dropped.append("params: no page to apply them to")
    if dropped:
        answer["dropped"] = dropped
    return answer


#: Traces one advice: ``(task, calls, output, error, provider)`` - ``AIAgentService.record`` bound to
#: the purpose, the user and the tenant of the turn
AdviceTrace = Callable[..., Awaitable[None]]


def build_navigation_advice_handler(
    ai_service: Any, routes: List[Dict[str, Any]], current_page_name: Optional[str],
    headings: Optional[List[str]], interface: Optional[str] = None, trace: Optional[AdviceTrace] = None,
) -> Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    """
    The ``advise_navigation`` handler of a turn: the pages the user may open (``routes``, already
    filtered by the user's rights), the page the user is on, the headings of the screen sections, and
    what surrounds every page (``interface``, the manifest's global prompt). A failure to answer is an
    error the chatbot reads, never a raise through the turn. Each advice asked is traced (``trace``):
    the question, the call's tokens and latency, the advice or the failure.
    """

    current_path = next((route["path"] for route in routes if route.get("name") == current_page_name), None)
    context = f"Pages the user may open:\n\n{pages_context(routes, headings)}"
    if interface and interface.strip():
        context += f"\n\nAround every page:\n{interface.strip()}"
    # One cache entry per set of pages: the same rights read the same context, first in the message
    cache_key = "navigation-" + hashlib.sha256("\n".join(sorted(r["path"] for r in routes)).encode()).hexdigest()[:16]

    async def handler(arguments: Dict[str, Any], _context: Dict[str, Any]) -> Dict[str, Any]:
        question = str(arguments.get("question") or "").strip()
        if not question or len(question) > QUESTION_MAX_LENGTH:
            return {"error": f"question must be 1 to {QUESTION_MAX_LENGTH} characters"}
        message = (
            f"{context}\n\n"
            f"Page the user is on: {current_path or 'unknown'}\n\nQuestion: {question}"
        )
        started = time.perf_counter()
        try:
            endpoint = ai_service.get_endpoint(NAVIGATION_ADVICE_PURPOSE).with_cache_key(cache_key)
            response = await ai_service.chat_json_with_metadata(
                [{"role": "user", "content": message}], endpoint, NavigationAdvice,
            )
        except Exception as error:  # noqa: BLE001 - a failed advice is the chatbot's to say, not the turn's
            logger.error("Navigation advice failed: %s", error)
            if trace:
                await trace(task=question, calls=[], output=None, error=str(error), provider=None)
            return {"error": "The navigation advice could not be given; use the pages of navigate."}
        answer = checked_advice(response.data, routes, current_path)
        if trace:
            latency_ms = int((time.perf_counter() - started) * 1000)
            await trace(
                task=question, calls=[traced_call("advice", latency_ms, response.usage, response.model)],
                output=answer, error=None, provider=response.provider,
            )
        return answer

    return handler


ADVISE_NAVIGATION_TOOL = {
    "type": "function",
    "function": {
        "name": "advise_navigation",
        "description": (
            "Ask WHERE something is in the application, or HOW to do it, when it is not on the page the user "
            "is on: an adviser who reads every page the user may open — what each screen shows, its filters — "
            "answers with the page, the filters to land on and how to do it there. Call it for « where do I "
            "see… », « how do I… », « can I… » questions; it navigates nothing: use navigate with what it "
            "returns. RETURNS page (null when no page the user may open answers), params (the arrival filters, "
            "already checked), message (what the page shows, where, what to do — or why nothing does), current "
            "(true when it is the page the user is on: answer from it, no navigation), dropped (what it advised "
            "that the user's rights or the page refuse: never repeat it), error (no advice: use the pages of "
            "navigate)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The user's question, complete: what they want to see or do, for which company "
                                   "or period",
                },
            },
            "required": ["question"],
        },
    },
}
