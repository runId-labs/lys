"""
License plan webservices.
"""

from typing import Annotated, Optional

import strawberry
from sqlalchemy import Select, select, or_
from strawberry import relay

from lys.apps.licensing.modules.plan.entities import LicensePlanVersion
from lys.apps.licensing.modules.plan.inputs import (
    CreatePlanVersionInput,
    SetPlanVersionRuleInput,
)
from lys.apps.licensing.modules.plan.nodes import (
    LicensePlanNode,
    LicensePlanVersionNode,
    LicensePlanVersionRuleNode,
)
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_mutation, register_query
from lys.core.graphql.types import Mutation, Query


@strawberry.type
@register_query()
class LicensePlanQuery(Query):
    @lys_connection(
        LicensePlanNode,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="List all active license plans with their current version and pricing."
    )
    async def all_active_license_plans(self, info: Info) -> Select:
        """
        Get all active (enabled) license plans available to the connected user.

        Returns:
        - If user has no associated client: only global plans (client_id IS NULL)
        - If user has an associated client: global plans + custom plans for that client
        """
        plan_entity = info.context.app_manager.get_entity("license_plan")
        client_entity = info.context.app_manager.get_entity("client")
        user_entity = info.context.app_manager.get_entity("user")

        connected_user = info.context.connected_user
        user_id = connected_user["sub"]
        session = info.context.session

        # Find user's client_id (owner or member)
        user_client_id = None

        # Check if user is owner of a client
        stmt = select(client_entity.id).where(client_entity.owner_id == user_id)
        result = await session.execute(stmt)
        client_id = result.scalar_one_or_none()

        if client_id:
            user_client_id = client_id
        else:
            # Check if user is member of a client (via user.client_id)
            stmt = select(user_entity.client_id).where(user_entity.id == user_id)
            result = await session.execute(stmt)
            client_id = result.scalar_one_or_none()
            if client_id:
                user_client_id = client_id

        # Build query based on user's client association
        if user_client_id:
            # User has a client: return global plans + custom plans for their client
            stmt = select(plan_entity).where(
                plan_entity.enabled == True,
                or_(
                    plan_entity.client_id.is_(None),
                    plan_entity.client_id == user_client_id
                )
            ).order_by(plan_entity.id)
        else:
            # User has no client: return only global plans
            stmt = select(plan_entity).where(
                plan_entity.enabled == True,
                plan_entity.client_id.is_(None)
            ).order_by(plan_entity.id)

        return stmt

    @lys_connection(
        LicensePlanNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description=(
            "List plans for catalogue administration, disabled and client-specific ones "
            "included. Use 'enabled' to filter by availability and 'client_id' to filter "
            "by the client a custom plan was negotiated with."
        )
    )
    async def all_license_plans(
        self,
        info: Info,
        enabled: Annotated[
            Optional[bool],
            strawberry.argument(description="Filter by availability for new subscriptions")
        ] = None,
        client_id: Annotated[
            Optional[relay.GlobalID],
            strawberry.argument(
                description="Filter by the client a custom plan belongs to"
            )
        ] = None
    ) -> Select:
        """
        List plans for catalogue administration.

        Unlike all_active_license_plans, which is the public catalogue and only
        returns what the connected user may subscribe to, this listing returns
        disabled plans and the custom plans of every client. It is therefore
        restricted to the licensing administrator role.

        Args:
            info: GraphQL context
            enabled: Optional availability filter
            client_id: Optional client the custom plans belong to

        Returns:
            Select statement, ordered by plan ID
        """
        plan_entity = info.context.app_manager.get_entity("license_plan")

        stmt = select(plan_entity)

        if enabled is not None:
            stmt = stmt.where(plan_entity.enabled == enabled)

        if client_id is not None:
            stmt = stmt.where(plan_entity.client_id == client_id.node_id)

        return stmt.order_by(plan_entity.id)

    @lys_connection(
        LicensePlanVersionNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description=(
            "List plan versions, disabled ones included. Use 'plan_id' to filter by plan "
            "and 'enabled' to filter by availability."
        )
    )
    async def all_license_plan_versions(
        self,
        info: Info,
        plan_id: Annotated[
            Optional[str],
            strawberry.argument(description="Filter by plan (e.g., 'PRO')")
        ] = None,
        enabled: Annotated[
            Optional[bool],
            strawberry.argument(description="Filter by availability for new subscriptions")
        ] = None
    ) -> Select:
        """
        List plan versions for catalogue administration.

        Unlike the public catalogue, disabled versions are returned: they are
        what an administrator needs to see to put a previous version back, and
        they remain referenced by the subscriptions sold under them.

        Args:
            info: GraphQL context
            plan_id: Optional plan to restrict the listing to
            enabled: Optional availability filter

        Returns:
            Select statement, ordered by plan then by descending version
        """
        version_entity = info.context.app_manager.get_entity("license_plan_version")

        stmt = select(version_entity)

        if plan_id is not None:
            stmt = stmt.where(version_entity.plan_id == plan_id)

        if enabled is not None:
            stmt = stmt.where(version_entity.enabled == enabled)

        return stmt.order_by(version_entity.plan_id, version_entity.version.desc())


