"""
Unit tests for SubscriptionService logic (create_subscription, change_plan, _handle_downgrade,
apply_pending_change).

Isolation: All tests use inline imports + patch.object. No global state modified.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch


class TestCreateSubscription:
    """Tests for SubscriptionService.create_subscription()."""

    @pytest.mark.asyncio
    async def test_already_exists_raises(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        with patch.object(
            SubscriptionService, "get_client_subscription",
            new_callable=AsyncMock, return_value=Mock()
        ):
            with patch.object(SubscriptionService, "app_manager", create=True):
                with pytest.raises(LysError, match="SUBSCRIPTION_ALREADY_EXISTS"):
                    await SubscriptionService.create_subscription("client-1", "pv-1", mock_session)

    @pytest.mark.asyncio
    async def test_plan_version_not_found_raises(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_pv_service = AsyncMock()
        mock_pv_service.get_by_id = AsyncMock(return_value=None)

        with patch.object(
            SubscriptionService, "get_client_subscription",
            new_callable=AsyncMock, return_value=None
        ):
            with patch.object(SubscriptionService, "app_manager", create=True) as mock_am:
                mock_am.get_service.return_value = mock_pv_service
                with pytest.raises(LysError, match="PLAN_VERSION_NOT_FOUND"):
                    await SubscriptionService.create_subscription("client-1", "pv-1", mock_session)

    @pytest.mark.asyncio
    async def test_success_creates_subscription(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        mock_session = AsyncMock()
        mock_pv = Mock()
        mock_pv_service = AsyncMock()
        mock_pv_service.get_by_id = AsyncMock(return_value=mock_pv)
        mock_sub = Mock()

        with patch.object(
            SubscriptionService, "get_client_subscription",
            new_callable=AsyncMock, return_value=None
        ):
            with patch.object(SubscriptionService, "app_manager", create=True) as mock_am:
                mock_am.get_service.return_value = mock_pv_service
                with patch.object(
                    SubscriptionService, "create",
                    new_callable=AsyncMock, return_value=mock_sub
                ) as mock_create:
                    result = await SubscriptionService.create_subscription(
                        "client-1", "pv-1", mock_session
                    )

        assert result is mock_sub
        mock_create.assert_called_once_with(
            mock_session,
            client_id="client-1",
            plan_version_id="pv-1",
            provider_subscription_id=None
        )


class TestChangePlan:
    """Tests for SubscriptionService.change_plan()."""

    @pytest.mark.asyncio
    async def test_no_subscription_raises(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        with patch.object(
            SubscriptionService, "get_client_subscription",
            new_callable=AsyncMock, return_value=None
        ):
            with patch.object(SubscriptionService, "app_manager", create=True):
                with pytest.raises(LysError, match="NO_ACTIVE_SUBSCRIPTION"):
                    await SubscriptionService.change_plan("client-1", "pv-2", mock_session)

    @pytest.mark.asyncio
    async def test_plan_version_not_found_raises(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_sub = Mock()
        mock_pv_service = AsyncMock()
        mock_pv_service.get_by_id = AsyncMock(return_value=None)

        with patch.object(
            SubscriptionService, "get_client_subscription",
            new_callable=AsyncMock, return_value=mock_sub
        ):
            with patch.object(SubscriptionService, "app_manager", create=True) as mock_am:
                mock_am.get_service.return_value = mock_pv_service
                with pytest.raises(LysError, match="PLAN_VERSION_NOT_FOUND"):
                    await SubscriptionService.change_plan("client-1", "pv-2", mock_session)

    @pytest.mark.asyncio
    async def test_immediate_change(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        mock_session = AsyncMock()
        mock_sub = Mock()
        mock_sub.plan_version_id = "pv-1"
        mock_sub.pending_plan_version_id = "pv-old"

        mock_pv = Mock()
        mock_pv_service = AsyncMock()
        mock_pv_service.get_by_id = AsyncMock(return_value=mock_pv)

        with patch.object(
            SubscriptionService, "get_client_subscription",
            new_callable=AsyncMock, return_value=mock_sub
        ):
            with patch.object(SubscriptionService, "app_manager", create=True) as mock_am:
                mock_am.get_service.return_value = mock_pv_service
                result = await SubscriptionService.change_plan(
                    "client-1", "pv-2", mock_session, immediate=True
                )

        assert result is mock_sub
        assert mock_sub.plan_version_id == "pv-2"
        assert mock_sub.pending_plan_version_id is None

    @pytest.mark.asyncio
    async def test_deferred_change(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        mock_session = AsyncMock()
        mock_sub = Mock()
        mock_sub.plan_version_id = "pv-1"
        mock_sub.pending_plan_version_id = None

        mock_pv = Mock()
        mock_pv_service = AsyncMock()
        mock_pv_service.get_by_id = AsyncMock(return_value=mock_pv)

        with patch.object(
            SubscriptionService, "get_client_subscription",
            new_callable=AsyncMock, return_value=mock_sub
        ):
            with patch.object(SubscriptionService, "app_manager", create=True) as mock_am:
                mock_am.get_service.return_value = mock_pv_service
                result = await SubscriptionService.change_plan(
                    "client-1", "pv-2", mock_session, immediate=False
                )

        assert result is mock_sub
        assert mock_sub.plan_version_id == "pv-1"  # Unchanged
        assert mock_sub.pending_plan_version_id == "pv-2"


class TestHandleDowngrade:
    """Tests for SubscriptionService._handle_downgrade() — pure sync logic."""

    def test_sets_pending_plan_version(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        from datetime import datetime

        mock_sub = Mock()
        mock_sub.pending_plan_version_id = None
        mock_sub.current_period_end = datetime(2025, 2, 1)

        result = SubscriptionService._handle_downgrade(
            subscription=mock_sub,
            plan_version_id="pv-new"
        )

        assert result.success is True
        assert mock_sub.pending_plan_version_id == "pv-new"
        assert result.effective_date == datetime(2025, 2, 1)


class TestApplyPendingChange:
    """Tests for SubscriptionService.apply_pending_change()."""

    @pytest.mark.asyncio
    async def test_no_subscription_returns_none(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        mock_session = AsyncMock()
        with patch.object(
            SubscriptionService, "get_by_id",
            new_callable=AsyncMock, return_value=None
        ):
            result = await SubscriptionService.apply_pending_change("sub-1", mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_pending_returns_none(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        mock_session = AsyncMock()
        mock_sub = Mock()
        mock_sub.pending_plan_version_id = None

        with patch.object(
            SubscriptionService, "get_by_id",
            new_callable=AsyncMock, return_value=mock_sub
        ):
            result = await SubscriptionService.apply_pending_change("sub-1", mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_applies_pending_change(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        mock_session = AsyncMock()
        mock_sub = Mock()
        mock_sub.plan_version_id = "pv-old"
        mock_sub.pending_plan_version_id = "pv-new"

        with patch.object(
            SubscriptionService, "get_by_id",
            new_callable=AsyncMock, return_value=mock_sub
        ):
            result = await SubscriptionService.apply_pending_change("sub-1", mock_session)

        assert result is mock_sub
        assert mock_sub.plan_version_id == "pv-new"
        assert mock_sub.pending_plan_version_id is None
