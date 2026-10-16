"""
Pure scene manipulation: no session, no entity, no I/O.

The Excalidraw scene is a plain dict, so everything here is a dict in and a dict out -
which makes the rules that matter (naming, idempotence, binding cleanup, geometry
validation) testable without a database or a browser.

Two invariants hold the whole design together, and only two:

- **An id is derived from its name, never sent.** One source of truth, so the same name
  can only ever designate the same element - which is what makes a patch idempotent and
  what lets a writer revise its own board instead of covering it in near-duplicates.
- **Nothing reaches the scene unvalidated.** Coordinates, sizes and colours are written
  into a document the editor renders without checking, so a NaN or an unclosed colour
  string is a board that fails to open, not a board that looks wrong.

Placement, by contrast, belongs to the caller. An earlier version owned it - every
element dropped into the next cell of a grid - and the result was that a caller asking
for a diagram got a row of boxes: the structure it was trying to express had nowhere to
go. Coordinates are therefore optional, not forbidden. What the caller omits, the grid
still places, and the two coexist because automatic placement skips the cells an element
already covers.
"""

import json
import math
import re
import time
import unicodedata
from random import randint
from typing import Any, Collection, Dict, Iterable, List, Optional, Sequence, Tuple

from lys.apps.ai_whiteboard.modules.whiteboard.font_metrics import CHAR_WIDTHS
from lys.apps.ai_whiteboard.errors import (
    WHITEBOARD_ELEMENT_NAME_REQUIRED,
    WHITEBOARD_INVALID_CHART,
    WHITEBOARD_INVALID_COLOR,
    WHITEBOARD_INVALID_GEOMETRY,
    WHITEBOARD_INVALID_OPERATION,
    WHITEBOARD_INVALID_SCENE,
    WHITEBOARD_INVALID_TABLE,
    WHITEBOARD_SCENE_TOO_LARGE,
    WHITEBOARD_TEXT_TOO_LONG,
    WHITEBOARD_TOO_MANY_ELEMENTS,
    WHITEBOARD_UNKNOWN_ELEMENT,
    WHITEBOARD_UNKNOWN_ELEMENT_KIND,
    WHITEBOARD_UNKNOWN_OPERATION,
)
from lys.apps.ai_whiteboard.modules.whiteboard.consts import (
    ADD_ITEM_FIELDS,
    ALIGNMENTS,
    BOUND_TEXT_PADDING,
    CELL_HEIGHT,
    CELL_WIDTH,
    CHAR_WIDTH_RATIO,
    CHART_CAPTION_FONT_RATIO,
    CHART_HEIGHT,
    CHART_LABEL_BAND,
    CHART_VALUE_BAND,
    CHART_VALUE_GAP,
    CHART_WIDTH,
    CORNERS,
    DEFAULT_BACKGROUND,
    DEFAULT_CORNERS,
    DEFAULT_STROKE,
    DEFAULT_TEXT_SIZE,
    DEFAULT_THICKNESS,
    DIAMOND_PADDING_FACTOR,
    ELLIPSE_PADDING_FACTOR,
    FONT_FAMILY,
    FONT_SIZE,
    FRAME_TEXT_SIZE,
    GRID_COLUMNS,
    IMAGE_CHART_TYPES,
    LABELLED_SHAPES,
    LINE_HEIGHT,
    LINEAR_KINDS,
    LINK_LANE_ATTEMPTS,
    LINK_LANE_MARGIN,
    MAX_CHART_POINTS,
    MAX_COORDINATE,
    MAX_ELEMENTS,
    MAX_GRID_ROWS,
    MAX_REPORTED_OVERLAPS,
    MAX_SIZE,
    MAX_TABLE_COLUMNS,
    MAX_TABLE_ROWS,
    MAX_TEXT_LENGTH,
    MIN_SHAPE_HEIGHT,
    MIN_SHAPE_WIDTH,
    MIN_SIZE,
    NOTE_BACKGROUND,
    NOTE_WIDTH,
    OPERATION_ADD,
    OPERATION_DELETE,
    OPERATION_KEYS,
    OPERATION_THEME,
    OPERATION_UPDATE,
    OVERLAP_TOLERANCE,
    SERIES_COLORS,
    SLIDE_ROW_OVERLAP_SHARE,
    STACK_GAP,
    STROKE_COLOR,
    STROKES,
    TABLE_COLUMN_MAX_WIDTH,
    TABLE_COLUMN_MIN_WIDTH,
    TABLE_ROW_HEIGHT,
    TEXT_SIZES,
    THEME_FIELDS,
    THEME_STROKE_KEY,
    THICKNESSES,
    TRANSPARENT,
    UPDATE_ITEM_FIELDS,
    ChartType,
    ElementKind,
)
from lys.core.errors import LysError

# Suffix of the text element bound inside a shape. Derived, never sent: the caller knows
# one name for the shape, and the pair moves together.
TEXT_SUFFIX = "-text"

# Marks every element a composite kind (a table, a chart) is made of, so the dozens of
# rectangles and texts behind one name can be found, moved and removed as one thing.
# Excalidraw ignores customData it does not know and carries it through a round trip,
# which is what makes it the right place for our own bookkeeping.
OWNER_KEY = "whiteboardOwner"
KIND_KEY = "whiteboardKind"
SPEC_KEY = "whiteboardSpec"
# The rectangle a figure occupies, relative to its anchor: [dx, dy, width, height]. Set
# when the anchor is not the figure's outline - a bar chart hangs from its baseline, a
# line with no height - so that "where is it" and "put it there" mean the figure's
# top-left corner for every kind, the way a caller thinks of it.
BOX_KEY = "whiteboardBox"
# What a table or a chart was drawn with beyond its data - text size, alignment, the
# width and height its caller gave - so a redraw from new figures keeps it. Kept apart
# from the spec: the spec is what the figure says, and is read back as its data.
LAYOUT_KEY = "whiteboardLayout"
LAYOUT_FIELDS = ("size", "align", "width", "height")

# The parts of an element that carry no line: a look (stroke, corners, thickness) does
# not apply to them.
_UNDRESSED_TYPES = ("text", "image", "frame")
# Each named look: the operation field, its choices, the editor field it resolves to.
_LOOK_FIELDS = (
    ("stroke", STROKES, "roughness"),
    ("corners", CORNERS, "roundness"),
    ("thickness", THICKNESSES, "strokeWidth"),
)
# The fields of an item that name a choice or a frame: strings, checked before anything
# reads them - a list there would surface as a TypeError, not as an answer to the model.
_NAME_FIELDS = ("frame", "size", "align", "stroke", "corners", "thickness")

_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def empty_scene() -> Dict[str, Any]:
    """A scene with nothing on it, in the shape the editor expects."""
    return {"elements": [], "appState": {}, "files": {}}


def slugify(name: str) -> str:
    """
    Derive an element id from a human name.

    Accents are folded and everything that is not a letter or a digit becomes a dash, so
    "Hypothese marge 2026" and "hypothese-marge-2026" designate the same element. That
    collapsing is the point: it is what makes a second mention of the same subject update
    rather than duplicate.
    """
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", folded).strip("-").lower()
    if not slug:
        raise LysError(WHITEBOARD_ELEMENT_NAME_REQUIRED, f"Name '{name}' has no usable characters")
    return slug


# ==================== Validation ====================


