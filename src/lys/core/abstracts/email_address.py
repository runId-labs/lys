from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from lys.core.entities import Entity


class AbstractEmailAddress(Entity):
    """
    Abstract class for email addresses
    """
    __abstract__ = True
    id: Mapped[str] = mapped_column(primary_key=True)
    validated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_validation_request_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    @property
    def address(self):
        return self.id
