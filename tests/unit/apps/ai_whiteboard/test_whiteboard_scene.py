"""
Unit tests for whiteboard scene manipulation.

``scene`` is pure - a dict in, a dict out - so the rules that hold the board together are
exercised here without a database, a session or a browser. What is tested is what a
caller can get wrong: naming, placement, links left dangling, and every value that
reaches the editor unchecked.
"""

import math

import pytest

from lys.apps.ai_whiteboard.modules.whiteboard import scene as scene_tools
from lys.apps.ai_whiteboard.modules.whiteboard.consts import MAX_ELEMENTS
from lys.core.errors import LysError


def draw(*operations):
    """Apply successive patches from an empty board, the way a conversation does."""
    board = scene_tools.empty_scene()
    for patch in operations:
        board = scene_tools.apply_operations(board, patch)
    return board


def described(board):
    """The board keyed by name, which is how a caller addresses it."""
    return {entry["name"]: entry for entry in scene_tools.describe(board)}


class TestSlugify:
    """Tests for name to id derivation."""

    @pytest.mark.parametrize("name,expected", [
        ("Hypothèse marge 2026", "hypothese-marge-2026"),
        ("hypothese-marge-2026", "hypothese-marge-2026"),
        ("  Trésorerie / BFR  ", "tresorerie-bfr"),
    ])
    def test_folds_to_the_same_id(self, name, expected):
        assert scene_tools.slugify(name) == expected

    def test_refuses_a_name_with_nothing_usable(self):
        with pytest.raises(LysError):
            scene_tools.slugify("...")


class TestNaming:
    """A name is the identity of an element, and the whole basis of idempotence."""

    def test_adding_a_known_name_rewrites_instead_of_duplicating(self):
        board = draw(
            {"add": [{"name": "Marge", "text": "first"}]},
            {"add": [{"name": "marge", "text": "second"}]},
        )
        assert len(scene_tools.element_names(board)) == 1
        assert described(board)["marge"]["text"] == "second"

    def test_updating_an_absent_element_is_refused(self):
        with pytest.raises(LysError):
            draw({"update": [{"name": "nowhere", "text": "x"}]})

    def test_unknown_operation_is_refused(self):
        with pytest.raises(LysError):
            draw({"move": []})


class TestPlacement:
    """Coordinates are the caller's when given, and the board's when not."""

    def test_given_coordinates_are_kept(self):
        board = draw({"add": [{"name": "A", "x": 640, "y": -120}]})
        assert (described(board)["a"]["x"], described(board)["a"]["y"]) == (640, -120)

    def test_half_a_position_is_refused(self):
        with pytest.raises(LysError):
            draw({"add": [{"name": "A", "x": 10}]})

    def test_automatic_placement_avoids_what_is_already_there(self):
        board = draw({"add": [
            {"name": "placed", "x": 0, "y": 0, "width": 240, "height": 160},
            {"name": "auto"},
        ]})
        auto = described(board)["auto"]
        assert (auto["x"], auto["y"]) != (0, 0)

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), "12", True, None])
    def test_a_coordinate_that_is_not_a_number_is_refused(self, value):
        with pytest.raises(LysError):
            draw({"add": [{"name": "A", "x": value, "y": 0}]})

    def test_a_coordinate_past_the_board_is_refused(self):
        with pytest.raises(LysError):
            draw({"add": [{"name": "A", "x": 10 ** 9, "y": 0}]})


class TestSizing:
    """A box exists to hold its text, which is what the fixed-size version failed at."""

    def test_a_long_label_gets_a_taller_box(self):
        short = described(draw({"add": [{"name": "A", "text": "court"}]}))["a"]
        long = described(draw({"add": [{"name": "A", "text": "mot " * 60}]}))["a"]
        assert long["height"] > short["height"]

    def test_rewriting_longer_text_grows_the_box(self):
        board = draw(
            {"add": [{"name": "A", "text": "court"}]},
            {"update": [{"name": "A", "text": "mot " * 60}]},
        )
        assert described(board)["a"]["height"] > 60

    def test_an_explicit_size_wins(self):
        board = draw({"add": [{"name": "A", "text": "court", "width": 400, "height": 300}]})
        assert (described(board)["a"]["width"], described(board)["a"]["height"]) == (400, 300)


