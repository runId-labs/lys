"""
Whiteboard webservices.

Reading a board, listing them, saving one edited by hand, and deleting one. Writing
from the chatbot does not go through here — it goes through the tools, which call the
same service.
"""

from typing import Optional

import strawberry
from sqlalchemy import Select, select
from strawberry import relay

from lys.apps.ai_whiteboard.errors import WHITEBOARD_NOT_FOUND
from lys.apps.ai_whiteboard.modules.whiteboard.consts import WHITEBOARD_NODE_NAME
from lys.apps.ai_whiteboard.modules.whiteboard.entities import Whiteboard
from lys.apps.ai_whiteboard.modules.whiteboard.inputs import (
    DuplicateWhiteboardInput,
    SaveWhiteboardSceneInput,
    UpdateWhiteboardTitleInput,
)
from lys.apps.ai_whiteboard.modules.whiteboard.nodes import WhiteboardNode
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.errors import LysError
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.delete import lys_delete
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registries import register_mutation, register_query
from lys.core.graphql.types import Mutation, Query
from lys.core.utils.validators import check_global_id_type


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
        description="List the connected user's whiteboards, most recently touched first - active "
                    "ones by default, the archive alone with archived=true, both with "
                    "archived=null. Callers that present pins separately narrow with "
                    "pinned=true (pinned ones, most recently pinned first via orderBy) or "
                    "pinned=false. Restricted to the connected user's own whiteboards "
                    "unless the caller is a super user.",
        options={"generate_tool": False},
    )
    async def all_whiteboards(
        self,
        info: Info,
        user_id: Optional[relay.GlobalID] = None,
        archived: Optional[bool] = False,
        pinned: Optional[bool] = None,
    ) -> Select:
        """
        List whiteboards.

        OWNER access only, on purpose: a board is personal content, so no role is
        granted a view of other users' boards. OWNER access applies
        Whiteboard.user_accessing_filters (own whiteboards only); the super user
        bypasses it with full, audited access - for support or terms-of-use
        enforcement. The user_id argument narrows that full-access listing to one
        user; it cannot widen an owner-scoped one.

        The ordering stays the one the connection name promises - most recently
        touched first - whatever slice of the flags the caller asks to see; the
        pinned slice re-orders through orderBy.

        Args:
            info: GraphQL context
            user_id: If set, restrict to this user's whiteboards. Only meaningful for
                the super user - an owner-scoped caller is already limited to itself.
            archived: False (default) lists the active whiteboards, True lists only the
                archived ones, null lists both. Same rule as the conversations the
                whiteboards travel with: archiving exists to set a board aside, so
                browsing the archive shows the archive alone.
            pinned: True lists only the pinned ones, False only the unpinned ones, null
                (default) ignores the pin. A pin never hides a whiteboard from a listing:
                it is a highlight the caller chooses to present apart, so the default
                listing keeps it.
        """
        check_global_id_type(user_id, "UserNode", "userId")

        entity = info.context.app_manager.get_entity("whiteboard")
        stmt = select(entity).order_by(
            entity.updated_at.desc().nullslast(),
            entity.created_at.desc(),
            entity.id.desc(),
        )

        if user_id is not None:
            stmt = stmt.where(entity.user_id == user_id.node_id)

        if archived is not None:
            stmt = stmt.where(
                entity.archived_at.isnot(None) if archived else entity.archived_at.is_(None)
            )

        if pinned is not None:
            stmt = stmt.where(
                entity.pinned_at.isnot(None) if pinned else entity.pinned_at.is_(None)
            )

        return stmt


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

    @lys_edition(
        ensure_type=WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Archive a whiteboard, hiding it from the default listing. Required: id. "
                    "The conversations pointing at it follow.",
        options={"generate_tool": False},
    )
    async def archive_whiteboard(self, obj: Whiteboard, info: Info):
        """
        Archive a whiteboard.

        A mirror of archive_ai_conversation on the other side of the link: OWNER access
        is applied by lys_edition before this body, and the service owns the rule -
        the flag and its propagation to the conversations pointing at this board.

        Args:
            obj: Whiteboard entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            Whiteboard: the archived whiteboard
        """
        service = info.context.app_manager.get_service("whiteboard")

        return await service.archive(obj, info.context.session)

    @lys_edition(
        ensure_type=WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Restore an archived whiteboard to the default listing. Required: id. "
                    "The conversations pointing at it follow.",
        options={"generate_tool": False},
    )
    async def unarchive_whiteboard(self, obj: Whiteboard, info: Info):
        """
        Restore an archived whiteboard.

        Args:
            obj: Whiteboard entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            Whiteboard: the restored whiteboard
        """
        service = info.context.app_manager.get_service("whiteboard")

        return await service.unarchive(obj, info.context.session)

    @lys_edition(
        ensure_type=WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Pin a whiteboard, highlighting it in the user's listing. Required: id. "
                    "The conversations pointing at it follow.",
        options={"generate_tool": False},
    )
    async def pin_whiteboard(self, obj: Whiteboard, info: Info):
        """
        Pin a whiteboard.

        Args:
            obj: Whiteboard entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            Whiteboard: the pinned whiteboard
        """
        service = info.context.app_manager.get_service("whiteboard")

        return await service.pin(obj, info.context.session)

    @lys_edition(
        ensure_type=WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Unpin a whiteboard. Required: id. The conversations pointing at it follow.",
        options={"generate_tool": False},
    )
    async def unpin_whiteboard(self, obj: Whiteboard, info: Info):
        """
        Unpin a whiteboard.

        Args:
            obj: Whiteboard entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            Whiteboard: the unpinned whiteboard
        """
        service = info.context.app_manager.get_service("whiteboard")

        return await service.unpin(obj, info.context.session)

    @lys_edition(
        ensure_type=WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Rename a whiteboard. Required: id, inputs.title.",
        options={"generate_tool": False},
    )
    async def update_whiteboard_title(self, obj: Whiteboard, inputs: UpdateWhiteboardTitleInput, info: Info):
        """
        Rename a board.

        OWNER access is applied by lys_edition before this body: a user renames only
        their own boards. The name does not touch the scene, so the revision stays.

        Args:
            obj: Whiteboard entity (fetched and validated by lys_edition)
            inputs: The new title
            info: GraphQL context

        Returns:
            Whiteboard: the renamed whiteboard
        """
        service = info.context.app_manager.get_service("whiteboard")

        return await service.rename(obj, inputs.to_pydantic().title, info.context.session)

    @lys_creation(
        ensure_type=WhiteboardNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Copy a whiteboard into a new one, attached to no conversation. Required: id. "
                    "Optional: inputs.title (the source's otherwise).",
        options={"generate_tool": False},
    )
    async def duplicate_whiteboard(
        self,
        info: Info,
        id: relay.GlobalID,
        inputs: Optional[DuplicateWhiteboardInput] = None,
    ) -> Whiteboard:
        """
        Make a copy of a board - the same deck for next month, or another company.

        lys_creation checks access on the created board only, after this body ran. The
        source is read here first, filtered on the connected user: a board of someone
        else's answers "not found", exactly like an unknown id, and is never copied.

        Args:
            info: GraphQL context
            id: The board to copy (WhiteboardNode GlobalID)
            inputs: The copy's name, validated like a rename; the source's when left out

        Returns:
            Whiteboard: the copy
        """
        check_global_id_type(id, WHITEBOARD_NODE_NAME, "id")
        title = inputs.to_pydantic().title if inputs is not None else None
        service = info.context.app_manager.get_service("whiteboard")
        session = info.context.session

        source = await service.get_for_user(id.node_id, info.context.connected_user["sub"], session)
        if source is None:
            raise LysError(WHITEBOARD_NOT_FOUND, f"Whiteboard '{id.node_id}' is not reachable")

        return await service.copy_for_user(source, title, session)

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