def _number(value: Any, field: str, minimum: float, maximum: float) -> float:
    """
    Read a number the caller supplied, or refuse it.

    ``bool`` is rejected explicitly because it is an ``int`` in Python and ``x=True``
    would silently place an element at 1. Infinities and NaN are rejected because JSON
    accepts them, the editor does not, and the failure surfaces as a blank canvas.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LysError(WHITEBOARD_INVALID_GEOMETRY, f"'{field}' must be a number, got {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise LysError(WHITEBOARD_INVALID_GEOMETRY, f"'{field}' must be a finite number")
    if not minimum <= number <= maximum:
        raise LysError(WHITEBOARD_INVALID_GEOMETRY, f"'{field}' must be between {minimum} and {maximum}, got {number}")
    return number


def _coordinate(value: Any, field: str) -> float:
    return _number(value, field, -MAX_COORDINATE, MAX_COORDINATE)


def _size(value: Any, field: str) -> float:
    return _number(value, field, MIN_SIZE, MAX_SIZE)


def _color(value: Any, field: str) -> str:
    """
    A colour the editor can render, and nothing else.

    The scene is a document rendered in the user's browser, so a colour is a string that
    travels from a model straight into a stylesheet-like position. A whitelist pattern
    costs nothing and closes that door without a thought about what CSS would do with the
    rest.
    """
    if not isinstance(value, str):
        raise LysError(WHITEBOARD_INVALID_COLOR, f"'{field}' must be a colour string")
    color = value.strip()
    if color == TRANSPARENT or _COLOR_PATTERN.match(color):
        return color
    raise LysError(
        WHITEBOARD_INVALID_COLOR,
        f"'{field}' must be an hexadecimal colour such as '#ffc9c9', or 'transparent', got '{value}'",
    )


def _text_value(value: Any, field: str = "text") -> str:
    """Text short enough to be read on a board rather than pasted onto one."""
    text = "" if value is None else str(value)
    if len(text) > MAX_TEXT_LENGTH:
        raise LysError(
            WHITEBOARD_TEXT_TOO_LONG,
            f"'{field}' is {len(text)} characters, the limit is {MAX_TEXT_LENGTH}. Put the detail in the chat",
        )
    return text


# ==================== Text measurement ====================


def _char_width(char: str, font_size: float) -> float:
    """One character's advance, in the face the editor measures with.

    The table holds the advances of the face the board writes with, which is
    what the canvas sums (kerning aside — see font_metrics.py). A character
    the table does not carry falls back to the historic generous ratio:
    unknown is not invisible, and a box slightly too wide is invisible where
    a clipped character is not.
    """
    return CHAR_WIDTHS.get(char, CHAR_WIDTH_RATIO) * font_size


def _text_width(text: str, font_size: float = FONT_SIZE) -> float:
    return sum(_char_width(char, font_size) for char in text)


def _wrap(text: str, max_width: float, font_size: float = FONT_SIZE) -> List[str]:
    """
    Break text into lines that fit ``max_width``, keeping the caller's own line breaks.

    Words longer than a line are left whole rather than cut: a broken IBAN or SIREN is
    worse than a line that runs slightly wide, and the editor draws it either way.
    """
    lines: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = f"{current} {word}".strip()
            if not current or _text_width(candidate, font_size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _wrapped(text: str, max_width: float, font_size: float = FONT_SIZE) -> str:
    """
    A text as it has to be WRITTEN in a box of fixed width: its lines already broken.

    The editor draws a fixed-width text exactly as stored. It wraps one while the user
    types in it, never when a scene is loaded - so a text handed over on one line
    stays on one line, runs out of its box and over its neighbour, whatever height
    was reserved for the lines it should have had. The breaks are therefore made
    here, by the same rule that sized the box, and the unbroken text goes in
    ``originalText``, which is what the editor re-wraps from when the user edits it.
    """
    return "\n".join(_wrap(text, max_width, font_size))


def _text_size(
    text: str, font_size: float = FONT_SIZE, max_width: Optional[float] = None
) -> Tuple[float, float]:
    """
    How much room a text needs.

    Measured from the font's own advance widths — the sum the editor's
    canvas makes once its fonts are loaded, which is the geometry the board
    settles on. The lines break at word boundaries the way the
    editor wraps; the height is one line box per line, unrounded like the
    editor leaves them.
    """
    if max_width:
        lines = _wrap(text, max_width, font_size)
    else:
        lines = text.split("\n")
    width = max((_text_width(line, font_size) for line in lines), default=0)
    return width, len(lines) * font_size * LINE_HEIGHT


# ==================== Element factory ====================


def _now_ms() -> int:
    return int(time.time() * 1000)


def _base_element(element_id: str, element_type: str, **fields: Any) -> Dict[str, Any]:
    """
    The fields every Excalidraw element carries.

    Deliberately a subset. The editor restores what is missing when a scene is loaded,
    and the fields left out here (roundness, link, locked...) have no meaning for a board
    drawn by a service. Keeping the factory in one place is what makes that a single edit
    if the retained package version turns out to want more.
    """
    element = {
        "id": element_id,
        "type": element_type,
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0,
        "angle": 0,
        "strokeColor": STROKE_COLOR,
        "backgroundColor": TRANSPARENT,
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "seed": randint(1, 2 ** 31),
        "version": 1,
        "versionNonce": randint(1, 2 ** 31),
        "isDeleted": False,
        "boundElements": [],
        "updated": _now_ms(),
    }
    element.update(fields)
    return element


def _touch(element: Dict[str, Any]) -> None:
    """Mark an element as changed. Excalidraw compares versions to reconcile scenes."""
    element["version"] = element.get("version", 1) + 1
    element["versionNonce"] = randint(1, 2 ** 31)
    element["updated"] = _now_ms()


def _index(elements: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {e["id"]: e for e in elements}


def _owner(element: Dict[str, Any]) -> Optional[str]:
    """The composite an element belongs to, if any."""
    return (element.get("customData") or {}).get(OWNER_KEY)


def _family(elements: Sequence[Dict[str, Any]], element_id: str) -> List[Dict[str, Any]]:
    """A named element and every part drawn under its name - its bound label aside."""
    by_id = _index(elements)
    return [by_id[element_id]] + [e for e in elements if _owner(e) == element_id and e["id"] != element_id]


def _is_anchor(element: Dict[str, Any]) -> bool:
    """
    Whether an element is one a caller named.

    Bound labels and the parts of a table or a chart are drawn by this module and have no
    name of their own; listing them would hand a caller ids it never created and cannot
    act on.
    """
    if element.get("containerId"):
        return False
    owner = _owner(element)
    return owner is None or owner == element["id"]


# ==================== Placement ====================


def _footprint(element: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """The rectangle an element covers, normalised so width and height are positive."""
    x, y = float(element.get("x", 0)), float(element.get("y", 0))
    width, height = float(element.get("width", 0)), float(element.get("height", 0))
    return min(x, x + width), min(y, y + height), abs(width), abs(height)


def _box(
    element: Dict[str, Any],
    elements: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[float, float, float, float]:
    """
    The rectangle a NAMED element occupies on the board: x, y, width, height.

    Its own geometry for everything whose anchor is its outline. A figure that records a
    box (see BOX_KEY) answers with that instead: read from the anchor of a bar chart, a
    position was its baseline and a height was zero - so a redraw "where it stood" put
    the chart a whole chart lower each time, and a caller told to place something under
    it was given the wrong bottom.

    A bar chart drawn before boxes were recorded has none. Given the scene, its box is
    read from the parts it is made of - without it the chart is a line to everything
    that looks for room on the board, and the next element lands on its bars.
    """
    box = (element.get("customData") or {}).get(BOX_KEY)
    if box:
        dx, dy, width, height = box
        return float(element.get("x", 0)) + dx, float(element.get("y", 0)) + dy, width, height
    if elements is not None and element.get("type") == "line" and _owner(element) == element["id"]:
        parts = [_footprint(part) for part in elements if _owner(part) == element["id"]]
        left = min(x for x, _, _, _ in parts)
        top = min(y for _, y, _, _ in parts)
        right = max(x + width for x, _, width, _ in parts)
        bottom = max(y + height for _, y, _, height in parts)
        return left, top, right - left, bottom - top
    return _footprint(element)


def _overlaps(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])


def _auto_position(
    elements: Sequence[Dict[str, Any]], width: float, height: float, frame: Optional[Dict[str, Any]] = None,
) -> Tuple[float, float]:
    """
    Where an element goes when the caller did not say.

    The first grid cell, scanning left to right then down, whose rectangle no existing
    element covers. That is what lets placed and unplaced elements share a board: a
    caller that positions a diagram by hand and then adds a note without coordinates gets
    the note beside the diagram, not on top of it.

    In a frame, the grid is the frame's: it starts at its corner and stays inside it,
    among the frame's own members. A board dense enough to fill the scanned rows gets the
    element stacked underneath everything, which is always free.
    """
    occupied = [
        _footprint(e) for e in elements
        if not e.get("containerId") and e.get("type") not in ("arrow", "line", "frame")
        and (frame is None or e.get("frameId") == frame["id"])
    ]
    origin_x, origin_y = (frame["x"], frame["y"]) if frame else (0.0, 0.0)
    columns = max(1, int(frame["width"] // CELL_WIDTH)) if frame else GRID_COLUMNS
    rows = max(1, int(frame["height"] // CELL_HEIGHT)) if frame else MAX_GRID_ROWS
    for row in range(rows):
        for column in range(columns):
            candidate = (origin_x + column * CELL_WIDTH, origin_y + row * CELL_HEIGHT, width, height)
            if not any(_overlaps(candidate, taken) for taken in occupied):
                return candidate[0], candidate[1]
    bottom = max((y + h for _, y, _, h in occupied), default=origin_y)
    return origin_x, bottom + STACK_GAP


def _frame_id_for(frame_name: str, by_id: Dict[str, Any]) -> str:
    """The id of a named frame that is on the board - and is a frame."""
    frame_id = slugify(frame_name)
    frame = by_id.get(frame_id)
    if frame is None or frame.get("type") != "frame":
        raise LysError(WHITEBOARD_UNKNOWN_ELEMENT, f"Frame '{frame_id}' is not on the board")
    return frame_id


def _frame_named(operation: Dict[str, Any], elements: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The frame an operation names, checked to be on the board; None when it names none."""
    if not operation.get("frame"):
        return None
    by_id = _index(elements)
    return by_id[_frame_id_for(operation["frame"], by_id)]


def _origin(frame: Optional[Dict[str, Any]]) -> Tuple[float, float]:
    """Where coordinates count from: a frame's top-left corner, or the board's origin."""
    return (frame["x"], frame["y"]) if frame is not None else (0.0, 0.0)


def _resolve_position(
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    width: float,
    height: float,
) -> Tuple[float, float]:
    """
    The position the caller gave, or the first free cell. Both, never half of each.

    In a frame, both count from the frame: a given position is offset by it, and the
    free cell is looked for inside it, so an unplaced element lands on its slide and
    not on the board's first empty row. A slide is a sheet whatever row of the deck it
    sits on - that is how anyone thinks of one, and what a caller laying out five of
    them did unasked: the same y for the same thing on every slide. Read as the
    board's, those landed five slides' worth of elements on the first one.
    """
    frame = _frame_named(operation, elements)
    origin_x, origin_y = _origin(frame)
    has_x, has_y = operation.get("x") is not None, operation.get("y") is not None
    if has_x and has_y:
        return origin_x + _coordinate(operation["x"], "x"), origin_y + _coordinate(operation["y"], "y")
    if has_x or has_y:
        raise LysError(WHITEBOARD_INVALID_GEOMETRY, "'x' and 'y' go together: give both or neither")
    return _auto_position(elements, width, height, frame)


# ==================== Shapes ====================


def _style(operation: Dict[str, Any], default_background: str = TRANSPARENT) -> Dict[str, Any]:
    """The look a caller may set on any shape, validated."""
    style: Dict[str, Any] = {
        "strokeColor": STROKE_COLOR,
        "backgroundColor": default_background,
    }
    if operation.get("color") is not None:
        style["strokeColor"] = _color(operation["color"], "color")
    if operation.get("background") is not None:
        style["backgroundColor"] = _color(operation["background"], "background")
    return style


def _named(operation: Dict[str, Any], field: str, choices: Collection[str]) -> Optional[str]:
    """A named choice an operation makes, validated; None when it makes none."""
    name = operation.get(field)
    if name is None:
        return None
    if not isinstance(name, str) or name not in choices:
        raise LysError(
            WHITEBOARD_INVALID_OPERATION, f"Unknown {field} {name!r}. Use one of: {', '.join(choices)}",
        )
    return name


def _size_choice(operation: Dict[str, Any]) -> str:
    """
    The text size an operation asks for, by name - or, unnamed, the one where it lands.

    "large" inside a frame, "normal" elsewhere: a frame is a slide, read from across a
    room, and a caller that forgot to say so must not produce a deck nobody at the table
    can read.
    """
    return _named(operation, "size", TEXT_SIZES) or (FRAME_TEXT_SIZE if operation.get("frame") else DEFAULT_TEXT_SIZE)


def _font_size(operation: Dict[str, Any]) -> float:
    """The font size an operation asks for, or the one where it lands (see ``_size_choice``)."""
    return TEXT_SIZES[_size_choice(operation)]


# What a cell holds when it holds a figure: digits with their separators, a sign, a unit
# or a percentage, nothing else - "7 356 k€", "-8,5 %", "62 j", "+123 k€/an", "n/a" is text.
# The digit run and the unit share no character, so a long cell is matched in linear time.
_FIGURE_PATTERN = re.compile(r"^[+\-−~≈]?\s*\d[\d\s.,\u202f\u00a0]*[a-zA-Z€$%/]{0,8}$")


def _cell_align(cell: str, is_header: bool) -> str:
    """
    Where a table cell's text sits when nobody said: the way a financial table reads.

    Headers centred, figures right so their units and decimals line up, labels left.
    """
    if is_header:
        return "center"
    return "right" if _FIGURE_PATTERN.match(cell.strip()) else "left"


def _align(operation: Dict[str, Any], current: str = "left") -> str:
    """How a text is aligned, by name; the current way when the operation says nothing."""
    return _named(operation, "align", ALIGNMENTS) or current


def _size_name(font_size: Any) -> Optional[str]:
    """The name of a text size, for reading a board back; None for the default."""
    for name, value in TEXT_SIZES.items():
        if value == font_size and name != DEFAULT_TEXT_SIZE:
            return name
    return None


def theme(scene: Dict[str, Any]) -> Dict[str, str]:
    """
    The board's look: its background and the stroke its elements are drawn with.

    Read defensively: the appState is saved wholesale by the editor and only its envelope
    is validated, so a value no name covers falls back on the default rather than being
    trusted - an unknown stroke would otherwise fail every later drawing on the board.
    """
    app_state = scene.get("appState") or {}
    background = app_state.get("viewBackgroundColor")
    stroke = app_state.get(THEME_STROKE_KEY)
    return {
        "background": background if isinstance(background, str) and _COLOR_PATTERN.match(background)
        else DEFAULT_BACKGROUND,
        "stroke": stroke if isinstance(stroke, str) and stroke in STROKES else DEFAULT_STROKE,
    }