class TestStyle:
    """Colours reach a rendered document, so nothing but a colour gets through."""

    def test_a_hexadecimal_colour_is_accepted(self):
        board = draw({"add": [{"name": "A", "background": "#ffc9c9"}]})
        element = scene_tools.find(board, "A")
        assert element["backgroundColor"] == "#ffc9c9"

    @pytest.mark.parametrize("value", ["red", "url(javascript:alert(1))", "#ff", "#12345g", 16])
    def test_anything_else_is_refused(self, value):
        with pytest.raises(LysError):
            draw({"add": [{"name": "A", "background": value}]})


class TestLinks:
    """An arrow is only a link while both its ends exist."""

    def test_an_arrow_binds_the_two_elements_it_names(self):
        board = draw({"add": [
            {"name": "A", "x": 0, "y": 0},
            {"name": "B", "x": 400, "y": 0},
            {"name": "flux", "kind": "arrow", "from": "A", "to": "B", "label": "1,2 M€"},
        ]})
        arrow = described(board)["flux"]
        assert (arrow["from"], arrow["to"], arrow["label"]) == ("a", "b", "1,2 M€")

    def test_an_arrow_to_nothing_is_refused(self):
        with pytest.raises(LysError):
            draw({"add": [{"name": "A"}, {"name": "x", "kind": "arrow", "from": "A", "to": "ghost"}]})

    def test_deleting_an_endpoint_removes_the_arrow_and_every_reference_to_it(self):
        board = draw(
            {"add": [
                {"name": "A", "x": 0, "y": 0},
                {"name": "B", "x": 400, "y": 0},
                {"name": "flux", "kind": "arrow", "from": "A", "to": "B"},
            ]},
            {"delete": ["A"]},
        )
        assert scene_tools.element_names(board) == ["b"]
        # B keeps its own label; what must be gone is every trace of the arrow and of A.
        gone = {"a", "flux"}
        for element in board["elements"]:
            assert not gone & {bound["id"] for bound in element.get("boundElements") or []}
            for side in ("startBinding", "endBinding"):
                assert (element.get(side) or {}).get("elementId") not in gone

    def test_moving_an_endpoint_redraws_the_arrow(self):
        board = draw({"add": [
            {"name": "A", "x": 0, "y": 0},
            {"name": "B", "x": 400, "y": 0},
            {"name": "flux", "kind": "arrow", "from": "A", "to": "B"},
        ]})
        before = described(board)["flux"]["x"]
        board = scene_tools.apply_operations(board, {"update": [{"name": "A", "x": 800, "y": 400}]})
        assert described(board)["flux"]["x"] != before


class TestTable:
    """A table is data: it is drawn from it, and redrawn when it changes."""

    def test_a_table_is_one_named_element_over_many_drawn_ones(self):
        board = draw({"add": [{
            "name": "synthese", "kind": "table",
            "headers": ["Société", "CA"], "rows": [["BTP", "924 k€"]],
        }]})
        assert scene_tools.element_names(board) == ["synthese"]
        assert len(board["elements"]) > 1
        assert described(board)["synthese"]["data"]["headers"] == ["Société", "CA"]

    def test_a_ragged_row_is_refused(self):
        with pytest.raises(LysError):
            draw({"add": [{"name": "t", "kind": "table", "headers": ["a", "b"], "rows": [["1"]]}]})

    def test_new_data_redraws_it_where_it_stood(self):
        board = draw(
            {"add": [{"name": "t", "kind": "table", "headers": ["a"], "rows": [["1"]], "x": 60, "y": 90}]},
            {"update": [{"name": "t", "headers": ["a", "b"], "rows": [["1", "2"], ["3", "4"]]}]},
        )
        entry = described(board)["t"]
        assert (entry["x"], entry["y"]) == (60, 90)
        assert entry["data"]["rows"] == [["1", "2"], ["3", "4"]]

    def test_deleting_it_removes_every_part(self):
        board = draw(
            {"add": [{"name": "t", "kind": "table", "headers": ["a", "b"], "rows": [["1", "2"]]}]},
            {"delete": ["t"]},
        )
        assert board["elements"] == []


