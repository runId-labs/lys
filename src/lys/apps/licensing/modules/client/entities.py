"""
Client entity extension for licensing-specific fields.

This module extends the base Client entity from organization app
to add payment provider integration fields.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from lys.apps.organization.modules.client.entities import Client as BaseClient
from lys.core.registries import register_entity


@register_entity()
class Client(BaseClient):
    """
    Extended Client entity with payment provider fields.

    Extends the base Client from organization app to add:
        provider_customer_id: Payment provider customer ID for billing management
    """
    __tablename__ = "client"
    __table_args__ = {"extend_existing": True}

    # Payment provider integration for billing
    provider_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Payment provider customer ID (Mollie: cst_xxx)"
    )
