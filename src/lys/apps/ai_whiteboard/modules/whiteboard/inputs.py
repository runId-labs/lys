"""
Whiteboard GraphQL inputs.
"""

import strawberry
from strawberry.scalars import JSON

from lys.apps.ai_whiteboard.modules.whiteboard.models import (
    DuplicateWhiteboardInputModel,
    SaveWhiteboardSceneInputModel,
    UpdateWhiteboardTitleInputModel,
)


@strawberry.experimental.pydantic.input(model=DuplicateWhiteboardInputModel)
class DuplicateWhiteboardInput:
    """Input for copying a whiteboard."""

    title: strawberry.auto = strawberry.field(description="Title of the copy; the source's when left out")


@strawberry.experimental.pydantic.input(model=UpdateWhiteboardTitleInputModel)
class UpdateWhiteboardTitleInput:
    """Input for renaming a whiteboard."""

    title: strawberry.auto = strawberry.field(description="New title of the whiteboard")


@strawberry.experimental.pydantic.input(model=SaveWhiteboardSceneInputModel)
class SaveWhiteboardSceneInput:
    """Input for storing a scene edited by hand."""

    scene: JSON = strawberry.field(description="The full Excalidraw scene to store")
    expected_revision: strawberry.auto = strawberry.field(
        description="Revision the editor loaded before the user started drawing"
    )