class TestChart:
    """Bars are drawn, the rest travels as its own data."""

    def test_a_bar_chart_is_drawn_natively(self):
        board = draw({"add": [{"name": "c", "kind": "chart", "chart": {
            "type": "bar", "data": [{"label": "A", "value": 3}, {"label": "B", "value": 7}],
        }}]})
        assert any(element["type"] == "rectangle" for element in board["elements"])
        assert not any(element["type"] == "image" for element in board["elements"])

    def test_a_pie_travels_as_a_spec_with_no_bytes(self):
        board = draw({"add": [{"name": "c", "kind": "chart", "chart": {
            "type": "pie", "data": [{"label": "A", "value": 3}],
        }}]})
        image = scene_tools.find(board, "c")
        assert image["type"] == "image" and image["fileId"]
        assert board["files"] == {}
        assert described(board)["c"]["data"]["type"] == "pie"

    @pytest.mark.parametrize("chart", [
        {"type": "donut", "data": [{"label": "A", "value": 1}]},
        {"type": "bar", "data": []},
        {"type": "bar", "data": [{"label": "A"}]},
        {"type": "pie", "data": [{"label": "A", "value": 0}]},
        {"type": "bar", "data": [{"label": "A", "value": math.nan}]},
    ])
    def test_data_that_describes_no_chart_is_refused(self, chart):
        with pytest.raises(LysError):
            draw({"add": [{"name": "c", "kind": "chart", "chart": chart}]})

    def test_a_drawn_figure_cannot_be_stretched(self):
        board = draw({"add": [{"name": "c", "kind": "chart", "chart": {
            "type": "bar", "data": [{"label": "A", "value": 3}],
        }}]})
        with pytest.raises(LysError):
            scene_tools.apply_operations(board, {"update": [{"name": "c", "width": 900}]})

    def test_it_moves_as_one_thing(self):
        board = draw(
            {"add": [{"name": "c", "kind": "chart", "x": 0, "y": 0, "chart": {
                "type": "bar", "data": [{"label": "A", "value": 3}, {"label": "B", "value": 5}],
            }}]},
            {"update": [{"name": "c", "x": 500, "y": 300}]},
        )
        parts = [e for e in board["elements"] if (e.get("customData") or {}).get("whiteboardOwner") == "c"]
        assert parts and all(element["x"] >= 500 for element in parts)


class TestFrame:
    """A frame is a zone, and the editor moves what it holds."""

    def test_an_element_can_be_put_in_a_frame(self):
        board = draw({"add": [
            {"name": "zone", "kind": "frame", "text": "Filiales", "x": 0, "y": 0},
            {"name": "A", "frame": "zone", "x": 20, "y": 20},
        ]})
        assert described(board)["a"]["frame"] == "zone"

    def test_an_unknown_frame_is_refused(self):
        with pytest.raises(LysError):
            draw({"add": [{"name": "A", "frame": "nowhere"}]})


class TestAtomicity:
    """A patch is drawn whole or not at all."""

    def test_a_refused_operation_leaves_the_board_untouched(self):
        board = draw({"add": [{"name": "A", "text": "kept"}]})
        with pytest.raises(LysError):
            scene_tools.apply_operations(board, {"add": [
                {"name": "B", "text": "never"},
                {"name": "C", "kind": "arrow", "from": "B", "to": "ghost"},
            ]})
        assert scene_tools.element_names(board) == ["a"]

    def test_a_board_past_its_cap_is_refused(self):
        board = draw({"add": [{"name": f"n{index}"} for index in range(40)]})
        with pytest.raises(LysError):
            scene_tools.apply_operations(board, {"add": [
                {"name": f"t{index}", "kind": "table",
                 "headers": ["a", "b", "c", "d", "e"], "rows": [["1"] * 5] * 20}
                for index in range(4)
            ]})