def _set_theme(scene: Dict[str, Any], operation: Any) -> Dict[str, Any]:
    """The scene with its look changed. Nothing already drawn is redrawn: a theme is a default."""
    if not isinstance(operation, dict):
        raise LysError(WHITEBOARD_INVALID_OPERATION, "'theme' is an object with background and stroke")
    unknown = sorted(set(operation) - set(THEME_FIELDS))
    if unknown:
        raise LysError(WHITEBOARD_INVALID_OPERATION, f"Unknown theme field(s) {', '.join(map(repr, unknown))}")
    app_state = dict(scene.get("appState") or {})
    if operation.get("background") is not None:
        app_state["viewBackgroundColor"] = _color(operation["background"], "background")
    stroke = _named(operation, "stroke", STROKES)
    if stroke is not None:
        app_state[THEME_STROKE_KEY] = stroke
    return {**scene, "appState": app_state}


def _asks_look(operation: Dict[str, Any]) -> bool:
    """Whether an operation names any part of an element's look."""
    return any(operation.get(field) is not None for field, _, _ in _LOOK_FIELDS)


def _look(operation: Dict[str, Any], default_stroke: Optional[str] = None) -> Dict[str, Any]:
    """
    The editor fields an operation's named look resolves to.

    A new element takes the board's stroke when it names none (``default_stroke``); an
    update changes only what it names.
    """
    look: Dict[str, Any] = {}
    for field, choices, key in _LOOK_FIELDS:
        name = _named(operation, field, choices)
        if name is None and field == "stroke":
            name = default_stroke
        if name is not None:
            look[key] = choices[name]
    return look


def _look_names(element: Dict[str, Any]) -> Dict[str, str]:
    """
    The named look an element is drawn with, as far as names reach.

    Nothing for an element with no line - its roughness is the editor's default and
    means nothing on a text. A value no name maps to (a stroke set by hand in the
    editor) is left out rather than guessed.
    """
    if element.get("type") in _UNDRESSED_TYPES:
        return {}
    names: Dict[str, str] = {}
    for field, choices, key in _LOOK_FIELDS:
        name = next((n for n, value in choices.items() if value == element.get(key)), None)
        if name is not None:
            names[field] = name
    return names


def _apply_look(parts: Sequence[Dict[str, Any]], look: Dict[str, Any], asked: bool = False) -> None:
    """
    Dress every drawn part of an element; its texts carry no stroke.

    An element made of nothing but text or picture - a free text, an image chart - has
    no line to dress. A look asked for it is refused rather than dropped: dropped, the
    caller is told its title is bold when nothing changed.
    """
    dressed = [part for part in parts if part.get("type") not in _UNDRESSED_TYPES]
    if asked and not dressed:
        raise LysError(
            WHITEBOARD_INVALID_OPERATION,
            f"'{parts[0]['id']}' has no line to dress: stroke, corners and thickness apply to shapes, "
            "links, tables and bar charts - use 'color' and 'size' on a text",
        )
    for part in dressed:
        part.update(look)
        _touch(part)


def _relook(elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any]) -> None:
    """Change the look of a named element and everything it is made of, keeping what is not said."""
    if _asks_look(operation):
        _apply_look(_family(elements, element_id), _look(operation), asked=True)


def _label_element(
    container_id: str, text: str, container: Dict[str, Any], font_size: float = FONT_SIZE,
) -> Dict[str, Any]:
    """The text bound inside a shape. Its geometry is the container's, always."""
    return _base_element(
        f"{container_id}{TEXT_SUFFIX}", "text",
        x=container["x"] + BOUND_TEXT_PADDING,
        y=container["y"] + BOUND_TEXT_PADDING,
        width=max(container["width"] - 2 * BOUND_TEXT_PADDING, 1),
        height=max(container["height"] - 2 * BOUND_TEXT_PADDING, 1),
        text=text, originalText=text,
        fontSize=font_size, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
        textAlign="center", verticalAlign="middle",
        autoResize=False,
        containerId=container_id,
    )


def _shape_size(
    kind: ElementKind, operation: Dict[str, Any], text: str, font_size: float = FONT_SIZE,
) -> Tuple[float, float]:
    """
    How big a labelled shape has to be to hold its text.

    The caller's width and height win when given, and otherwise the box is measured from
    the text rather than fixed: a title of forty characters in a box of two hundred and
    twenty pixels is the clipping this replaces. An ellipse and a diamond get a margin on
    top, because only about half of their bounding box is usable area.
    """
    width = _size(operation["width"], "width") if operation.get("width") is not None else None
    height = _size(operation["height"], "height") if operation.get("height") is not None else None

    factor = {
        ElementKind.ELLIPSE: ELLIPSE_PADDING_FACTOR,
        ElementKind.DIAMOND: DIAMOND_PADDING_FACTOR,
    }.get(kind, 1.0)

    # The editor gives a label the shape's width divided by the factor, MINUS the
    # padding: the padding is therefore scaled with the text, not added after it. Added
    # after, a diamond came out ten pixels short of its own label, which the editor then
    # broke in the middle of a word. The text is rounded up first: the editor rounds the
    # room it gives, and an exact fit here is a pixel short there.
    # A bigger face gets a proportionally wider box, so a note at "large" wraps on as
    # many words as one at "normal", not on half of them.
    scale = font_size / FONT_SIZE
    if width is None:
        natural, _ = _text_size(text, font_size)
        width = max(
            MIN_SHAPE_WIDTH * scale, min(NOTE_WIDTH * scale, (math.ceil(natural) + 2 * BOUND_TEXT_PADDING) * factor),
        )
    if height is None:
        usable = max(width / factor - 2 * BOUND_TEXT_PADDING, 1)
        _, needed = _text_size(text, font_size, max_width=usable)
        height = max(MIN_SHAPE_HEIGHT * scale, (math.ceil(needed) + 2 * BOUND_TEXT_PADDING) * factor)
    return width, height


def _make_labelled_shape(
    element_id: str,
    kind: ElementKind,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    text: str,
) -> List[Dict[str, Any]]:
    """A shape and the text bound inside it, which move and resize together."""
    font_size = _font_size(operation)
    width, height = _shape_size(kind, operation, text, font_size)
    x, y = _resolve_position(operation, elements, width, height)
    default_background = NOTE_BACKGROUND if kind is ElementKind.NOTE else TRANSPARENT
    container = _base_element(
        element_id, LABELLED_SHAPES[kind],
        x=x, y=y, width=width, height=height,
        boundElements=[{"type": "text", "id": f"{element_id}{TEXT_SUFFIX}"}],
        **_style(operation, default_background),
    )
    label = _label_element(element_id, text, container, font_size)
    label["textAlign"] = _align(operation, "center")
    return [container, label]


def _make_text(
    element_id: str,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    text: str,
) -> List[Dict[str, Any]]:
    """
    Free-standing text, for a title or a caption.

    ``autoResize`` is left on: nothing is bound to it, so the editor is free to remeasure
    the box with the real font the moment the user touches it, and our approximation only
    has to be right enough to place the next element.
    """
    font_size = _font_size(operation)
    natural_width, natural_height = _text_size(text, font_size)
    width = _size(operation["width"], "width") if operation.get("width") is not None else max(natural_width, 1)
    if operation.get("height") is not None:
        height = _size(operation["height"], "height")
    else:
        _, height = _text_size(text, font_size, max_width=width)
    x, y = _resolve_position(operation, elements, width, height)
    style = _style(operation)
    return [_base_element(
        element_id, "text",
        x=x, y=y, width=width, height=max(height, 1),
        text=text, originalText=text,
        fontSize=font_size, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
        textAlign=_align(operation), verticalAlign="top",
        autoResize=True,
        strokeColor=style["strokeColor"],
    )]


def _make_frame(
    element_id: str,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    text: str,
) -> List[Dict[str, Any]]:
    """
    A named zone. The editor draws its label in the corner and moves what sits inside it.

    The label is the caller's text and nothing else: a caller that passes an empty text
    wants a bare zone - typically under a title it drew itself - and gets one. Falling
    back on the element's identifier wrote an internal slug on the user's board.

    Sized generously by default: a frame is a container, and one born too small for what
    the caller is about to put in it is a frame the user has to resize by hand.
    """
    width = _size(operation["width"], "width") if operation.get("width") is not None else CELL_WIDTH * 2
    height = _size(operation["height"], "height") if operation.get("height") is not None else CELL_HEIGHT * 2
    x, y = _resolve_position(operation, elements, width, height)
    return [_base_element(
        element_id, "frame",
        x=x, y=y, width=width, height=height,
        name=text,
    )]


# ==================== Links ====================


