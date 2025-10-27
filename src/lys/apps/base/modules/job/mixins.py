from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class CronJobExecutionChildMixin:
    cron_job_execution_id: Mapped[str] = mapped_column(
        ForeignKey("cron_job_execution.id", ondelete='SET NULL'),
        nullable=True
    )