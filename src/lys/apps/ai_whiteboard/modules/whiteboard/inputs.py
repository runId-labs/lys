"""
Whiteboard GraphQL inputs.
"""

import strawberry
from strawberry.scalars import JSON

from lys.apps.ai_whiteboard.modules.whiteboard.models import SaveWhiteboardSceneInputModel


@strawberry.experimental.pydantic.input(model=SaveWhiteboardSceneInputModel)
class SaveWhiteboardSceneInput:
    """Input for storing a scene edited by hand."""

    scene: JSON = strawberry.field(description="The full Excalidraw scene to store")
    expected_revision: strawberry.auto = strawberry.field(
        description="Revision the editor loaded before the user started drawing"
    )
