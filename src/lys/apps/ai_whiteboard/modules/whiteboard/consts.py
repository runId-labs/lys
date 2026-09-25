"""
Whiteboard constants: what a caller may draw, and the limits it is held to.
"""

from enum import Enum


class ElementKind(str, Enum):
    """
    What a caller may ask for.

    Business shapes rather than the Excalidraw type system: ``note`` is a rectangle and
    the text bound inside it, ``table`` is a few dozen elements laid out as a grid. The
    caller says what it means; how many elements that takes is this module's business.
    """

    NOTE = "note"        # a labelled box - the post-it of a reflection
    ELLIPSE = "ellipse"  # a labelled ellipse - a state, a start or an end
    DIAMOND = "diamond"  # a labelled diamond - a decision point
    TEXT = "text"        # free-standing text, for a title or a caption
    ARROW = "arrow"      # a directed link, optionally labelled
    LINE = "line"        # an undirected link or a plain rule
    FRAME = "frame"      # a named zone grouping what sits inside it
    TABLE = "table"      # a grid of cells, drawn from headers and rows
    CHART = "chart"      # a chart, drawn from its data


# Kinds that are a shape carrying a text label inside them. They share a factory: the
# only thing that changes is the Excalidraw type, and a label that had to be centred
# differently per shape would be a layout rule hiding in three places.
LABELLED_SHAPES = {
    ElementKind.NOTE: "rectangle",
    ElementKind.ELLIPSE: "ellipse",
    ElementKind.DIAMOND: "diamond",
}

# Kinds drawn as a segment between two points, bound to elements when named.
LINEAR_KINDS = (ElementKind.ARROW, ElementKind.LINE)


class ChartType(str, Enum):
    """
    How a chart is drawn, which is not a style choice: it decides whether the result
    stays editable by hand.

    ``BAR`` becomes real rectangles the user can drag, recolour and annotate — the whole
    point of a whiteboard. ``PIE`` and ``LINE`` have no native equivalent (the format has
    neither arcs nor polylines with axes), so they travel as a spec and are rendered as
    an image by the viewer.
    """

    BAR = "bar"
    PIE = "pie"
    LINE = "line"


# Chart types the editor cannot express natively, carried as a spec and rendered by the
# front from ``customData``. Kept as a set so the split is read from one place.
IMAGE_CHART_TYPES = {ChartType.PIE, ChartType.LINE}


# ==================== Automatic layout ====================

# Where an element goes when the caller did not say. Callers place what they care about
# and leave the rest to the grid, so both have to coexist: the search below walks these
# cells and skips the ones an existing element already covers.
GRID_COLUMNS = 4
CELL_WIDTH = 260
CELL_HEIGHT = 200
# Rows scanned before giving up and stacking underneath everything. A board dense enough
# to exhaust this is one the caller has been placing by hand anyway.
MAX_GRID_ROWS = 60
# Vertical gap left when placement falls back to stacking under the existing content.
STACK_GAP = 60

NOTE_WIDTH = 220
NOTE_HEIGHT = 120
# An ellipse needs more room than a rectangle for the same text: its inscribed area is
# roughly half the bounding box, so a label that fits a note overflows an ellipse.
ELLIPSE_PADDING_FACTOR = 1.45
DIAMOND_PADDING_FACTOR = 1.6


# ==================== Text ====================

# Excalidraw's own defaults. Font family 1 is its hand-drawn face.
FONT_SIZE = 16
FONT_FAMILY = 1
LINE_HEIGHT = 1.25
# Width of an average character as a fraction of the font size. The editor measures text
# with real font metrics and we cannot, so this errs generous: a box slightly too wide is
# invisible, a box too narrow clips the text — which is the failure this replaces.
CHAR_WIDTH_RATIO = 0.58
# Excalidraw's padding between a container's edge and the text bound inside it.
BOUND_TEXT_PADDING = 5
# Size floor for a labelled shape, so a one-word note is still a box and not a sliver.
MIN_SHAPE_WIDTH = 120
MIN_SHAPE_HEIGHT = 60


# ==================== Palette ====================

STROKE_COLOR = "#1e1e1e"
NOTE_BACKGROUND = "#fff3bf"
TRANSPARENT = "transparent"
# Excalidraw's own element colours, used to give chart series distinct fills without
# inventing a palette the rest of the board does not use.
SERIES_COLORS = ("#a5d8ff", "#b2f2bb", "#ffc9c9", "#ffec99", "#d0bfff", "#99e9f2", "#ffd8a8", "#eebefa")


# ==================== Limits ====================

# A board past this stops being readable long before it stops being storable. The cap
# exists against a writer that loops, not against a user who works.
MAX_ELEMENTS = 500
# Serialized size of a scene saved by the editor. Images travel inside the scene as
# base64 in ``files``, so this is generous; override per project with the
# ``ai_whiteboard.max_scene_bytes`` plugin setting.
DEFAULT_MAX_SCENE_BYTES = 10 * 1024 * 1024
MAX_SCENE_BYTES_SETTING = "max_scene_bytes"
PLUGIN_NAME = "ai_whiteboard"
# Coordinates are unbounded in the format, which makes a typo a board nobody can find
# again: the editor would scroll to content a million pixels away and show white.
MAX_COORDINATE = 100_000
MIN_SIZE = 1
MAX_SIZE = 10_000
MAX_TEXT_LENGTH = 2_000
# Tables are drawn as real elements, so their size is bounded by the board's: a grid
# past this is both unreadable and most of the element budget.
MAX_TABLE_COLUMNS = 10
MAX_TABLE_ROWS = 25
MAX_CHART_POINTS = 24

TABLE_CELL_WIDTH = 160
TABLE_ROW_HEIGHT = 36
CHART_WIDTH = 420
CHART_HEIGHT = 260
# Room left under a bar chart for the category labels.
CHART_LABEL_BAND = 28


# Operation keys accepted in a patch, applied in this order: an add followed by a delete
# of the same name in one patch must resolve the same way every time.
OPERATION_ADD = "add"
OPERATION_UPDATE = "update"
OPERATION_DELETE = "delete"
OPERATION_KEYS = (OPERATION_ADD, OPERATION_UPDATE, OPERATION_DELETE)


# Title of a board the chatbot opens for a conversation that has none yet. Conversation
# titles are written by a background task on the first exchange, so a board opened early
# would otherwise have nothing to copy - and the column is NOT NULL on purpose, an
# untitled board is unfindable in a list.
DEFAULT_TITLE = "Untitled whiteboard"

# Mirrors the Whiteboard.title column, which would reject anything longer.
TITLE_MAX_LENGTH = 255

# Pushed on the owner's channel whenever the scene changes. Carries the board id and the
# new revision, never the scene: signals are not replayed, so a client that missed one
# must be able to tell and refetch rather than apply a patch onto a stale scene.
WHITEBOARD_UPDATED_SIGNAL = "WHITEBOARD_UPDATED"

# GraphQL node type a whiteboard GlobalID carries. Clients only ever handle GlobalIDs, so
# the signal hands one out and the query takes the same back. The chatbot tools are not
# clients of the schema - they call the service - and keep the raw id.
WHITEBOARD_NODE_NAME = "WhiteboardNode"
USER_CHANNEL_TEMPLATE = "user:{user_id}"
