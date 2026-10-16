"""
Chatbot tool definitions for the whiteboard.

The descriptions are the prompt: they are what decides whether the model reaches for a
board at the right moment and what it does with it once there, and they are written for
it rather than for a reader of this file.

Two tools only - one to draw, one to read back - because a model given many ways to
touch a surface spends its turn choosing between them. The vocabulary lives inside the
single draw call instead, where one patch can lay out a whole diagram at once.
"""

from lys.apps.ai_whiteboard.modules.whiteboard.consts import SLIDE_GAP, SLIDE_HEIGHT, SLIDE_WIDTH

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
    "align": {
        "type": "string",
        "enum": ["left", "center", "right"],
        "description": (
            "Where the text sits: in a box (centred unless said), a free text (left unless "
            "said), or every cell of a table. Unsaid, a table reads like a financial one: "
            "headers centred, figures right, labels left - say it only to override that."
        ),
    },
    "stroke": {
        "type": "string",
        "enum": ["clean", "sketch"],
        "description": (
            "How the lines are drawn: 'clean' is ruled, 'sketch' hand-drawn. Unsaid, the "
            "board's theme decides."
        ),
    },
    "corners": {"type": "string", "enum": ["square", "round"], "description": "Box corners."},
    "thickness": {
        "type": "string",
        "enum": ["thin", "bold"],
        "description": "Line weight. 'bold' to single something out.",
    },
    "size": {
        "type": "string",
        "enum": ["small", "normal", "large", "title"],
        "description": (
            "Text size. 'normal' for a diagram worked on at a desk; on a slide, read from "
            "across a room, 'title' for the slide's title and 'large' for everything else."
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
                "frame: a zone labelled with its 'text' (an empty 'text' leaves it bare); "
                "put elements in it with their 'frame' field. "
                "table: a grid, from 'headers' and 'rows' - sized to its content, never pass a width. "
                "chart: a chart, from 'chart'."
            ),
        },
        "text": {"type": "string", "description": "What the element says. A few words, not a paragraph."},
        "label": {"type": "string", "description": "For an arrow or a line: a couple of words written on it."},
        "from": {"type": "string", "description": "For an arrow or a line: name of the source element."},
        "to": {"type": "string", "description": "For an arrow or a line: name of the target element."},
        "frame": {
            "type": "string",
            "description": (
                "Name of a frame this element belongs inside. Inside a frame, 'x' and 'y' "
                f"count from the frame's top-left corner: a slide is 0 to {SLIDE_WIDTH} across "
                f"and 0 to {SLIDE_HEIGHT} down, whatever row of the deck it sits on."
            ),
        },
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
        "frame": {
            "type": "string",
            "description": (
                "Name of the frame to move the element into, with everything it is made of "
                "- moving it by 'x' and 'y' alone leaves it attached to its old frame. "
                "Without 'x' and 'y' it lands in the frame's next free slot. An empty string "
                "takes it out of its frame, its 'x' and 'y' then counting from the board's "
                "corner. Inside a frame, 'x' and 'y' count from the frame's top-left corner."
            ),
        },
        "headers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Redraw a table with these columns. Leave out 'rows' to keep its current lines.",
        },
        "rows": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
            "description": (
                "Redraw a table with these lines, all of them: they replace the current ones. "
                "Leave out 'headers' to keep its current columns."
            ),
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
            "**A story is a deck.** When what you have to say unfolds in steps - a finding, "
            f"its causes, the options, a recommendation - draw one frame per step, {SLIDE_WIDTH} "
            f"wide and {SLIDE_HEIGHT} tall, stacked in a column {SLIDE_GAP} apart (y: 0, "
            f"{SLIDE_HEIGHT + SLIDE_GAP}, {2 * (SLIDE_HEIGHT + SLIDE_GAP)}…). The frame's 'text' "
            "is the slide's title as the user's slide list shows it ('1. Findings') - never a "
            "code like 's1' - and the slide repeats it as a 'text' at its top. Put every "
            "element of a step inside its frame with 'frame' - its coordinates then count "
            "from the frame's corner, so the title of every slide is at the same 'y'. The "
            "user presents the frames as slides in the order they read on "
            "the board: top to bottom, then left to right - so a new step goes below the "
            "last, and reordering is moving frames. Keep a step's elements within its "
            "frame: what sticks out is cut off the slide. A slide is read from across a room: "
            "a 'text' title at the top in size 'title', everything else in size 'large', "
            "at most five boxes, each 400 to 560 wide, laid out in two columns or a row - "
            "fill the frame, its lower half included: two rows of boxes, or a chart 360 tall "
            "beside them; never pile small boxes in one corner. A table on a slide takes "
            "size 'large' too; a chart takes a 'width' of 560 to 700 and a 'height' of 320 "
            "to 400. Put the speaker notes of a slide - "
            "the points to make, what to say - in a 'note' (a sticky, 420 wide) named "
            "'notes-<frame name>' placed just RIGHT of the frame, outside it: on the board "
            "for the user to work on with you, off the slide when it is presented.\n"
            "You place blind: a box is as tall as its text turns out to need, and you only "
            "learn sizes from the result. When the result carries 'overlaps' - each entry "
            "an 'element' you drew sitting on a 'with', over a 'width' and a 'height' - "
            "something is unreadable on the user's screen: fix it before you answer, by "
            "moving one of the two with update (x, y), using the sizes the result gives.\n"
            "Reuse the SAME name to come back to an element: naming an existing one "
            "rewrites it instead of adding a near-duplicate beside it, so keep a name "
            "stable once you have used it, even if you would phrase the title differently "
            "today. Moving an element carries its label and its arrows with it.\n"
            "The board never stands in for what another of your tools records: when a tool "
            "exists for it, propose it with that tool; drawing it instead leaves the user "
            "with a picture of something that was never recorded.\n"
            "Revisit as much as you add: when something on the board turns out wrong or "
            "outdated, update or delete it. A board only ever added to stops being "
            "readable, and the user relies on it to still be true.\n"
            "The user's view follows you: it moves onto what a call adds or changes. To "
            "SHOW something already on the board - 'show me the org chart', 'go back to "
            "the table' - call with 'focus' alone: nothing is redrawn, the view goes there."
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
                "theme": {
                    "type": "object",
                    "description": (
                        "The board's look, for the whole board: 'background' (a hexadecimal "
                        "colour) and 'stroke' ('clean', ruled lines, the default - or 'sketch', "
                        "hand-drawn, only when the user asks for it). The stroke applies to "
                        "what is drawn from then on; set it before drawing a deck."
                    ),
                    "properties": {
                        "background": {"type": "string"},
                        "stroke": {"type": "string", "enum": ["clean", "sketch"]},
                    },
                },
                "focus": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Names of the elements to bring into the user's view. Leave it out "
                        "when drawing, unless the point of the call is somewhere else than "
                        "what it changes. Alone - no add, update or delete - it shows what is "
                        "already there without touching it; name every element of the "
                        "diagram you mean, title included."
                    ),
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
            "table and chart - and the deck: 'slides', the frames in the order the user "
            "presents them, with their titles; a slide's notes are the 'notes-<frame>' text. "
            "Call it before changing a board you did not fill during this "
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
