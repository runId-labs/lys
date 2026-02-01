"""
Unit tests for base job module mixins.

Tests mixin structure.
"""

import pytest


class TestCronJobExecutionChildMixin:
    """Tests for CronJobExecutionChildMixin."""

    def test_mixin_exists(self):
        """Test CronJobExecutionChildMixin class exists."""
        from lys.apps.base.modules.job.mixins import CronJobExecutionChildMixin
        assert CronJobExecutionChildMixin is not None

    def test_mixin_has_cron_job_execution_id_column(self):
        """Test mixin has cron_job_execution_id column annotation."""
        from lys.apps.base.modules.job.mixins import CronJobExecutionChildMixin
        assert "cron_job_execution_id" in CronJobExecutionChildMixin.__annotations__

    def test_mixin_column_is_mapped(self):
        """Test cron_job_execution_id is properly mapped."""
        from lys.apps.base.modules.job.mixins import CronJobExecutionChildMixin
        from sqlalchemy.orm import Mapped
        # The annotation should indicate it's a Mapped type
        annotation = CronJobExecutionChildMixin.__annotations__["cron_job_execution_id"]
        assert "Mapped" in str(annotation) or hasattr(annotation, "__origin__")
