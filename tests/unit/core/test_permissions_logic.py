"""
Unit tests for core permissions module.

Tests cover:
- get_access_type: unknown webservice, disabled webservice, boolean permissions, dict permissions
- generate_webservice_permission: factory creates valid permission class
- add_access_constraints: false access, dict access
- check_access_to_object: permission granted, denied
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from lys.core.consts.errors import PERMISSION_DENIED_ERROR, UNKNOWN_WEBSERVICE_ERROR, NOT_FOUND_ERROR


@pytest.mark.asyncio
class TestGetAccessType:
    """Test get_access_type function."""

    async def test_unknown_webservice_returns_error(self):
        """Test that unknown webservice returns UNKNOWN_WEBSERVICE_ERROR."""
        from lys.core.permissions import get_access_type

        app_manager = MagicMock()
        app_manager.registry.webservices = {}
        context = MagicMock()

        access_type, error = await get_access_type(app_manager, "unknown_ws", context)

        assert access_type is False
        assert error == UNKNOWN_WEBSERVICE_ERROR

    async def test_disabled_webservice_returns_error(self):
        """Test that disabled webservice returns UNKNOWN_WEBSERVICE_ERROR."""
        from lys.core.permissions import get_access_type

        app_manager = MagicMock()
        app_manager.registry.webservices = {
            "disabled_ws": {"attributes": {"enabled": False}}
        }
        context = MagicMock()

        access_type, error = await get_access_type(app_manager, "disabled_ws", context)

        assert access_type is False
        assert error == UNKNOWN_WEBSERVICE_ERROR

    async def test_boolean_permission_granted(self):
        """Test that boolean True from permission grants access."""
        from lys.core.permissions import get_access_type

        permission = AsyncMock()
        permission.check_webservice_permission = AsyncMock(return_value=(True, None))

        app_manager = MagicMock()
        app_manager.registry.webservices = {
            "test_ws": {"attributes": {"enabled": True}}
        }
        app_manager.permissions = [permission]
        context = MagicMock()

        access_type, error = await get_access_type(app_manager, "test_ws", context)

        assert access_type is True

    async def test_boolean_permission_denied(self):
        """Test that boolean False from permission denies access."""
        from lys.core.permissions import get_access_type

        permission = AsyncMock()
        error_tuple = (403, "CUSTOM_DENIED")
        permission.check_webservice_permission = AsyncMock(return_value=(False, error_tuple))

        app_manager = MagicMock()
        app_manager.registry.webservices = {
            "test_ws": {"attributes": {"enabled": True}}
        }
        app_manager.permissions = [permission]
        context = MagicMock()

        access_type, error = await get_access_type(app_manager, "test_ws", context)

        assert access_type is False
        assert error == error_tuple

    async def test_dict_permissions_merged(self):
        """Test that dict permissions from multiple modules are merged."""
        from lys.core.permissions import get_access_type

        perm1 = AsyncMock()
        perm1.check_webservice_permission = AsyncMock(
            return_value=({"role": "admin"}, None)
        )
        perm2 = AsyncMock()
        perm2.check_webservice_permission = AsyncMock(
            return_value=({"org": "client_1"}, None)
        )

        app_manager = MagicMock()
        app_manager.registry.webservices = {
            "test_ws": {"attributes": {"enabled": True}}
        }
        app_manager.permissions = [perm1, perm2]
        context = MagicMock()

        access_type, _ = await get_access_type(app_manager, "test_ws", context)

        assert isinstance(access_type, dict)
        assert access_type["role"] == "admin"
        assert access_type["org"] == "client_1"

    async def test_permission_exception_continues_chain(self):
        """Test that permission exception doesn't crash, continues chain."""
        from lys.core.permissions import get_access_type

        perm_broken = AsyncMock()
        perm_broken.check_webservice_permission = AsyncMock(side_effect=RuntimeError("boom"))
        perm_broken.__class__.__name__ = "BrokenPermission"

        perm_ok = AsyncMock()
        perm_ok.check_webservice_permission = AsyncMock(return_value=(True, None))

        app_manager = MagicMock()
        app_manager.registry.webservices = {
            "test_ws": {"attributes": {"enabled": True}}
        }
        app_manager.permissions = [perm_broken, perm_ok]
        context = MagicMock()

        access_type, _ = await get_access_type(app_manager, "test_ws", context)

        assert access_type is True


