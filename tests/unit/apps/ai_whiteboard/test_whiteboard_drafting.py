"""A drawing drafted for the chatbot: the drafter's loop (drafting.py) and the handler that writes it."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lys.apps.ai.utils.providers.exceptions import AIError
from lys.apps.ai_whiteboard.modules.conversation import drafting
from lys.apps.ai_whiteboard.modules.conversation.services import DRAFT_FAILED, AIConversationService
from lys.apps.ai_whiteboard.modules.conversation.tools import DRAFT_PATCH_TOOL
from lys.apps.ai_whiteboard.modules.whiteboard import scene as scene_tools
from lys.core.graphql.client import build_global_id


def _call(arguments, call_id="call-1"):
    return {"id": call_id, "type": "function",
            "function": {"name": "apply_patch", "arguments": json.dumps(arguments)}}


USAGE = {"prompt_tokens": 900, "completion_tokens": 200, "cache_read_tokens": 8000}


def _ai(*responses):
    """An AI service answering the drafter's rounds in turn."""
    service = MagicMock()
    service.chat_with_purpose = AsyncMock(side_effect=[
        SimpleNamespace(content=content, tool_calls=calls, usage=USAGE, model="flash", provider="mistral")
        for content, calls in responses
    ])
    return service


class TestApplied:

    def test_a_patch_is_applied_in_memory_and_read_back(self):
        outcome = drafting.applied(scene_tools.empty_scene(), {"add": [{"name": "a", "text": "Sales"}], "focus": ["x"]})
        assert outcome["patch"] == {"add": [{"name": "a", "text": "Sales"}]}
        assert [element["name"] for element in outcome["result"]["elements"]] == ["a"]
        assert "overlaps" not in outcome["result"]

    def test_what_a_patch_leaves_on_top_of_something_else_is_reported(self):
        drawn = drafting.applied(scene_tools.empty_scene(), {"add": [{"name": "a", "text": "A", "x": 0, "y": 0}]})
        outcome = drafting.applied(drawn["scene"], {"add": [{"name": "b", "text": "B", "x": 10, "y": 10}]})
        assert outcome["result"]["overlaps"][0]["element"] == "b"

    def test_a_refused_or_empty_patch_is_an_error_and_changes_nothing(self):
        refused = drafting.applied(scene_tools.empty_scene(), {"update": [{"name": "nowhere", "text": "x"}]})
        assert set(refused) == {"result"} and "error" in refused["result"]
        assert drafting.applied(scene_tools.empty_scene(), {})["result"]["error"] == "EMPTY_PATCH"


class TestDraft:

    @pytest.mark.asyncio
    async def test_the_drafter_patches_reads_back_and_closes_with_a_note(self):
        ai = _ai(
            (None, [_call({"add": [{"name": "a", "text": "A", "x": 0, "y": 0},
                                   {"name": "b", "text": "B", "x": 10, "y": 10}]})]),
            (None, [_call({"update": [{"name": "b", "x": 400, "y": 0}]}, "call-2")]),
            ("Two boxes side by side, top left.", []),
        )
        draft = await drafting.draft(ai, "Draw A and B", scene_tools.empty_scene(), cache_key="k")

        assert draft.patches == [
            {"add": [{"name": "a", "text": "A", "x": 0, "y": 0}, {"name": "b", "text": "B", "x": 10, "y": 10}]},
            {"update": [{"name": "b", "x": 400, "y": 0}]},
        ]
        assert draft.drawn == ["a", "b"] and draft.note == "Two boxes side by side, top left."
        messages, purpose, tools = ai.chat_with_purpose.await_args.args
        assert purpose == drafting.DRAFTING_PURPOSE and tools == [DRAFT_PATCH_TOOL]
        overlap = json.loads(messages[2]["content"])["overlaps"][0]
        assert {overlap["element"], overlap["with"]} == {"a", "b"}
        assert messages[0]["content"].endswith("(a whole deck in one or two):\nDraw A and B")

    @pytest.mark.asyncio
    async def test_the_last_round_answers_in_words(self):
        rounds = [(None, [_call({"add": [{"name": f"n{i}"}]}, f"c{i}")]) for i in range(drafting.MAX_DRAFT_ROUNDS - 1)]
        ai = _ai(*rounds, ("Done.", [_call({"add": [{"name": "late"}]})]))
        draft = await drafting.draft(ai, "Draw", scene_tools.empty_scene(), cache_key="k")

        assert ai.chat_with_purpose.await_args.kwargs["tool_calls_allowed"] is False
        assert "late" not in draft.drawn and len(draft.patches) == drafting.MAX_DRAFT_ROUNDS - 1

    @pytest.mark.asyncio
    async def test_a_refused_patch_is_read_by_the_drafter_and_not_kept(self):
        ai = _ai((None, [_call({"update": [{"name": "nowhere", "text": "x"}]})]), ("Nothing to change.", []))
        draft = await drafting.draft(ai, "Draw", scene_tools.empty_scene(), cache_key="k")
        assert draft.patches == [] and draft.note == "Nothing to change."


