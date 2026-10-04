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


class TestLinkRouting:
    """A link goes round what stands between its two ends instead of through it."""

    ROW = [
        {"name": "A", "x": 0, "y": 0, "width": 120, "height": 60},
        {"name": "B", "x": 300, "y": 0, "width": 120, "height": 60},
        {"name": "C", "x": 600, "y": 0, "width": 120, "height": 60},
    ]

    @staticmethod
    def path(board, name):
        link = scene_tools.find(board, name)
        return [(link["x"] + x, link["y"] + y) for x, y in link["points"]]

    def test_nothing_in_the_way_is_a_straight_link(self):
        board = draw({"add": [*self.ROW, {"name": "ab", "kind": "arrow", "from": "A", "to": "B"}]})
        assert len(self.path(board, "ab")) == 2

    def test_a_link_goes_round_the_box_between_its_ends(self):
        board = draw({"add": [*self.ROW, {"name": "retour", "kind": "arrow", "from": "C", "to": "A"}]})
        path = self.path(board, "retour")
        # Out of C and into A by the same side, along a lane clear of the whole row.
        assert len(path) == 4
        assert path[0] == (660, 60) and path[-1] == (60, 60)
        assert path[1][1] == path[2][1] > 60

    def test_the_lane_keeps_clear_of_what_is_under_the_row(self):
        board = draw({"add": [
            *self.ROW,
            {"name": "dessous", "x": 300, "y": 80, "width": 120, "height": 60},
            {"name": "retour", "kind": "arrow", "from": "C", "to": "A"},
        ]})
        path = self.path(board, "retour")
        # Below is taken: the lane runs above the row instead.
        assert path[1][1] == path[2][1] < 0

    def test_a_link_down_a_column_goes_round_by_the_side(self):
        board = draw({"add": [
            {"name": "haut", "x": 0, "y": 0, "width": 120, "height": 60},
            {"name": "milieu", "x": 0, "y": 140, "width": 120, "height": 60},
            {"name": "bas", "x": 0, "y": 280, "width": 120, "height": 60},
            {"name": "direct", "kind": "arrow", "from": "haut", "to": "bas"},
        ]})
        path = self.path(board, "direct")
        assert len(path) == 4
        assert path[1][0] == path[2][0] > 120

    def test_a_box_drawn_after_the_link_in_the_same_patch_is_seen(self):
        # The patch is routed as a whole once it is applied, whatever order it names things in.
        board = draw({"add": [
            self.ROW[0], self.ROW[2],
            {"name": "retour", "kind": "arrow", "from": "C", "to": "A"},
            self.ROW[1],
        ]})
        assert len(self.path(board, "retour")) == 4

    def test_moving_an_end_routes_its_link_again(self):
        board = draw({"add": [*self.ROW, {"name": "retour", "kind": "arrow", "from": "C", "to": "A"}]})
        board = scene_tools.apply_operations(board, {"update": [{"name": "A", "x": 0, "y": 400}]})
        # B no longer stands between the two: the detour is gone with the reason for it.
        path = self.path(board, "retour")
        assert len(path) == 2
        assert path[-1][1] >= 400

    def test_a_frame_around_the_ends_is_not_in_the_way(self):
        board = draw({"add": [
            {"name": "zone", "kind": "frame", "text": "", "x": -40, "y": -40, "width": 600, "height": 200},
            self.ROW[0], self.ROW[1],
            {"name": "ab", "kind": "arrow", "from": "A", "to": "B"},
        ]})
        assert len(self.path(board, "ab")) == 2

    def test_no_free_lane_leaves_the_link_straight(self):
        walls = [
            {"name": "mur haut", "x": -400, "y": -400, "width": 1600, "height": 380},
            {"name": "mur bas", "x": -400, "y": 80, "width": 1600, "height": 380},
        ]
        board = draw({"add": [*self.ROW, *walls, {"name": "retour", "kind": "arrow", "from": "C", "to": "A"}]})
        assert len(self.path(board, "retour")) == 2


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

    def test_new_rows_alone_redraw_it_with_its_headers(self):
        # Correcting a cell sends the lines again, not the column titles: the update
        # must redraw, not succeed while changing nothing (the caller repeats it).
        board = draw(
            {"add": [{"name": "t", "kind": "table", "headers": ["Item", "Total"], "rows": [["first", "10"]]}]},
            {"update": [{"name": "t", "rows": [["first", "3"]]}]},
        )
        data = described(board)["t"]["data"]
        assert data == {"headers": ["Item", "Total"], "rows": [["first", "3"]]}

    def test_new_headers_alone_redraw_it_with_its_rows(self):
        board = draw(
            {"add": [{"name": "t", "kind": "table", "headers": ["a", "b"], "rows": [["1", "2"]]}]},
            {"update": [{"name": "t", "headers": ["x", "y"]}]},
        )
        assert described(board)["t"]["data"] == {"headers": ["x", "y"], "rows": [["1", "2"]]}

    def test_rows_that_no_longer_fit_the_headers_are_refused(self):
        with pytest.raises(LysError) as error:
            draw(
                {"add": [{"name": "t", "kind": "table", "headers": ["a", "b"], "rows": [["1", "2"]]}]},
                {"update": [{"name": "t", "rows": [["1"]]}]},
            )
        assert error.value.detail == "WHITEBOARD_INVALID_TABLE"

    def test_an_add_of_rows_on_an_existing_table_redraws_it(self):
        board = draw(
            {"add": [{"name": "t", "kind": "table", "headers": ["a"], "rows": [["1"]]}]},
            {"add": [{"name": "t", "rows": [["2"]]}]},
        )
        assert described(board)["t"]["data"]["rows"] == [["2"]]

    def test_table_data_on_what_is_not_a_table_is_refused(self):
        with pytest.raises(LysError) as error:
            draw({"add": [{"name": "n", "text": "note"}]}, {"update": [{"name": "n", "rows": [["1"]]}]})
        assert error.value.detail == "WHITEBOARD_INVALID_TABLE"

    def test_a_redraw_leaves_no_part_of_the_old_grid_behind(self):
        # The rules of a table are lines, like the links a redraw has to keep: told
        # apart by who owns them, or the old rules stay under the new ones.
        board = draw(
            {"add": [{"name": "t", "kind": "table", "headers": ["a", "b"], "rows": [["1", "2"], ["3", "4"]]}]},
            {"update": [{"name": "t", "headers": ["a", "b"], "rows": [["1", "2"]]}]},
        )
        ids = [element["id"] for element in board["elements"]]
        assert len(ids) == len(set(ids))
        assert "t-row-2" not in ids

    def test_a_redraw_keeps_the_links_whole(self):
        board = draw(
            {"add": [
                {"name": "t", "kind": "table", "headers": ["a"], "rows": [["1"]]},
                {"name": "n", "x": 900, "y": 0},
                {"name": "lien", "kind": "arrow", "from": "n", "to": "t", "label": "voir"},
            ]},
            {"update": [{"name": "t", "headers": ["a"], "rows": [["1"], ["2"]]}]},
        )
        assert described(board)["lien"]["label"] == "voir"
        # Bound on both sides: the rebuilt table knows the arrow that ends on it.
        table = scene_tools.find(board, "t")
        assert {"type": "arrow", "id": "lien"} in table["boundElements"]

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

    def test_a_bar_carries_its_name_under_it_and_its_figure_over_it(self):
        board = draw({"add": [{"name": "c", "kind": "chart", "chart": {
            "type": "bar", "title": "CA", "data": [{"label": "A", "value": 3}, {"label": "B", "value": 7}],
        }}]})
        parts = {element["id"]: element for element in board["elements"]}
        title, baseline = parts["c-title"], parts["c"]["y"]
        for position, (label, figure) in enumerate([("A", "3"), ("B", "7")]):
            bar, name, value = parts[f"c-bar-{position}"], parts[f"c-label-{position}"], parts[f"c-value-{position}"]
            assert (name["text"], value["text"]) == (label, figure)
            assert name["y"] >= baseline
            assert value["y"] + value["height"] <= bar["y"]
        # The tallest bar's figure clears the title: neither is written over the other.
        assert parts["c-value-1"]["y"] >= title["y"] + title["height"]

    def test_a_name_too_long_for_its_slot_is_written_on_two_lines(self):
        data = [{"label": f"SOCIETE NUMERO {index}", "value": index + 1} for index in range(6)]
        board = draw({"add": [{"name": "c", "kind": "chart", "chart": {"type": "bar", "data": data}}]})
        name = scene_tools.find(board, "c-label-0")
        assert name["text"].count("\n") == 1
        assert name["originalText"] == "SOCIETE NUMERO 0"

    @pytest.mark.parametrize("value,expected", [
        (924, "924"),
        (6878, "6\u00a0878"),
        (1234567, "1\u00a0234\u00a0567"),
        (1234.5, "1\u00a0234.5"),
        (0.1, "0.1"),
    ])
    def test_a_figure_reads_as_a_figure(self, value, expected):
        # Never an exponent, thousands apart: "1.23457e+06" is not a revenue.
        assert scene_tools._format_figure(value) == expected

    def test_a_redraw_leaves_no_part_of_the_old_chart_behind(self):
        board = draw(
            {"add": [{"name": "c", "kind": "chart", "chart": {
                "type": "bar", "data": [{"label": "A", "value": 3}, {"label": "B", "value": 7}],
            }}]},
            {"update": [{"name": "c", "chart": {"type": "bar", "data": [{"label": "A", "value": 1}]}}]},
        )
        ids = [element["id"] for element in board["elements"]]
        assert len(ids) == len(set(ids))
        assert "c-bar-1" not in ids

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

    BARS = {"type": "bar", "title": "CA", "data": [{"label": "A", "value": 3}, {"label": "B", "value": 7}]}

    def top_of(self, board):
        return min(e["y"] for e in board["elements"] if (e.get("customData") or {}).get("whiteboardOwner") == "c")

    def test_a_bar_chart_is_where_its_top_left_corner_is(self):
        # Its anchor is its baseline: read from there, it was 232 lower and had no height.
        board = draw({"add": [{"name": "c", "kind": "chart", "x": 100, "y": 200, "chart": self.BARS}]})
        entry = described(board)["c"]
        assert (entry["x"], entry["y"]) == (100, 200)
        assert entry["height"] > 200
        assert self.top_of(board) == pytest.approx(200)

    def test_new_data_redraws_a_bar_chart_where_it_stood(self):
        board = draw(
            {"add": [{"name": "c", "kind": "chart", "x": 100, "y": 200, "chart": self.BARS}]},
            {"update": [{"name": "c", "chart": self.BARS}]},
            {"update": [{"name": "c", "chart": self.BARS}]},
        )
        assert self.top_of(board) == pytest.approx(200)

    def test_moving_a_bar_chart_puts_its_top_left_corner_there(self):
        board = draw(
            {"add": [{"name": "c", "kind": "chart", "x": 100, "y": 200, "chart": self.BARS}]},
            {"update": [{"name": "c", "x": 500, "y": 300}]},
        )
        entry = described(board)["c"]
        assert (entry["x"], entry["y"]) == (500, 300)
        assert self.top_of(board) == pytest.approx(300)