@pytest.mark.asyncio
class TestGenerateWebservicePermission:
    """Test generate_webservice_permission factory."""

    async def test_creates_permission_class(self):
        """Test factory returns a permission class."""
        from lys.core.permissions import generate_webservice_permission

        perm_class = generate_webservice_permission("test_ws")
        assert perm_class is not None
        assert hasattr(perm_class, "has_permission")

    async def test_permission_grants_access_for_enabled_webservice(self):
        """Test generated permission grants access when permission chain allows."""
        from lys.core.permissions import generate_webservice_permission

        perm_class = generate_webservice_permission("test_ws")
        instance = object.__new__(perm_class)

        # Mock app_manager on the class
        mock_app_manager = MagicMock()
        mock_app_manager.registry.webservices = {
            "test_ws": {"attributes": {"enabled": True}}
        }
        perm_ok = AsyncMock()
        perm_ok.check_webservice_permission = AsyncMock(return_value=(True, None))
        mock_app_manager.permissions = [perm_ok]

        with patch.object(perm_class, "_app_manager", mock_app_manager):
            context = MagicMock()
            result = await instance.has_routers_permission(context)

        assert result is True
        assert context.access_type is True

    async def test_permission_denies_for_unknown_webservice(self):
        """Test generated permission denies for unknown webservice."""
        from lys.core.permissions import generate_webservice_permission

        perm_class = generate_webservice_permission("unknown_ws")
        instance = object.__new__(perm_class)

        mock_app_manager = MagicMock()
        mock_app_manager.registry.webservices = {}
        mock_app_manager.permissions = []

        with patch.object(perm_class, "_app_manager", mock_app_manager):
            context = MagicMock()
            result = await instance.has_routers_permission(context)

        assert result is False

    async def test_permission_handles_exception_gracefully(self):
        """Test generated permission handles exceptions without crashing."""
        from lys.core.permissions import generate_webservice_permission

        perm_class = generate_webservice_permission("test_ws")
        instance = object.__new__(perm_class)

        # Mock that raises during get_access_type
        mock_app_manager = MagicMock()
        mock_app_manager.registry = MagicMock(side_effect=RuntimeError("boom"))

        with patch.object(perm_class, "_app_manager", mock_app_manager):
            with patch("lys.core.permissions.get_access_type", side_effect=RuntimeError("boom")):
                context = MagicMock()
                result = await instance.has_routers_permission(context)

        assert result is False


