"""
A drawing drafted for the chatbot: it says what the board must show, a drafter lays it out.

Drawn by the chatbot itself, a board costs the chatbot's own model the whole layout - a patch of
thousands of characters written on its slowest rounds - and a second round to move what the
result reports on top of something else. Drafted, the chatbot writes a request (what to show, in
what form, with which figures and arrows) and a drafter on a model of its own (``whiteboard_drafting``
endpoint) composes the patch, reads where everything landed, and fixes it, before anything reaches
the user.

The drafter draws on a copy of the scene held in memory, with the same scene rules as a drawing
written at once (``scene.apply_operations``): a patch it applies is checked and measured as it would
be on the board, and nothing is written. Its patches are then written in one go, in the order it
applied them (``WhiteboardService.draw``), on the board as it stands then: a patch names its elements,
so a hand edit made meanwhile elsewhere on the board is kept.

Once it stops, what it drew is checked in code (``review``), the way a reader of the board would see
it: an element on top of another, an element sticking out of its slide (cut when presented), a label
its box does not hold, a link asked for that no arrow draws, an arrow running through a box over its text,
a figure the request does not give - and
what it left out: a figure the request gives that the drawing does not show, a slide left blank. What
is found goes back to the drafter for one correction pass, on a budget of calls of its own; what is left
reaches the chatbot as ``issues``, never hidden.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from lys.apps.ai.utils.providers.exceptions import AIError
from lys.apps.ai.utils.sourced_figures import context_of, unsourced_figures
from lys.apps.ai.utils.tracing import traced_call
from lys.apps.ai_whiteboard.modules.conversation.tools import DRAFT_PATCH_TOOL
from lys.apps.ai_whiteboard.modules.whiteboard import scene as scene_tools
from lys.apps.ai_whiteboard.modules.whiteboard.consts import OPERATION_KEYS
from lys.core.errors import LysError

logger = logging.getLogger(__name__)

#: The AI endpoint purpose the drafter runs on (the consumer configures it: model, prompt)
DRAFTING_PURPOSE = "whiteboard_drafting"

#: Model calls of a drafting's first pass: its patches - a deck of several slides takes a few -, a
#: correction or two of its own, and its closing note. Six were too few: a four-slide deck drawn a
#: slide per patch ran out of calls after the first slide, leaving three slides blank.
MAX_DRAFT_ROUNDS = 8

#: Model calls of the pass that corrects what the checks found, a budget of its own: shared with
#: the first pass, a drafter that kept patching to its last call never had its checks sent back,
#: and the chatbot was left to relay them itself.
MAX_CORRECTION_ROUNDS = 5

#: How long a request may be: a drawing described, not a document pasted
REQUEST_MAX_LENGTH = 20000

#: How many links a request may ask for, and how long the text of one end may be
MAX_LINKS = 60
LINK_END_MAX_LENGTH = 200


#: A measure on the board - "310 px", "236 to 307 px", a size "1280×720" -: an instruction of layout,
#: never a figure the drawing has to show. Read as one, the drafter wrote "1280 × 720" on the slide
#: to satisfy the check.
_MEASURE = re.compile(
    r"\d[\d\s.,]*(?:\s+\S{1,3}\s+\d[\d\s.,]*)?\s*px\b|\b\d+\s*[×xX]\s*\d+\b", re.IGNORECASE,
)


@dataclass
class Draft:
    """
    What the drafter applied, in order, what it drew, and what it says of it - and, for its trace,
    its model calls (``traced_call``), its messages, the provider of its last call, and the error
    that stopped it (its patches are then not to be written).
    """

    patches: List[Dict[str, Any]] = field(default_factory=list)
    drawn: List[str] = field(default_factory=list)
    note: str = ""
    issues: List[Dict[str, Any]] = field(default_factory=list)
    calls: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    provider: Optional[str] = None
    error: Optional[str] = None


def drafting_task(request: str, scene: Dict[str, Any], links: Optional[List[Dict[str, str]]] = None) -> str:
    """The drafter's message: the board as it stands, what to draw on it, and the links asked for."""
    board = {
        "elements": scene_tools.describe(scene),
        "slides": scene_tools.slides(scene),
        "theme": scene_tools.theme(scene),
    }
    return (
        "The board as it stands (names, kinds, texts, places and sizes):\n"
        f"{json.dumps(board, ensure_ascii=False)}\n\n"
        "What to draw - all of it, every figure and every slide, in as few patches as you can (a whole deck "
        f"in one or two):\n{request}"
    ) + (f"\n\nLinks to draw as arrows (from -> to):\n{json.dumps(links, ensure_ascii=False)}" if links else "")


