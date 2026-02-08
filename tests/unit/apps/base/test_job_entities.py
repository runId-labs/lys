"""
Unit tests for base job module entities.

Tests entity structure.
"""

import pytest


class TestJobStatusEntity:
    """Tests for JobStatus entity."""

    def test_entity_exists(self):
        """Test JobStatus entity exists."""
        from lys.apps.base.modules.job.entities import JobStatus
        assert JobStatus is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test JobStatus inherits from ParametricEntity."""
        from lys.apps.base.modules.job.entities import JobStatus
        from lys.core.entities import ParametricEntity
        assert issubclass(JobStatus, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test JobStatus has correct __tablename__."""
        from lys.apps.base.modules.job.entities import JobStatus
        assert JobStatus.__tablename__ == "job_status"


class TestJobEntity:
    """Tests for Job entity."""

    def test_entity_exists(self):
        """Test Job entity exists."""
        from lys.apps.base.modules.job.entities import Job
        assert Job is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test Job inherits from ParametricEntity."""
        from lys.apps.base.modules.job.entities import Job
        from lys.core.entities import ParametricEntity
        assert issubclass(Job, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test Job has correct __tablename__."""
        from lys.apps.base.modules.job.entities import Job
        assert Job.__tablename__ == "job"

    def test_entity_has_status_id_column(self):
        """Test Job has status_id column."""
        from lys.apps.base.modules.job.entities import Job
        assert "status_id" in Job.__annotations__

    def test_entity_has_status_relationship(self):
        """Test Job has status relationship."""
        from lys.apps.base.modules.job.entities import Job
        from tests.mocks.utils import has_relationship
        assert has_relationship(Job, "status")


class TestJobExecutionEntity:
    """Tests for JobExecution abstract entity."""

    def test_entity_exists(self):
        """Test JobExecution entity exists."""
        from lys.apps.base.modules.job.entities import JobExecution
        assert JobExecution is not None

    def test_entity_inherits_from_entity(self):
        """Test JobExecution inherits from Entity."""
        from lys.apps.base.modules.job.entities import JobExecution
        from lys.core.entities import Entity
        assert issubclass(JobExecution, Entity)

    def test_entity_is_abstract(self):
        """Test JobExecution is abstract."""
        from lys.apps.base.modules.job.entities import JobExecution
        assert JobExecution.__abstract__ is True

    def test_entity_has_job_id_column(self):
        """Test JobExecution has job_id column."""
        from lys.apps.base.modules.job.entities import JobExecution
        assert "job_id" in JobExecution.__annotations__

    def test_entity_has_ended_at_column(self):
        """Test JobExecution has ended_at column."""
        from lys.apps.base.modules.job.entities import JobExecution
        assert "ended_at" in JobExecution.__annotations__

    def test_entity_has_data_column(self):
        """Test JobExecution has data column."""
        from lys.apps.base.modules.job.entities import JobExecution
        assert "data" in JobExecution.__annotations__

    def test_entity_has_started_at_property(self):
        """Test JobExecution has started_at property."""
        from lys.apps.base.modules.job.entities import JobExecution
        assert hasattr(JobExecution, "started_at")

    def test_entity_has_accessing_users_method(self):
        """Test JobExecution has accessing_users method."""
        from lys.apps.base.modules.job.entities import JobExecution
        assert hasattr(JobExecution, "accessing_users")

    def test_entity_has_accessing_organizations_method(self):
        """Test JobExecution has accessing_organizations method."""
        from lys.apps.base.modules.job.entities import JobExecution
        assert hasattr(JobExecution, "accessing_organizations")


class TestCronJobExecutionEntity:
    """Tests for CronJobExecution entity."""

    def test_entity_exists(self):
        """Test CronJobExecution entity exists."""
        from lys.apps.base.modules.job.entities import CronJobExecution
        assert CronJobExecution is not None

    def test_entity_inherits_from_job_execution(self):
        """Test CronJobExecution inherits from JobExecution."""
        from lys.apps.base.modules.job.entities import CronJobExecution, JobExecution
        assert issubclass(CronJobExecution, JobExecution)

    def test_entity_has_tablename(self):
        """Test CronJobExecution has correct __tablename__."""
        from lys.apps.base.modules.job.entities import CronJobExecution
        assert CronJobExecution.__tablename__ == "cron_job_execution"

    def test_entity_has_cron_column(self):
        """Test CronJobExecution has cron column."""
        from lys.apps.base.modules.job.entities import CronJobExecution
        assert "cron" in CronJobExecution.__annotations__


class TestMigrationJobExecutionEntity:
    """Tests for MigrationJobExecution entity."""

    def test_entity_exists(self):
        """Test MigrationJobExecution entity exists."""
        from lys.apps.base.modules.job.entities import MigrationJobExecution
        assert MigrationJobExecution is not None

    def test_entity_inherits_from_job_execution(self):
        """Test MigrationJobExecution inherits from JobExecution."""
        from lys.apps.base.modules.job.entities import MigrationJobExecution, JobExecution
        assert issubclass(MigrationJobExecution, JobExecution)

    def test_entity_has_tablename(self):
        """Test MigrationJobExecution has correct __tablename__."""
        from lys.apps.base.modules.job.entities import MigrationJobExecution
        assert MigrationJobExecution.__tablename__ == "migration_job_execution"

    def test_entity_has_cron_column(self):
        """Test MigrationJobExecution has cron column."""
        from lys.apps.base.modules.job.entities import MigrationJobExecution
        assert "cron" in MigrationJobExecution.__annotations__