@strawberry.type
@register_mutation()
class LicensePlanVersionMutation(Mutation):
    """
    Catalogue administration.

    These mutations publish the commercial offer: they are what a licensing
    administrator uses to give a plan its versions, its prices and its quotas.
    Prices are never modified, only published with a new version, so that
    existing subscribers keep the terms they agreed to.
    """

    @lys_creation(
        ensure_type=LicensePlanVersionNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Publish a new version of a plan, with its prices"
    )
    async def create_license_plan_version(
        self,
        info: Info,
        input: CreatePlanVersionInput
    ):
        """
        Publish a new version of a plan.

        The version number is incremented automatically and the previous version
        is disabled, so that only one version is offered at a time. Prices and
        rules are published together, since the new version is offered as soon
        as it exists. An empty price list produces a free version.

        The version is already persisted when it is returned: its prices need an
        identifier to reference. The decorator's own add and flush are therefore
        no-ops here, and only its permission check applies.
        """
        data = input.to_pydantic()
        version_service = info.context.app_manager.get_service("license_plan_version")

        return await version_service.create_new_version(
            plan_id=data.plan_id,
            session=info.context.session,
            prices=[price.model_dump() for price in data.prices],
            rules=[rule.model_dump() for rule in data.rules]
        )

    @lys_field(
        ensure_type=LicensePlanVersionRuleNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Set the limit of a rule on a plan version"
    )
    async def set_license_plan_version_rule(
        self,
        info: Info,
        input: SetPlanVersionRuleInput
    ):
        """
        Set or update the limit of a rule on a plan version.

        A null limit means unlimited for a quota rule, or simply grants the
        feature for a toggle rule.
        """
        data = input.to_pydantic()
        rule_service = info.context.app_manager.get_service("license_plan_version_rule")

        version_rule = await rule_service.set_rule_limit(
            plan_version_id=data.plan_version_id,
            rule_id=data.rule_id,
            limit_value=data.limit_value,
            session=info.context.session
        )

        return LicensePlanVersionRuleNode.from_obj(version_rule)

    @lys_edition(
        ensure_type=LicensePlanVersionNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Enable or disable a plan version"
    )
    async def set_license_plan_version_enabled(
        self,
        obj: LicensePlanVersion,
        enabled: bool,
        info: Info
    ):
        """
        Enable or disable a plan version.

        Disabling withdraws the version from the catalogue without touching the
        subscriptions that reference it.

        Args:
            obj: The plan version, resolved and permission-checked by the decorator
            enabled: Whether the version can be selected for new subscriptions
        """
        version_service = info.context.app_manager.get_service("license_plan_version")

        await version_service.set_enabled(
            plan_version_id=obj.id,
            enabled=enabled,
            session=info.context.session
        )
