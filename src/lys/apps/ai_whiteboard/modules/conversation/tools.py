"""
Chatbot tool definitions for the whiteboard.

The descriptions are the prompt: they are what decides whether the model reaches for a
board at the right moment and what it does with it once there, and they are written for
it rather than for a reader of this file.

Two tools only - one to draw, one to read back - because a model given many ways to
touch a surface spends its turn choosing between them. The vocabulary lives inside the
single draw call instead, where one patch can lay out a whole diagram at once.
"""

from lys.apps.ai_whiteboard.modules.whiteboard.consts import (
    HEADS,
    PATHS,
    PATTERNS,
    SLIDE_GAP,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    SLIDE_ZONES,
    TONES,
)

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
    "zone": {
        "type": "string",
        "enum": list(SLIDE_ZONES),
        "description": (
            "In a slide (with 'frame'), where the element goes instead of 'x' and 'y': title (the band at "
            "the top), full (the body), left / right, top / bottom (its halves), top-left, top-right, "
            "bottom-left, bottom-right (its quarters). It takes the zone's width; its height is its content's."
        ),
    },
    "slot": {
        "type": "string",
        "description": (
            "With 'zone', several elements side by side: 'k/n', the k-th of n equal columns of the zone "
            "('1/3', '2/3', '3/3' for three KPIs across the top)."
        ),
    },
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
    "pattern": {
        "type": "string",
        "enum": list(PATTERNS),
        "description": (
            "The line: solid (default), dashed or dotted - what is not established: a hypothesis, a "
            "projection, an indirect link."
        ),
    },
    "tone": {
        "type": "string",
        "enum": list(TONES),
        "description": (
            "The colours by what they mean, from the board's palette - prefer it to 'color' and "
            "'background': accent (the message to remember), positive (a favourable move, a target "
            "met), risk (an alert, an unfavourable move), watch (a point to keep an eye on), neutral "
            "(context). A link or a text takes the line colour only. A 'color' or 'background' given "
            "too wins over the tone's."
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
                    "value": {
                        "type": "number",
                        "description": (
                            "Its figure, in the unit it is given in - never converted or rounded: the "
                            "chart writes its axis readably itself."
                        ),
                    },
                },
                "required": ["label", "value"],
            },
        },
        "references": {
            "type": "array",
            "description": (
                "Line chart only: up to 3 horizontal reference lines read against the curve - a "
                "threshold, a target, a budget -, drawn dashed with their label."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "What the line is ('Alert threshold')."},
                    "value": {"type": "number", "description": "Its level, in the unit of the points."},
                },
                "required": ["label", "value"],
            },
        },
    },
    "required": ["type", "data"],
}

# How a link is drawn: the same two fields whether it is added or changed.
_LINK_PROPERTIES = {
    "path": {
        "type": "string",
        "enum": list(PATHS),
        "description": (
            "For a link between 'from' and 'to': straight (default), elbow (at right angles - an "
            "org chart, a process) or curved (a loop, a return)."
        ),
    },
    "head": {
        "type": "string",
        "enum": list(HEADS),
        "description": "For a link: its end - arrow (default for an arrow), triangle, dot, bar or none.",
    },
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
            "enum": [
                "note", "ellipse", "diamond", "text", "arrow", "line", "frame", "table", "chart", "kpi", "callout",
                "steps",
            ],
            "description": (
                "note: a labelled box, the default for an idea, an option, a figure. "
                "ellipse: a start or an end state. diamond: a decision point. "
                "text: free-standing text, for a title or a caption. "
                "arrow: a directed link between two elements named in 'from' and 'to'. "
                "line: an undirected link, or a plain rule. "
                "frame: a zone labelled with its 'text' (an empty 'text' leaves it bare); "
                "put elements in it with their 'frame' field. "
                "table: a grid, from 'headers' and 'rows' - sized to its content, never pass a width. "
                "chart: a chart, from 'chart'. "
                "kpi: a key figure, laid out for you - 'value' in large type, 'text' (what it measures) "
                "below, 'delta' (how it moved) in its tone's colour. "
                "callout: the message to remember, 'text' in a card with a bar in its tone's colour. "
                "steps: 2 to 8 numbered steps in a row, joined by arrows, from 'items'. "
                "Prefer them to notes you would place yourself: they are laid out the same way every time."
            ),
        },
        "text": {"type": "string", "description": "What the element says. A few words, not a paragraph."},
        "label": {"type": "string", "description": "For an arrow or a line: a couple of words written on it."},
        "from": {"type": "string", "description": "For an arrow or a line: name of the source element."},
        "to": {"type": "string", "description": "For an arrow or a line: name of the target element."},
        **_LINK_PROPERTIES,
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
        "value": {"type": "string", "description": "For a kpi: the figure, written as it is to be read ('€4.9M')."},
        "delta": {
            "type": "string",
            "description": "For a kpi: how it moved, written as it is to be read ('+17 % vs 2024').",
        },
        "items": {
            "type": "array",
            "items": {"type": "string"},
            "description": "For steps: the steps in their order, a few words each.",
        },
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
        **_LINK_PROPERTIES,
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
        "value": {"type": "string", "description": "For a kpi: the figure, written as it is to be read ('€4.9M')."},
        "delta": {
            "type": "string",
            "description": "For a kpi: how it moved, written as it is to be read ('+17 % vs 2024').",
        },
        "items": {
            "type": "array",
            "items": {"type": "string"},
            "description": "For steps: the steps in their order, a few words each.",
        },
        **_GEOMETRY_PROPERTIES,
    },
    "required": ["name"],
}

