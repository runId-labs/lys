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

    @pytest.mark.asyncio
    async def test_sets_pending_plan_version(self):
        """Downgrading to a cheaper paid plan only schedules the change."""
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        from datetime import datetime

        mock_sub = Mock()
        mock_sub.pending_plan_version_id = None
        mock_sub.current_period_end = datetime(2025, 2, 1)
        mock_sub.provider_subscription_id = "sub_123"
        mock_sub.commitment_end_date = None
        mock_sub.is_committed = False
        mock_sub.effective_change_date = datetime(2025, 2, 1)

        paid_target = Mock()
        paid_target.is_free = False

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=paid_target)

        with patch.object(SubscriptionService, "app_manager", create=True) as mock_am:
            result = await SubscriptionService._handle_downgrade(
                subscription=mock_sub,
                plan_version_id="pv-new",
                session=mock_session
            )

            assert result.success is True
            assert mock_sub.pending_plan_version_id == "pv-new"
            assert result.effective_date == datetime(2025, 2, 1)
            # The provider subscription is left alone until the change applies
            mock_am.get_service.assert_not_called()

    @pytest.mark.asyncio
    async def test_downgrade_to_free_stops_the_provider_subscription(self):
        """Nothing else would stop collection, so it must happen right away."""
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        from datetime import datetime

        mock_sub = Mock()
        mock_sub.pending_plan_version_id = None
        mock_sub.canceled_at = None
        mock_sub.current_period_end = datetime(2025, 2, 1)
        mock_sub.provider_subscription_id = "sub_123"
        mock_sub.client_id = "client-1"
        mock_sub.commitment_end_date = None
        mock_sub.is_committed = False
        mock_sub.effective_change_date = datetime(2025, 2, 1)

        free_target = Mock()
        free_target.is_free = True

        client = Mock()
        client.provider_customer_id = "cst_123"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[free_target, client])

        checkout_service = Mock()
        checkout_service.cancel_provider_subscription = Mock(return_value=True)

        with patch.object(SubscriptionService, "app_manager", create=True) as mock_am:
            mock_am.get_service.return_value = checkout_service

            result = await SubscriptionService._handle_downgrade(
                subscription=mock_sub,
                plan_version_id="pv-free",
                session=mock_session
            )

            assert result.success is True
            checkout_service.cancel_provider_subscription.assert_called_once_with(
                customer_id="cst_123",
                provider_subscription_id="sub_123"
            )
            assert mock_sub.canceled_at is not None


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


class TestApplyPendingPlanChangesGuards:
    """Guards on the task applying pending plan changes."""

    def test_paid_target_without_matching_price_is_not_applied(self):
        """
        Applying it would grant a paid plan we cannot bill, while the provider
        keeps collecting the previous amount. The change stays pending instead.
        """
        from lys.apps.licensing.tasks import apply_pending_plan_changes

        current_price = Mock(period_id="MONTHLY", currency_id="EUR")

        subscription = Mock()
        subscription.id = "sub-1"
        subscription.plan_version_id = "pv-current"
        subscription.pending_plan_version_id = "pv-target"
        subscription.plan_version_price = current_price
        subscription.canceled_at = None
        subscription.provider_subscription_id = "sub_mollie"

        # Target is paid but carries no price on the subscribed terms
        target_version = Mock()
        target_version.is_free = False
        target_version.price_for = Mock(return_value=None)

        session = Mock()
        session.get = Mock(return_value=target_version)
        session.execute = Mock(
            return_value=Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[subscription]))))
        )
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)

        subscription_entity = Mock()
        subscription_entity.current_period_end = Mock(__le__=Mock(return_value=Mock()))
        subscription_entity.commitment_end_date = Mock(__le__=Mock(return_value=Mock()))

        app_manager = Mock()
        app_manager.get_entity = Mock(return_value=subscription_entity)
        app_manager.database.get_sync_session = Mock(return_value=session)

        with patch("lys.apps.licensing.tasks.current_app") as mock_current_app:
            mock_current_app.app_manager = app_manager
            # The entity registry is mocked, so the query cannot be built for real
            with patch("lys.apps.licensing.tasks.select"), \
                    patch("lys.apps.licensing.tasks.and_"), \
                    patch("lys.apps.licensing.tasks.or_"):
                applied = apply_pending_plan_changes()

        assert applied == 0
        # The change is still pending, and the plan was not switched
        assert subscription.pending_plan_version_id == "pv-target"
        assert subscription.plan_version_id == "pv-current"


class TestSubscriptionCommitmentExposure:
    """The commitment terms a client is bound by must be readable."""

    def test_node_exposes_the_commitment_fields(self):
        """
        A client cannot know when they may leave unless the term and the notice
        deadline are exposed.
        """
        from lys.apps.licensing.modules.subscription.nodes import SubscriptionNode

        for field in (
            "commitment_end_date", "notice_deadline", "is_committed",
            "can_be_cancelled_now", "effective_change_date", "plan_version_price"
        ):
            assert hasattr(SubscriptionNode, field), f"{field} is not exposed"

    def test_commitment_node_exposes_renewal_and_notice(self):
        """A buyer must see the renewal and notice terms before committing."""
        from lys.apps.licensing.modules.plan.nodes import LicenseCommitmentNode

        annotations = LicenseCommitmentNode.__annotations__
        assert "duration_months" in annotations
        assert "renewal_months" in annotations
        assert "notice_months" in annotations
        assert hasattr(LicenseCommitmentNode, "is_renewable")