class TestFrame:
    """A frame is a zone, and the editor moves what it holds."""

    def test_an_element_can_be_put_in_a_frame(self):
        board = draw({"add": [
            {"name": "zone", "kind": "frame", "text": "Filiales", "x": 0, "y": 0},
            {"name": "A", "frame": "zone", "x": 20, "y": 20},
        ]})
        assert described(board)["a"]["frame"] == "zone"

    def test_a_frame_is_labelled_with_its_text_and_nothing_else(self):
        board = draw({"add": [
            {"name": "zone_filiales", "kind": "frame", "text": "Filiales", "x": 0, "y": 0},
            {"name": "zone_nue", "kind": "frame", "text": "", "x": 600, "y": 0},
        ]})
        assert scene_tools.find(board, "zone_filiales")["name"] == "Filiales"
        # An empty text is a bare zone, never the identifier written on the board.
        assert scene_tools.find(board, "zone_nue")["name"] == ""

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


class TestOverlaps:
    """A caller places blind: the board tells it what it put on top of what."""

    def found(self, *operations):
        board = draw(*operations)
        return scene_tools.overlaps(board, scene_tools.drawn_names(operations[-1]))

    def test_two_notes_drawn_on_each_other_are_reported(self):
        found = self.found({"add": [
            {"name": "a", "x": 0, "y": 0, "width": 200, "height": 100},
            {"name": "b", "x": 150, "y": 90, "width": 200, "height": 100},
        ]})
        assert found == [{"element": "a", "with": "b", "width": 50, "height": 10}]

    def test_neighbours_are_not_an_overlap(self):
        assert self.found({"add": [
            {"name": "a", "x": 0, "y": 0, "width": 200, "height": 100},
            {"name": "b", "x": 0, "y": 100, "width": 200, "height": 100},
            {"name": "c", "x": 201, "y": 0, "width": 200, "height": 100},
        ]}) == []

    def test_a_title_written_under_a_card_is_reported(self):
        found = self.found({"add": [
            {"name": "titre", "kind": "text", "text": "Événements marquants du groupe", "x": 720, "y": 1450},
            {"name": "carte", "x": 740, "y": 1440, "width": 220, "height": 90},
        ]})
        assert [(entry["element"], entry["with"]) for entry in found] == [("titre", "carte")]

    def test_what_sits_inside_a_frame_is_where_it_belongs(self):
        found = self.found({"add": [
            {"name": "zone", "kind": "frame", "text": "", "x": 0, "y": 0, "width": 600, "height": 400},
            {"name": "dedans", "x": 40, "y": 40, "width": 200, "height": 100},
            {"name": "a cheval", "x": 500, "y": 40, "width": 200, "height": 100},
        ]})
        assert [(entry["element"], entry["with"]) for entry in found] == [("zone", "a-cheval")]

    def test_a_link_crossing_something_is_not_an_overlap(self):
        assert self.found({"add": [
            {"name": "a", "x": 0, "y": 0, "width": 100, "height": 60},
            {"name": "entre", "x": 300, "y": 0, "width": 100, "height": 60},
            {"name": "b", "x": 600, "y": 0, "width": 100, "height": 60},
            {"name": "lien", "kind": "arrow", "from": "a", "to": "b", "label": "retour"},
        ]}) == []

    def test_only_what_the_patch_drew_is_checked(self):
        # Two elements already on each other are the board's past, not this call's doing.
        found = self.found(
            {"add": [
                {"name": "a", "x": 0, "y": 0, "width": 200, "height": 100},
                {"name": "b", "x": 100, "y": 50, "width": 200, "height": 100},
            ]},
            {"add": [{"name": "c", "x": 1000, "y": 0, "width": 200, "height": 100}]},
        )
        assert found == []

    def test_a_bar_chart_counts_for_its_whole_box(self):
        found = self.found({"add": [
            {"name": "c", "kind": "chart", "x": 0, "y": 0, "chart": {
                "type": "bar", "data": [{"label": "A", "value": 3}],
            }},
            {"name": "sous le titre", "x": 20, "y": 20, "width": 100, "height": 60},
        ]})
        assert [(entry["element"], entry["with"]) for entry in found] == [("c", "sous-le-titre")]

    def test_a_bar_chart_drawn_before_boxes_were_recorded_still_counts_for_its_bars(self):
        board = draw({"add": [{"name": "c", "kind": "chart", "x": 0, "y": 0, "chart": {
            "type": "bar", "data": [{"label": "A", "value": 3}],
        }}]})
        # As stored by an earlier version: the anchor knows nothing of the figure's box.
        scene_tools.find(board, "c")["customData"].pop("whiteboardBox")
        board = scene_tools.apply_operations(
            board, {"add": [{"name": "sur les barres", "x": 150, "y": 100, "width": 100, "height": 60}]}
        )
        found = scene_tools.overlaps(board, ["sur-les-barres"])
        assert [(entry["element"], entry["with"]) for entry in found] == [("sur-les-barres", "c")]
        assert described(board)["c"]["height"] > 200

    def test_the_report_is_capped_largest_first(self):
        pile = [{"name": f"n{index}", "x": index * 5, "y": 0, "width": 200, "height": 100} for index in range(12)]
        found = self.found({"add": pile})
        assert len(found) == 10
        assert found[0]["width"] >= found[-1]["width"]