# ==================== The handler ====================

BOARD = SimpleNamespace(id="board-1", title="Board", scene_json=None)
DRAWN = {
    "whiteboard_id": "board-1", "title": "Board", "slides": [],
    "elements": [{"name": "a", "kind": "note", "text": "A", "x": 0, "y": 0}, {"name": "old", "kind": "note"}],
}


@pytest.fixture
def whiteboard_service():
    service = MagicMock()
    service.draw = AsyncMock(return_value=DRAWN)
    service.find_for_conversation = AsyncMock(return_value=BOARD)
    service.get_for_user = AsyncMock(return_value=BOARD)
    service.follow_conversation_archive = AsyncMock()
    service.follow_conversation_pin = AsyncMock()
    service.record = AsyncMock()  # the trace service: get_service answers this double for every name
    return service


@pytest.fixture
def service(whiteboard_service):
    conversation = SimpleNamespace(
        id="conv-1", user_id="user-1", client_id="client-1", title="Titre", whiteboard_id="board-1",
    )
    app_manager = MagicMock()
    app_manager.get_service.return_value = whiteboard_service
    with patch.object(AIConversationService, "app_manager", app_manager, create=True), \
            patch.object(AIConversationService, "get_by_id", AsyncMock(return_value=conversation)):
        yield AIConversationService


def context():
    session = MagicMock()
    session.flush = AsyncMock()
    return {"session": session, "conversation_id": "conv-1"}