# The description of the drawing tool, in the parts the two ways of drawing share. Drawn by the
# chatbot itself, every part is its own; drafted (see drafting.py), the layout goes to the drafter
# and the rest stays the chatbot's - the same text either way, never two versions of a rule.
_PURPOSE = (
    "Put something on the user's whiteboard: a side panel they can see, edit by "
    "hand, and come back to weeks later. Use it when what you have to say is not "
    "a sentence - several items to compare, a chain of cause and effect, options "
    "weighed against each other, figures that mean more side by side than in a "
    "paragraph. Say a short sentence in the chat and draw the rest; do not repeat "
    "the board's content in your answer.\n"
    "**One figure, one computation.** A figure you put both on the board and in your "
    "answer is computed once: the answer quotes the board's value, never a second "
    "estimate of it. Two values of the same thing on screen and in the chat leave the "
    "user unable to tell which one holds.\n"
)

_LAYOUT = (
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
)

_RECORDED = (
    "The board never stands in for what another of your tools records: when a tool "
    "exists for it, propose it with that tool; drawing it instead leaves the user "
    "with a picture of something that was never recorded.\n"
)

_REVISIT = (
    "Revisit as much as you add: when something on the board turns out wrong or "
    "outdated, update or delete it. A board only ever added to stops being "
    "readable, and the user relies on it to still be true.\n"
)

_VIEW = (
    "The user's view follows you: it moves onto what a call adds or changes. To "
    "SHOW something already on the board - 'show me the org chart', 'go back to "
    "the table' - call with 'focus' alone: nothing is redrawn, the view goes there.\n"
)

_BOARDS = (
    "**Your board and the user's boards.** Without 'whiteboard_id' or 'copy_from' a "
    "call draws on THIS conversation's board, opened if there is none. Every result "
    "says 'conversation_board': true for that one, false for a board you reached by "
    "id - the one on the user's screen, a deck from last month. Such a board stays "
    "the user's: you change it in place when asked to, and it never becomes yours. "
)

# Reusing a board as a model: the same opening whoever lays the drawing out, then what the call does.
_COPY_OPENING = (
    "To reuse a board as a model - the same deck next month, or for another company "
    "- call with 'copy_from' (and a 'title' for the copy): a new board opens as its "
    "exact copy, becomes this conversation's board, and the "
)

_COPY = _COPY_OPENING + (
    "patch of the same call "
    "lands on the copy; the original is left untouched. Then read it back and "
    "replace what differs - texts, figures, the data behind tables and charts - "
    "rather than redrawing it."
)

_DRAFTED_COPY = _COPY_OPENING + (
    "request of the same call "
    "is drawn on the copy; the original is left untouched. Say in the request what "
    "differs - texts, figures, the data behind tables and charts - to replace rather "
    "than redraw."
)

# The chatbot asks, the drafter draws (drafting.py): what the chatbot says of a drawing it does not lay out.
_DRAFTING = (
    "**Say what to draw; a drafter lays it out.** 'request' is all the drafter reads of the "
    "conversation: say in it what the board must show and in what form - a table, a flow, a "
    "comparison, a deck with the message of each slide -, every figure exactly as you "
    "computed it with its unit, period and source, and, on a board that already holds something, what to "
    "change or remove by "
    "the names a result or read_whiteboard gave. Every relation to draw as an arrow goes in "
    "'links', by the texts of its two boxes. It places, sizes and fixes what it drew itself, "
    "and what it drew is checked - overlaps, what sticks out of a slide, a label its box does "
    "not hold, a link left out, a figure the request does not give, a figure or a slide asked for and "
    "left out - and corrected once. The "
    "result says what it drew: 'drawn' (name, kind and text of what this call put or "
    "changed), 'note' (where it put it), and 'issues' for what the checks still find. Your "
    "answer quotes the figures the request gave, never another value of them.\n"
)