def _segment_between(source: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    """
    The straight run between two shapes, from edge to edge.

    Rough on purpose: the editor recomputes the real path from the bindings when the
    scene loads and whenever either end moves, so anything more here would duplicate
    geometry it owns - and lose to it.
    """
    sx, sy, sw, sh = _footprint(source)
    tx, ty, tw, th = _footprint(target)
    start_x, start_y = sx + sw / 2, sy + sh / 2
    end_x, end_y = tx + tw / 2, ty + th / 2
    if abs(end_x - start_x) >= abs(end_y - start_y):
        start_x, end_x = (sx + sw, tx) if end_x >= start_x else (sx, tx + tw)
    else:
        start_y, end_y = (sy + sh, ty) if end_y >= start_y else (sy, ty + th)
    return {
        "x": start_x, "y": start_y,
        "width": abs(end_x - start_x), "height": abs(end_y - start_y),
        "points": [[0, 0], [end_x - start_x, end_y - start_y]],
    }


Point = Tuple[float, float]
Box = Tuple[float, float, float, float]


def _segment_hits(start: Point, end: Point, box: Box) -> bool:
    """
    Whether a segment passes through a box (Liang-Barsky clipping).

    The box is taken a pixel inside its edges: a link that starts on the edge of a
    shape, or runs along the side of one, touches it and does not cross it.
    """
    left, top = box[0] + 1, box[1] + 1
    right, bottom = box[0] + box[2] - 1, box[1] + box[3] - 1
    if right <= left or bottom <= top:
        return False
    dx, dy = end[0] - start[0], end[1] - start[1]
    entry, leave = 0.0, 1.0
    for direction, distance in ((-dx, start[0] - left), (dx, right - start[0]),
                                (-dy, start[1] - top), (dy, bottom - start[1])):
        if direction == 0:
            if distance < 0:
                return False
            continue
        ratio = distance / direction
        if direction < 0:
            entry = max(entry, ratio)
        else:
            leave = min(leave, ratio)
    return entry < leave


def _path_hits(path: Sequence[Point], boxes: Iterable[Box]) -> List[Box]:
    """The boxes a path passes through."""
    return [
        box for box in boxes
        if any(_segment_hits(path[index], path[index + 1], box) for index in range(len(path) - 1))
    ]


def _as_link_geometry(path: Sequence[Point]) -> Dict[str, Any]:
    """A path as the editor stores a link: an origin, and points relative to it."""
    origin_x, origin_y = path[0]
    xs, ys = [x for x, _ in path], [y for _, y in path]
    return {
        "x": origin_x, "y": origin_y,
        "width": max(xs) - min(xs), "height": max(ys) - min(ys),
        "points": [[x - origin_x, y - origin_y] for x, y in path],
    }


def _route_between(
    source: Dict[str, Any],
    target: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    The path of a link: straight when nothing stands in the way, round it otherwise.

    A straight link between two boxes with a third one on the line runs through that
    third box, under its text, and lies on top of the links that box already has - on a
    cycle drawn in a row, the return arrow from the last box to the first vanished into
    the row itself and its label was written across the middle box.

    The detour is three straight runs: out of the source, along a lane clear of the row
    (or of the column), into the target. Out and in on the same side, so a return link
    reads as the loop it is. The lane is the nearer free one - below or above for a link
    that runs mostly sideways, right or left for one that runs up or down - and it has
    to be free of everything named on the board, texts included: a lane through a title
    trades one collision for another. With no free lane within reach the link stays
    straight, which is what it was.
    """
    straight = _segment_between(source, target)
    source_box, target_box = _box(source, elements), _box(target, elements)
    ends = {source["id"], target["id"]}
    named = [
        element for element in elements
        if element["id"] not in ends and _is_anchor(element) and element.get("type") != "frame"
        and not (element.get("type") in ("arrow", "line") and _owner(element) is None)
    ]
    # What a link must not run through, and what a lane must stay clear of.
    blocks = [_box(element, elements) for element in named if element.get("type") != "text"]
    everything = [_box(element, elements) for element in named]

    start = (straight["x"], straight["y"])
    end = (start[0] + straight["points"][-1][0], start[1] + straight["points"][-1][1])
    crossed = _path_hits([start, end], blocks)
    if not crossed:
        return straight

    source_x, source_y, source_width, source_height = source_box
    target_x, target_y, target_width, target_height = target_box
    source_centre = (source_x + source_width / 2, source_y + source_height / 2)
    target_centre = (target_x + target_width / 2, target_y + target_height / 2)
    passed = [source_box, target_box, *crossed]
    sideways = abs(target_centre[0] - source_centre[0]) >= abs(target_centre[1] - source_centre[1])

    for attempt in range(1, LINK_LANE_ATTEMPTS + 1):
        margin = LINK_LANE_MARGIN * attempt
        if sideways:
            below = max(y + height for _, y, _, height in passed) + margin
            above = min(y for _, y, _, _ in passed) - margin
            candidates = [
                [(source_centre[0], source_y + source_height), (source_centre[0], below),
                 (target_centre[0], below), (target_centre[0], target_y + target_height)],
                [(source_centre[0], source_y), (source_centre[0], above),
                 (target_centre[0], above), (target_centre[0], target_y)],
            ]
        else:
            right = max(x + width for x, _, width, _ in passed) + margin
            left = min(x for x, _, _, _ in passed) - margin
            candidates = [
                [(source_x + source_width, source_centre[1]), (right, source_centre[1]),
                 (right, target_centre[1]), (target_x + target_width, target_centre[1])],
                [(source_x, source_centre[1]), (left, source_centre[1]),
                 (left, target_centre[1]), (target_x, target_centre[1])],
            ]
        for path in candidates:
            if not _path_hits(path, everything):
                return _as_link_geometry(path)
    return straight


def _make_linear(
    element_id: str,
    kind: ElementKind,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    text: str,
) -> List[Dict[str, Any]]:
    """
    A link, bound to the elements it joins when the caller named them.

    Two ways in, because both are legitimate: ``from``/``to`` binds the ends so the link
    follows the shapes when the user drags them - what a diagram wants - while raw
    coordinates draw a free segment, which is what an underline or a bracket is.

    A label is a text bound to the link, exactly as a note's label is bound to its box;
    the editor keeps it centred on the path.
    """
    by_id = _index(elements)
    style = _style(operation)
    fields: Dict[str, Any] = {
        "startBinding": None, "endBinding": None,
        "startArrowhead": None,
        "endArrowhead": "arrow" if kind is ElementKind.ARROW else None,
        "elbowed": False,
        "strokeColor": style["strokeColor"],
    }

    source_name, target_name = operation.get("from"), operation.get("to")
    if source_name or target_name:
        source_id, target_id = slugify(source_name or ""), slugify(target_name or "")
        for endpoint in (source_id, target_id):
            if endpoint not in by_id:
                raise LysError(WHITEBOARD_UNKNOWN_ELEMENT, f"Link endpoint '{endpoint}' is not on the board")
        fields.update(_route_between(by_id[source_id], by_id[target_id], elements))
        fields["startBinding"] = {"elementId": source_id, "focus": 0, "gap": 4}
        fields["endBinding"] = {"elementId": target_id, "focus": 0, "gap": 4}
    else:
        width = _size(operation["width"], "width") if operation.get("width") is not None else CELL_WIDTH
        height = _number(operation.get("height", 0), "height", -MAX_SIZE, MAX_SIZE)
        x, y = _resolve_position(operation, elements, width, abs(height) or 1)
        fields.update({"x": x, "y": y, "width": width, "height": abs(height),
                       "points": [[0, 0], [width, height]]})

    link = _base_element(element_id, "arrow" if kind is ElementKind.ARROW else "line", **fields)

    created = [link]
    if text:
        link["boundElements"] = [{"type": "text", "id": f"{element_id}{TEXT_SUFFIX}"}]
        label = _label_element(element_id, text, link)
        label["textAlign"] = "center"
        label_width, label_height = _text_size(text)
        label["width"], label["height"] = max(label_width, 1), max(label_height, 1)
        created.append(label)

    if fields["startBinding"]:
        _bind(by_id[fields["startBinding"]["elementId"]], element_id)
        _bind(by_id[fields["endBinding"]["elementId"]], element_id)
    return created


def _bind(element: Dict[str, Any], link_id: str) -> None:
    """Record on an element that a link now touches it."""
    bound = element.setdefault("boundElements", []) or []
    if not any(b.get("id") == link_id for b in bound):
        bound.append({"type": "arrow", "id": link_id})
    element["boundElements"] = bound


def _refresh_links(elements: List[Dict[str, Any]], moved_ids: Iterable[str]) -> None:
    """
    Redraw the links touching elements that just moved or were just drawn - and the
    links just drawn themselves.

    A link is routed against what is on the board when it is added, and a patch may
    well add the box that stands in its way a line later: the pass that closes a patch
    is the first moment the whole of it can be seen.

    The editor repairs bound paths on load, but only once it has them: a link whose
    stored segment points somewhere else entirely shows up wrong in the scene the browser
    already has, and the user watches an arrow jump when they nudge the box. Recomputing
    the segment here is the difference between a board that is right and a board that
    becomes right.
    """
    moved = set(moved_ids)
    if not moved:
        return
    by_id = _index(elements)
    for element in elements:
        if element.get("type") not in ("arrow", "line"):
            continue
        start = (element.get("startBinding") or {}).get("elementId")
        end = (element.get("endBinding") or {}).get("elementId")
        if not start or not end or not moved & {start, end, element["id"]}:
            continue
        if start not in by_id or end not in by_id:
            continue
        element.update(_route_between(by_id[start], by_id[end], elements))
        _touch(element)


def _unbind_everywhere(elements: List[Dict[str, Any]], removed_ids: set) -> None:
    """
    Drop every reference to elements that no longer exist.

    Excalidraw does not maintain the two sides of a link: deleting one without clearing
    the ``boundElements`` of the shapes it joined leaves entries pointing at nothing, and
    the editor then renders - or crashes on - a binding it cannot resolve.
    """
    for element in elements:
        bound = element.get("boundElements")
        if bound:
            element["boundElements"] = [b for b in bound if b.get("id") not in removed_ids]
        for side in ("startBinding", "endBinding"):
            binding = element.get(side)
            if binding and binding.get("elementId") in removed_ids:
                element[side] = None
        if element.get("frameId") in removed_ids:
            element["frameId"] = None


def _collect_removals(elements: Sequence[Dict[str, Any]], element_id: str) -> set:
    """
    Everything that disappears with one element: itself, its bound label, the parts it is
    made of when it is a table or a chart, and the links that had it as an endpoint.

    A link bound to nothing is not a link, it is a stray stroke the user has to clean up
    by hand - which is exactly the kind of debris that makes a months-old board unusable.
    """
    removed = {element_id, f"{element_id}{TEXT_SUFFIX}"}
    for element in elements:
        if _owner(element) == element_id:
            removed.add(element["id"])
    for element in elements:
        if element.get("type") not in ("arrow", "line"):
            continue
        ends = {
            (element.get("startBinding") or {}).get("elementId"),
            (element.get("endBinding") or {}).get("elementId"),
        }
        if ends & removed:
            removed.add(element["id"])
            removed.add(f"{element['id']}{TEXT_SUFFIX}")
    return removed


# ==================== Tables ====================


def _read_table(operation: Dict[str, Any]) -> Tuple[List[str], List[List[str]]]:
    """Validate the data a table is drawn from, before a single element exists."""
    headers = operation.get("headers")
    rows = operation.get("rows") or []
    if not isinstance(headers, list) or not headers:
        raise LysError(WHITEBOARD_INVALID_TABLE, "A table needs 'headers': a non-empty list of column titles")
    if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
        raise LysError(WHITEBOARD_INVALID_TABLE, "'rows' must be a list of lists, one list per line")
    if len(headers) > MAX_TABLE_COLUMNS:
        raise LysError(
            WHITEBOARD_INVALID_TABLE,
            f"A table holds at most {MAX_TABLE_COLUMNS} columns, got {len(headers)}. Split it in two",
        )
    if len(rows) > MAX_TABLE_ROWS:
        raise LysError(
            WHITEBOARD_INVALID_TABLE,
            f"A table holds at most {MAX_TABLE_ROWS} rows, got {len(rows)}. Keep what matters on the board",
        )
    for number, row in enumerate(rows, start=1):
        if len(row) != len(headers):
            raise LysError(
                WHITEBOARD_INVALID_TABLE,
                f"Row {number} has {len(row)} cells for {len(headers)} columns: every row fills every column",
            )
    clean_headers = [_text_value(header, "header") for header in headers]
    clean_rows = [[_text_value(cell, "cell") for cell in row] for row in rows]
    return clean_headers, clean_rows


def _make_table(
    element_id: str,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    A grid drawn from real elements: an outer box, the rules between cells, and one text
    per cell.

    Native rather than an image, because the board's promise is that the user can edit
    what is on it. A table the user cannot retype a figure into would be a screenshot
    with extra steps - and the caller still only sends data, never geometry.

    The grid is sized by its content, cell by cell: a column is as wide as its widest
    cell demands (past the cap the cell wraps and the row grows instead), a row as tall
    as its tallest wrapped cell. The uniform grid this replaces starved the narrow
    columns and drowned the wide ones - every overflow a reader saw was a cell whose
    content nobody had asked about.
    """
    headers, rows = _read_table(operation)
    columns = len(headers)
    grid = [headers] + rows
    # The face scales the whole grid: a table at "large" keeps its proportions and
    # its wrapping, only bigger - what a slide read from across a room needs.
    font_size = _font_size(operation)
    scale = font_size / FONT_SIZE
    forced_align = _named(operation, "align", ALIGNMENTS)

    # Column widths: the widest natural cell decides, inside [min, cap].
    natural_widths = [
        max(_text_size(row[column], font_size)[0] for row in grid) for column in range(columns)
    ]
    column_widths = [
        min(
            max(natural + 2 * BOUND_TEXT_PADDING, TABLE_COLUMN_MIN_WIDTH * scale),
            TABLE_COLUMN_MAX_WIDTH * scale,
        )
        for natural in natural_widths
    ]
    if operation.get("width") is not None:
        # The caller asked for a width: the content-proportional columns are
        # scaled to it, the proportions preserved.
        wanted = _size(operation["width"], "width")
        factor = wanted / sum(column_widths)
        column_widths = [column * factor for column in column_widths]

    # Row heights: the tallest WRAPPED cell decides — a cell past its column's
    # cap wraps, and the row carries the extra lines.
    row_heights: List[float] = []
    for row in grid:
        needed = max(
            _text_size(
                row[column], font_size, max_width=column_widths[column] - 2 * BOUND_TEXT_PADDING
            )[1]
            for column in range(columns)
        )
        row_heights.append(max(needed + 2 * BOUND_TEXT_PADDING, TABLE_ROW_HEIGHT * scale))

    width, height = sum(column_widths), sum(row_heights)
    x, y = _resolve_position(operation, elements, width, height)
    tag = {OWNER_KEY: element_id, KIND_KEY: ElementKind.TABLE.value}

    parts: List[Dict[str, Any]] = [_base_element(
        element_id, "rectangle",
        x=x, y=y, width=width, height=height,
        groupIds=[element_id], customData=tag,
        **_style(operation),
    )]
    column_edges = _cumulative_edges(column_widths)
    row_edges = _cumulative_edges(row_heights)
    for column in range(1, columns):
        parts.append(_base_element(
            f"{element_id}-col-{column}", "line",
            x=x + column_edges[column], y=y, width=0, height=height,
            points=[[0, 0], [0, height]],
            groupIds=[element_id], customData=dict(tag),
            strokeColor=parts[0]["strokeColor"],
        ))
    for line in range(1, len(grid)):
        parts.append(_base_element(
            f"{element_id}-row-{line}", "line",
            x=x, y=y + row_edges[line], width=width, height=0,
            points=[[0, 0], [width, 0]],
            groupIds=[element_id], customData=dict(tag),
            strokeColor=parts[0]["strokeColor"],
        ))
    for line, cells in enumerate(grid):
        for column, cell in enumerate(cells):
            parts.append(_base_element(
                f"{element_id}-cell-{line}-{column}", "text",
                x=x + column_edges[column] + BOUND_TEXT_PADDING,
                y=y + row_edges[line] + BOUND_TEXT_PADDING,
                width=max(column_widths[column] - 2 * BOUND_TEXT_PADDING, 1),
                height=max(row_heights[line] - 2 * BOUND_TEXT_PADDING, 1),
                text=_wrapped(cell, column_widths[column] - 2 * BOUND_TEXT_PADDING, font_size), originalText=cell,
                fontSize=font_size, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
                textAlign=forced_align or _cell_align(cell, is_header=line == 0),
                verticalAlign="middle", autoResize=False,
                groupIds=[element_id], customData=dict(tag),
                strokeColor=parts[0]["strokeColor"],
            ))
    parts[0]["customData"] = {**tag, SPEC_KEY: {"headers": headers, "rows": rows}, LAYOUT_KEY: _layout(operation)}
    return parts


def _layout(operation: Dict[str, Any]) -> Dict[str, Any]:
    """
    What a figure is drawn with beyond its data, recorded so a redraw keeps it.

    The size is recorded resolved: a table drawn "large" by default in a frame stays
    large when a redraw no longer says so.
    """
    layout: Dict[str, Any] = {field: operation[field] for field in LAYOUT_FIELDS if operation.get(field) is not None}
    layout["size"] = _size_choice(operation)
    return layout


def _cumulative_edges(sizes: Sequence[float]) -> List[float]:
    """The offset each boundary sits at: [0, w0, w0 + w1, ...] - where the
    next element starts, which is where the rule between them is drawn."""
    edges: List[float] = [0.0]
    for size in sizes:
        edges.append(edges[-1] + size)
    return edges


# ==================== Charts ====================


def _read_chart(operation: Dict[str, Any]) -> Tuple[ChartType, List[str], List[float], str]:
    """Validate the data a chart is drawn from, and the type that decides how."""
    chart = operation.get("chart")
    if not isinstance(chart, dict):
        raise LysError(WHITEBOARD_INVALID_CHART, "A chart needs 'chart': {type, data:[{label, value}]}")
    try:
        chart_type = ChartType(str(chart.get("type") or ChartType.BAR.value))
    except ValueError:
        raise LysError(
            WHITEBOARD_INVALID_CHART,
            f"Unknown chart type '{chart.get('type')}'. Use one of: {', '.join(t.value for t in ChartType)}",
        )
    data = chart.get("data")
    if not isinstance(data, list) or not data:
        raise LysError(WHITEBOARD_INVALID_CHART, "'chart.data' must be a non-empty list of {label, value}")
    if len(data) > MAX_CHART_POINTS:
        raise LysError(
            WHITEBOARD_INVALID_CHART,
            f"A chart holds at most {MAX_CHART_POINTS} points, got {len(data)}. Aggregate the tail",
        )
    labels: List[str] = []
    values: List[float] = []
    for position, point in enumerate(data, start=1):
        if not isinstance(point, dict) or "value" not in point:
            raise LysError(WHITEBOARD_INVALID_CHART, f"Point {position} must be an object with a 'value'")
        labels.append(_text_value(point.get("label") or f"#{position}", "label"))
        values.append(_number(point["value"], f"chart.data[{position}].value", -MAX_COORDINATE, MAX_COORDINATE))
    if chart_type is ChartType.PIE and (min(values) < 0 or sum(values) <= 0):
        raise LysError(WHITEBOARD_INVALID_CHART, "A pie needs positive values summing to more than zero")
    return chart_type, labels, values, _text_value(chart.get("title"), "chart.title")


def _format_figure(value: float) -> str:
    """
    A figure as a reader expects it on a chart: whole when it is whole, two decimals at
    most otherwise, thousands apart.

    Never the general float format: past a million it switches to an exponent, and
    "1.23457e+06" on a revenue chart is a figure nobody can read. The separator is a
    no-break space - the one grouping no locale reads as a decimal mark.
    """
    if float(value).is_integer():
        grouped = f"{int(value):,}"
    else:
        grouped = f"{value:,.2f}".rstrip("0").rstrip(".")
    return grouped.replace(",", "\u00a0")


def _make_bar_chart(
    element_id: str,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    labels: List[str],
    values: List[float],
    title: str,
) -> List[Dict[str, Any]]:
    """
    Bars as real rectangles, sitting on a baseline: the name of each under it, its
    figure above it.

    Drawn natively because the format can express it exactly and the user can then drag a
    bar, recolour it or write next to it. Negative values are not plotted below the axis:
    a whiteboard bar chart is a comparison of magnitudes, and an axis crossing mid-figure
    is a statistics chart nobody asked for.

    The figure sits on top of its bar, where the eye reads a bar's height; stacked under
    the name it turned the caption into three lines for any name that wrapped, and the
    last one fell out of the band. Both captions take the whole slot rather than the
    bar's width - the gap between two bars is room a long name can use.
    """
    width = _size(operation["width"], "width") if operation.get("width") is not None else CHART_WIDTH
    height = _size(operation["height"], "height") if operation.get("height") is not None else CHART_HEIGHT
    x, y = _resolve_position(operation, elements, width, height + CHART_LABEL_BAND)
    tag = {OWNER_KEY: element_id, KIND_KEY: ElementKind.CHART.value}

    font_size = _font_size(operation)
    title_height = font_size * LINE_HEIGHT if title else 0
    # The tallest bar stops short of the title by one band: the room its figure needs.
    plot_height = height - title_height - CHART_VALUE_BAND - CHART_LABEL_BAND
    baseline = y + title_height + CHART_VALUE_BAND + plot_height
    caption_font_size = font_size * CHART_CAPTION_FONT_RATIO
    caption_line = caption_font_size * LINE_HEIGHT
    slot = width / len(values)
    bar_width = slot * 0.7
    scale = max(abs(value) for value in values) or 1

    parts: List[Dict[str, Any]] = [_base_element(
        element_id, "line",
        x=x, y=baseline, width=width, height=0,
        points=[[0, 0], [width, 0]],
        groupIds=[element_id],
        customData={
            **tag,
            SPEC_KEY: {
                "type": ChartType.BAR.value, "title": title,
                "data": [{"label": label, "value": value} for label, value in zip(labels, values)],
            },
            # From the title's top to the bottom of the names under the bars.
            BOX_KEY: [0, y - baseline, width, height + BOUND_TEXT_PADDING],
            LAYOUT_KEY: _layout(operation),
        },
    )]
    if title:
        parts.append(_base_element(
            f"{element_id}-title", "text",
            x=x, y=y, width=max(_text_size(title, font_size)[0], 1), height=title_height,
            text=title, originalText=title,
            fontSize=font_size, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
            textAlign="left", verticalAlign="top", autoResize=True,
            groupIds=[element_id], customData=dict(tag),
        ))
    for position, (label, value) in enumerate(zip(labels, values)):
        bar_height = max(abs(value) / scale * plot_height, 1)
        bar_x = x + position * slot + (slot - bar_width) / 2
        parts.append(_base_element(
            f"{element_id}-bar-{position}", "rectangle",
            x=bar_x, y=baseline - bar_height, width=bar_width, height=bar_height,
            backgroundColor=SERIES_COLORS[position % len(SERIES_COLORS)],
            groupIds=[element_id], customData=dict(tag),
        ))
        slot_x = x + position * slot
        parts.append(_base_element(
            f"{element_id}-label-{position}", "text",
            x=slot_x, y=baseline + BOUND_TEXT_PADDING,
            width=max(slot, 1), height=CHART_LABEL_BAND,
            text=_wrapped(label, slot, caption_font_size), originalText=label,
            fontSize=caption_font_size, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
            textAlign="center", verticalAlign="top", autoResize=False,
            groupIds=[element_id], customData=dict(tag),
        ))
        figure = _format_figure(value)
        parts.append(_base_element(
            f"{element_id}-value-{position}", "text",
            x=slot_x, y=baseline - bar_height - caption_line - CHART_VALUE_GAP,
            width=max(slot, 1), height=caption_line,
            text=figure, originalText=figure,
            fontSize=caption_font_size, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
            textAlign="center", verticalAlign="top", autoResize=False,
            groupIds=[element_id], customData=dict(tag),
        ))
    return parts


def _make_image_chart(
    element_id: str,
    chart_type: ChartType,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    labels: List[str],
    values: List[float],
    title: str,
) -> List[Dict[str, Any]]:
    """
    A chart the format cannot express, carried as its own data.

    Excalidraw has neither arcs nor plotted curves, so a pie or a line chart can only be
    an image. The element therefore holds the **spec**, not a picture: the viewer renders
    it when it loads the board, and nothing binary is ever stored. That keeps the board a
    JSON document, keeps it small, and - the reason that matters - keeps the figures
    readable, so this module or a later viewer can redraw the same chart at any size.
    """
    width = _size(operation["width"], "width") if operation.get("width") is not None else CHART_WIDTH
    height = _size(operation["height"], "height") if operation.get("height") is not None else CHART_HEIGHT
    x, y = _resolve_position(operation, elements, width, height)
    return [_base_element(
        element_id, "image",
        x=x, y=y, width=width, height=height,
        fileId=f"chart-{element_id}",
        status="saved", scale=[1, 1], crop=None,
        customData={
            OWNER_KEY: element_id,
            KIND_KEY: ElementKind.CHART.value,
            SPEC_KEY: {
                "type": chart_type.value, "title": title,
                "data": [{"label": label, "value": value} for label, value in zip(labels, values)],
            },
            LAYOUT_KEY: _layout(operation),
        },
    )]


def _make_chart(
    element_id: str,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Draw a chart, natively or as a spec, according to what the format can express."""
    chart_type, labels, values, title = _read_chart(operation)
    if chart_type in IMAGE_CHART_TYPES:
        return _make_image_chart(element_id, chart_type, operation, elements, labels, values, title)
    return _make_bar_chart(element_id, operation, elements, labels, values, title)


# ==================== Operations ====================


def _kind_of(operation: Dict[str, Any]) -> ElementKind:
    raw = operation.get("kind") or ElementKind.NOTE.value
    try:
        return ElementKind(str(raw))
    except ValueError:
        raise LysError(
            WHITEBOARD_UNKNOWN_ELEMENT_KIND,
            f"Unknown kind '{raw}'. Use one of: {', '.join(k.value for k in ElementKind)}",
        )


def _refuse_nesting(elements: Sequence[Dict[str, Any]]) -> None:
    """
    Frames hold elements, never frames.

    The editor does not nest them: a frame given a frameId is clipped by its parent and
    moves with it, but keeps its own members, and what the user sees no longer matches
    what the board says. Refused rather than drawn wrong.
    """
    for element in elements:
        if element.get("type") == "frame":
            raise LysError(
                WHITEBOARD_INVALID_OPERATION, f"'{element['id']}' is a frame, and a frame cannot sit in a frame",
            )


def _attach_to_frame(created: List[Dict[str, Any]], operation: Dict[str, Any], elements: List[Dict[str, Any]]) -> None:
    """Put new elements inside a named frame, so the editor moves them with it."""
    frame = _frame_named(operation, elements)
    if frame is None:
        return
    _refuse_nesting(created)
    for element in created:
        element["frameId"] = frame["id"]


def _target_frame(
    elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    The frame an updated element ends up in, which its coordinates count from.

    The one the update names; none for an empty name, which takes the element out of
    any; otherwise the one it already sits in. A frame named for a frame is refused.
    """
    by_id = _index(elements)
    anchor = by_id[element_id]
    name = operation.get("frame")
    if name is None:
        current = by_id.get(anchor.get("frameId") or "")
        return current if current is not None and current.get("type") == "frame" else None
    if name == "":
        return None
    frame = by_id[_frame_id_for(name, by_id)]
    _refuse_nesting([anchor])
    return frame


def _placed_in_frame(
    elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any], target: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    The update with a place in the frame it moves the element into, when it gives none.

    An element entering a frame without coordinates lands in the frame's own grid, as an
    unplaced add does: kept where it stood on the board, it would most often sit outside
    its new frame - and the editor clips an element to the frame it names.
    """
    anchor = _index(elements)[element_id]
    entering = target is not None and target["id"] != anchor.get("frameId")
    if not entering or operation.get("x") is not None or operation.get("y") is not None:
        return operation
    _, _, width, height = _box(anchor, elements)
    x, y = _auto_position(elements, width, height, target)
    return {**operation, "x": x - target["x"], "y": y - target["y"]}


def _reframe(
    elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any], target: Optional[Dict[str, Any]],
) -> None:
    """
    Move a named element, and everything it is made of, into a frame - or out of any.

    Geometry alone does not do it: the editor shows an element where its frameId says,
    clipped to that frame, so a note moved by its coordinates onto another frame stays
    clipped by the first and disappears. An empty frame name takes the element out.
    """
    if operation.get("frame") is None:
        return
    label = _index(elements).get(f"{element_id}{TEXT_SUFFIX}")
    for element in _family(elements, element_id) + ([label] if label else []):
        element["frameId"] = target["id"] if target is not None else None
        _touch(element)


def _add(
    elements: List[Dict[str, Any]], operation: Dict[str, Any], element_id: str, default_stroke: str = DEFAULT_STROKE,
) -> None:
    """Apply one add. An add naming an existing element updates it - see apply_operations."""
    kind = _kind_of(operation)
    text = _text_value(operation.get("text") if operation.get("text") is not None else operation.get("name"))

    if kind in LABELLED_SHAPES:
        created = _make_labelled_shape(element_id, kind, operation, elements, text)
    elif kind is ElementKind.TEXT:
        created = _make_text(element_id, operation, elements, text)
    elif kind in LINEAR_KINDS:
        created = _make_linear(element_id, kind, operation, elements,
                               _text_value(operation.get("label"), "label"))
    elif kind is ElementKind.FRAME:
        created = _make_frame(element_id, operation, elements, text)
    elif kind is ElementKind.TABLE:
        created = _make_table(element_id, operation, elements)
    elif kind is ElementKind.CHART:
        created = _make_chart(element_id, operation, elements)
    else:  # pragma: no cover - ElementKind is exhaustive above
        raise LysError(WHITEBOARD_UNKNOWN_ELEMENT_KIND, f"Nothing draws a '{kind.value}'")

    _attach_to_frame(created, operation, elements)
    _apply_look(created, _look(operation, default_stroke), asked=_asks_look(operation))
    elements.extend(created)


def _set_text(elements: List[Dict[str, Any]], element_id: str, text: str) -> None:
    """
    Write text on an element, whether it carries it directly or through a bound label.

    A shape whose label no longer fits grows to hold it: text set once at creation and
    then rewritten longer is the other half of the clipping problem, and the user cannot
    see there is more to read.
    """
    by_id = _index(elements)
    element = by_id[element_id]
    if element.get("type") == "frame":
        element["name"] = text
        _touch(element)
        return

    label = by_id.get(f"{element_id}{TEXT_SUFFIX}")
    if label is None:
        element["text"] = text
        element["originalText"] = text
        _touch(element)
        _fit_text(element)
        return

    label["text"] = text
    label["originalText"] = text
    _touch(label)

    if element.get("type") in ("arrow", "line"):
        label["width"], label["height"] = (max(size, 1) for size in _text_size(text, label.get("fontSize", FONT_SIZE)))
        return

    _fit_label(element, label)


def _fit_text(element: Dict[str, Any]) -> None:
    """
    Give a free text the room its words need at its size: never narrower than it was,
    and as wide as its longest line - the way the editor sizes an auto-resizing text.
    """
    if element.get("type") != "text" or element.get("autoResize") is False:
        return
    font_size = element.get("fontSize", FONT_SIZE)
    natural_width, _ = _text_size(element.get("text", ""), font_size)
    element["width"] = max(element.get("width", 0), natural_width, 1)
    _, element["height"] = _text_size(element.get("text", ""), font_size, max_width=element["width"])
    element["height"] = max(element["height"], 1)


def _fit_label(container: Dict[str, Any], label: Dict[str, Any]) -> None:
    """Grow a shape until its label fits, at the label's size."""
    usable = max(container["width"] - 2 * BOUND_TEXT_PADDING, 1)
    _, needed = _text_size(label.get("text", ""), label.get("fontSize", FONT_SIZE), max_width=usable)
    if needed + 2 * BOUND_TEXT_PADDING > container["height"]:
        container["height"] = needed + 2 * BOUND_TEXT_PADDING
        _touch(container)
    _resize_label(container, label)


def _realign(elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any]) -> None:
    """Align the text of a named element - its label, or itself."""
    if operation.get("align") is None:
        return
    by_id = _index(elements)
    element = by_id[element_id]
    target = by_id.get(f"{element_id}{TEXT_SUFFIX}") or element
    if target.get("type") != "text":
        raise LysError(WHITEBOARD_INVALID_OPERATION, f"'{element_id}' carries no text to align")
    target["textAlign"] = _align(operation)
    _touch(target)


def _resize_text(elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any]) -> None:
    """Change the text size of a named element - its label, or itself - and refit it."""
    if operation.get("size") is None:
        return
    by_id = _index(elements)
    element = by_id[element_id]
    label = by_id.get(f"{element_id}{TEXT_SUFFIX}")
    target = label if label is not None else element
    if target.get("type") != "text":
        raise LysError(WHITEBOARD_INVALID_OPERATION, f"'{element_id}' carries no text to size")
    target["fontSize"] = _font_size(operation)
    _touch(target)
    if label is None:
        _fit_text(element)
    elif element.get("type") in ("arrow", "line"):
        label["width"], label["height"] = (max(size, 1) for size in _text_size(label["text"], target["fontSize"]))
    else:
        _fit_label(element, label)


def _resize_label(container: Dict[str, Any], label: Dict[str, Any]) -> None:
    label["x"] = container["x"] + BOUND_TEXT_PADDING
    label["y"] = container["y"] + BOUND_TEXT_PADDING
    label["width"] = max(container["width"] - 2 * BOUND_TEXT_PADDING, 1)
    label["height"] = max(container["height"] - 2 * BOUND_TEXT_PADDING, 1)


def _move_and_resize(
    elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any], target: Optional[Dict[str, Any]],
) -> bool:
    """
    Move or resize a named element, carrying with it everything it is made of.

    Coordinates count from the corner of the frame the element ends up in (``target``),
    or from the board's origin when it ends up in none.

    Returns whether anything changed, so the caller knows whether links need redrawing.
    A table is fifty elements behind one name; a caller that moved "the comparison" must
    not have to know that.
    """
    by_id = _index(elements)
    anchor = by_id[element_id]
    family = _family(elements, element_id)
    label = by_id.get(f"{element_id}{TEXT_SUFFIX}")

    changed = False
    has_x, has_y = operation.get("x") is not None, operation.get("y") is not None
    if has_x != has_y:
        raise LysError(WHITEBOARD_INVALID_GEOMETRY, "'x' and 'y' go together: give both or neither")
    if has_x:
        left, top, _, _ = _box(anchor, elements)
        origin_x, origin_y = _origin(target)
        dx = origin_x + _coordinate(operation["x"], "x") - left
        dy = origin_y + _coordinate(operation["y"], "y") - top
        for element in family + ([label] if label else []):
            element["x"] += dx
            element["y"] += dy
            _touch(element)
        changed = True

    for field in ("width", "height"):
        if operation.get(field) is None:
            continue
        if len(family) > 1:
            raise LysError(
                WHITEBOARD_INVALID_GEOMETRY,
                f"'{element_id}' is drawn from its data: change the data to resize it, or delete and redraw it",
            )
        anchor[field] = _size(operation[field], field)
        custom = anchor.get("customData") or {}
        if LAYOUT_KEY in custom:
            # A figure of one element (an image chart) keeps its new size through a redraw.
            anchor["customData"] = {**custom, LAYOUT_KEY: {**custom[LAYOUT_KEY], field: anchor[field]}}
        _touch(anchor)
        changed = True
    if label and changed:
        _resize_label(anchor, label)
    return changed