class TestDraftHandler:

    @pytest.mark.asyncio
    async def test_the_drafted_patches_are_written_and_only_what_they_drew_comes_back(
        self, service, whiteboard_service,
    ):
        draft = drafting.Draft(patches=[{"add": [{"name": "a"}]}], drawn=["a"], note="Top left.")
        with patch.object(drafting, "draft", AsyncMock(return_value=draft)) as drafted:
            result = await service._handle_draft_on_whiteboard({"request": " Draw A "}, context())

        assert drafted.await_args.args[1] == "Draw A"
        assert whiteboard_service.draw.await_args.kwargs["patches"] == [{"add": [{"name": "a"}]}]
        assert result["drawn"] == [{"name": "a", "kind": "note", "text": "A"}]
        assert result["note"] == "Top left." and "elements" not in result
        assert result["whiteboard_id"] == build_global_id("WhiteboardNode", "board-1")

    @pytest.mark.asyncio
    async def test_a_focus_given_with_a_request_is_left_to_what_the_drafter_drew(self, service, whiteboard_service):
        draft = drafting.Draft(patches=[{"add": [{"name": "a"}]}], drawn=["a"])
        with patch.object(drafting, "draft", AsyncMock(return_value=draft)):
            await service._handle_draft_on_whiteboard({"request": "Draw", "focus": ["a guessed name"]}, context())
        assert whiteboard_service.draw.await_args.kwargs["focus"] is None

    @pytest.mark.asyncio
    async def test_a_failed_or_empty_draft_writes_nothing(self, service, whiteboard_service):
        for outcome in (drafting.Draft(patches=[{"add": [{"name": "a"}]}], error="down"), drafting.Draft(note="")):
            with patch.object(drafting, "draft", AsyncMock(return_value=outcome)):
                result = await service._handle_draft_on_whiteboard({"request": "Draw"}, context())
            assert result["error"] == DRAFT_FAILED
        whiteboard_service.draw.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_focus_alone_shows_without_drafting(self, service, whiteboard_service):
        with patch.object(drafting, "draft", AsyncMock()) as drafted:
            await service._handle_draft_on_whiteboard({"focus": ["a"]}, context())
        drafted.assert_not_awaited()
        kwargs = whiteboard_service.draw.await_args.kwargs
        assert kwargs["patches"] == [] and kwargs["focus"] == ["a"]

    @pytest.mark.asyncio
    async def test_a_copy_is_drafted_on_its_source(self, service, whiteboard_service):
        source = SimpleNamespace(id="board-9", scene_json=scene_tools.apply_operations(
            scene_tools.empty_scene(), {"add": [{"name": "kept"}]}))
        whiteboard_service.get_for_user = AsyncMock(return_value=source)
        draft = drafting.Draft(patches=[{"add": [{"name": "a"}]}], drawn=["a"])
        with patch.object(drafting, "draft", AsyncMock(return_value=draft)) as drafted:
            await service._handle_draft_on_whiteboard(
                {"request": "Same for June", "copy_from": build_global_id("WhiteboardNode", "board-9")}, context(),
            )
        assert drafted.await_args.args[2] is source.scene_json
        assert whiteboard_service.draw.await_args.kwargs["copy_from_whiteboard_id"] == "board-9"

    @pytest.mark.asyncio
    async def test_nothing_asked_or_too_much_is_refused_before_any_draft(self, service, whiteboard_service):
        with patch.object(drafting, "draft", AsyncMock()) as drafted:
            empty = await service._handle_draft_on_whiteboard({"request": "  "}, context())
            long = await service._handle_draft_on_whiteboard(
                {"request": "x" * (drafting.REQUEST_MAX_LENGTH + 1)}, context(),
            )
        assert empty["error"] == "EMPTY_PATCH" and long["error"] == "REQUEST_TOO_LONG"
        drafted.assert_not_awaited()


# ==================== The checks ====================

def _scene(*items):
    return scene_tools.apply_operations(scene_tools.empty_scene(), {"add": list(items)})


class TestSceneChecks:

    def test_an_element_out_of_its_slide_is_found_with_how_far(self):
        scene = _scene({"name": "s1", "kind": "frame", "text": "1. Facts", "x": 0, "y": 0,
                        "width": 1280, "height": 720},
                       {"name": "inside", "text": "ok", "frame": "s1", "x": 40, "y": 40},
                       {"name": "below", "text": "lost", "frame": "s1", "x": 40, "y": 840})
        found = scene_tools.outside_frames(scene, ["inside", "below", "s1"])
        assert [entry["element"] for entry in found] == ["below"]
        assert found[0]["frame"] == "s1" and found[0]["beyond"]["bottom"] > 0

    def test_a_label_its_box_does_not_hold_is_found(self):
        scene = _scene({"name": "small", "text": "A long sentence that will never fit"},
                       {"name": "fits", "text": "Short", "x": 400, "y": 0})
        # Sized in the editor: a size given in a patch grows to hold its text
        scene_tools.find(scene, "small").update(width=120, height=30)
        found = scene_tools.unfit_labels(scene, ["small", "fits"])
        assert [entry["element"] for entry in found] == ["small"]
        assert found[0]["needs_height"] > 30

    def test_a_link_is_matched_by_the_texts_of_its_ends_accents_and_case_aside(self):
        scene = _scene({"name": "a", "text": "Analyse IA"}, {"name": "b", "text": "Décision actée", "x": 400, "y": 0},
                       {"name": "l", "kind": "arrow", "from": "a", "to": "b"})
        asked = [{"from": "analyse ia", "to": "DECISION"}, {"from": "Décision", "to": "Analyse"}]
        assert scene_tools.missing_links(scene, asked) == [{"from": "Décision", "to": "Analyse"}]


