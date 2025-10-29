from typing import Any

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.apps.base.modules.emailing.consts import WAITING_EMAILING_STATUS
from lys.core.entities import Entity, ParametricEntity
from lys.core.registers import register_entity


@register_entity()
class EmailingStatus(ParametricEntity):
    __tablename__ = "emailing_status"


@register_entity()
class EmailingType(ParametricEntity):
    __tablename__ = "emailing_type"

    subject: Mapped[str] = mapped_column(nullable=False)
    template: Mapped[str] = mapped_column(nullable=False)
    context_description: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)


@register_entity()
class Emailing(Entity):
    __tablename__ = "emailing"

    email_address: Mapped[str] = mapped_column()
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    error: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)

    status_id: Mapped[str] = mapped_column(
        ForeignKey("emailing_status.id", ondelete='CASCADE'),
        default=WAITING_EMAILING_STATUS
    )

    @declared_attr
    def status(self):
        return relationship("emailing_status", lazy='selectin')

    type_id: Mapped[str] = mapped_column(ForeignKey("emailing_type.id", ondelete='CASCADE'))

    @declared_attr
    def type(self):
        return relationship("emailing_type", lazy='selectin')

    language_id: Mapped[str] = mapped_column(ForeignKey("language.id"), nullable=False)

    @declared_attr
    def language(self):
        return relationship("language", lazy='selectin')

    def accessing_users(self):
        return []

    def accessing_organizations(self):
        return {}