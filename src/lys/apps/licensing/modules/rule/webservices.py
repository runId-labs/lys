"""
License rule webservices.
"""

from typing import Annotated, Optional

import strawberry
from sqlalchemy import Select, select

from lys.apps.licensing.modules.rule.nodes import LicenseRuleNode
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registries import register_query
from lys.core.graphql.types import Query


@strawberry.type
@register_query()
class LicenseRuleQuery(Query):
    @lys_connection(
        LicenseRuleNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description=(
            "List the rules a plan version can be limited by. Use 'enabled' to filter by "
            "whether the rule is still enforced."
        )
    )
    async def all_license_rules(
        self,
        info: Info,
        enabled: Annotated[
            Optional[bool],
            strawberry.argument(description="Filter by whether the rule is enforced")
        ] = None
    ) -> Select:
        """
        List the rules a plan version can be limited by.

        Rules are reference data an application declares through fixtures, so the only
        way to know which ones exist is to read them. Without this listing, an interface
        publishing a version has to restate the identifiers it knows about, and a rule
        added later is silently absent from every version it publishes — which the
        checker then reads as unlimited.

        Restricted to the licensing administrator role: this is catalogue data, not
        something a subscriber chooses from.

        Args:
            info: GraphQL context
            enabled: Optional enforcement filter

        Returns:
            Select statement, ordered by rule ID
        """
        rule_entity = info.context.app_manager.get_entity("license_rule")

        stmt = select(rule_entity)

        if enabled is not None:
            stmt = stmt.where(rule_entity.enabled == enabled)

        return stmt.order_by(rule_entity.id)
