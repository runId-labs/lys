"""
Auth service for licensing app.

Extends OrganizationAuthService to filter organization webservices based on
license status. Only users with active licenses can access licensed webservices.

Adds subscription claims to JWT with payment provider verification.
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.modules.mollie.services import (
    get_mollie_client,
    get_payment_provider
)
from lys.apps.licensing.modules.subscription.entities import subscription_user
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.organization.modules.auth.services import OrganizationAuthService
from lys.apps.user_auth.modules.user.entities import User
from lys.core.registries import register_service

logger = logging.getLogger(__name__)


@register_service()
class LicensingAuthService(OrganizationAuthService):
    """
    Authentication service that filters webservices based on license status.

    For licensed webservices (is_licenced=True):
    - Owners: need their client to have an active subscription
    - Client users: need to be in the subscription_user table

    For non-licensed webservices: same behavior as OrganizationAuthService

    Adds to JWT claims:
    - subscriptions: {client_id: {plan_id, status, rules}}
    """

    @classmethod
    async def generate_access_claims(cls, user: User, session: AsyncSession) -> dict:
        """
        Generate JWT claims with subscription information.

        Extends OrganizationAuthService to add subscription claims per client.
        For paid subscriptions, verifies status with payment provider.

        Args:
            user: The authenticated user
            session: Database session

        Returns:
            Claims dict with "subscriptions" key added
        """
        # Get base claims from parent (includes organizations)
        claims = await super().generate_access_claims(user, session)

        # Skip subscription claims for super users (they have full access)
        if user.is_super_user:
            return claims

        # Get subscription claims for user's clients
        subscriptions = await cls._get_subscription_claims(user.id, session)

        if subscriptions:
            claims["subscriptions"] = subscriptions

        return claims

    @classmethod
    async def _get_subscription_claims(
        cls,
        user_id: str,
        session: AsyncSession
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get subscription claims for all clients the user has access to.

        Returns:
            Dict: {client_id: {plan_id, plan_version_id, status, rules}}
        """
        subscriptions = {}

        client_entity = cls.app_manager.get_entity("client")
        user_entity = cls.app_manager.get_entity("user")

        # Get owned clients
        stmt = select(client_entity.id).where(client_entity.owner_id == user_id)
        result = await session.execute(stmt)
        owned_client_ids = [str(row[0]) for row in result.all()]

        # Get client from user.client_id
        stmt = select(user_entity.client_id).where(user_entity.id == user_id)
        result = await session.execute(stmt)
        row = result.first()
        member_client_id = str(row[0]) if row and row[0] else None

        # Combine unique client IDs
        all_client_ids = list(set(owned_client_ids + ([member_client_id] if member_client_id else [])))

        # Get subscription claim for each client
        for client_id in all_client_ids:
            claim = await cls._get_client_subscription_claim(client_id, session)
            if claim:
                subscriptions[client_id] = claim

        return subscriptions

    @classmethod
    async def _get_client_subscription_claim(
        cls,
        client_id: str,
        session: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        Get subscription claim for a single client.

        For paid subscriptions, verifies status with payment provider.

        Returns:
            Dict with plan_id, plan_version_id, status, rules or None
        """
        subscription_service = cls.app_manager.get_service("subscription")
        subscription = await subscription_service.get_client_subscription(client_id, session)

        if not subscription:
            return None

        # Load plan version with rules
        await session.refresh(subscription, ["plan_version"])
        plan_version = subscription.plan_version

        if not plan_version:
            return None

        await session.refresh(plan_version, ["rules"])

        # Build rules dict
        rules = {}
        for version_rule in plan_version.rules:
            await session.refresh(version_rule, ["rule"])
            rule_id = version_rule.rule_id

            if version_rule.limit_value is not None:
                # Quota rule
                rules[rule_id] = version_rule.limit_value
            else:
                # Feature toggle (presence = enabled)
                rules[rule_id] = True

        # Determine subscription status
        status = "active"  # Default for free plans

        if subscription.provider_subscription_id:
            # Paid plan: verify with payment provider
            client_entity = cls.app_manager.get_entity("client")
            client = await session.get(client_entity, client_id)

            if client and client.provider_customer_id:
                status = await cls._verify_subscription_status(
                    client.provider_customer_id,
                    subscription.provider_subscription_id
                )

        return {
            "plan_id": plan_version.plan_id,
            "plan_version_id": str(plan_version.id),
            "status": status,
            "rules": rules
        }

    @classmethod
    async def _verify_subscription_status(
        cls,
        customer_id: str,
        subscription_id: str
    ) -> str:
        """
        Verify subscription status with payment provider.

        Args:
            customer_id: Payment provider customer ID
            subscription_id: Payment provider subscription ID

        Returns:
            Status string: "active", "pending", "canceled", "suspended", "past_due"
        """
        provider = get_payment_provider()

        if provider == "mollie":
            return await cls._verify_mollie_subscription(customer_id, subscription_id)
        else:
            # Unknown provider or not configured - assume active
            logger.warning(f"Unknown payment provider '{provider}', assuming active")
            return "active"

    @classmethod
    async def _verify_mollie_subscription(
        cls,
        customer_id: str,
        subscription_id: str
    ) -> str:
        """
        Verify subscription status with Mollie API.

        Returns:
            Status: "active", "pending", "canceled", "suspended", "completed"
        """
        mollie = get_mollie_client()
        if not mollie:
            logger.warning("Mollie not configured, assuming active status")
            return "active"

        try:
            customer = mollie.customers.get(customer_id)
            subscription = customer.subscriptions.get(subscription_id)
            return subscription.status
        except Exception as e:
            logger.error(f"Error verifying Mollie subscription: {e}")
            return "active"  # Fail open to avoid blocking users

    @classmethod
    async def _get_owner_webservices(cls, user_id: str, session: AsyncSession) -> dict:
        """
        Get webservices for clients owned by the user.

        For licensed webservices, the client must have an active subscription.

        Args:
            user_id: User ID
            session: Database session

        Returns:
            Dictionary: {client_id: {"level": "client", "webservices": [...]}}
        """
        client_entity = cls.app_manager.get_entity("client")
        webservice_entity = cls.app_manager.get_entity("webservice")
        access_level_entity = cls.app_manager.get_entity("access_level")
        subscription_entity = cls.app_manager.get_entity("subscription")

        # Get owned clients
        stmt = select(client_entity).where(client_entity.owner_id == user_id)
        result = await session.execute(stmt)
        owned_clients = list(result.scalars().all())

        if not owned_clients:
            return {}

        # Get clients with active subscriptions
        stmt = select(subscription_entity.client_id)
        result = await session.execute(stmt)
        clients_with_subscription = {str(row[0]) for row in result.all()}

        # Get all webservices with ORGANIZATION_ROLE_ACCESS_LEVEL enabled
        stmt = (
            select(webservice_entity)
            .where(
                webservice_entity.access_levels.any(
                    access_level_entity.id == ORGANIZATION_ROLE_ACCESS_LEVEL,
                    enabled=True
                )
            )
        )
        result = await session.execute(stmt)
        all_org_webservices = list(result.scalars().all())

        # Separate licensed and non-licensed webservices
        licensed_ws_names = [ws.id for ws in all_org_webservices if ws.is_licenced]
        non_licensed_ws_names = [ws.id for ws in all_org_webservices if not ws.is_licenced]

        organizations = {}
        for client in owned_clients:
            client_id = str(client.id)

            # Owner gets non-licensed webservices always
            webservices = list(non_licensed_ws_names)

            # Owner gets licensed webservices only if client has subscription
            if client_id in clients_with_subscription:
                webservices.extend(licensed_ws_names)

            if webservices:
                organizations[client_id] = {
                    "level": "client",
                    "webservices": webservices
                }

        return organizations

    @classmethod
    async def _get_client_user_role_webservices(cls, user_id: str, session: AsyncSession) -> dict:
        """
        Get webservices from client_user_roles, filtered by license status.

        For licensed webservices, the user must be in subscription_user table.

        Args:
            user_id: User ID
            session: Database session

        Returns:
            Dictionary: {client_id: {"level": "client", "webservices": [...]}}
        """
        user_entity = cls.app_manager.get_entity("user")

        # Get user with client_id
        stmt = select(user_entity).where(user_entity.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.client_id:
            return {}

        # Check if user has a license (is in subscription_user)
        stmt = select(exists().where(subscription_user.c.user_id == user_id))
        result = await session.execute(stmt)
        has_license = result.scalar()

        await session.refresh(user, ["client_user_roles"])

        # Collect webservice IDs from all roles
        role_webservice_ids = set()
        for client_user_role in user.client_user_roles:
            await session.refresh(client_user_role, ["role"])
            role = client_user_role.role

            if role and role.enabled:
                role_webservice_ids.update(role.get_webservice_ids())

        if not role_webservice_ids:
            return {}

        # Filter webservices by license status
        webservice_entity = cls.app_manager.get_entity("webservice")
        webservice_names = set()

        stmt = select(webservice_entity).where(
            webservice_entity.id.in_(role_webservice_ids)
        )
        result = await session.execute(stmt)

        for ws in result.scalars().all():
            # Include webservice only if:
            # - It's not licensed, OR
            # - User has a license
            if not ws.is_licenced or has_license:
                webservice_names.add(ws.id)

        if not webservice_names:
            return {}

        return {
            str(user.client_id): {
                "level": "client",
                "webservices": list(webservice_names)
            }
        }