# What a patch is made of: drawn by the chatbot or by the drafter, the same vocabulary.
_PATCH_PROPERTIES = {
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
}

_FOCUS_PROPERTY = {
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
}

# The view of a drafted drawing: the drafter chooses the names, so the view follows what it drew.
_DRAFTED_FOCUS_PROPERTY = {
    "focus": {
        "type": "array",
        "items": {"type": "string"},
        "description": (
            "Only without 'request': names of elements already on the board to bring "
            "into the user's view, without touching them; name every element of the "
            "diagram you mean, title included. With a 'request' it is not read: the "
            "view goes to what the drafter drew."
        ),
    },
}

# The board a call draws on: the conversation's own, one named by id, or a copy of one.
_BOARD_PROPERTIES = {
    "whiteboard_id": {
        "type": "string",
        "description": (
            "Only when the user is looking at a specific board and asks you to "
            "change THAT one: it is changed in place and stays the user's - it "
            "does not become this conversation's board. Leave it out otherwise: "
            "the conversation's own board is used, and opened if it does not "
            "exist yet. The id exactly as the page context or a whiteboard tool "
            "result gives it."
        ),
    },
    "copy_from": {
        "type": "string",
        "description": (
            "A board to reuse as a model: a NEW board opens as its exact copy and "
            "becomes this conversation's board; what this call draws or changes "
            "then applies to the copy, never to the original. Not with "
            "'whiteboard_id'. The id exactly as the page context or a whiteboard "
            "tool result gives it."
        ),
    },
    "title": {
        "type": "string",
        "description": (
            "The board's name, as the user will find it again weeks later: a few "
            "words naming the subject ('Personnel costs 2025'), in the user's "
            "language. Only read when this call opens a new board - a copy "
            "included - an existing board keeps its name."
        ),
    },
}

DRAW_ON_WHITEBOARD_TOOL = {
    "type": "function",
    "function": {
        "name": "draw_on_whiteboard",
        "description": _PURPOSE + _LAYOUT + _RECORDED + _REVISIT + _VIEW + _BOARDS + _COPY,
        "parameters": {
            "type": "object",
            "properties": {**_PATCH_PROPERTIES, **_FOCUS_PROPERTY, **_BOARD_PROPERTIES},
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
                    "description": (
                        "The board to read, exactly as the page context or a whiteboard tool "
                        "result gives it. Leave it out for the conversation's own board."
                    ),
                },
            },
        },
    },
}

#: The tool of the drafter (drafting.py): the layout rules and the patch, nothing of the conversation.
DRAFT_PATCH_TOOL = {
    "type": "function",
    "function": {
        "name": "apply_patch",
        "description": (
            "Draw on the board you are composing. What you add, change or delete is applied at "
            "once, and the result gives every element's place and size: read it before your next "
            "patch. Nothing reaches the user until you stop calling - then everything you applied "
            "is written in one go, so fix what the result reports instead of leaving it.\n"
        ) + _LAYOUT + _REVISIT,
        "parameters": {"type": "object", "properties": _PATCH_PROPERTIES},
    },
}

#: The drawing tool of a chatbot whose drawings are drafted: it says what to draw, the drafter lays it out.
DRAFT_ON_WHITEBOARD_TOOL = {
    "type": "function",
    "function": {
        "name": "draw_on_whiteboard",
        "description": _PURPOSE + _DRAFTING + _RECORDED + _VIEW + _BOARDS + _DRAFTED_COPY,
        "parameters": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": (
                        "What to draw, for the drafter: the content and its form, every figure with its "
                        "unit, period and source, the arrows to draw, what to change or remove on the board."
                    ),
                },
                "links": {
                    "type": "array",
                    "description": (
                        "The arrows the drawing must hold, each by the texts of its two boxes as the "
                        "request writes them ('from': 'AI analysis', 'to': 'Decision recorded')."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {"from": {"type": "string"}, "to": {"type": "string"}},
                        "required": ["from", "to"],
                    },
                },
                **_DRAFTED_FOCUS_PROPERTY,
                **_BOARD_PROPERTIES,
            },
        },
    },
}

