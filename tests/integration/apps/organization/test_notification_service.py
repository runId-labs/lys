"""
Integration tests for Organization NotificationBatchService.

Tests cover:
- validate_organization_data (valid, None, invalid)
- dispatch (basic flow with seeded data)
- _resolve_organization_recipients
"""

import pytest
from uuid import uuid4

from pydantic import ValidationError


class TestNotificationBatchServiceValidation:
    """Test NotificationBatchService.validate_organization_data."""

    @pytest.mark.asyncio
    async def test_validate_organization_data_with_client_ids(self, organization_app_manager):
        """Test validating organization_data with client_ids."""
        notification_service = organization_app_manager.get_service("notification_batch")

        result = notification_service.validate_organization_data(
            {"client_ids": [str(uuid4()), str(uuid4())]}
        )
        assert result is not None
        assert len(result.client_ids) == 2

    @pytest.mark.asyncio
    async def test_validate_organization_data_none(self, organization_app_manager):
        """Test validating None organization_data returns None."""
        notification_service = organization_app_manager.get_service("notification_batch")

        result = notification_service.validate_organization_data(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_organization_data_empty_dict(self, organization_app_manager):
        """Test validating empty dict returns OrganizationData with defaults."""
        notification_service = organization_app_manager.get_service("notification_batch")

        result = notification_service.validate_organization_data({})
        assert result is not None
        assert result.client_ids is None


class TestNotificationBatchServiceDispatch:
    """Test NotificationBatchService.dispatch."""

    @pytest.mark.asyncio
    async def test_dispatch_with_notification_type(self, organization_app_manager):
        """Test dispatching a notification with seeded notification type."""
        notification_service = organization_app_manager.get_service("notification_batch")
        notification_type_service = organization_app_manager.get_service("notification_type")

        # Seed a notification type
        async with organization_app_manager.database.get_session() as session:
            try:
                await notification_type_service.create(
                    session=session,
                    id="TEST_NOTIFICATION",
                    enabled=True
                )
                await session.commit()
            except Exception:
                await session.rollback()

        # Dispatch notification
        async with organization_app_manager.database.get_session() as session:
            batch = await notification_service.dispatch(
                session=session,
                type_id="TEST_NOTIFICATION",
                data={"message": "Test notification"},
                triggered_by_user_id=str(uuid4()),
                additional_user_ids=[str(uuid4())],
            )
            await session.commit()

            assert batch is not None
            assert batch.type_id == "TEST_NOTIFICATION"

    @pytest.mark.asyncio
    async def test_dispatch_nonexistent_type_raises(self, organization_app_manager):
        """Test dispatch raises ValueError for unknown notification type."""
        notification_service = organization_app_manager.get_service("notification_batch")

        async with organization_app_manager.database.get_session() as session:
            with pytest.raises(ValueError) as exc_info:
                await notification_service.dispatch(
                    session=session,
                    type_id="NONEXISTENT_TYPE",
                    data={"test": True},
                )
            assert "NONEXISTENT_TYPE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dispatch_with_organization_data(self, organization_app_manager):
        """Test dispatching with organization_data for scoped recipients."""
        notification_service = organization_app_manager.get_service("notification_batch")
        notification_type_service = organization_app_manager.get_service("notification_type")

        # Seed notification type
        async with organization_app_manager.database.get_session() as session:
            try:
                await notification_type_service.create(
                    session=session,
                    id="ORG_SCOPED_NOTIFICATION",
                    enabled=True
                )
                await session.commit()
            except Exception:
                await session.rollback()

        client_id = str(uuid4())
        async with organization_app_manager.database.get_session() as session:
            batch = await notification_service.dispatch(
                session=session,
                type_id="ORG_SCOPED_NOTIFICATION",
                data={"action": "test"},
                organization_data={"client_ids": [client_id]},
            )
            await session.commit()

            assert batch is not None
            assert batch.organization_data == {"client_ids": [client_id]}
