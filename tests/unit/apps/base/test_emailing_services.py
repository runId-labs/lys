"""
Unit tests for emailing services.

Tests EmailingService methods with mocked dependencies.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from pathlib import Path

from lys.core.entities import Entity


class TestEmailingServiceComputeContext:
    """Tests for EmailingService.compute_context static method."""

    @pytest.fixture
    def mock_entity(self):
        """Create a mock entity with attributes."""
        entity = MagicMock(spec=Entity)
        entity.id = "entity-123"
        entity.name = "Test Entity"
        entity.email = "test@example.com"
        return entity

    @pytest.fixture
    def mock_nested_entity(self):
        """Create a mock entity with nested entity."""
        # Nested entity
        nested = MagicMock(spec=Entity)
        nested.id = "nested-456"
        nested.code = "CODE123"

        # Parent entity
        parent = MagicMock(spec=Entity)
        parent.id = "parent-123"
        parent.name = "Parent Entity"
        parent.child = nested

        return parent

    def test_compute_context_with_simple_attributes(self, mock_entity):
        """Test computing context with simple string attributes."""
        from lys.apps.base.modules.emailing.services import EmailingService

        context_description = {
            "user": ["name", "email"]
        }

        result = EmailingService.compute_context(context_description, user=mock_entity)

        assert result["name"] == "Test Entity"
        assert result["email"] == "test@example.com"

    def test_compute_context_with_nested_entity(self, mock_nested_entity):
        """Test computing context with nested entity attributes."""
        from lys.apps.base.modules.emailing.services import EmailingService

        context_description = {
            "user": ["name", {"child": ["code"]}]
        }

        result = EmailingService.compute_context(context_description, user=mock_nested_entity)

        assert result["name"] == "Parent Entity"
        assert result["child"]["code"] == "CODE123"

    def test_compute_context_with_string_value(self):
        """Test computing context with direct string value."""
        from lys.apps.base.modules.emailing.services import EmailingService

        context_description = {
            "reset_url": None  # None means pass value directly
        }

        result = EmailingService.compute_context(
            context_description,
            reset_url="https://example.com/reset/token123"
        )

        assert result["reset_url"] == "https://example.com/reset/token123"

    def test_compute_context_with_integer_value(self):
        """Test computing context with direct integer value."""
        from lys.apps.base.modules.emailing.services import EmailingService

        context_description = {
            "verification_code": None
        }

        result = EmailingService.compute_context(
            context_description,
            verification_code=123456
        )

        assert result["verification_code"] == 123456

    def test_compute_context_with_float_value(self):
        """Test computing context with direct float value."""
        from lys.apps.base.modules.emailing.services import EmailingService

        context_description = {
            "total_amount": None
        }

        result = EmailingService.compute_context(
            context_description,
            total_amount=99.99
        )

        assert result["total_amount"] == 99.99

    def test_compute_context_with_mixed_values(self, mock_entity):
        """Test computing context with both entity attributes and direct values."""
        from lys.apps.base.modules.emailing.services import EmailingService

        context_description = {
            "user": ["name", "email"],
            "reset_url": None,
            "expiry_hours": None
        }

        result = EmailingService.compute_context(
            context_description,
            user=mock_entity,
            reset_url="https://example.com/reset",
            expiry_hours=24
        )

        assert result["name"] == "Test Entity"
        assert result["email"] == "test@example.com"
        assert result["reset_url"] == "https://example.com/reset"
        assert result["expiry_hours"] == 24

    def test_compute_context_with_empty_description(self):
        """Test computing context with empty description."""
        from lys.apps.base.modules.emailing.services import EmailingService

        result = EmailingService.compute_context({})

        assert result == {}

    def test_compute_context_ignores_missing_kwargs(self, mock_entity):
        """Test that missing kwargs are ignored."""
        from lys.apps.base.modules.emailing.services import EmailingService

        context_description = {
            "user": ["name"],
            "missing_key": None  # This key is not in kwargs
        }

        result = EmailingService.compute_context(context_description, user=mock_entity)

        assert result["name"] == "Test Entity"
        assert "missing_key" not in result

    def test_compute_context_ignores_non_entity_with_description(self):
        """Test that non-entity objects with description are ignored."""
        from lys.apps.base.modules.emailing.services import EmailingService

        context_description = {
            "not_entity": ["some_attr"]  # Has description but not an entity
        }

        result = EmailingService.compute_context(
            context_description,
            not_entity="just a string"
        )

        # String with description should be ignored
        assert "some_attr" not in result

    def test_compute_context_deeply_nested_entity(self):
        """Test computing context with deeply nested entity."""
        from lys.apps.base.modules.emailing.services import EmailingService

        # Create deeply nested structure
        level3 = MagicMock(spec=Entity)
        level3.value = "deep_value"

        level2 = MagicMock(spec=Entity)
        level2.level3 = level3

        level1 = MagicMock(spec=Entity)
        level1.level2 = level2

        context_description = {
            "root": [{"level2": [{"level3": ["value"]}]}]
        }

        result = EmailingService.compute_context(context_description, root=level1)

        assert result["level2"]["level3"]["value"] == "deep_value"

    def test_compute_context_multiple_entities(self):
        """Test computing context with multiple entity objects."""
        from lys.apps.base.modules.emailing.services import EmailingService

        user = MagicMock(spec=Entity)
        user.name = "John Doe"

        organization = MagicMock(spec=Entity)
        organization.name = "Acme Corp"

        context_description = {
            "user": ["name"],
            "organization": ["name"]
        }

        result = EmailingService.compute_context(
            context_description,
            user=user,
            organization=organization
        )

        # Both should be in result but merged flat
        assert result["name"] in ["John Doe", "Acme Corp"]  # Last one wins

    def test_compute_context_with_none_value_for_entity_key(self, mock_entity):
        """Test that entity with None description is treated as direct value."""
        from lys.apps.base.modules.emailing.services import EmailingService

        context_description = {
            "user": None  # Description is None
        }

        # Entity with None description - since it's an Entity and description is None,
        # it should be ignored (not extracted, not passed directly)
        result = EmailingService.compute_context(context_description, user=mock_entity)

        assert "user" not in result


class TestEmailingServiceComputeContextEdgeCases:
    """Edge case tests for EmailingService.compute_context."""

    def test_compute_context_with_attribute_not_on_entity(self):
        """Test computing context when attribute doesn't exist on entity."""
        from lys.apps.base.modules.emailing.services import EmailingService

        entity = MagicMock(spec=Entity)
        entity.name = "Test"
        # 'nonexistent' attribute will raise AttributeError

        context_description = {
            "obj": ["name", "nonexistent"]
        }

        # This should raise AttributeError because MagicMock with spec
        # doesn't have 'nonexistent'
        with pytest.raises(AttributeError):
            EmailingService.compute_context(context_description, obj=entity)

    def test_compute_context_entity_attribute_is_none(self):
        """Test computing context when entity attribute is None."""
        from lys.apps.base.modules.emailing.services import EmailingService

        entity = MagicMock(spec=Entity)
        entity.name = None

        context_description = {
            "obj": ["name"]
        }

        result = EmailingService.compute_context(context_description, obj=entity)

        assert result["name"] is None

    def test_compute_context_nested_entity_is_not_entity(self):
        """Test that non-entity nested objects don't recurse."""
        from lys.apps.base.modules.emailing.services import EmailingService

        entity = MagicMock(spec=Entity)
        entity.name = "Parent"
        entity.nested = "not an entity"  # String, not Entity

        context_description = {
            "obj": ["name", {"nested": ["value"]}]
        }

        # nested is not an Entity, so it won't be processed
        result = EmailingService.compute_context(context_description, obj=entity)

        assert result["name"] == "Parent"
        assert "nested" not in result


