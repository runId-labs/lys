"""
Unit tests for webservice services.

Tests WebserviceService methods with mocked dependencies.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestWebserviceServiceAccessibleWebservices:
    """Tests for WebserviceService.accessible_webservices method.

    Note: These tests verify method signature and behavior, but cannot fully test
    SQLAlchemy select() as it requires real entity classes. Full testing requires
    integration tests.
    """

    def test_accessible_webservices_method_exists(self):
        """Test that accessible_webservices method exists."""
        from lys.apps.base.modules.webservice.services import WebserviceService

        assert hasattr(WebserviceService, 'accessible_webservices')
        assert callable(getattr(WebserviceService, 'accessible_webservices'))

    def test_accessible_webservices_is_async(self):
        """Test that accessible_webservices is an async method."""
        import inspect
        from lys.apps.base.modules.webservice.services import WebserviceService

        assert inspect.iscoroutinefunction(WebserviceService.accessible_webservices)

    def test_accessible_webservices_is_classmethod(self):
        """Test that accessible_webservices is a classmethod."""
        from lys.apps.base.modules.webservice.services import WebserviceService

        # Check it can be called on the class without instance
        method = getattr(WebserviceService, 'accessible_webservices')
        assert hasattr(method, '__func__')


class TestWebserviceServiceGetUserAccessLevels:
    """Tests for WebserviceService.get_user_access_levels method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def mock_webservice(self):
        """Create mock webservice entity."""
        webservice = MagicMock()
        webservice.id = "get_users"
        return webservice

    @pytest.mark.asyncio
    async def test_get_user_access_levels_returns_empty_list(self, mock_session, mock_webservice):
        """Test that base implementation returns empty list."""
        from lys.apps.base.modules.webservice.services import WebserviceService

        result = await WebserviceService.get_user_access_levels(
            mock_webservice,
            {"id": "user-123"},
            mock_session
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_access_levels_with_none_user(self, mock_session, mock_webservice):
        """Test with anonymous user (None)."""
        from lys.apps.base.modules.webservice.services import WebserviceService

        result = await WebserviceService.get_user_access_levels(
            mock_webservice,
            None,
            mock_session
        )

        assert result == []


class TestWebserviceServiceRegisterWebservices:
    """Tests for WebserviceService.register_webservices method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.get = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_app_manager(self):
        """Create mock app manager."""
        app_manager = MagicMock()
        app_manager.get_entity.return_value = MagicMock()
        return app_manager

    @pytest.fixture
    def mock_webservice_config(self):
        """Create mock webservice config."""
        config = MagicMock()
        config.id = "test_webservice"
        config.attributes.access_levels = ["PUBLIC"]
        config.attributes.public_type = "NO_LIMITATION"
        config.attributes.is_licenced = False
        config.attributes.enabled = True
        config.attributes.operation_type = "READ"
        config.attributes.ai_tool = False
        return config

    @pytest.mark.asyncio
    async def test_register_webservices_creates_new(self, mock_session, mock_app_manager, mock_webservice_config):
        """Test registering a new webservice."""
        from lys.apps.base.modules.webservice.services import WebserviceService

        # Webservice doesn't exist yet
        mock_session.get.side_effect = [MagicMock(), None]  # access_level, webservice

        mock_entity_class = MagicMock()

        with patch.object(WebserviceService, 'app_manager', mock_app_manager):
            with patch.object(WebserviceService, 'entity_class', mock_entity_class):
                result = await WebserviceService.register_webservices(
                    [mock_webservice_config],
                    "test_app",
                    mock_session
                )

        assert result == 1
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_webservices_updates_existing(self, mock_session, mock_app_manager, mock_webservice_config):
        """Test updating an existing webservice."""
        from lys.apps.base.modules.webservice.services import WebserviceService

        # Existing webservice
        existing_ws = MagicMock()
        mock_session.get.side_effect = [MagicMock(), existing_ws]  # access_level, webservice

        with patch.object(WebserviceService, 'app_manager', mock_app_manager):
            with patch.object(WebserviceService, 'entity_class', MagicMock()):
                result = await WebserviceService.register_webservices(
                    [mock_webservice_config],
                    "test_app",
                    mock_session
                )

        assert result == 1
        # Should not call add for existing webservice
        mock_session.add.assert_not_called()
        # Should update properties
        assert existing_ws.app_name == "test_app"
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_webservices_returns_count(self, mock_session, mock_app_manager):
        """Test that method returns count of registered webservices."""
        from lys.apps.base.modules.webservice.services import WebserviceService

        configs = []
        for i in range(3):
            config = MagicMock()
            config.id = f"ws_{i}"
            config.attributes.access_levels = []
            config.attributes.public_type = None
            config.attributes.is_licenced = False
            config.attributes.enabled = True
            config.attributes.operation_type = "READ"
            config.attributes.ai_tool = False
            configs.append(config)

        mock_session.get.return_value = None

        with patch.object(WebserviceService, 'app_manager', mock_app_manager):
            with patch.object(WebserviceService, 'entity_class', MagicMock()):
                result = await WebserviceService.register_webservices(
                    configs,
                    "test_app",
                    mock_session
                )

        assert result == 3

    @pytest.mark.asyncio
    async def test_register_webservices_fetches_access_levels(self, mock_session, mock_app_manager, mock_webservice_config):
        """Test that access levels are fetched from database."""
        from lys.apps.base.modules.webservice.services import WebserviceService

        mock_webservice_config.attributes.access_levels = ["PUBLIC", "AUTHENTICATED"]

        mock_access_level = MagicMock()
        # First two calls for access levels, third for webservice
        mock_session.get.side_effect = [mock_access_level, mock_access_level, None]

        with patch.object(WebserviceService, 'app_manager', mock_app_manager):
            with patch.object(WebserviceService, 'entity_class', MagicMock()):
                await WebserviceService.register_webservices(
                    [mock_webservice_config],
                    "test_app",
                    mock_session
                )

        # Should fetch access_level entity - check it was called at some point
        calls = [str(c) for c in mock_app_manager.get_entity.call_args_list]
        assert any("access_level" in c for c in calls)


class TestWebserviceServiceInheritance:
    """Tests for WebserviceService class structure."""

    def test_inherits_from_entity_service(self):
        """Test that WebserviceService inherits from EntityService."""
        from lys.apps.base.modules.webservice.services import WebserviceService
        from lys.core.services import EntityService

        assert issubclass(WebserviceService, EntityService)