def applied(
    scene: Dict[str, Any], arguments: Dict[str, Any], style: Optional[scene_tools.BoardStyle] = None,
) -> Dict[str, Any]:
    """
    One patch of the drafter, applied to the scene in memory, and what it reads back: the board's
    elements with their places and sizes, its slides, and what the patch left on top of something
    else. A patch the scene refuses comes back as the error the drafter can act on.

    Returns:
        ``{"scene", "patch", "result"}`` for an applied patch; ``{"result"}`` alone for a refused one.
    """
    patch = {key: arguments[key] for key in OPERATION_KEYS if arguments.get(key)}
    if not patch:
        return {"result": {"error": "EMPTY_PATCH", "message": "Nothing to apply: give add, update, delete or theme"}}
    try:
        new_scene = scene_tools.apply_operations(scene, patch, style)
    except LysError as error:
        return {"result": {"error": error.detail, "message": error.debug_message}}
    result: Dict[str, Any] = {
        "elements": scene_tools.describe(new_scene),
        "slides": scene_tools.slides(new_scene),
    }
    found = scene_tools.overlaps(new_scene, scene_tools.drawn_names(patch))
    if found:
        result["overlaps"] = found
    return {"scene": new_scene, "patch": patch, "result": result}


def review(
    scene: Dict[str, Any], drawn: List[str], request: str, links: Optional[List[Dict[str, str]]] = None,
    before: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    What the checks find in what a drafting drew, as a reader of the board would see it - only
    in the elements it drew: what the user drew by hand is theirs.

    Args:
        scene: The scene once drawn (in memory).
        drawn: The names the drafting drew.
        request: The request it was given: every figure it draws must be read in it.
        links: The links the request asked for, by the texts of their two ends.
        before: The scene as the drafting found it: what an element already said there is not this
            drafting's writing - a slide only moved is not checked against the new request - and a figure
            the board already shows is not missing.

    Returns:
        One entry per finding, its ``check`` naming what is wrong.
    """
    issues: List[Dict[str, Any]] = []
    issues += [{"check": "overlap", **entry} for entry in scene_tools.overlaps(scene, drawn)]
    issues += [{"check": "outside_frame", **entry} for entry in scene_tools.outside_frames(scene, drawn)]
    issues += [{"check": "label_does_not_fit", **entry} for entry in scene_tools.unfit_labels(scene, drawn)]
    issues += [{"check": "missing_link", **entry} for entry in scene_tools.missing_links(scene, links or [])]
    issues += [{"check": "link_crosses", **entry} for entry in scene_tools.crossing_links(scene, drawn)]
    said_before = {entry["name"]: _said(entry) for entry in scene_tools.describe(before or scene_tools.empty_scene())}
    described = scene_tools.describe(scene)
    # What this drafting wrote: the elements it drew whose words are new, not those it only moved
    written = "\n".join(
        _said(entry) for entry in described
        if entry["name"] in drawn and said_before.get(entry["name"]) != _said(entry)
    )
    board = "\n".join(_said(entry) for entry in described)
    issues += [
        {"check": "figure_not_in_request", "figure": figure.text, "where": context_of(written, figure)}
        for figure in unsourced_figures(written, [request])
    ]
    # What was asked and is not there: a figure of the request the drawing never shows, a slide left blank
    asked = _MEASURE.sub("", request)
    issues += [
        {"check": "figure_missing", "figure": figure.text, "asked": context_of(asked, figure)}
        for figure in unsourced_figures(asked, [board])
    ]
    issues += [{"check": "empty_slide", **entry} for entry in scene_tools.empty_frames(scene, drawn)]
    return issues


def _said(entry: Dict[str, Any]) -> str:
    """What an element of the board says - its text, label and data -, as one comparable string."""
    return json.dumps({key: entry[key] for key in ("text", "label", "data") if key in entry}, ensure_ascii=False)


async def draft(
    ai_service: Any, request: str, scene: Dict[str, Any], cache_key: str,
    links: Optional[List[Dict[str, str]]] = None, style: Optional[scene_tools.BoardStyle] = None,
) -> Draft:
    """
    Have the drafter lay out ``request`` on ``scene``: it applies patches in memory and reads each
    result until it stops (at most MAX_DRAFT_ROUNDS model calls, the last one answering in words);
    what it drew is then checked (``review``) and what the checks find is sent back once, for a
    pass of its own (at most MAX_CORRECTION_ROUNDS calls).

    Args:
        ai_service: The AI service the drafter's endpoint is called through.
        request: What to draw, as the chatbot wrote it.
        scene: The board's scene as it stands (an empty one for a board not opened yet).
        cache_key: Names the drafting's cache bucket (its rounds share their prefix).
        links: The links the request asks for, by the texts of their two ends.
        style: How the board will draw what the patches leave unsaid (``WhiteboardService.style``).

    Returns:
        The patches applied, in order, the names drawn, the drafter's closing note and what the
        checks still find. No patch when the drafter drew nothing. A drafter whose endpoint did not
        answer on its first pass is a result too, its ``error`` set, its calls up to then kept for
        its trace; one that stops answering during the correction pass keeps what it drew, with the
        issues left.
    """
    messages: List[Dict[str, Any]] = [{"role": "user", "content": drafting_task(request, scene, links)}]
    before = scene
    result = Draft(messages=messages)
    scene = await _drafting_pass(ai_service, scene, cache_key, style, result, "draft", MAX_DRAFT_ROUNDS)
    if result.error or not result.patches:
        return result
    result.issues = review(scene, result.drawn, request, links, before)
    if not result.issues:
        return result
    # One pass to correct what the checks found, with the drafter's own tool
    messages.append({"role": "assistant", "content": result.note or "Done."})
    messages.append({"role": "user", "content": _correction(result.issues)})
    scene = await _drafting_pass(ai_service, scene, cache_key, style, result, "correction", MAX_CORRECTION_ROUNDS)
    if result.error:
        # The correction is a second chance, never a condition: what is drawn stands, with what the
        # checks still find. The failed call stays in the trace (``calls``).
        logger.warning("Whiteboard drafting: correction pass stopped (%s), the drawing is kept", result.error)
        result.error = None
    result.issues = review(scene, result.drawn, request, links, before)
    return result


async def _drafting_pass(
    ai_service: Any, scene: Dict[str, Any], cache_key: str, style: Optional[scene_tools.BoardStyle],
    result: Draft, kind: str, rounds: int,
) -> Dict[str, Any]:
    """
    The drafter patching ``scene`` until it answers in words - at the latest on the last of
    ``rounds`` calls, where it may not call its tool. What it applies and calls is added to
    ``result``; an endpoint that stops answering sets its ``error`` and ends the pass.

    Returns:
        The scene as the pass left it.
    """
    messages = result.messages
    for drafting_round in range(rounds):
        last = drafting_round == rounds - 1
        started = time.perf_counter()
        try:
            response = await ai_service.chat_with_purpose(
                messages, DRAFTING_PURPOSE, [DRAFT_PATCH_TOOL], cache_key=cache_key, tool_calls_allowed=not last,
            )
        except AIError as error:
            result.calls.append(traced_call(kind, _elapsed_ms(started), None, None, error=str(error)))
            result.error = str(error)
            return scene
        tool_calls = [] if last else (response.tool_calls or [])
        result.calls.append(traced_call(
            kind, _elapsed_ms(started), response.usage, response.model, tool_calls=len(tool_calls),
        ))
        result.provider = response.provider
        if not tool_calls:
            result.note = (response.content or "").strip()
            return scene

        messages.append({"role": "assistant", "content": response.content, "tool_calls": tool_calls})
        for tool_call in tool_calls:
            outcome = applied(scene, _arguments(tool_call), style)
            if "patch" in outcome:
                scene = outcome["scene"]
                result.patches.append(outcome["patch"])
                result.drawn += [name for name in scene_tools.drawn_names(outcome["patch"]) if name not in result.drawn]
            messages.append({
                "role": "tool", "tool_call_id": tool_call.get("id", ""),
                "content": json.dumps(outcome["result"], ensure_ascii=False),
            })
    return scene


def _elapsed_ms(started: float) -> int:
    """Milliseconds since ``started`` (a perf_counter reading)."""
    return int((time.perf_counter() - started) * 1000)


def _correction(issues: List[Dict[str, Any]]) -> str:
    """What the checks found, for the drafter to fix with apply_patch before answering again."""
    return (
        "The checks of your drawing found what a reader would see:\n"
        f"{json.dumps(issues, ensure_ascii=False)}\n\n"
        "Fix each with apply_patch, then answer again: figure_missing -> draw it where it belongs, as the "
        "request writes it; empty_slide -> fill the slide with what the request puts on it; overlap -> move "
        "one of the two; outside_frame -> "
        "bring the element inside its frame (coordinates count from the frame's corner); label_does_not_fit "
        "-> give the box at least the size it needs, or shorten the text; missing_link -> draw the arrow "
        "between the two elements; link_crosses -> move the boxes so the arrow runs clear of the ones it "
        "crosses (a column further apart, a row out of its way); figure_not_in_request -> write the figure as "
        "the request gives it, or remove it."
    )


def _arguments(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """A tool call's arguments, as a dict whatever the provider sent: malformed ones read as none."""
    raw = (tool_call.get("function") or {}).get("arguments") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        arguments = json.loads(raw)
    except ValueError:
        logger.info("Whiteboard drafter sent malformed arguments")
        return {}
    return arguments if isinstance(arguments, dict) else {}


def asked_links(value: Any) -> Optional[List[Dict[str, str]]]:
    """
    The links a request asks for, as the chatbot sent them: a list of ``{from, to}`` texts.

    Returns:
        The links, ends trimmed; an empty list for none; None when the value is not a list of
        such pairs (too many, an end empty or too long), for the caller to refuse.
    """
    if value in (None, []):
        return []
    if not isinstance(value, list) or len(value) > MAX_LINKS:
        return None
    links = []
    for link in value:
        ends = [link.get(key) for key in ("from", "to")] if isinstance(link, dict) else [None, None]
        if not all(isinstance(end, str) and 0 < len(end.strip()) <= LINK_END_MAX_LENGTH for end in ends):
            return None
        links.append({"from": ends[0].strip(), "to": ends[1].strip()})
    return links

