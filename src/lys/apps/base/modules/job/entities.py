from typing import Dict, List, Self, Any

from sqlalchemy import ForeignKey, DateTime, JSON
from sqlalchemy.orm import mapped_column, Mapped, relationship, declared_attr

from lys.core.entities import ParametricEntity, Entity
from lys.core.registries import register_entity


@register_entity()
class JobStatus(ParametricEntity):
    __tablename__ = "job_status"


@register_entity()
class Job(ParametricEntity):
    __tablename__ = "job"

    status_id: Mapped[str] = mapped_column(ForeignKey("job_status.id", ondelete='CASCADE'))

    @declared_attr
    def status(self):
        return relationship("job_status", lazy='selectin')


class JobExecution(Entity):
    __abstract__ = True

    job_id: Mapped[str] = mapped_column(ForeignKey("job.id", ondelete='CASCADE'))
    ended_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)

    @declared_attr
    def job(self):
        return relationship("job", lazy='selectin')

    @property
    def started_at(self):
        return self.created_at

    def accessing_users(self):
        return []

    def accessing_organizations(self) -> Dict[str, List[Self]]:
        return {}


@register_entity()
class CronJobExecution(JobExecution):
    __tablename__ = "cron_job_execution"

    cron: Mapped[str] = mapped_column()


@register_entity()
class MigrationJobExecution(JobExecution):
    __tablename__ = "migration_job_execution"

    cron: Mapped[str] = mapped_column()