def _restyle(elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any]) -> None:
    """Recolour a named element and everything drawn under its name."""
    family = _family(elements, element_id)
    for field, key in (("color", "strokeColor"), ("background", "backgroundColor")):
        if operation.get(field) is None:
            continue
        value = _color(operation[field], field)
        for element in family:
            element[key] = value
            _touch(element)


def _update(elements: List[Dict[str, Any]], operation: Dict[str, Any], element_id: str) -> bool:
    """
    Apply one update: text, geometry, colour, frame, look, or a redraw from new data.

    Returns whether the element moved, so links can be redrawn once at the end rather
    than after every operation.
    """
    if element_id not in _index(elements):
        raise LysError(WHITEBOARD_UNKNOWN_ELEMENT, f"Element '{element_id}' is not on the board")

    # A repeated kind is tolerated, a different one refused: nothing turns an element into
    # another kind in place, and ignoring the request would report a change never made.
    current_kind = _kind_on_board(_index(elements)[element_id])
    if operation.get("kind") is not None and operation["kind"] != current_kind:
        raise LysError(
            WHITEBOARD_INVALID_OPERATION,
            f"'{element_id}' is a {current_kind} and cannot become a {operation['kind']} in place. "
            f"Delete it and add it again under the new kind",
        )

    target = _target_frame(elements, element_id, operation)
    operation = _placed_in_frame(elements, element_id, operation, target)

    # A figure is a function of its data and its layout: a change to either redraws it.
    if operation.get("chart") is not None:
        return _redraw(elements, operation, element_id, target)
    if operation.get("headers") is not None or operation.get("rows") is not None:
        return _redraw(elements, _complete_table_data(elements, operation, element_id), element_id, target)
    if current_kind == ElementKind.TABLE.value and any(operation.get(f) is not None for f in ("size", "align")):
        return _redraw(elements, _complete_table_data(elements, operation, element_id), element_id, target)
    if current_kind == ElementKind.CHART.value and operation.get("size") is not None:
        return _redraw(elements, _complete_chart_data(elements, operation, element_id), element_id, target)

    moved = _move_and_resize(elements, element_id, operation, target)
    _restyle(elements, element_id, operation)
    _reframe(elements, element_id, operation, target)
    _resize_text(elements, element_id, operation)
    _realign(elements, element_id, operation)
    _relook(elements, element_id, operation)
    text = operation.get("text") if operation.get("text") is not None else operation.get("label")
    if text is not None:
        _set_text(elements, element_id, _text_value(text))
    elif not moved and not any(
        operation.get(field) is not None
        for field in ("color", "background", "frame", "size", "align", "stroke", "corners", "thickness")
    ):
        _touch(_index(elements)[element_id])
    return moved


