"""
Whiteboard webservices.

Reading a board, listing them, saving one edited by hand, and deleting one. Writing
from the chatbot does not go through here — it goes through the tools, which call the
same service.
"""

import strawberry
from sqlalchemy import Select, select

from lys.apps.ai_whiteboard.modules.whiteboard.entities import Whiteboard
from lys.apps.ai_whiteboard.modules.whiteboard.inputs import SaveWhiteboardSceneInput
from lys.apps.ai_whiteboard.modules.whiteboard.nodes import WhiteboardNode
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.delete import lys_delete
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registries import register_mutation, register_query
from lys.core.graphql.types import Mutation, Query


@strawberry.type
@register_query()
class WhiteboardQuery(Query):
    """GraphQL queries for whiteboards."""

    @lys_getter(
        WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Get one whiteboard with its scene and revision. Required: id.",
        options={"generate_tool": False},
    )
    async def whiteboard(self, obj: Whiteboard, info: Info):
        """
        Read one whiteboard.

        Nothing to do here: lys_getter resolved the row and OWNER access already applied
        the entity's own filters, so a board belonging to someone else never reaches this
        function.
        """

    @lys_connection(
        WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="List the connected user's whiteboards, most recently touched first.",
        options={"generate_tool": False},
    )
    async def all_whiteboards(self, info: Info) -> Select:
        """
        List whiteboards.

        Ordered by last touched rather than by creation: a board is a surface one comes
        back to, so the one worked on this morning belongs at the top even if it was
        opened months ago. `updated_at` is null until the first write, hence the fallback.
        """
        entity = info.context.app_manager.get_entity("whiteboard")

        return select(entity).order_by(
            entity.updated_at.desc().nullslast(),
            entity.created_at.desc(),
            entity.id.desc(),
        )


@strawberry.type
@register_mutation()
class WhiteboardMutation(Mutation):
    """GraphQL mutations for whiteboards."""

    @lys_edition(
        ensure_type=WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Store a scene edited by hand. Required: id, scene, expectedRevision. "
                    "Refused when the board moved since expectedRevision was read.",
        options={"generate_tool": False},
    )
    async def save_whiteboard_scene(self, obj: Whiteboard, inputs: SaveWhiteboardSceneInput, info: Info):
        """
        Replace a scene with the one the editor holds.

        The revision check lives in the service, not here: the chatbot tools write to the
        same rows, and a rule that only the GraphQL path enforced would be no rule at all.

        Args:
            obj: Whiteboard entity (fetched and validated by lys_edition)
            inputs: The scene, and the revision it was drawn on
            info: GraphQL context

        Returns:
            Whiteboard: the saved whiteboard, at its new revision
        """
        service = info.context.app_manager.get_service("whiteboard")
        parameters = inputs.to_pydantic()

        return await service.save_scene(
            obj,
            parameters.scene,
            parameters.expected_revision,
            info.context.session,
        )

    @lys_delete(
        WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Delete a whiteboard. Required: id.",
        options={"generate_tool": False},
    )
    async def delete_whiteboard(self, obj: Whiteboard, info: Info):
        """
        Delete a whiteboard, and clear the conversations that pointed at it.

        lys_delete removes the row itself after this returns, so this path never reaches
        the service's delete(). It calls the cleanup directly instead of restating it -
        the rule of what a disappearing board leaves behind belongs in one place.

        Args:
            obj: Whiteboard entity (fetched and validated by lys_delete)
            info: GraphQL context
        """
        service = info.context.app_manager.get_service("whiteboard")
        await service.forget_everywhere(obj.id, info.context.session)