class TestReview:

    def test_a_figure_the_request_does_not_give_is_found(self):
        scene = _scene({"name": "t", "kind": "table", "headers": ["Year", "Sales"], "rows": [["2025", "4,9 M€"]]},
                       {"name": "n", "text": "Margin 12,4 %", "x": 800, "y": 0})
        issues = drafting.review(scene, ["t", "n"], "Sales 2025: 4,9 M€", None)
        assert [(issue["check"], issue["figure"]) for issue in issues] == [("figure_not_in_request", "12,4 %")]

    def test_only_what_the_drafting_drew_is_checked(self):
        scene = _scene({"name": "mine", "text": "A", "x": 0, "y": 0},
                       {"name": "theirs", "text": "B 999 €", "x": 10, "y": 10})
        assert drafting.review(scene, ["mine"], "", None)[0]["check"] == "overlap"
        assert all(issue["check"] != "figure_not_in_request" for issue in drafting.review(scene, ["mine"], "", None))


class TestCompleteness:
    """What the request asks for and the drawing leaves out."""

    def test_a_figure_of_the_request_the_drawing_never_shows_is_found(self):
        scene = _scene({"name": "k", "kind": "kpi", "value": "4,9 M€", "text": "CA 2025"})
        issues = drafting.review(scene, ["k"], "CA 2025 : 4,9 M€ ; EBE 2025 : 455 k€", None)
        assert [(issue["check"], issue["figure"]) for issue in issues] == [("figure_missing", "455 k€")]

    def test_a_slide_left_with_its_title_alone_is_found(self):
        frame = {"kind": "frame", "x": 0, "width": 1280, "height": 720}
        scene = _scene({"name": "s1", "text": "1. Facts", "y": 0, **frame},
                       {"name": "t1", "kind": "text", "text": "Facts", "frame": "s1", "zone": "title"},
                       {"name": "n1", "text": "Content", "frame": "s1", "zone": "full"},
                       {"name": "s2", "text": "2. Causes", "y": 820, **frame},
                       {"name": "t2", "kind": "text", "text": "Causes", "frame": "s2", "zone": "title"})
        issues = drafting.review(scene, ["s1", "t1", "n1", "s2", "t2"], "", None)
        assert [issue for issue in issues if issue["check"] == "empty_slide"] == [
            {"check": "empty_slide", "frame": "s2", "title": "2. Causes"},
        ]


class TestWhatTheDraftingWrote:
    """An element the drafting only moved is not its writing; a figure already on the board is not missing."""

    def test_a_slide_moved_down_is_not_checked_against_the_new_request(self):
        before = _scene({"name": "k", "kind": "kpi", "value": "4,9 M€", "text": "CA 2025"})
        after = scene_tools.apply_operations(before, {"update": [{"name": "k", "x": 0, "y": 900}],
                                                      "add": [{"name": "t", "kind": "text", "text": "Synthèse",
                                                               "x": 0, "y": 0}]})
        issues = drafting.review(after, ["k", "t"], "Ajoute une synthèse en tête, sans chiffre", None, before)
        assert [issue for issue in issues if issue["check"] == "figure_not_in_request"] == []

    def test_a_figure_of_the_request_already_on_the_board_is_not_missing(self):
        before = _scene({"name": "k", "kind": "kpi", "value": "4,9 M€", "text": "CA 2025"})
        after = scene_tools.apply_operations(before, {"add": [{"name": "t", "kind": "text", "text": "Synthèse",
                                                               "x": 0, "y": 600}]})
        issues = drafting.review(after, ["t"], "Rappelle le CA 2025 de 4,9 M€ en synthèse", None, before)
        assert [issue for issue in issues if issue["check"] == "figure_missing"] == []