def _complete_table_data(
    elements: List[Dict[str, Any]], operation: Dict[str, Any], element_id: str,
) -> Dict[str, Any]:
    """
    The update with the half of the table data it leaves out taken from the table on the board.

    Correcting one cell means sending the lines again, not the column titles: an update
    with only ``rows`` (or only ``headers``) redraws the table with the other half it
    already has. Table data aimed at an element that is not a table is refused rather
    than dropped - an update that silently changes nothing reads as done to its caller,
    which then repeats it.
    """
    custom = _index(elements)[element_id].get("customData") or {}
    if custom.get(KIND_KEY) != ElementKind.TABLE.value:
        raise LysError(
            WHITEBOARD_INVALID_TABLE,
            f"'{element_id}' is not a table: 'headers' and 'rows' only redraw a table",
        )
    current = custom.get(SPEC_KEY) or {}
    return {
        **operation,
        "headers": operation["headers"] if operation.get("headers") is not None else current.get("headers"),
        "rows": operation["rows"] if operation.get("rows") is not None else current.get("rows", []),
    }


def _complete_chart_data(
    elements: List[Dict[str, Any]], operation: Dict[str, Any], element_id: str,
) -> Dict[str, Any]:
    """The update with the chart's data taken from the board: resizing its text redraws it."""
    custom = _index(elements)[element_id].get("customData") or {}
    return {**operation, "chart": custom.get(SPEC_KEY)}


