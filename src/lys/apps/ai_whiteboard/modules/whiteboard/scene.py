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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
    BOUND_TEXT_PADDING,
    CELL_HEIGHT,
    CELL_WIDTH,
    CHAR_WIDTH_RATIO,
    CHART_HEIGHT,
    CHART_LABEL_BAND,
    CHART_WIDTH,
    ChartType,
    DIAMOND_PADDING_FACTOR,
    ELLIPSE_PADDING_FACTOR,
    FONT_FAMILY,
    FONT_SIZE,
    GRID_COLUMNS,
    IMAGE_CHART_TYPES,
    LABELLED_SHAPES,
    LINE_HEIGHT,
    LINEAR_KINDS,
    MAX_CHART_POINTS,
    MAX_COORDINATE,
    MAX_ELEMENTS,
    MAX_GRID_ROWS,
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
    OPERATION_UPDATE,
    SERIES_COLORS,
    STACK_GAP,
    STROKE_COLOR,
    TABLE_CELL_WIDTH,
    TABLE_ROW_HEIGHT,
    TRANSPARENT,
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


def _char_width(font_size: float) -> float:
    return font_size * CHAR_WIDTH_RATIO


def _wrap(text: str, max_chars: int) -> List[str]:
    """
    Break text into lines that fit ``max_chars``, keeping the caller's own line breaks.

    Words longer than a line are left whole rather than cut: a broken IBAN or SIREN is
    worse than a line that runs slightly wide, and the editor draws it either way.
    """
    max_chars = max(1, max_chars)
    lines: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _text_size(text: str, font_size: float = FONT_SIZE, max_width: Optional[float] = None) -> Tuple[float, float]:
    """
    How much room a text needs.

    Measured from character counts, not font metrics: the editor has the real face and we
    do not, so :data:`CHAR_WIDTH_RATIO` errs generous. A box slightly too wide is
    invisible on a whiteboard; a box too narrow clips the text, which is the failure this
    replaces.
    """
    char_width = _char_width(font_size)
    if max_width:
        lines = _wrap(text, int(max_width / char_width))
    else:
        lines = text.split("\n")
    width = max((len(line) for line in lines), default=0) * char_width
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


def _overlaps(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])


def _auto_position(elements: Sequence[Dict[str, Any]], width: float, height: float) -> Tuple[float, float]:
    """
    Where an element goes when the caller did not say.

    The first grid cell, scanning left to right then down, whose rectangle no existing
    element covers. That is what lets placed and unplaced elements share a board: a
    caller that positions a diagram by hand and then adds a note without coordinates gets
    the note beside the diagram, not on top of it.

    A board dense enough to fill the scanned rows gets the element stacked underneath
    everything, which is always free.
    """
    occupied = [
        _footprint(e) for e in elements
        if not e.get("containerId") and e.get("type") not in ("arrow", "line")
    ]
    for row in range(MAX_GRID_ROWS):
        for column in range(GRID_COLUMNS):
            candidate = (column * CELL_WIDTH, row * CELL_HEIGHT, width, height)
            if not any(_overlaps(candidate, taken) for taken in occupied):
                return candidate[0], candidate[1]
    bottom = max((y + h for _, y, _, h in occupied), default=0.0)
    return 0.0, bottom + STACK_GAP


def _resolve_position(
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    width: float,
    height: float,
) -> Tuple[float, float]:
    """The position the caller gave, or the first free cell. Both, never half of each."""
    has_x, has_y = operation.get("x") is not None, operation.get("y") is not None
    if has_x and has_y:
        return _coordinate(operation["x"], "x"), _coordinate(operation["y"], "y")
    if has_x or has_y:
        raise LysError(WHITEBOARD_INVALID_GEOMETRY, "'x' and 'y' go together: give both or neither")
    return _auto_position(elements, width, height)


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


