"""
Discount webservices.
"""

from typing import Annotated, Optional

import strawberry
from sqlalchemy import Select, select

from lys.apps.licensing.consts import MANUAL_GRANT
from lys.apps.licensing.modules.discount.entities import LicenseDiscount
from lys.apps.licensing.modules.discount.inputs import CreateDiscountInput
from lys.apps.licensing.modules.discount.nodes import LicenseDiscountNode
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.registries import register_mutation, register_query
from lys.core.graphql.types import Mutation, Query


@strawberry.type
@register_query()
class LicenseDiscountQuery(Query):

    @lys_connection(
        LicenseDiscountNode,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="List the discounts that can be claimed when subscribing."
    )
    async def all_claimable_license_discounts(self, info: Info) -> Select:
        """
        List the discounts to offer when subscribing.

        Only the ones that are claimed are returned — those someone ticks, and
        whose identifier then travels with the subscription. The filter looks
        redundant while claiming is the only way to obtain a discount; it is what
        keeps this listing correct the day another way exists.

        Returns:
            Select statement, ordered by discount ID
        """
        discount_entity = info.context.app_manager.get_entity("license_discount")

        return (
            select(discount_entity)
            .where(
                discount_entity.enabled.is_(True),
                discount_entity.grant_id == MANUAL_GRANT,
            )
            .order_by(discount_entity.id)
        )

    @lys_connection(
        LicenseDiscountNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description=(
            "List discounts for catalogue administration, withdrawn ones included. "
            "Use 'enabled' to filter by availability."
        )
    )
    async def all_license_discounts(
        self,
        info: Info,
        enabled: Annotated[
            Optional[bool],
            strawberry.argument(description="Filter by availability for new grants")
        ] = None
    ) -> Select:
        """
        List discounts for catalogue administration.

        Unlike the client-facing listing, this one returns the discounts reserved
        to administrators and those withdrawn from the catalogue: both are what
        an operator needs to see, the latter remaining referenced by the
        subscriptions granted under them.

        Args:
            info: GraphQL context
            enabled: Optional availability filter

        Returns:
            Select statement, ordered by discount ID
        """
        discount_entity = info.context.app_manager.get_entity("license_discount")

        stmt = select(discount_entity)

        if enabled is not None:
            stmt = stmt.where(discount_entity.enabled == enabled)

        return stmt.order_by(discount_entity.id)


@strawberry.type
@register_mutation()
class LicenseDiscountMutation(Mutation):
    """
    Discount administration.

    Declaring a discount is a commercial act, reserved to the licensing
    administrator: it decides what may be taken off a catalogue price.
    """

    @lys_creation(
        ensure_type=LicenseDiscountNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Declare a discount the catalogue can offer"
    )
    async def create_license_discount(self, info: Info, input: CreateDiscountInput):
        """
        Declare a discount.

        Nothing is granted here: this only adds a reduction to the catalogue.
        Granting it happens when a subscription is created, which is where the
        value is frozen.

        Args:
            info: GraphQL context
            input: Code, value, unit and who may offer it

        Returns:
            The declared LicenseDiscountNode.
        """
        data = input.to_pydantic()
        discount_service = info.context.app_manager.get_service("license_discount")

        discount = await discount_service.create(
            session=info.context.session,
            id=data.code,
            enabled=True,
            value=data.value,
            unit_id=data.unit_id,
            grant_id=data.grant_id,
            description=data.description,
        )

        return LicenseDiscountNode.from_obj(discount)

    @lys_edition(
        ensure_type=LicenseDiscountNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Offer or withdraw a discount"
    )
    async def set_license_discount_enabled(
        self,
        obj: LicenseDiscount,
        enabled: bool,
        info: Info
    ):
        """
        Offer or withdraw a discount.

        Withdrawing closes it to new grants without touching the subscriptions
        already benefiting from it: they keep what they were granted until their
        term, which is the promise the frozen value carries.

        Args:
            obj: The discount, resolved and permission-checked by the decorator
            enabled: Whether the discount can still be granted
        """
        obj.enabled = enabled
