"""
Whiteboard input validation models.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from lys.apps.ai_whiteboard.modules.whiteboard.consts import TITLE_MAX_LENGTH


def _one_line_title(value: str) -> str:
    """Reject a blank title, and keep it on one line: it is shown in a header and a list."""
    title = " ".join(value.split())
    if not title:
        raise ValueError("Title cannot be empty")
    return title


class UpdateWhiteboardTitleInputModel(BaseModel):
    """A board renamed by its owner."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=TITLE_MAX_LENGTH,
        description="New title of the whiteboard",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        """Same rule as every title a user gives a board (see _one_line_title)."""
        return _one_line_title(value)


class DuplicateWhiteboardInputModel(BaseModel):
    """A board copied by its owner, optionally under a new name."""

    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=TITLE_MAX_LENGTH,
        description="Title of the copy; the source's when left out",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        """Same rule as a rename: a given title is never blank and fits on one line."""
        return None if value is None else _one_line_title(value)


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
