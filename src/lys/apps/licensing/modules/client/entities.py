"""
Client entity extension for licensing-specific fields.

This module extends the base Client entity from organization app
to add Stripe billing integration fields.
"""

from sqlalchemy.orm import Mapped, mapped_column

from lys.apps.organization.modules.client.entities import Client as BaseClient
from lys.core.registries import register_entity


@register_entity()
class Client(BaseClient):
    """
    Extended Client entity with Stripe billing fields.

    Extends the base Client from organization app to add:
        stripe_customer_id: Stripe Customer ID for billing management
    """
    __tablename__ = "client"
    __table_args__ = {"extend_existing": True}

    # Stripe integration for billing
    stripe_customer_id: Mapped[str | None] = mapped_column(nullable=True, unique=True)