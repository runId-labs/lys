"""
Language entity for multi-language support.
"""

from lys.core.entities import ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class Language(ParametricEntity):
    """
    Language entity for managing available languages in the application.

    Uses ISO 639-1 codes as IDs (fr, en, es, etc.)
    """
    __tablename__ = "language"
