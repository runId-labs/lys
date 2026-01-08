from typing import Any, Dict, List, Optional

from pydantic import Field

from lys.core.models.fixtures import ParametricEntityFixturesModel


class WebserviceFixturesModel(ParametricEntityFixturesModel):
    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        public_type: str | None = Field(..., min_length=1)
        is_licenced: bool
        enabled: bool
        access_levels: List[str]
        operation_type: Optional[str] = Field(default=None, description="GraphQL operation type (query or mutation)")
        ai_tool: Optional[Dict[str, Any]] = Field(default=None, description="AI tool definition for LLM function calling")

    id: str = Field(..., min_length=1)
    attributes: AttributesModel