def _drawn_with(anchor: Dict[str, Any]) -> Dict[str, Any]:
    """
    What a figure was drawn with beyond its data, as the fields of an operation.

    Its layout, its colours and its look: a redraw from new figures keeps them, as a
    theme change does - nothing already drawn changes look unless asked. A figure drawn
    before layouts were recorded was drawn at the normal size.
    """
    custom = anchor.get("customData") or {}
    drawn: Dict[str, Any] = dict(custom.get(LAYOUT_KEY) or {"size": DEFAULT_TEXT_SIZE})
    # Only a colour this module could have written: one picked by hand in the editor may
    # be spelled in a way the validation refuses, and must not make the redraw fail.
    for field, key, default in (("color", "strokeColor", STROKE_COLOR), ("background", "backgroundColor", TRANSPARENT)):
        value = anchor.get(key)
        if isinstance(value, str) and value != default and _COLOR_PATTERN.match(value):
            drawn[field] = value
    drawn.update(_look_names(anchor))
    return drawn


def _redraw(
    elements: List[Dict[str, Any]], operation: Dict[str, Any], element_id: str, target: Optional[Dict[str, Any]],
) -> bool:
    """
    Rebuild a table or a chart from new data, where the old one stood.

    Redrawn rather than patched: the parts are a function of the data, so recomputing
    them is the only way to stay consistent with a row added or a value corrected - and
    the caller keeps the name it has been using, which is what it reaches the figure by.

    The figure stays in the frame it ends up in (``target``), with what it was drawn
    with (see ``_drawn_with``) unless the update says otherwise. Its coordinates count
    from that frame, like any update's.
    """
    by_id = _index(elements)
    anchor = by_id[element_id]
    left, top, _, _ = _box(anchor, elements)
    removed = _collect_removals(elements, element_id)
    # The links to this figure survive, labels included: only the drawing is rebuilt,
    # and they are redrawn against the new geometry by the caller. The figure's OWN
    # lines do not - a table's rules and a bar chart's baseline are lines too, and kept
    # they would sit under the rebuilt ones, same ids twice in the scene.
    links = {
        e["id"] for e in elements
        if e.get("type") in ("arrow", "line") and _owner(e) != element_id
    }
    removed -= links | {f"{link}{TEXT_SUFFIX}" for link in links}
    # Both sides of a binding: the rebuilt anchor is a new element, and the links still
    # name it as their endpoint.
    carried = [bound for bound in anchor.get("boundElements") or [] if bound.get("id") in links]

    rebuilt = {**_drawn_with(anchor), **operation}
    kind = ElementKind.TABLE if operation.get("headers") is not None else ElementKind.CHART
    rebuilt["kind"] = kind.value
    rebuilt["frame"] = target["id"] if target is not None else None
    if operation.get("x") is None and operation.get("y") is None:
        origin_x, origin_y = _origin(target)
        rebuilt["x"], rebuilt["y"] = left - origin_x, top - origin_y

    elements[:] = [e for e in elements if e["id"] not in removed]
    _add(elements, rebuilt, element_id)
    if carried:
        rebuilt_anchor = _index(elements)[element_id]
        rebuilt_anchor["boundElements"] = [*(rebuilt_anchor.get("boundElements") or []), *carried]
    return True