class TestShapeSizing:
    """A shape is sized for the room the editor gives its label, not for the label alone."""

    @pytest.mark.parametrize("kind,factor", [("diamond", 2.0), ("ellipse", 2 ** 0.5)])
    def test_a_label_fits_on_one_line_in_its_shape(self, kind, factor):
        board = draw({"add": [{"name": "s", "kind": kind, "text": "Valider ?"}]})
        shape = scene_tools.find(board, "s")
        natural, _ = scene_tools._text_size("Valider ?")
        # What the editor leaves a label: the shape's width over the factor, less the padding.
        assert shape["width"] / factor - 10 >= natural


class TestFocus:
    """What there is to look at: what a patch drew, or what the caller names."""

    def test_a_patch_draws_what_it_adds_and_updates_not_what_it_deletes(self):
        operations = {
            "add": [{"name": "Titre org"}, {"name": "A"}, {"name": "B"}],
            "update": [{"name": "A", "text": "a"}, {"name": "C", "text": "c"}],
            "delete": ["B", "D"],
        }
        assert scene_tools.drawn_names(operations) == ["titre-org", "a", "c"]

    def test_a_delete_alone_draws_nothing(self):
        assert scene_tools.drawn_names({"delete": ["a"]}) == []

    def test_a_focus_resolves_to_the_names_on_the_board(self):
        board = draw({"add": [{"name": "Organigramme"}, {"name": "Titre"}]})
        assert scene_tools.resolve_focus(board, ["Titre", "organigramme", "Titre"]) == ["titre", "organigramme"]

    @pytest.mark.parametrize("names", [["nowhere"], ["organigramme-text"], [], "organigramme", [1]])
    def test_a_focus_on_nothing_is_refused(self, names):
        # A bound label is not a name a caller can use, and an empty focus shows nothing.
        board = draw({"add": [{"name": "Organigramme"}]})
        with pytest.raises(LysError):
            scene_tools.resolve_focus(board, names)