class TestCorrectionRound:

    @pytest.mark.asyncio
    async def test_what_the_checks_find_goes_back_once_and_what_is_left_is_reported(self):
        ai = _ai(
            (None, [_call({"add": [{"name": "a", "text": "Analyse"},
                                   {"name": "b", "text": "Décision", "x": 400, "y": 0}]})]),
            ("Drawn.", []),
            (None, [_call({"add": [{"name": "l", "kind": "arrow", "from": "a", "to": "b"}]}, "call-2")]),
            ("Arrow added.", []),
        )
        draft = await drafting.draft(ai, "Draw", scene_tools.empty_scene(), cache_key="k",
                                     links=[{"from": "Analyse", "to": "Décision"}])

        sent = ai.chat_with_purpose.await_args.args[0]
        corrections = [m for m in sent if m["role"] == "user" and "missing_link" in m["content"]]
        assert len(corrections) == 1
        assert draft.issues == [] and draft.note == "Arrow added." and draft.drawn == ["a", "b", "l"]

    @pytest.mark.asyncio
    async def test_a_second_finding_is_reported_not_sent_back(self):
        ai = _ai((None, [_call({"add": [{"name": "a", "text": "A"}]})]), ("Drawn.", []), ("Still drawn.", []))
        draft = await drafting.draft(ai, "Draw", scene_tools.empty_scene(), cache_key="k",
                                     links=[{"from": "A", "to": "B"}])
        assert ai.chat_with_purpose.await_count == 3
        assert draft.issues == [{"check": "missing_link", "from": "A", "to": "B"}]

    @pytest.mark.asyncio
    async def test_a_correction_that_stops_answering_keeps_what_was_drawn(self):
        ai = MagicMock()
        ai.chat_with_purpose = AsyncMock(side_effect=[
            SimpleNamespace(content=None, tool_calls=[_call({"add": [{"name": "a", "text": "A"}]})],
                            usage=USAGE, model="flash", provider="mistral"),
            SimpleNamespace(content="Drawn.", tool_calls=[], usage=USAGE, model="flash", provider="mistral"),
            AIError("rate limited"),
        ])
        draft = await drafting.draft(ai, "Draw", scene_tools.empty_scene(), cache_key="k",
                                     links=[{"from": "A", "to": "B"}])
        assert draft.error is None and draft.patches == [{"add": [{"name": "a", "text": "A"}]}]
        assert draft.issues == [{"check": "missing_link", "from": "A", "to": "B"}]
        assert draft.calls[-1]["kind"] == "correction" and draft.calls[-1]["error"] == "rate limited"


class TestAskedLinks:

    @pytest.mark.parametrize("value,expected", [
        (None, []), ([], []),
        ([{"from": " A ", "to": "B"}], [{"from": "A", "to": "B"}]),
        ("A -> B", None), ([{"from": "A"}], None), ([{"from": "", "to": "B"}], None),
        ([{"from": "A", "to": "B"}] * (drafting.MAX_LINKS + 1), None),
    ])
    def test_links_are_pairs_of_texts_or_refused(self, value, expected):
        assert drafting.asked_links(value) == expected


class TestHandlerChecks:

    @pytest.mark.asyncio
    async def test_what_the_checks_still_find_reaches_the_chatbot(self, service, whiteboard_service):
        draft = drafting.Draft(patches=[{"add": [{"name": "a"}]}], drawn=["a"],
                               issues=[{"check": "missing_link", "from": "A", "to": "B"}])
        with patch.object(drafting, "draft", AsyncMock(return_value=draft)) as drafted:
            result = await service._handle_draft_on_whiteboard(
                {"request": "Draw", "links": [{"from": "A", "to": "B"}]}, context(),
            )
        assert drafted.await_args.kwargs["links"] == [{"from": "A", "to": "B"}]
        assert result["issues"] == [{"check": "missing_link", "from": "A", "to": "B"}]

    @pytest.mark.asyncio
    async def test_malformed_links_are_refused_before_any_draft(self, service, whiteboard_service):
        with patch.object(drafting, "draft", AsyncMock()) as drafted:
            result = await service._handle_draft_on_whiteboard({"request": "Draw", "links": "A -> B"}, context())
        assert result["error"] == "INVALID_LINKS"
        drafted.assert_not_awaited()


class TestChartFigures:
    """A line chart's points and reference lines are figures of the drawing like any text (2026-11-28)."""

    REQUEST = "Trésorerie S1 71 446 €, S2 87 635 € ; seuil d'alerte 186 200 €"

    def test_points_and_a_threshold_given_as_written_are_neither_missing_nor_invented(self):
        scene = _scene({"name": "c", "kind": "chart", "chart": {
            "type": "line", "data": [{"label": "S1", "value": 71446}, {"label": "S2", "value": 87635}],
            "references": [{"label": "Seuil d'alerte", "value": 186200}]}})
        assert drafting.review(scene, ["c"], self.REQUEST, None) == []

    def test_points_converted_to_another_unit_are_found(self):
        scene = _scene({"name": "c", "kind": "chart", "chart": {
            "type": "line", "data": [{"label": "S1", "value": 71.446}, {"label": "S2", "value": 87.635}]}})
        checks = {issue["check"] for issue in drafting.review(scene, ["c"], self.REQUEST, None)}
        assert checks == {"figure_not_in_request", "figure_missing"}