class TestEmailingServiceGetTemplateEnv:
    """Tests for EmailingService.get_template_env method."""

    @pytest.fixture
    def mock_app_manager(self):
        """Create mock app manager with email settings."""
        app_manager = MagicMock()
        app_manager.settings.email.template_path = "/templates/email"
        return app_manager

    def test_get_template_env_creates_environment(self, mock_app_manager):
        """Test that get_template_env creates Jinja2 Environment."""
        from lys.apps.base.modules.emailing.services import EmailingService
        from jinja2 import Environment

        # Reset cached environment
        EmailingService._template_env = None

        with patch.object(EmailingService, 'app_manager', mock_app_manager):
            with patch('lys.apps.base.modules.emailing.services.Environment') as mock_env:
                with patch('lys.apps.base.modules.emailing.services.FileSystemLoader'):
                    mock_env.return_value = MagicMock(spec=Environment)
                    result = EmailingService.get_template_env()

        assert result is not None
        mock_env.assert_called_once()

    def test_get_template_env_caches_environment(self, mock_app_manager):
        """Test that template environment is cached."""
        from lys.apps.base.modules.emailing.services import EmailingService

        # Set a cached value
        cached_env = MagicMock()
        EmailingService._template_env = cached_env

        result = EmailingService.get_template_env()

        assert result is cached_env

        # Clean up
        EmailingService._template_env = None

    def test_get_template_env_uses_settings_path(self, mock_app_manager):
        """Test that template path comes from settings."""
        from lys.apps.base.modules.emailing.services import EmailingService

        EmailingService._template_env = None

        with patch.object(EmailingService, 'app_manager', mock_app_manager):
            with patch('lys.apps.base.modules.emailing.services.Environment'):
                with patch('lys.apps.base.modules.emailing.services.FileSystemLoader') as mock_loader:
                    EmailingService.get_template_env()

        # Verify FileSystemLoader was called with a path
        mock_loader.assert_called_once()

        # Clean up
        EmailingService._template_env = None