def _delete(elements: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
    """Apply one delete, and leave no reference to what it removed."""
    element_id = slugify(name or "")
    if element_id not in _index(elements):
        raise LysError(WHITEBOARD_UNKNOWN_ELEMENT, f"Element '{element_id}' is not on the board")
    removed = _collect_removals(elements, element_id)
    remaining = [e for e in elements if e["id"] not in removed]
    _unbind_everywhere(remaining, removed)
    return remaining


def _check_patch_shape(operations: Any) -> None:
    """
    Refuse a patch that is not shaped the way the tool declares it.

    The patch comes from a model, and a model can send a string where an object belongs.
    Left alone that surfaces as an ``AttributeError`` deep in a factory, which no caller
    expects and nothing hands back to the model.
    """
    if not isinstance(operations, dict):
        raise LysError(WHITEBOARD_INVALID_OPERATION, "A patch is an object with add, update, delete and theme")

    for key, fields in ((OPERATION_ADD, ADD_ITEM_FIELDS), (OPERATION_UPDATE, UPDATE_ITEM_FIELDS)):
        items = operations.get(key)
        if items is None:
            continue
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise LysError(WHITEBOARD_INVALID_OPERATION, f"'{key}' is a list of objects")
        if not all(isinstance(item.get("name"), str) for item in items):
            raise LysError(WHITEBOARD_INVALID_OPERATION, f"Every item of '{key}' needs a 'name' string")
        # A field the tool does not declare is a field nothing reads. Skipping it draws
        # something other than what was asked and reports success: a link whose ends
        # were nested under a key of their own came out as a free stroke with no ends.
        for item in items:
            unknown = sorted(set(item) - set(fields))
            if unknown:
                raise LysError(
                    WHITEBOARD_INVALID_OPERATION,
                    f"Unknown field(s) {', '.join(repr(f) for f in unknown)} on '{item['name']}' in '{key}'. "
                    f"An item of '{key}' takes only: {', '.join(fields)} - all at the top level of the item",
                )
            for field in _NAME_FIELDS:
                if item.get(field) is not None and not isinstance(item[field], str):
                    raise LysError(
                        WHITEBOARD_INVALID_OPERATION, f"'{field}' on '{item['name']}' in '{key}' is a string",
                    )

    names = operations.get(OPERATION_DELETE)
    if names is not None and (not isinstance(names, list) or not all(isinstance(n, str) for n in names)):
        raise LysError(WHITEBOARD_INVALID_OPERATION, f"'{OPERATION_DELETE}' is a list of names")


def validate_scene(scene: Any, max_bytes: int) -> None:
    """
    Check a scene the editor sends wholesale before it is stored.

    Only the envelope is checked - the editor owns the format of what is inside an
    element - but the envelope is what the rest of the app reads: ``elements`` is walked
    by ``describe`` and patched by ``apply_operations``, so a scene without it, or with
    something that is not an element in it, would break the next chatbot turn.

    Raises:
        LysError: Not a scene, too many elements, or larger than ``max_bytes`` serialized.
    """
    if not isinstance(scene, dict):
        raise LysError(WHITEBOARD_INVALID_SCENE, "A scene is an object")

    elements = scene.get("elements")
    if not isinstance(elements, list):
        raise LysError(WHITEBOARD_INVALID_SCENE, "A scene holds its elements in a list")
    if len(elements) > MAX_ELEMENTS:
        raise LysError(WHITEBOARD_INVALID_SCENE, f"A board holds at most {MAX_ELEMENTS} elements")
    if not all(isinstance(e, dict) and isinstance(e.get("id"), str) and isinstance(e.get("type"), str)
               for e in elements):
        raise LysError(WHITEBOARD_INVALID_SCENE, "Every element is an object with an 'id' and a 'type'")

    for key in ("appState", "files"):
        if key in scene and not isinstance(scene[key], dict):
            raise LysError(WHITEBOARD_INVALID_SCENE, f"'{key}' is an object")

    try:
        size = len(json.dumps(scene, separators=(",", ":"), allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as e:
        raise LysError(WHITEBOARD_INVALID_SCENE, f"Scene is not serializable: {e}")
    if size > max_bytes:
        raise LysError(WHITEBOARD_SCENE_TOO_LARGE, f"Scene is {size} bytes, the limit is {max_bytes}")


def apply_operations(scene: Dict[str, Any], operations: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a patch to a scene and return the new scene.

    The patch is ``{"add": [...], "update": [...], "delete": ["name", ...]}``, applied in
    that order so the same patch always resolves the same way. Elements are named, never
    identified: an add whose name is already on the board **updates it**, which is what
    keeps a writer that rephrases its own titles from covering the board in near-duplicates
    of the same idea.

    Pure: the scene passed in is not modified. An invalid operation raises, and the
    caller keeps the scene it had - a patch is all or nothing, never half drawn.

    Args:
        scene: The current scene.
        operations: The patch.

    Returns:
        A new scene with the patch applied.

    Raises:
        LysError: Unknown operation or kind, unnamed or unknown element, geometry or
            colour the scene refuses, malformed table or chart data, or a board that
            would grow past its cap.
    """
    _check_patch_shape(operations)

    unknown = set(operations) - set(OPERATION_KEYS)
    if unknown:
        raise LysError(WHITEBOARD_UNKNOWN_OPERATION, f"Unknown operations: {', '.join(sorted(unknown))}")

    if operations.get(OPERATION_THEME) is not None:
        scene = _set_theme(scene, operations[OPERATION_THEME])
    default_stroke = theme(scene)["stroke"]

    elements: List[Dict[str, Any]] = [dict(e) for e in scene.get("elements", [])]
    # What changed place or appeared: the links touching it are routed again at the end.
    moved: List[str] = []

    for operation in operations.get(OPERATION_ADD) or []:
        element_id = slugify(operation.get("name") or "")
        if element_id in _index(elements):
            if _update(elements, operation, element_id):
                moved.append(element_id)
        else:
            _add(elements, operation, element_id, default_stroke)
            moved.append(element_id)

    for operation in operations.get(OPERATION_UPDATE) or []:
        element_id = slugify(operation.get("name") or "")
        if _update(elements, operation, element_id):
            moved.append(element_id)

    for name in operations.get(OPERATION_DELETE) or []:
        elements = _delete(elements, name)

    _refresh_links(elements, moved)

    if len(elements) > MAX_ELEMENTS:
        raise LysError(
            WHITEBOARD_TOO_MANY_ELEMENTS,
            f"A board holds at most {MAX_ELEMENTS} elements, this patch would bring it to {len(elements)}",
        )

    return {**scene, "elements": elements}


def _kind_on_board(element: Dict[str, Any]) -> str:
    """The kind an anchor element was drawn as, read back from its Excalidraw shape."""
    custom = element.get("customData") or {}
    if custom.get(KIND_KEY) in (ElementKind.TABLE.value, ElementKind.CHART.value):
        return custom[KIND_KEY]
    if element.get("type") == "arrow":
        return ElementKind.ARROW.value
    if element.get("type") == "line":
        return ElementKind.LINE.value
    if element.get("type") == "frame":
        return ElementKind.FRAME.value
    if element.get("type") == "text":
        return ElementKind.TEXT.value
    return next(
        (kind.value for kind, shape in LABELLED_SHAPES.items() if shape == element.get("type")),
        ElementKind.NOTE.value,
    )


def describe(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    What is on the board, as the caller that drew it can read it back.

    Names, texts **and geometry**: a caller that places has to be able to see where the
    rest already is, or its second patch lands on top of its first. Bound labels and the
    parts of a table or a chart are folded into the element they belong to rather than
    listed as elements of their own - they have no name their caller could use.

    This is what lets a writer revisit instead of only append - without it, a board grown
    over months can only be added to.
    """
    elements = scene.get("elements", [])
    by_id = _index(elements)
    board_stroke = theme(scene)["stroke"]
    described: List[Dict[str, Any]] = []
    for element in elements:
        if not _is_anchor(element):
            continue
        custom = element.get("customData") or {}
        left, top, width, height = _box(element, elements)
        if element.get("frameId") and element["frameId"] in by_id:
            # Reported as they are given: from the frame's corner.
            left -= by_id[element["frameId"]]["x"]
            top -= by_id[element["frameId"]]["y"]
        entry: Dict[str, Any] = {
            "name": element["id"],
            "x": round(left),
            "y": round(top),
            "width": round(width),
            "height": round(height),
        }
        label = by_id.get(f"{element['id']}{TEXT_SUFFIX}")

        entry["kind"] = kind = _kind_on_board(element)
        if kind in (ElementKind.TABLE.value, ElementKind.CHART.value):
            entry["data"] = custom.get(SPEC_KEY)
        elif kind in (ElementKind.ARROW.value, ElementKind.LINE.value):
            entry["from"] = (element.get("startBinding") or {}).get("elementId")
            entry["to"] = (element.get("endBinding") or {}).get("elementId")
            if label:
                entry["label"] = label.get("text", "")
        elif kind == ElementKind.FRAME.value:
            entry["text"] = element.get("name") or ""
        elif kind == ElementKind.TEXT.value:
            entry["text"] = element.get("text", "")
        else:
            entry["text"] = (label or element).get("text", "")

        if kind in (ElementKind.TABLE.value, ElementKind.CHART.value):
            # A figure's size and alignment are the ones it was drawn with, not its cells'.
            layout = custom.get(LAYOUT_KEY) or {}
            if layout.get("size", DEFAULT_TEXT_SIZE) != DEFAULT_TEXT_SIZE:
                entry["size"] = layout["size"]
            if layout.get("align"):
                entry["align"] = layout["align"]
        elif kind != ElementKind.FRAME.value:
            text_element = label or element
            size = _size_name(text_element.get("fontSize"))
            if size:
                entry["size"] = size
            default_align = "center" if label else "left"
            if text_element.get("type") == "text" and text_element.get("textAlign", default_align) != default_align:
                entry["align"] = text_element["textAlign"]
        # Only what departs from the board's theme: that is what a reader has to know.
        defaults = {"stroke": board_stroke, "corners": DEFAULT_CORNERS, "thickness": DEFAULT_THICKNESS}
        for field, name in _look_names(element).items():
            if name != defaults[field]:
                entry[field] = name
        if element.get("frameId"):
            entry["frame"] = element["frameId"]
        described.append(entry)
    return described


def slides(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    The deck: the board's frames in reading order, numbered from one, with their titles.

    Rows from the top, left to right inside a row; two frames share a row when their
    vertical extents overlap by more than half the shorter one. The editor orders its
    slides by the same rule, and nothing else orders them: a frame's position IS its
    rank, so the reader and the writer of the board agree on the deck without storing
    it anywhere.
    """
    frames = sorted(
        (e for e in scene.get("elements", []) if e.get("type") == "frame" and not e.get("isDeleted")),
        key=lambda e: (e.get("y", 0), e.get("x", 0)),
    )
    rows: List[List[Dict[str, Any]]] = []
    row_top = row_bottom = 0.0
    for frame in frames:
        top, height = frame.get("y", 0), max(frame.get("height", 0), 0)
        if rows:
            overlap = min(row_bottom, top + height) - max(row_top, top)
            shorter = min(row_bottom - row_top, height)
            if overlap > shorter * SLIDE_ROW_OVERLAP_SHARE:
                rows[-1].append(frame)
                row_bottom = max(row_bottom, top + height)
                continue
        rows.append([frame])
        row_top, row_bottom = top, top + height

    deck: List[Dict[str, Any]] = []
    for row in rows:
        for frame in sorted(row, key=lambda e: e.get("x", 0)):
            deck.append({"index": len(deck) + 1, "name": frame["id"], "title": frame.get("name") or ""})
    return deck


def drawn_names(operations: Dict[str, Any]) -> List[str]:
    """
    The elements a patch puts on the board or changes, by name, in the order it names
    them - what there is to look at once it is applied.

    Not the ones it deletes: nothing is left of them to show. A name both drawn and
    deleted by the same patch is gone too, since deletes are applied last.
    """
    deleted = {slugify(name) for name in operations.get(OPERATION_DELETE) or []}
    names: List[str] = []
    for key in (OPERATION_ADD, OPERATION_UPDATE):
        for item in operations.get(key) or []:
            name = slugify(item.get("name") or "")
            if name and name not in deleted and name not in names:
                names.append(name)
    return names


def resolve_focus(scene: Dict[str, Any], names: Any) -> List[str]:
    """
    The elements a caller asks to bring into view, checked against the board.

    Refused rather than skipped when one is not there: a caller told "shown" about an
    element that does not exist would describe to the user a view they are not looking
    at. It is the caller that can fix the name, and only if it is told.

    Raises:
        LysError: Not a list of names, or a name that is not on the board.
    """
    if not isinstance(names, list) or not names or not all(isinstance(name, str) for name in names):
        raise LysError(WHITEBOARD_INVALID_OPERATION, "'focus' is a list of element names")
    by_id = _index(scene.get("elements", []))
    resolved: List[str] = []
    for name in names:
        element_id = slugify(name)
        if element_id not in by_id or not _is_anchor(by_id[element_id]):
            raise LysError(WHITEBOARD_UNKNOWN_ELEMENT, f"Element '{element_id}' is not on the board")
        if element_id not in resolved:
            resolved.append(element_id)
    return resolved


def overlaps(scene: Dict[str, Any], names: Sequence[str]) -> List[Dict[str, Any]]:
    """
    Where the elements named sit on top of something else on the board.

    A caller places by coordinates it chooses BEFORE the sizes exist: a note is as tall
    as its text turns out to need, a table as wide as its content. It cannot see the
    result either. So the board looks for it, and says: which element, on which other,
    over how much - enough for the caller to move one of the two in its next call.

    Only what the caller just drew is checked, against everything: an overlap the user
    made by hand elsewhere on the board is theirs, and reporting it on every call would
    teach the caller to ignore the report.

    Links are left out - an arrow crosses things by nature - and so is an element lying
    wholly inside a frame, which is what a frame is for. The largest overlaps come
    first, and the list is capped: past a handful the layout has to be redone, not
    patched pair by pair.
    """
    elements = scene.get("elements", [])
    by_id = _index(elements)
    boxes = {
        element_id: _box(element, elements)
        for element_id, element in by_id.items()
        if _is_anchor(element) and not (element.get("type") in ("arrow", "line") and _owner(element) is None)
    }

    found: List[Tuple[float, Dict[str, Any]]] = []
    reported: set = set()
    for name in names:
        if name not in boxes:
            continue
        x, y, width, height = boxes[name]
        for other, (other_x, other_y, other_width, other_height) in boxes.items():
            if other == name or (other, name) in reported:
                continue
            shared_width = min(x + width, other_x + other_width) - max(x, other_x)
            shared_height = min(y + height, other_y + other_height) - max(y, other_y)
            if shared_width <= OVERLAP_TOLERANCE or shared_height <= OVERLAP_TOLERANCE:
                continue
            if _holds(by_id[other], boxes[other], boxes[name]) or _holds(by_id[name], boxes[name], boxes[other]):
                continue
            reported.add((name, other))
            found.append((shared_width * shared_height, {
                "element": name, "with": other,
                "width": round(shared_width), "height": round(shared_height),
            }))

    found.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in found[:MAX_REPORTED_OVERLAPS]]


def _holds(
    container: Dict[str, Any],
    outer: Tuple[float, float, float, float],
    inner: Tuple[float, float, float, float],
) -> bool:
    """Whether ``container`` is a frame with ``inner`` lying wholly inside it."""
    if container.get("type") != "frame":
        return False
    return (
        inner[0] >= outer[0] and inner[1] >= outer[1]
        and inner[0] + inner[2] <= outer[0] + outer[2]
        and inner[1] + inner[3] <= outer[1] + outer[3]
    )


def element_names(scene: Dict[str, Any]) -> List[str]:
    """Names on the board, bound labels and composite parts excluded."""
    return [e["id"] for e in scene.get("elements", []) if _is_anchor(e)]


def find(scene: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """One element by name, or None."""
    return _index(scene.get("elements", [])).get(slugify(name))
