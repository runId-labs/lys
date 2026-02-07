"""
AI Text Improvement models.

Pydantic models for text improvement data validation.
"""

from typing import Optional

from pydantic import BaseModel


class ImproveTextInputModel(BaseModel):
    """Pydantic model for improve text input validation."""

    text: str
    context: Optional[str] = None
    language: str = "fr"
    max_length: Optional[int] = None