@pytest.mark.asyncio
class TestAddAccessConstraints:
    """Test add_access_constraints function."""

    async def test_false_access_adds_false_where(self):
        """Test that False access_type adds a false() WHERE clause."""
        from lys.core.permissions import add_access_constraints

        context = MagicMock()
        context.access_type = False
        app_manager = MagicMock()
        stmt = MagicMock()

        result = await add_access_constraints(stmt, context, None, app_manager)

        stmt.where.assert_called_once()
        assert result == stmt.where.return_value

    async def test_dict_access_calls_permission_constraints(self):
        """Test that dict access_type invokes permission add_statement_access_constraints."""
        from lys.core.permissions import add_access_constraints

        context = MagicMock()
        context.access_type = {"role": "admin"}

        perm = AsyncMock()
        perm.add_statement_access_constraints = AsyncMock(
            return_value=(MagicMock(), MagicMock())
        )

        app_manager = MagicMock()
        app_manager.permissions = [perm]

        stmt = MagicMock()
        await add_access_constraints(stmt, context, None, app_manager)

        perm.add_statement_access_constraints.assert_called_once()

    async def test_true_access_returns_unchanged_stmt(self):
        """Test that True access_type returns statement unchanged."""
        from lys.core.permissions import add_access_constraints

        context = MagicMock()
        context.access_type = True
        context.connected_user = None

        app_manager = MagicMock()
        stmt = MagicMock()

        result = await add_access_constraints(stmt, context, None, app_manager)

        # True access → no WHERE clause added
        assert result == stmt

    async def test_sensitive_entity_list_access_is_logged(self, caplog):
        """Test that list access to a sensitive entity produces an audit log."""
        from lys.core.permissions import add_access_constraints

        entity_class = MagicMock()
        entity_class.__name__ = "User"
        entity_class._sensitive = True

        context = MagicMock()
        context.access_type = True
        context.connected_user = {"sub": "user-123"}
        context.webservice_name = "all_users"

        app_manager = MagicMock()
        stmt = MagicMock()

        with caplog.at_level("INFO", logger="lys.core.permissions"):
            await add_access_constraints(stmt, context, entity_class, app_manager)

        assert any("AUDIT: List access to User" in msg for msg in caplog.messages)
        assert any("user=user-123" in msg for msg in caplog.messages)
        assert any("webservice=all_users" in msg for msg in caplog.messages)

    async def test_non_sensitive_entity_list_access_not_logged(self, caplog):
        """Test that list access to a non-sensitive entity does not log."""
        from lys.core.permissions import add_access_constraints

        entity_class = MagicMock()
        entity_class.__name__ = "Invoice"
        entity_class._sensitive = False

        context = MagicMock()
        context.access_type = True
        context.connected_user = {"sub": "user-123"}

        app_manager = MagicMock()
        stmt = MagicMock()

        with caplog.at_level("INFO", logger="lys.core.permissions"):
            await add_access_constraints(stmt, context, entity_class, app_manager)

        assert not any("AUDIT" in msg for msg in caplog.messages)

    async def test_false_access_sensitive_entity_not_logged(self, caplog):
        """Test that denied list access to a sensitive entity is not logged."""
        from lys.core.permissions import add_access_constraints

        entity_class = MagicMock()
        entity_class.__name__ = "User"
        entity_class._sensitive = True

        context = MagicMock()
        context.access_type = False
        context.connected_user = {"sub": "user-123"}

        app_manager = MagicMock()
        stmt = MagicMock()

        with caplog.at_level("INFO", logger="lys.core.permissions"):
            await add_access_constraints(stmt, context, entity_class, app_manager)

        assert not any("AUDIT" in msg for msg in caplog.messages)