class TestTextMeasurement:
    """The server lays text out with the advances of the face the board
    writes with — the sum the editor's canvas makes once its fonts are loaded."""

    # One line box, in the board's face: font size times that face's line height.
    LINE_BOX = 16 * 1.15

    def test_a_texts_width_is_the_fonts_own_sum_of_advances(self):
        # Ground truth, summed the long way from the face's advance widths
        # (Liberation Sans, metric-compatible with Arial). No pair in this word
        # is kerned, so the canvas gives the same figure.
        width, _ = scene_tools._text_size("Société")
        assert width == pytest.approx(53.37, abs=0.1)

    def test_an_unknown_character_falls_back_generously(self):
        # Not in the table: the historic ratio, never zero — a clipped
        # character is worse than a box slightly too wide.
        width, _ = scene_tools._text_size("\u4e2d")
        assert width > 0

    def test_a_constrained_text_wraps_at_word_boundaries(self):
        # The natural width of one long word cannot be broken: it stays whole
        # and runs wide rather than cutting an IBAN in half.
        long_word = "SIREN-123456789"
        _, height = scene_tools._text_size(long_word, max_width=10)
        assert height == pytest.approx(self.LINE_BOX)

    def test_wrapping_counts_the_lines_the_editor_will_draw(self):
        text = "un rendement en nette amelioration sur l'exercice"
        _, natural = scene_tools._text_size(text)
        _, wrapped = scene_tools._text_size(text, max_width=120)
        assert wrapped > natural
        # One line box per line, unrounded.
        assert wrapped / self.LINE_BOX == pytest.approx(round(wrapped / self.LINE_BOX))


