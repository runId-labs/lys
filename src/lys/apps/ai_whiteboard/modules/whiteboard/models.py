"""
Whiteboard input validation models.
"""

from typing import Any, Dict

from pydantic import BaseModel, Field


class SaveWhiteboardSceneInputModel(BaseModel):
    """
    A scene saved wholesale by the editor, and the revision it was drawn on.

    ``expected_revision`` is not optional and has no default: a client that cannot say
    what it started from cannot be allowed to replace a scene, since the write would
    silently erase whatever landed in between.
    """

    scene: Dict[str, Any] = Field(description="The full Excalidraw scene to store")
    expected_revision: int = Field(
        ge=0,
        description="Revision the editor loaded before the user started drawing",
    )