class TestEmailingServiceGenerateEmailing:
    """Tests for EmailingService.generate_emailing method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def mock_app_manager(self):
        """Create mock app manager."""
        app_manager = MagicMock()
        return app_manager

    @pytest.fixture
    def mock_emailing_type(self):
        """Create mock emailing type."""
        emailing_type = MagicMock()
        emailing_type.context_description = {"user": ["name"]}
        return emailing_type

    @pytest.mark.asyncio
    async def test_generate_emailing_creates_emailing(self, mock_session, mock_app_manager, mock_emailing_type):
        """Test that generate_emailing creates an Emailing record."""
        from lys.apps.base.modules.emailing.services import EmailingService

        mock_emailing = MagicMock()
        mock_emailing_type_service = AsyncMock()
        mock_emailing_type_service.get_by_id.return_value = mock_emailing_type

        mock_app_manager.get_service.return_value = mock_emailing_type_service

        with patch.object(EmailingService, 'app_manager', mock_app_manager):
            with patch.object(EmailingService, 'create', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_emailing

                result = await EmailingService.generate_emailing(
                    type_id="welcome_email",
                    email_address="test@example.com",
                    language_id="en",
                    session=mock_session
                )

        mock_create.assert_called_once()
        assert result is mock_emailing

    @pytest.mark.asyncio
    async def test_generate_emailing_with_none_context_description(self, mock_session, mock_app_manager):
        """Test that None context_description is handled."""
        from lys.apps.base.modules.emailing.services import EmailingService

        emailing_type = MagicMock()
        emailing_type.context_description = None

        mock_emailing_type_service = AsyncMock()
        mock_emailing_type_service.get_by_id.return_value = emailing_type

        mock_app_manager.get_service.return_value = mock_emailing_type_service

        with patch.object(EmailingService, 'app_manager', mock_app_manager):
            with patch.object(EmailingService, 'create', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock()

                await EmailingService.generate_emailing(
                    type_id="simple_email",
                    email_address="test@example.com",
                    language_id="fr",
                    session=mock_session
                )

        # Should have been called with empty context
        call_args = mock_create.call_args
        assert call_args.kwargs["context"] == {}

    @pytest.mark.asyncio
    async def test_generate_emailing_fetches_type_from_service(self, mock_session, mock_app_manager, mock_emailing_type):
        """Test that emailing type is fetched via service."""
        from lys.apps.base.modules.emailing.services import EmailingService

        mock_emailing_type_service = AsyncMock()
        mock_emailing_type_service.get_by_id.return_value = mock_emailing_type

        mock_app_manager.get_service.return_value = mock_emailing_type_service

        with patch.object(EmailingService, 'app_manager', mock_app_manager):
            with patch.object(EmailingService, 'create', new_callable=AsyncMock):
                await EmailingService.generate_emailing(
                    type_id="test_type",
                    email_address="test@example.com",
                    language_id="en",
                    session=mock_session
                )

        mock_app_manager.get_service.assert_called_with("emailing_type")
        mock_emailing_type_service.get_by_id.assert_called_with("test_type", mock_session)


class TestEmailingServiceSendEmail:
    """Tests for EmailingService.send_email method."""

    @pytest.fixture
    def mock_app_manager(self):
        """Create mock app manager with email settings."""
        app_manager = MagicMock()
        app_manager.settings.email.sender = "noreply@example.com"
        app_manager.settings.email.server = "smtp.example.com"
        app_manager.settings.email.port = 587
        app_manager.settings.email.starttls = True
        app_manager.settings.email.login = "user"
        app_manager.settings.email.password = "pass"
        return app_manager

    @pytest.fixture
    def mock_emailing(self):
        """Create mock emailing entity."""
        emailing = MagicMock()
        emailing.id = "emailing-123"
        emailing.email_address = "recipient@example.com"
        emailing.context = {"name": "Test User"}
        emailing.language_id = "en"
        emailing.type.subject = "Test Subject"
        emailing.type.template = "welcome"
        emailing.status_id = "WAITING"
        return emailing

    def test_send_email_raises_when_not_found(self, mock_app_manager):
        """Test that ValueError is raised when emailing not found."""
        from lys.apps.base.modules.emailing.services import EmailingService

        mock_session = MagicMock()
        mock_session.get.return_value = None

        mock_app_manager.database.get_sync_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_app_manager.database.get_sync_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(EmailingService, 'app_manager', mock_app_manager):
            with patch.object(EmailingService, 'get_template_env'):
                with patch.object(EmailingService, 'entity_class', MagicMock()):
                    with pytest.raises(ValueError) as exc_info:
                        EmailingService.send_email("nonexistent-123")

        assert "not found" in str(exc_info.value)

    def test_send_email_updates_status_on_smtp_error(self, mock_app_manager, mock_emailing):
        """Test that status is set to ERROR on SMTP failure."""
        from lys.apps.base.modules.emailing.services import EmailingService
        from lys.apps.base.modules.emailing.consts import ERROR_EMAILING_STATUS
        import smtplib

        mock_session = MagicMock()
        mock_session.get.return_value = mock_emailing

        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = MagicMock(return_value=mock_session)
        mock_context_manager.__exit__ = MagicMock(return_value=False)
        mock_app_manager.database.get_sync_session.return_value = mock_context_manager

        mock_template = MagicMock()
        mock_template.render.return_value = "<html>Test</html>"

        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_template

        # Create SMTP mock that raises on sendmail
        mock_smtp_instance = MagicMock()
        mock_smtp_instance.starttls = MagicMock()
        mock_smtp_instance.login = MagicMock()
        mock_smtp_instance.sendmail.side_effect = smtplib.SMTPException("Error")

        mock_smtp_context = MagicMock()
        mock_smtp_context.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_context.__exit__ = MagicMock(return_value=False)

        with patch.object(EmailingService, 'app_manager', mock_app_manager):
            with patch.object(EmailingService, 'get_template_env', return_value=mock_env):
                with patch.object(EmailingService, 'entity_class', MagicMock()):
                    with patch('lys.apps.base.modules.emailing.services.smtplib.SMTP', return_value=mock_smtp_context):
                        with pytest.raises(smtplib.SMTPException):
                            EmailingService.send_email("emailing-123")

        assert mock_emailing.status_id == ERROR_EMAILING_STATUS

    def test_send_email_sets_sent_status_on_success(self, mock_app_manager, mock_emailing):
        """Test that status is set to SENT on success."""
        from lys.apps.base.modules.emailing.services import EmailingService
        from lys.apps.base.modules.emailing.consts import SENT_EMAILING_STATUS

        mock_session = MagicMock()
        mock_session.get.return_value = mock_emailing

        mock_app_manager.database.get_sync_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_app_manager.database.get_sync_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_template = MagicMock()
        mock_template.render.return_value = "<html>Test</html>"

        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_template

        mock_smtp_instance = MagicMock()

        with patch.object(EmailingService, 'app_manager', mock_app_manager):
            with patch.object(EmailingService, 'get_template_env', return_value=mock_env):
                with patch.object(EmailingService, 'entity_class', MagicMock()):
                    with patch('lys.apps.base.modules.emailing.services.smtplib.SMTP') as mock_smtp:
                        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
                        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

                        EmailingService.send_email("emailing-123")

        assert mock_emailing.status_id == SENT_EMAILING_STATUS


class TestEmailingServiceInheritance:
    """Tests for EmailingService class structure."""

    def test_inherits_from_entity_service(self):
        """Test that EmailingService inherits from EntityService."""
        from lys.apps.base.modules.emailing.services import EmailingService
        from lys.core.services import EntityService

        assert issubclass(EmailingService, EntityService)

    def test_has_template_env_class_attribute(self):
        """Test that _template_env class attribute exists."""
        from lys.apps.base.modules.emailing.services import EmailingService

        assert hasattr(EmailingService, '_template_env')


class TestEmailingStatusService:
    """Tests for EmailingStatusService."""

    def test_inherits_from_entity_service(self):
        """Test that EmailingStatusService inherits from EntityService."""
        from lys.apps.base.modules.emailing.services import EmailingStatusService
        from lys.core.services import EntityService

        assert issubclass(EmailingStatusService, EntityService)


class TestEmailingTypeService:
    """Tests for EmailingTypeService."""

    def test_inherits_from_entity_service(self):
        """Test that EmailingTypeService inherits from EntityService."""
        from lys.apps.base.modules.emailing.services import EmailingTypeService
        from lys.core.services import EntityService

        assert issubclass(EmailingTypeService, EntityService)
