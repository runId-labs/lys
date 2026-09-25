"""
Error definitions for the whiteboard app.
"""

# The scene moved since the caller read it. Never silently resolved: the two writers
# are a human editing and a model drawing, and merging them blindly loses one of them.
WHITEBOARD_REVISION_CONFLICT = (409, "WHITEBOARD_REVISION_CONFLICT")

# Operation payload the service refuses to guess at.
WHITEBOARD_UNKNOWN_OPERATION = (400, "WHITEBOARD_UNKNOWN_OPERATION")
WHITEBOARD_UNKNOWN_ELEMENT_KIND = (400, "WHITEBOARD_UNKNOWN_ELEMENT_KIND")
WHITEBOARD_ELEMENT_NAME_REQUIRED = (400, "WHITEBOARD_ELEMENT_NAME_REQUIRED")

# An update, a delete or a link endpoint naming something the scene does not hold.
# Returned to the model, which is the caller that can act on it: it renamed, or it
# invented a name it never created.
WHITEBOARD_UNKNOWN_ELEMENT = (404, "WHITEBOARD_UNKNOWN_ELEMENT")

# Guard against a runaway writer. A board past this size stops being readable long
# before it stops being storable.
WHITEBOARD_TOO_MANY_ELEMENTS = (400, "WHITEBOARD_TOO_MANY_ELEMENTS")

# A position, a size, a colour or a text the scene refuses to hold. Coordinates and
# sizes reach the editor untouched, so an infinity or a NaN there is a board that fails
# to render rather than a board that renders wrong - and a caller free to place is a
# caller free to place a typo.
WHITEBOARD_INVALID_GEOMETRY = (400, "WHITEBOARD_INVALID_GEOMETRY")
WHITEBOARD_INVALID_COLOR = (400, "WHITEBOARD_INVALID_COLOR")
WHITEBOARD_TEXT_TOO_LONG = (400, "WHITEBOARD_TEXT_TOO_LONG")

# A table or a chart whose data does not describe what it claims to: ragged rows, no
# column, a chart type nobody draws, values that are not numbers.
WHITEBOARD_INVALID_TABLE = (400, "WHITEBOARD_INVALID_TABLE")
WHITEBOARD_INVALID_CHART = (400, "WHITEBOARD_INVALID_CHART")

# A patch whose shape is not the one the tool declares: an operation that is not a list, an
# item that is not an object, a name that is not a string. Returned to the model, which
# produced it and can send it again correctly.
WHITEBOARD_INVALID_OPERATION = (400, "WHITEBOARD_INVALID_OPERATION")

# A scene saved by the editor that is not an Excalidraw document, or is larger than the
# board is allowed to be. The editor is a client like any other: its payload is input.
WHITEBOARD_INVALID_SCENE = (400, "WHITEBOARD_INVALID_SCENE")
WHITEBOARD_SCENE_TOO_LARGE = (413, "WHITEBOARD_SCENE_TOO_LARGE")

# A tool naming a board that is not the caller's, or does not exist. One code for both:
# telling them apart would say which ids exist.
WHITEBOARD_NOT_FOUND = (404, "WHITEBOARD_NOT_FOUND")
