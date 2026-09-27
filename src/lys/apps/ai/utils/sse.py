"""
Server-Sent Events wire format for the streaming chat endpoints.

One formatter, shared: the conversation service emits the turn's events and the
spoken-block pipeline emits the voice's, and a second copy of three lines is how
two streams on the same connection drift apart in their framing.
"""

import json
from typing import Any


def format_sse(event: str, data: Any) -> str:
    """
    Format one SSE event.

    Args:
        event: The event name a client dispatches on (``token``, ``voice``...).
        data: The JSON-serializable payload.

    Returns:
        The wire-formatted event, terminated by the blank line that closes it.
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