def _label_element(container_id: str, text: str, container: Dict[str, Any]) -> Dict[str, Any]:
    """The text bound inside a shape. Its geometry is the container's, always."""
    return _base_element(
        f"{container_id}{TEXT_SUFFIX}", "text",
        x=container["x"] + BOUND_TEXT_PADDING,
        y=container["y"] + BOUND_TEXT_PADDING,
        width=max(container["width"] - 2 * BOUND_TEXT_PADDING, 1),
        height=max(container["height"] - 2 * BOUND_TEXT_PADDING, 1),
        text=text, originalText=text,
        fontSize=FONT_SIZE, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
        textAlign="center", verticalAlign="middle",
        autoResize=False,
        containerId=container_id,
    )


def _shape_size(kind: ElementKind, operation: Dict[str, Any], text: str) -> Tuple[float, float]:
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

    if width is None:
        natural, _ = _text_size(text)
        width = max(MIN_SHAPE_WIDTH, min(NOTE_WIDTH, natural * factor + 2 * BOUND_TEXT_PADDING))
    if height is None:
        usable = max(width / factor - 2 * BOUND_TEXT_PADDING, 1)
        _, needed = _text_size(text, max_width=usable)
        height = max(MIN_SHAPE_HEIGHT, needed * factor + 2 * BOUND_TEXT_PADDING)
    return width, height