class TestDescribe:
    """What a caller reads back is what it can act on: names, texts and geometry."""

    def test_bound_labels_are_folded_into_their_shape(self):
        board = draw({"add": [{"name": "A", "text": "libellé"}]})
        entries = scene_tools.describe(board)
        assert len(entries) == 1 and entries[0]["text"] == "libellé"

    def test_geometry_is_reported(self):
        board = draw({"add": [{"name": "A", "x": 120, "y": 240, "width": 200, "height": 100}]})
        entry = described(board)["a"]
        assert (entry["x"], entry["y"], entry["width"], entry["height"]) == (120, 240, 200, 100)

    def test_every_kind_reads_back_under_its_own_kind(self):
        board = draw({"add": [
            {"name": "n"},
            {"name": "e", "kind": "ellipse"},
            {"name": "d", "kind": "diamond"},
            {"name": "t", "kind": "text", "text": "titre"},
            {"name": "f", "kind": "frame"},
            {"name": "a", "kind": "arrow", "from": "n", "to": "e"},
        ]})
        kinds = {name: entry["kind"] for name, entry in described(board).items()}
        assert kinds == {"n": "note", "e": "ellipse", "d": "diamond", "t": "text", "f": "frame", "a": "arrow"}


class TestPatchShape:
    """A patch comes from a model: a wrong shape is refused as data, never as a crash."""

    @pytest.mark.parametrize("patch", [
        ["add"],
        {"add": "note"},
        {"add": ["note"]},
        {"add": [{"text": "no name"}]},
        {"add": [{"name": 3}]},
        {"update": [{"name": ["x"]}]},
        {"delete": "marge"},
        {"delete": [1]},
    ])
    def test_malformed_patch_raises_lys_error(self, patch):
        with pytest.raises(LysError):
            scene_tools.apply_operations(scene_tools.empty_scene(), patch)

    def test_empty_operations_are_accepted(self):
        board = scene_tools.apply_operations(scene_tools.empty_scene(), {"add": None, "delete": []})
        assert board["elements"] == []


class TestValidateScene:
    """A scene saved by the editor is input: its envelope is checked, its size bounded."""

    LIMIT = 10_000

    def test_accepts_an_empty_scene(self):
        scene_tools.validate_scene(scene_tools.empty_scene(), self.LIMIT)

    def test_accepts_a_scene_built_by_the_app(self):
        scene_tools.validate_scene(draw({"add": [{"name": "a", "text": "x"}]}), self.LIMIT)

    @pytest.mark.parametrize("scene", [
        None,
        [],
        "scene",
        {},
        {"elements": {}},
        {"elements": ["a"]},
        {"elements": [{"id": "a"}]},
        {"elements": [{"type": "rectangle"}]},
        {"elements": [{"id": 1, "type": "rectangle"}]},
        {"elements": [], "appState": []},
        {"elements": [], "files": "x"},
    ])
    def test_refuses_what_is_not_a_scene(self, scene):
        with pytest.raises(LysError) as error:
            scene_tools.validate_scene(scene, self.LIMIT)
        assert error.value.detail == "WHITEBOARD_INVALID_SCENE"

    def test_refuses_too_many_elements(self):
        elements = [{"id": str(i), "type": "rectangle"} for i in range(MAX_ELEMENTS + 1)]
        with pytest.raises(LysError):
            scene_tools.validate_scene({"elements": elements}, 10**9)

    def test_refuses_a_scene_over_the_size_limit(self):
        scene = {"elements": [], "files": {"img": "x" * 200}}
        with pytest.raises(LysError) as error:
            scene_tools.validate_scene(scene, 100)
        assert error.value.detail == "WHITEBOARD_SCENE_TOO_LARGE"

    def test_refuses_a_non_finite_number(self):
        scene = {"elements": [{"id": "a", "type": "rectangle", "x": float("nan")}]}
        with pytest.raises(LysError):
            scene_tools.validate_scene(scene, self.LIMIT)
