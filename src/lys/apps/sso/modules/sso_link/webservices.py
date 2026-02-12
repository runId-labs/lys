import logging
from typing import List, Optional

import strawberry

from lys.apps.sso.consts import SSO_PLUGIN_KEY
from lys.apps.sso.modules.sso_link.nodes import (
    SSOProviderNode, SSOProvidersNode, SSOSessionNode, UserSSOLinkNode, UserSSOLinksNode
)
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.delete import lys_delete
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation

logger = logging.getLogger(__name__)


@strawberry.type
@register_query()
class SSOProviderQuery(Query):

    @lys_field(
        ensure_type=SSOProvidersNode,
        is_public="disconnected",
        is_licenced=False,
        description="List configured SSO providers for login/signup buttons."
    )
    async def sso_providers(self, info: Info) -> SSOProvidersNode:
        """Return the list of configured SSO providers."""
        node = SSOProvidersNode.get_effective_node()
        sso_config = info.context.app_manager.settings.get_plugin_config(SSO_PLUGIN_KEY)
        providers = sso_config.get("providers", {})
        callback_base_url = sso_config.get("callback_base_url", "")

        items = []
        for provider_id, provider_config in providers.items():
            items.append(SSOProviderNode(
                provider_id=provider_id,
                name=provider_config.get("display_name", provider_id.capitalize()),
                login_url=f"{callback_base_url}/auth/sso/{provider_id}/login",
            ))
        return node(providers=items)


@strawberry.type
@register_query()
class SSOSessionQuery(Query):

    @lys_field(
        ensure_type=SSOSessionNode,
        is_public="disconnected",
        is_licenced=False,
        description="Get SSO session data for pre-filling signup form."
    )
    async def sso_session(self, info: Info, token: str) -> Optional[SSOSessionNode]:
        """Read an SSO session token and return the stored user info (non-destructive)."""
        node = SSOSessionNode.get_effective_node()
        sso_auth_service = info.context.app_manager.get_service("sso_auth")
        session_data = await sso_auth_service.get_sso_session(token)
        if not session_data:
            return None
        return node(
            email=session_data.get("email", ""),
            first_name=session_data.get("first_name"),
            last_name=session_data.get("last_name"),
            provider=session_data.get("provider", ""),
        )


@strawberry.type
@register_query()
class MySSOLinksQuery(Query):

    @lys_field(
        ensure_type=UserSSOLinksNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="List SSO links for the connected user."
    )
    async def my_sso_links(self, info: Info) -> UserSSOLinksNode:
        """Return SSO links for the currently authenticated user."""
        node = UserSSOLinksNode.get_effective_node()
        connected_user = info.context.connected_user
        if not connected_user:
            return node(links=[])

        user_id = connected_user.get("sub")
        if not user_id:
            return node(links=[])

        sso_link_service = info.context.app_manager.get_service("user_sso_link")
        links = await sso_link_service.find_all_by_user(user_id, info.context.session)
        return node(links=[UserSSOLinkNode.from_obj(link) for link in links])


@register_mutation()
@strawberry.type
class SSOLinkMutation(Mutation):

    @lys_delete(
        ensure_type=UserSSOLinkNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Remove an SSO link by ID. Only the owning user can delete their own links."
    )
    async def delete_sso_link(self, obj, info: Info):
        """Delete an SSO link. Access control via OWNER on accessing_users()."""
        logger.info(f"Deleted SSO link {obj.id} (provider={obj.provider}, user={obj.user_id})")