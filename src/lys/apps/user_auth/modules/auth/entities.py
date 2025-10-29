from datetime import datetime
from typing import Dict, List, Self

from sqlalchemy import ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr
from sqlalchemy.types import DateTime

from lys.core.entities import ParametricEntity, Entity
from lys.core.registers import register_entity


@register_entity()
class LoginAttemptStatus(ParametricEntity):
    __tablename__ = "login_attempt_status"


class LoginAttempt(Entity):
    __abstract__ = True

    status_id: Mapped[str] = mapped_column(ForeignKey("login_attempt_status.id", ondelete='CASCADE'))

    @declared_attr
    def status(self):
        return relationship("login_attempt_status", lazy='selectin')

    attempt_count: Mapped[int] = mapped_column(SmallInteger, default=1)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def accessing_users(self):
        return []

    def accessing_organizations(self) -> Dict[str, List[Self]]:
        return {}


@register_entity()
class UserLoginAttempt(LoginAttempt):
    __tablename__ = "user_login_attempt"

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete='CASCADE'))

    @declared_attr
    def user(self):
        return relationship("user", lazy='selectin')