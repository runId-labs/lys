"""
Chatbot tool definitions for the whiteboard.

The descriptions are the prompt: they are what decides whether the model reaches for a
board at the right moment and what it does with it once there, and they are written for
it rather than for a reader of this file.

Two tools only - one to draw, one to read back - because a model given many ways to
touch a surface spends its turn choosing between them. The vocabulary lives inside the
single draw call instead, where one patch can lay out a whole diagram at once.
"""

# Shared by add and update: everything about how an element looks and where it sits.
# Declared once so the two operations cannot drift apart - a field the model can set on
# creation and not afterwards is a board it can draw but not fix.
_GEOMETRY_PROPERTIES = {
    "x": {
        "type": "number",
        "description": (
            "Left edge, in board units (roughly pixels). Goes with 'y' - give both or "
            "neither. Omit both to let the board place the element in the next free slot."
        ),
    },
    "y": {"type": "number", "description": "Top edge. Positive goes down. Goes with 'x'."},
    "width": {"type": "number", "description": "Width. Omitted, it is measured from the text."},
    "height": {"type": "number", "description": "Height. Omitted, it is measured from the text."},
    "color": {
        "type": "string",
        "description": "Stroke and text colour, hexadecimal ('#1e1e1e') or 'transparent'.",
    },
    "background": {
        "type": "string",
        "description": (
            "Fill colour, hexadecimal ('#ffc9c9') or 'transparent'. Use it to group by "
            "meaning - one colour per theme, or red for what is at risk."
        ),
    },
}

_CHART_SCHEMA = {
    "type": "object",
    "description": "For kind 'chart': the figures. The board draws the chart from them.",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["bar", "pie", "line"],
            "description": (
                "bar: compare magnitudes - drawn as real rectangles the user can move and "
                "recolour, so prefer it. pie: shares of one whole. line: a series over time."
            ),
        },
        "title": {"type": "string", "description": "Short caption above the chart."},
        "data": {
            "type": "array",
            "description": "The points, in the order they should read.",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "What this point is."},
                    "value": {"type": "number", "description": "Its figure."},
                },
                "required": ["label", "value"],
            },
        },
    },
    "required": ["type", "data"],
}

_ADD_ITEM = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": (
                "Short, stable, human name identifying this element. This is how you reach "
                "it again later, and naming one that already exists rewrites it rather than "
                "adding a near-duplicate beside it."
            ),
        },
        "kind": {
            "type": "string",
            "enum": ["note", "ellipse", "diamond", "text", "arrow", "line", "frame", "table", "chart"],
            "description": (
                "note: a labelled box, the default for an idea, an option, a figure. "
                "ellipse: a start or an end state. diamond: a decision point. "
                "text: free-standing text, for a title or a caption. "
                "arrow: a directed link between two elements named in 'from' and 'to'. "
                "line: an undirected link, or a plain rule. "
                "frame: a named zone; put elements in it with their 'frame' field. "
                "table: a grid, from 'headers' and 'rows'. "
                "chart: a chart, from 'chart'."
            ),
        },
        "text": {"type": "string", "description": "What the element says. A few words, not a paragraph."},
        "label": {"type": "string", "description": "For an arrow or a line: a couple of words written on it."},
        "from": {"type": "string", "description": "For an arrow or a line: name of the source element."},
        "to": {"type": "string", "description": "For an arrow or a line: name of the target element."},
        "frame": {"type": "string", "description": "Name of a frame this element belongs inside."},
        "headers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "For kind 'table': the column titles.",
        },
        "rows": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
            "description": "For kind 'table': one list of cells per line, every line filling every column.",
        },
        "chart": _CHART_SCHEMA,
        **_GEOMETRY_PROPERTIES,
    },
    "required": ["name"],
}

_UPDATE_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Name of the element to change."},
        "text": {"type": "string", "description": "Its new text. The box grows if the text no longer fits."},
        "label": {"type": "string", "description": "For an arrow or a line: its new label."},
        "headers": {"type": "array", "items": {"type": "string"}, "description": "Redraw a table with these columns."},
        "rows": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
            "description": "Redraw a table with these lines.",
        },
        "chart": _CHART_SCHEMA,
        **_GEOMETRY_PROPERTIES,
    },
    "required": ["name"],
}

DRAW_ON_WHITEBOARD_TOOL = {
    "type": "function",
    "function": {
        "name": "draw_on_whiteboard",
        "description": (
            "Put something on the user's whiteboard: a side panel they can see, edit by "
            "hand, and come back to weeks later. Use it when what you have to say is not "
            "a sentence - several items to compare, a chain of cause and effect, options "
            "weighed against each other, figures that mean more side by side than in a "
            "paragraph. Say a short sentence in the chat and draw the rest; do not repeat "
            "the board's content in your answer.\n"
            "**Lay it out yourself.** You choose where every element goes, with 'x' and "
            "'y', and how big it is. Think of the board as a sheet you are drawing on: a "
            "flow reads left to right with arrows between the boxes, a comparison reads as "
            "columns, a hierarchy reads top down. Leave real space between elements - a "
            "note is about 220 wide and 100 tall, so 260 between their left edges and 180 "
            "between their tops keeps a diagram breathing. Give a diagram a title in 'text' "
            "above it, and send the whole layout in ONE call so it appears at once. "
            "Coordinates are optional: elements you do not place are dropped in the next "
            "free slot, which is fine for a lone note and wrong for a diagram.\n"
            "Reuse the SAME name to come back to an element: naming an existing one "
            "rewrites it instead of adding a near-duplicate beside it, so keep a name "
            "stable once you have used it, even if you would phrase the title differently "
            "today. Moving an element carries its label and its arrows with it.\n"
            "Revisit as much as you add: when something on the board turns out wrong or "
            "outdated, update or delete it. A board only ever added to stops being "
            "readable, and the user relies on it to still be true."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "add": {"type": "array", "description": "Elements to put on the board.", "items": _ADD_ITEM},
                "update": {
                    "type": "array",
                    "description": (
                        "Elements to change, by name: text, position, size, colour, or the "
                        "data a table or a chart is drawn from."
                    ),
                    "items": _UPDATE_ITEM,
                },
                "delete": {
                    "type": "array",
                    "description": (
                        "Names of elements to remove. Removing one also removes its label "
                        "and the arrows attached to it."
                    ),
                    "items": {"type": "string"},
                },
                "whiteboard_id": {
                    "type": "string",
                    "description": (
                        "Only when the user is looking at a specific board and asks you to "
                        "change THAT one. Leave it out otherwise: the conversation's own "
                        "board is used, and opened if it does not exist yet."
                    ),
                },
            },
        },
    },
}

READ_WHITEBOARD_TOOL = {
    "type": "function",
    "function": {
        "name": "read_whiteboard",
        "description": (
            "List what is on a whiteboard: the name, the kind, the text and the position "
            "and size of each element, what the arrows link, and the data behind each "
            "table and chart. Call it before changing a board you did not fill during this "
            "exchange - you cannot see it, and a board built over weeks holds things you "
            "never wrote. Also call it when the user refers to something 'on the board' "
            "without saying which element, and before adding to a board you placed by hand "
            "earlier, so your new elements land beside the old ones instead of on top."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "whiteboard_id": {
                    "type": "string",
                    "description": "The board to read. Leave it out for the conversation's own board.",
                },
            },
        },
    },
}