class TestDraftTrace:
    """A drafting is traced like a specialist run: its calls, their tokens, what it drew or why it failed."""

    @pytest.mark.asyncio
    async def test_each_call_of_the_drafter_is_counted_with_its_tokens(self):
        ai = _ai((None, [_call({"add": [{"name": "a", "text": "A"}]})]), ("Top left.", []))
        draft = await drafting.draft(ai, "Draw A", scene_tools.empty_scene(), cache_key="k")
        assert [call["kind"] for call in draft.calls] == ["draft", "draft"]
        assert draft.calls[0]["tool_calls"] == 1 and draft.messages[0]["role"] == "user"
        assert (draft.calls[0]["tokens_in"], draft.calls[0]["tokens_out"], draft.calls[0]["cache_read_tokens"]) == (
            900, 200, 8000,
        )
        assert draft.calls[0]["model"] == "flash" and draft.provider == "mistral"

    @pytest.mark.asyncio
    async def test_a_drafter_that_stops_answering_is_a_result_with_its_calls(self):
        ai = MagicMock()
        ai.chat_with_purpose = AsyncMock(side_effect=AIError("down"))
        draft = await drafting.draft(ai, "Draw", scene_tools.empty_scene(), cache_key="k")
        assert draft.error == "down" and draft.calls[0]["error"] == "down" and draft.patches == []

    @pytest.mark.asyncio
    async def test_the_handler_records_the_drafting_for_the_user_and_tenant(self, service, whiteboard_service):
        draft = drafting.Draft(patches=[{"add": [{"name": "a"}]}], drawn=["a"], note="Top left.",
                               calls=[{"kind": "draft", "latency_ms": 5}], provider="mistral")
        with patch.object(drafting, "draft", AsyncMock(return_value=draft)):
            await service._handle_draft_on_whiteboard({"request": "Draw A"}, context())
        args, kwargs = whiteboard_service.record.await_args
        assert args == (drafting.DRAFTING_PURPOSE, "user-1", "client-1", "Draw A", draft.calls)
        assert kwargs["output"] == {"drawn": ["a"], "note": "Top left.", "issues": []} and kwargs["error"] is None


class TestCorrectionBudget:
    """The checks go back to the drafter on calls of their own, however long it patched (2026-11-28)."""

    @pytest.mark.asyncio
    async def test_a_drafter_that_patches_to_its_last_call_still_gets_its_checks_back(self):
        overlapping = [(None, [_call({"add": [{"name": f"n{i}", "text": "X", "x": 0, "y": 0}]}, f"c{i}")])
                       for i in range(drafting.MAX_DRAFT_ROUNDS - 1)]
        moved = [(None, [_call({"update": [{"name": f"n{i}", "x": 300 * i, "y": 0}
                                           for i in range(drafting.MAX_DRAFT_ROUNDS - 1)]}, "fix")])]
        ai = _ai(*overlapping, ("Drawn.", []), *moved, ("Moved apart.", []))
        draft = await drafting.draft(ai, "Draw", scene_tools.empty_scene(), cache_key="k")
        kinds = [call["kind"] for call in draft.calls]
        assert kinds.count("draft") == drafting.MAX_DRAFT_ROUNDS and kinds.count("correction") == 2
        assert draft.issues == [] and draft.note == "Moved apart."


class TestMeasures:
    """A measure the request quotes is layout, never a figure the drawing must show."""

    def test_pixels_quoted_in_a_request_are_not_missing_figures(self):
        scene = _scene({"name": "k", "kind": "kpi", "value": "4,9 M€", "text": "CA 2025"})
        request = "CA 2025 : 4,9 M€. In the 1280×720 frame (1280 x 720), the arrow sticks out by 310 px; " \
                  "boxes need 236 to 307 px."
        assert drafting.review(scene, ["k"], request, None) == []