@pytest.mark.asyncio
class TestCheckAccessToObject:
    """Test check_access_to_object and get_db_object_and_check_access."""

    async def test_check_access_granted(self):
        """Test check_access_to_object returns True when permission granted."""
        from lys.core.utils.access import check_access_to_object

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = True
        entity_obj._sensitive = False

        context = MagicMock()
        context.connected_user = {"sub": "user-123"}
        context.access_type = True

        result = await check_access_to_object(entity_obj, context)
        assert result is True

    async def test_check_access_denied_raises(self):
        """Test check_access_to_object raises LysError when denied."""
        from lys.core.utils.access import check_access_to_object
        from lys.core.errors import LysError

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = False
        entity_obj._sensitive = False

        context = MagicMock()
        context.connected_user = {"sub": "user-123"}
        context.access_type = True

        with pytest.raises(LysError):
            await check_access_to_object(entity_obj, context)

    async def test_check_access_no_connected_user(self):
        """Test check_access_to_object with no connected user."""
        from lys.core.utils.access import check_access_to_object

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = True
        entity_obj._sensitive = False

        context = MagicMock()
        context.connected_user = None
        context.access_type = True

        result = await check_access_to_object(entity_obj, context)
        assert result is True
        entity_obj.check_permission.assert_called_once_with(None, True)

    async def test_sensitive_entity_access_is_logged(self, caplog):
        """Test that accessing a sensitive entity produces an audit log after permission check."""
        from lys.core.utils.access import check_access_to_object

        entity_obj = MagicMock()
        entity_obj.__class__.__name__ = "UserPrivateData"
        entity_obj._sensitive = True
        entity_obj.id = "entity-456"
        entity_obj.check_permission.return_value = True

        context = MagicMock()
        context.connected_user = {"sub": "user-123"}
        context.access_type = True

        with caplog.at_level("INFO", logger="lys.core.utils.access"):
            await check_access_to_object(entity_obj, context)

        assert any("AUDIT: Access to UserPrivateData" in msg for msg in caplog.messages)
        assert any("user=user-123" in msg for msg in caplog.messages)
        assert any("id=entity-456" in msg for msg in caplog.messages)

    async def test_non_sensitive_entity_access_not_logged(self, caplog):
        """Test that accessing a non-sensitive entity does not produce an audit log."""
        from lys.core.utils.access import check_access_to_object

        entity_obj = MagicMock()
        entity_obj._sensitive = False
        entity_obj.check_permission.return_value = True

        context = MagicMock()
        context.connected_user = {"sub": "user-123"}
        context.access_type = True

        with caplog.at_level("INFO", logger="lys.core.utils.access"):
            await check_access_to_object(entity_obj, context)

        assert not any("AUDIT" in msg for msg in caplog.messages)

    async def test_sensitive_entity_denied_not_logged(self, caplog):
        """Test that denied access to a sensitive entity is not logged."""
        from lys.core.utils.access import check_access_to_object
        from lys.core.errors import LysError

        entity_obj = MagicMock()
        entity_obj.__class__.__name__ = "User"
        entity_obj._sensitive = True
        entity_obj.check_permission.return_value = False

        context = MagicMock()
        context.connected_user = {"sub": "user-123"}
        context.access_type = True

        with caplog.at_level("INFO", logger="lys.core.utils.access"):
            with pytest.raises(LysError):
                await check_access_to_object(entity_obj, context)

        assert not any("AUDIT" in msg for msg in caplog.messages)

    async def test_sensitive_entity_anonymous_access_is_logged(self, caplog):
        """Test that anonymous access to a sensitive entity is still logged."""
        from lys.core.utils.access import check_access_to_object

        entity_obj = MagicMock()
        entity_obj.__class__.__name__ = "User"
        entity_obj._sensitive = True
        entity_obj.id = "entity-789"
        entity_obj.check_permission.return_value = True

        context = MagicMock()
        context.connected_user = None
        context.access_type = True

        with caplog.at_level("INFO", logger="lys.core.utils.access"):
            await check_access_to_object(entity_obj, context)

        assert any("AUDIT: Access to User" in msg for msg in caplog.messages)
        assert any("user=None" in msg for msg in caplog.messages)

    async def test_sensitive_entity_log_includes_webservice(self, caplog):
        """Test that audit log includes the webservice name."""
        from lys.core.utils.access import check_access_to_object

        entity_obj = MagicMock()
        entity_obj.__class__.__name__ = "UserPrivateData"
        entity_obj._sensitive = True
        entity_obj.id = "entity-456"
        entity_obj.check_permission.return_value = True

        context = MagicMock()
        context.connected_user = {"sub": "user-123"}
        context.access_type = True
        context.webservice_name = "get_user_private_data"

        with caplog.at_level("INFO", logger="lys.core.utils.access"):
            await check_access_to_object(entity_obj, context)

        assert any("webservice=get_user_private_data" in msg for msg in caplog.messages)

    async def test_get_db_object_not_found_raises(self):
        """Test get_db_object_and_check_access raises for missing entity."""
        from lys.core.utils.access import get_db_object_and_check_access
        from lys.core.errors import LysError

        service_class = AsyncMock()
        service_class.get_by_id = AsyncMock(return_value=None)
        service_class.entity_class.__tablename__ = "test_entity"

        context = MagicMock()
        session = AsyncMock()

        with pytest.raises(LysError):
            await get_db_object_and_check_access("bad-id", service_class, context, session)

    async def test_get_db_object_nullable_returns_none(self):
        """Test get_db_object_and_check_access with nullable=True returns None."""
        from lys.core.utils.access import get_db_object_and_check_access

        service_class = AsyncMock()
        service_class.get_by_id = AsyncMock(return_value=None)

        context = MagicMock()
        session = AsyncMock()

        result = await get_db_object_and_check_access(
            "bad-id", service_class, context, session, nullable=True
        )
        assert result is None

    async def test_get_db_object_found_checks_access(self):
        """Test get_db_object_and_check_access checks access on found entity."""
        from lys.core.utils.access import get_db_object_and_check_access

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = True

        service_class = AsyncMock()
        service_class.get_by_id = AsyncMock(return_value=entity_obj)

        context = MagicMock()
        context.connected_user = {"sub": "user-123"}
        context.access_type = True
        session = AsyncMock()

        result = await get_db_object_and_check_access(
            "good-id", service_class, context, session
        )
        assert result == entity_obj