class TestContentSizedTable:
    """A table is sized by its content: columns to their widest cell, rows to
    their tallest wrapped one. The uniform grid starved the narrow columns
    and drowned the wide ones."""

    def table(self, board):
        return next(e for e in board["elements"] if e["type"] == "rectangle")

    def cells(self, board):
        return {e["id"]: e for e in board["elements"] if e["type"] == "text"}

    def test_a_column_is_as_wide_as_its_widest_cell(self):
        board = draw({"add": [{
            "name": "t", "kind": "table",
            "headers": ["N°", "Société"],
            "rows": [["1", "PREFA BLOC AGREGATS"]],
        }]})
        columns = {e["id"] for e in board["elements"] if "-col-" in e["id"]}
        rule = next(e for e in board["elements"] if e["id"] == "t-col-1")
        cell = self.cells(board)["t-cell-0-1"]
        # The Société column starts wide (its content), the N° column narrow.
        assert rule["x"] < 90
        assert cell["width"] > 150

    def test_a_capped_column_wraps_and_the_row_grows(self):
        board = draw({"add": [{
            "name": "t", "kind": "table",
            "headers": ["Société", "Chiffre d'affaires consolidé sur l'exercice 2025, toutes sociétés du groupe"],
            "rows": [["BTP", "924 k€"]],
        }]})
        rows = {e["id"]: e for e in board["elements"] if "-row-" in e["id"]}
        table = self.table(board)
        # The header row carries two wrapped lines: it is taller than the
        # one-line data row.
        header_bottom = rows["t-row-1"]["y"]
        assert header_bottom - table["y"] > 36
        assert table["height"] - (header_bottom - table["y"]) == pytest.approx(36)

    def test_a_wrapped_cell_is_written_with_its_line_breaks(self):
        # The editor draws a fixed-width text as stored and never wraps it on load:
        # the breaks the row was sized for have to be in the text itself.
        header = "Chiffre d'affaires consolidé sur l'exercice 2025, toutes sociétés du groupe"
        board = draw({"add": [{
            "name": "t", "kind": "table",
            "headers": ["Société", header], "rows": [["BTP", "924 k€"]],
        }]})
        cells = self.cells(board)
        assert "\n" in cells["t-cell-0-1"]["text"]
        assert cells["t-cell-0-1"]["text"].replace("\n", " ") == header
        assert cells["t-cell-0-1"]["originalText"] == header
        assert cells["t-cell-1-1"]["text"] == "924 k€"

    def test_a_short_table_is_compact(self):
        board = draw({"add": [{
            "name": "t", "kind": "table",
            "headers": ["a", "b"], "rows": [["1", "2"]],
        }]})
        table = self.table(board)
        # Two columns at the content floor, two rows (header + data) at the
        # row floor: the uniform grid could not have been smaller either.
        assert table["width"] == pytest.approx(160)
        assert table["height"] == pytest.approx(72)

    def test_the_callers_width_scales_the_content_proportions(self):
        board = draw({"add": [{
            "name": "t", "kind": "table", "width": 600,
            "headers": ["N°", "Société"],
            "rows": [["1", "PREFA BLOC AGREGATS"]],
        }]})
        table = self.table(board)
        rule = next(e for e in board["elements"] if e["id"] == "t-col-1")
        # The total is the caller's width; the split keeps the content's
        # proportions - the narrow N° column stays narrower than Société.
        assert table["width"] == pytest.approx(600)
        assert rule["x"] < 300
        assert rule["x"] > 80

    def test_new_data_resizes_the_grid_in_place(self):
        board = draw(
            {"add": [{"name": "t", "kind": "table", "headers": ["a"], "rows": [["1"]]}]},
            {"update": [{"name": "t", "kind": "table",
                         "headers": ["a", "Société"],
                         "rows": [["1", "PREFA BLOC AGREGATS"]]}]},
        )
        table = self.table(board)
        described_entry = described(board)["t"]
        assert described_entry["data"]["headers"] == ["a", "Société"]
        assert table["width"] > 80