def _make_labelled_shape(
    element_id: str,
    kind: ElementKind,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    text: str,
) -> List[Dict[str, Any]]:
    """A shape and the text bound inside it, which move and resize together."""
    width, height = _shape_size(kind, operation, text)
    x, y = _resolve_position(operation, elements, width, height)
    default_background = NOTE_BACKGROUND if kind is ElementKind.NOTE else TRANSPARENT
    container = _base_element(
        element_id, LABELLED_SHAPES[kind],
        x=x, y=y, width=width, height=height,
        boundElements=[{"type": "text", "id": f"{element_id}{TEXT_SUFFIX}"}],
        **_style(operation, default_background),
    )
    return [container, _label_element(element_id, text, container)]


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
    natural_width, natural_height = _text_size(text)
    width = _size(operation["width"], "width") if operation.get("width") is not None else max(natural_width, 1)
    if operation.get("height") is not None:
        height = _size(operation["height"], "height")
    else:
        _, height = _text_size(text, max_width=width)
    x, y = _resolve_position(operation, elements, width, height)
    style = _style(operation)
    return [_base_element(
        element_id, "text",
        x=x, y=y, width=width, height=max(height, 1),
        text=text, originalText=text,
        fontSize=FONT_SIZE, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
        textAlign="left", verticalAlign="top",
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
    A named zone. The editor draws its name in the corner and moves what sits inside it.

    Sized generously by default: a frame is a container, and one born too small for what
    the caller is about to put in it is a frame the user has to resize by hand.
    """
    width = _size(operation["width"], "width") if operation.get("width") is not None else CELL_WIDTH * 2
    height = _size(operation["height"], "height") if operation.get("height") is not None else CELL_HEIGHT * 2
    x, y = _resolve_position(operation, elements, width, height)
    return [_base_element(
        element_id, "frame",
        x=x, y=y, width=width, height=height,
        name=text or element_id,
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
        fields.update(_segment_between(by_id[source_id], by_id[target_id]))
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
    Redraw the links touching elements that just moved.

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
        if not start or not end or not moved & {start, end}:
            continue
        if start not in by_id or end not in by_id:
            continue
        element.update(_segment_between(by_id[start], by_id[end]))
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
    """
    headers, rows = _read_table(operation)
    columns = len(headers)
    lines = len(rows) + 1

    column_width = _size(operation["width"], "width") / columns if operation.get("width") is not None \
        else TABLE_CELL_WIDTH
    width, height = column_width * columns, TABLE_ROW_HEIGHT * lines
    x, y = _resolve_position(operation, elements, width, height)
    tag = {OWNER_KEY: element_id, KIND_KEY: ElementKind.TABLE.value}

    parts: List[Dict[str, Any]] = [_base_element(
        element_id, "rectangle",
        x=x, y=y, width=width, height=height,
        groupIds=[element_id], customData=tag,
        **_style(operation),
    )]
    for column in range(1, columns):
        parts.append(_base_element(
            f"{element_id}-col-{column}", "line",
            x=x + column * column_width, y=y, width=0, height=height,
            points=[[0, 0], [0, height]],
            groupIds=[element_id], customData=dict(tag),
            strokeColor=parts[0]["strokeColor"],
        ))
    for line in range(1, lines):
        parts.append(_base_element(
            f"{element_id}-row-{line}", "line",
            x=x, y=y + line * TABLE_ROW_HEIGHT, width=width, height=0,
            points=[[0, 0], [width, 0]],
            groupIds=[element_id], customData=dict(tag),
            strokeColor=parts[0]["strokeColor"],
        ))
    for line, cells in enumerate([headers] + rows):
        for column, cell in enumerate(cells):
            parts.append(_base_element(
                f"{element_id}-cell-{line}-{column}", "text",
                x=x + column * column_width + BOUND_TEXT_PADDING,
                y=y + line * TABLE_ROW_HEIGHT + BOUND_TEXT_PADDING,
                width=max(column_width - 2 * BOUND_TEXT_PADDING, 1),
                height=TABLE_ROW_HEIGHT - 2 * BOUND_TEXT_PADDING,
                text=cell, originalText=cell,
                fontSize=FONT_SIZE, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
                textAlign="left", verticalAlign="middle", autoResize=False,
                groupIds=[element_id], customData=dict(tag),
                strokeColor=parts[0]["strokeColor"],
            ))
    parts[0]["customData"] = {**tag, SPEC_KEY: {"headers": headers, "rows": rows}}
    return parts


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


def _make_bar_chart(
    element_id: str,
    operation: Dict[str, Any],
    elements: Sequence[Dict[str, Any]],
    labels: List[str],
    values: List[float],
    title: str,
) -> List[Dict[str, Any]]:
    """
    Bars as real rectangles, sitting on a baseline, each with its label underneath.

    Drawn natively because the format can express it exactly and the user can then drag a
    bar, recolour it or write next to it. Negative values are not plotted below the axis:
    a whiteboard bar chart is a comparison of magnitudes, and an axis crossing mid-figure
    is a statistics chart nobody asked for.
    """
    width = _size(operation["width"], "width") if operation.get("width") is not None else CHART_WIDTH
    height = _size(operation["height"], "height") if operation.get("height") is not None else CHART_HEIGHT
    x, y = _resolve_position(operation, elements, width, height + CHART_LABEL_BAND)
    tag = {OWNER_KEY: element_id, KIND_KEY: ElementKind.CHART.value}

    title_height = FONT_SIZE * LINE_HEIGHT if title else 0
    plot_height = height - title_height - CHART_LABEL_BAND
    baseline = y + title_height + plot_height
    slot = width / len(values)
    bar_width = slot * 0.7
    scale = max(abs(value) for value in values) or 1

    parts: List[Dict[str, Any]] = [_base_element(
        element_id, "line",
        x=x, y=baseline, width=width, height=0,
        points=[[0, 0], [width, 0]],
        groupIds=[element_id],
        customData={**tag, SPEC_KEY: {
            "type": ChartType.BAR.value, "title": title,
            "data": [{"label": label, "value": value} for label, value in zip(labels, values)],
        }},
    )]
    if title:
        parts.append(_base_element(
            f"{element_id}-title", "text",
            x=x, y=y, width=max(_text_size(title)[0], 1), height=title_height,
            text=title, originalText=title,
            fontSize=FONT_SIZE, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
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
        caption = f"{label}\n{value:g}"
        parts.append(_base_element(
            f"{element_id}-label-{position}", "text",
            x=bar_x, y=baseline + BOUND_TEXT_PADDING,
            width=max(bar_width, 1), height=CHART_LABEL_BAND,
            text=caption, originalText=caption,
            fontSize=FONT_SIZE * 0.75, fontFamily=FONT_FAMILY, lineHeight=LINE_HEIGHT,
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


def _attach_to_frame(created: List[Dict[str, Any]], operation: Dict[str, Any], by_id: Dict[str, Any]) -> None:
    """Put new elements inside a named frame, so the editor moves them with it."""
    frame_name = operation.get("frame")
    if not frame_name:
        return
    frame_id = slugify(frame_name)
    frame = by_id.get(frame_id)
    if frame is None or frame.get("type") != "frame":
        raise LysError(WHITEBOARD_UNKNOWN_ELEMENT, f"Frame '{frame_id}' is not on the board")
    for element in created:
        element["frameId"] = frame_id


def _add(elements: List[Dict[str, Any]], operation: Dict[str, Any], element_id: str) -> None:
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

    _attach_to_frame(created, operation, _index(elements))
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
        return

    label["text"] = text
    label["originalText"] = text
    _touch(label)

    if element.get("type") in ("arrow", "line"):
        label["width"], label["height"] = (max(size, 1) for size in _text_size(text))
        return

    usable = max(element["width"] - 2 * BOUND_TEXT_PADDING, 1)
    _, needed = _text_size(text, max_width=usable)
    if needed + 2 * BOUND_TEXT_PADDING > element["height"]:
        element["height"] = needed + 2 * BOUND_TEXT_PADDING
        _touch(element)
    _resize_label(element, label)


def _resize_label(container: Dict[str, Any], label: Dict[str, Any]) -> None:
    label["x"] = container["x"] + BOUND_TEXT_PADDING
    label["y"] = container["y"] + BOUND_TEXT_PADDING
    label["width"] = max(container["width"] - 2 * BOUND_TEXT_PADDING, 1)
    label["height"] = max(container["height"] - 2 * BOUND_TEXT_PADDING, 1)


def _move_and_resize(elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any]) -> bool:
    """
    Move or resize a named element, carrying with it everything it is made of.

    Returns whether anything changed, so the caller knows whether links need redrawing.
    A table is fifty elements behind one name; a caller that moved "the comparison" must
    not have to know that.
    """
    by_id = _index(elements)
    anchor = by_id[element_id]
    family = [anchor] + [e for e in elements if _owner(e) == element_id and e["id"] != element_id]
    label = by_id.get(f"{element_id}{TEXT_SUFFIX}")

    changed = False
    has_x, has_y = operation.get("x") is not None, operation.get("y") is not None
    if has_x != has_y:
        raise LysError(WHITEBOARD_INVALID_GEOMETRY, "'x' and 'y' go together: give both or neither")
    if has_x:
        dx = _coordinate(operation["x"], "x") - anchor["x"]
        dy = _coordinate(operation["y"], "y") - anchor["y"]
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
        _touch(anchor)
        changed = True
    if label and changed:
        _resize_label(anchor, label)
    return changed


def _restyle(elements: List[Dict[str, Any]], element_id: str, operation: Dict[str, Any]) -> None:
    """Recolour a named element and everything drawn under its name."""
    by_id = _index(elements)
    family = [by_id[element_id]] + [e for e in elements if _owner(e) == element_id and e["id"] != element_id]
    for field, key in (("color", "strokeColor"), ("background", "backgroundColor")):
        if operation.get(field) is None:
            continue
        value = _color(operation[field], field)
        for element in family:
            element[key] = value
            _touch(element)


def _update(elements: List[Dict[str, Any]], operation: Dict[str, Any], element_id: str) -> bool:
    """
    Apply one update: text, geometry, colour, or a redraw from new data.

    Returns whether the element moved, so links can be redrawn once at the end rather
    than after every operation.
    """
    if element_id not in _index(elements):
        raise LysError(WHITEBOARD_UNKNOWN_ELEMENT, f"Element '{element_id}' is not on the board")

    if operation.get("headers") is not None or operation.get("chart") is not None:
        return _redraw(elements, operation, element_id)

    moved = _move_and_resize(elements, element_id, operation)
    _restyle(elements, element_id, operation)
    text = operation.get("text") if operation.get("text") is not None else operation.get("label")
    if text is not None:
        _set_text(elements, element_id, _text_value(text))
    elif not moved and not any(operation.get(field) is not None for field in ("color", "background")):
        _touch(_index(elements)[element_id])
    return moved


def _redraw(elements: List[Dict[str, Any]], operation: Dict[str, Any], element_id: str) -> bool:
    """
    Rebuild a table or a chart from new data, where the old one stood.

    Redrawn rather than patched: the parts are a function of the data, so recomputing
    them is the only way to stay consistent with a row added or a value corrected - and
    the caller keeps the name it has been using, which is what it reaches the figure by.
    """
    by_id = _index(elements)
    anchor = by_id[element_id]
    position = {"x": anchor["x"], "y": anchor["y"]}
    removed = _collect_removals(elements, element_id)
    # The links to this figure survive: only the drawing is rebuilt, and they are
    # redrawn against the new geometry below.
    removed -= {e["id"] for e in elements if e.get("type") in ("arrow", "line")}

    remaining = [e for e in elements if e["id"] not in removed]
    rebuilt = dict(operation)
    rebuilt.setdefault("x", position["x"])
    rebuilt.setdefault("y", position["y"])
    kind = ElementKind.TABLE if operation.get("headers") is not None else ElementKind.CHART
    rebuilt["kind"] = kind.value

    elements[:] = remaining
    _add(elements, rebuilt, element_id)
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
        raise LysError(WHITEBOARD_INVALID_OPERATION, "A patch is an object with add, update and delete")

    for key in (OPERATION_ADD, OPERATION_UPDATE):
        items = operations.get(key)
        if items is None:
            continue
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise LysError(WHITEBOARD_INVALID_OPERATION, f"'{key}' is a list of objects")
        if not all(isinstance(item.get("name"), str) for item in items):
            raise LysError(WHITEBOARD_INVALID_OPERATION, f"Every item of '{key}' needs a 'name' string")

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

    elements: List[Dict[str, Any]] = [dict(e) for e in scene.get("elements", [])]
    moved: List[str] = []

    for operation in operations.get(OPERATION_ADD) or []:
        element_id = slugify(operation.get("name") or "")
        if element_id in _index(elements):
            if _update(elements, operation, element_id):
                moved.append(element_id)
        else:
            _add(elements, operation, element_id)

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
    described: List[Dict[str, Any]] = []
    for element in elements:
        if not _is_anchor(element):
            continue
        custom = element.get("customData") or {}
        entry: Dict[str, Any] = {
            "name": element["id"],
            "x": round(float(element.get("x", 0))),
            "y": round(float(element.get("y", 0))),
            "width": round(float(element.get("width", 0))),
            "height": round(float(element.get("height", 0))),
        }
        label = by_id.get(f"{element['id']}{TEXT_SUFFIX}")

        if custom.get(KIND_KEY) in (ElementKind.TABLE.value, ElementKind.CHART.value):
            entry["kind"] = custom[KIND_KEY]
            entry["data"] = custom.get(SPEC_KEY)
        elif element.get("type") in ("arrow", "line"):
            entry["kind"] = ElementKind.ARROW.value if element["type"] == "arrow" else ElementKind.LINE.value
            entry["from"] = (element.get("startBinding") or {}).get("elementId")
            entry["to"] = (element.get("endBinding") or {}).get("elementId")
            if label:
                entry["label"] = label.get("text", "")
        elif element.get("type") == "frame":
            entry["kind"] = ElementKind.FRAME.value
            entry["text"] = element.get("name") or ""
        elif element.get("type") == "text":
            entry["kind"] = ElementKind.TEXT.value
            entry["text"] = element.get("text", "")
        else:
            entry["kind"] = next(
                (kind.value for kind, shape in LABELLED_SHAPES.items() if shape == element.get("type")),
                ElementKind.NOTE.value,
            )
            entry["text"] = (label or element).get("text", "")

        if element.get("frameId"):
            entry["frame"] = element["frameId"]
        described.append(entry)
    return described


def element_names(scene: Dict[str, Any]) -> List[str]:
    """Names on the board, bound labels and composite parts excluded."""
    return [e["id"] for e in scene.get("elements", []) if _is_anchor(e)]


def find(scene: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """One element by name, or None."""
    return _index(scene.get("elements", [])).get(slugify(name))
