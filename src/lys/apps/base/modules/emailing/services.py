import json
import logging
import pathlib
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Callable

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.base.mixins.recipient_resolution import RecipientResolutionMixin
from lys.apps.base.modules.emailing.consts import SENT_EMAILING_STATUS, ERROR_EMAILING_STATUS
from lys.apps.base.modules.emailing.entities import Emailing, EmailingType, EmailingStatus
from lys.core.entities import Entity
from lys.core.registries import register_service
from lys.core.services import Service, EntityService

logger = logging.getLogger(__name__)


@register_service()
class EmailingStatusService(EntityService[EmailingStatus]):
    pass


@register_service()
class EmailingTypeService(EntityService[EmailingType]):
    pass


@register_service()
class EmailingService(EntityService[Emailing]):
    _template_env = None
    _translations_cache: dict[str, dict] = {}

    @classmethod
    def get_template_env(cls) -> Environment:
        """
        Get or create the Jinja2 template environment.
        Loads templates from the configured template path in application settings.

        Cached to avoid recreating on every email send.
        """
        if cls._template_env is None:
            email_settings = cls.app_manager.settings.email

            # Application templates path (configured in settings)
            app_template_path = pathlib.Path().resolve() / email_settings.template_path.lstrip('/')

            cls._template_env = Environment(
                loader=FileSystemLoader(str(app_template_path))
            )
        return cls._template_env

    @classmethod
    def get_translations(cls, language_id: str) -> dict:
        """
        Load translations for a specific language from translations.json.

        Args:
            language_id: The language ID (e.g., "fr", "en")

        Returns:
            Dictionary of translations, or empty dict if file not found
        """
        if language_id in cls._translations_cache:
            return cls._translations_cache[language_id]

        email_settings = cls.app_manager.settings.email
        app_template_path = pathlib.Path().resolve() / email_settings.template_path.lstrip('/')
        translations_path = app_template_path / language_id / "translations.json"

        translations = {}
        if translations_path.exists():
            try:
                with open(translations_path, "r", encoding="utf-8") as f:
                    translations = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load translations from {translations_path}: {e}")

        cls._translations_cache[language_id] = translations
        return translations

    @classmethod
    def get_subject(cls, template_name: str, language_id: str, fallback_subject: str) -> str:
        """
        Get the translated subject for an email template.

        Args:
            template_name: The template name (e.g., "user_password_reset")
            language_id: The language ID (e.g., "fr", "en")
            fallback_subject: Fallback subject if translation not found

        Returns:
            The translated subject or fallback
        """
        translations = cls.get_translations(language_id)
        template_translations = translations.get(template_name, {})
        return template_translations.get("subject", fallback_subject)

    @staticmethod
    def compute_context(context_description: dict, **kwargs):
        def _compute_context(_context: dict, _obj_description: list, _obj: Entity):
            for _key in _obj_description:
                if isinstance(_key, str):
                    _context[_key] = getattr(_obj, _key)
                elif isinstance(_key, dict):
                    for sub_key, sub_description in _key.items():
                        sub_obj = getattr(_obj, sub_key)
                        if isinstance(sub_obj, Entity):
                            _context[sub_key] = {}
                            _compute_context(_context[sub_key], sub_description, sub_obj)

        context = {}

        for key, obj_description in context_description.items():
            obj = kwargs.get(key)

            if isinstance(obj, Entity) and obj_description is not None:
                _compute_context(context, obj_description, obj)
            elif isinstance(obj, str) or isinstance(obj, int) or isinstance(obj, float):
                context[key] = obj

        return context

    @classmethod
    async def generate_emailing(
            cls,
            type_id: str,
            email_address: str,
            language_id: str,
            session: AsyncSession,
            **kwargs
    ) -> Emailing:
        """
        Generate an emailing record.

        Args:
            type_id: The emailing type ID
            email_address: The recipient email address
            language_id: The language ID for the email
            session: Database session
            **kwargs: Additional context data for the email template

        Returns:
            The created Emailing entity
        """
        emailing_type_service: EntityService[EmailingType] = cls.app_manager.get_service("emailing_type")

        emailing_type: EmailingType | None = await emailing_type_service.get_by_id(type_id, session)

        context_description = emailing_type.context_description

        if context_description is None:
            context_description = {}

        new_emailing: Emailing = await cls.create(
            session,
            email_address=email_address,
            context=cls.compute_context(context_description, **kwargs),
            type_id=type_id,
            language_id=language_id
        )

        return new_emailing

    @classmethod
    def send_email(cls, emailing_id: str) -> None:
        """
        Send an email by its ID.

        Args:
            emailing_id: The ID of the emailing record to send

        Raises:
            ValueError: If emailing with given ID does not exist
        """
        email_settings = cls.app_manager.settings.email
        template_env = cls.get_template_env()

        with cls.app_manager.database.get_sync_session() as session:
            emailing = session.get(cls.entity_class, emailing_id)

            if emailing is None:
                error_msg = f"Emailing with id {emailing_id} not found"
                logger.error(error_msg)
                raise ValueError(error_msg)

            try:
                # Create email message
                message = MIMEMultipart("alternative")
                message["From"] = email_settings.sender
                message["To"] = emailing.email_address

                # Get translated subject (fallback to type.subject if not found)
                subject = cls.get_subject(
                    emailing.type.template,
                    emailing.language_id,
                    emailing.type.subject
                )
                message["Subject"] = subject

                # Render HTML template using the emailing's language
                template = template_env.get_template(f"{emailing.language_id}/{emailing.type.template}.html")
                html_content = template.render(**emailing.context)

                # Attach HTML version
                message.attach(MIMEText(html_content, "html"))

                # Send email via SMTP
                with smtplib.SMTP(
                        host=email_settings.server,
                        port=email_settings.port,
                ) as server:
                    if email_settings.starttls:
                        server.starttls()
                    if email_settings.login:
                        server.login(email_settings.login, email_settings.password)

                    server.sendmail(
                        email_settings.sender,
                        emailing.email_address,
                        message.as_string()
                    )

                # Mark as sent
                emailing.status_id = SENT_EMAILING_STATUS
                logger.info(f"Email {emailing_id} sent successfully to {emailing.email_address}")

            except smtplib.SMTPException as ex:
                # SMTP-specific errors
                emailing.status_id = ERROR_EMAILING_STATUS
                emailing.error = str(ex)
                logger.error(f"SMTP error sending email {emailing_id}: {ex}")
                raise

            except Exception as ex:
                # Other errors (template rendering, etc.)
                emailing.status_id = ERROR_EMAILING_STATUS
                emailing.error = str(ex)
                logger.error(f"Error sending email {emailing_id}: {ex}")
                raise


@register_service()
class EmailingBatchService(RecipientResolutionMixin, Service):
    """
    Service for dispatching emails to multiple recipients based on role/org resolution.

    Follows the same mixin override chain as NotificationBatchService:
    - RecipientResolutionMixin: triggered_by + additional_user_ids
    - RoleRecipientResolutionMixin (user_role app): + role-based
    - OrganizationRecipientResolutionMixin (organization app): + org-scoped

    Unlike NotificationBatchService, there is no EmailingBatch entity.
    Each resolved recipient gets their own Emailing record.

    Critical emails (password reset, email verification, invitation) are NOT
    handled here — they use the pre-created emailing_id path in trigger_event.
    """
    service_name = "emailing_batch"

    @classmethod
    async def dispatch(
        cls,
        session: AsyncSession,
        type_id: str,
        email_context: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> List[str]:
        """
        Create and send emails to all resolved recipients.

        Args:
            session: Async database session
            type_id: EmailingType ID (e.g., "LICENSE_GRANTED")
            email_context: Context data for the email template
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to email
            should_send_fn: Optional callback to filter recipients by user preference.
                            Signature: (user_id: str) -> bool

        Returns:
            List of created Emailing IDs

        Raises:
            ValueError: If EmailingType not found
        """
        # Fetch EmailingType
        emailing_type = await session.get(
            cls.app_manager.get_entity("emailing_type"),
            type_id
        )
        if not emailing_type:
            raise ValueError(f"EmailingType '{type_id}' not found")

        # Resolve recipients via mixin
        recipient_user_ids = await cls._resolve_recipients(
            app_manager=cls.app_manager,
            session=session,
            type_entity=emailing_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
        )

        # Create and send emails
        return await cls._create_and_send_emails(
            session=session,
            type_id=type_id,
            email_context=email_context,
            recipient_user_ids=recipient_user_ids,
            should_send_fn=should_send_fn,
        )

    @classmethod
    async def _create_and_send_emails(
        cls,
        session: AsyncSession,
        type_id: str,
        email_context: dict | None,
        recipient_user_ids: List[str],
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> List[str]:
        """
        Create Emailing records and send emails for each recipient.

        Args:
            session: Async database session
            type_id: EmailingType ID
            email_context: Context data for the email template
            recipient_user_ids: Resolved list of user IDs
            should_send_fn: Optional callback to filter recipients

        Returns:
            List of created Emailing IDs
        """
        user_entity = cls.app_manager.get_entity("user")
        emailing_service = cls.app_manager.get_service("emailing")
        created_ids = []

        for user_id in recipient_user_ids:
            if should_send_fn is not None and not should_send_fn(user_id):
                continue

            user = await session.get(user_entity, user_id)
            if not user or not hasattr(user, "email_address") or not user.email_address:
                logger.warning(f"EmailingBatch: user {user_id} not found or has no email, skipping")
                continue

            # Enrich context with per-recipient user data
            recipient_context = dict(email_context or {})
            if hasattr(user, "private_data") and user.private_data:
                recipient_context["private_data"] = {
                    "first_name": user.private_data.first_name,
                    "last_name": user.private_data.last_name,
                }

            emailing = await emailing_service.create(
                session,
                email_address=user.email_address.id,
                type_id=type_id,
                language_id=user.language_id or "fr",
                context=recipient_context,
            )

            emailing_service.send_email(str(emailing.id))
            created_ids.append(str(emailing.id))

        return created_ids

    @classmethod
    def dispatch_sync(
        cls,
        session: Session,
        type_id: str,
        email_context: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> List[str]:
        """
        Synchronous version of dispatch for use in Celery tasks.

        Args:
            session: Sync database session
            type_id: EmailingType ID (e.g., "LICENSE_GRANTED")
            email_context: Context data for the email template
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to email
            should_send_fn: Optional callback to filter recipients by user preference.
                            Signature: (user_id: str) -> bool

        Returns:
            List of created Emailing IDs

        Raises:
            ValueError: If EmailingType not found
        """
        # Fetch EmailingType
        emailing_type = session.get(
            cls.app_manager.get_entity("emailing_type"),
            type_id
        )
        if not emailing_type:
            raise ValueError(f"EmailingType '{type_id}' not found")

        # Resolve recipients via mixin
        recipient_user_ids = cls._resolve_recipients_sync(
            app_manager=cls.app_manager,
            session=session,
            type_entity=emailing_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
        )

        # Create and send emails
        return cls._create_and_send_emails_sync(
            session=session,
            type_id=type_id,
            email_context=email_context,
            recipient_user_ids=recipient_user_ids,
            should_send_fn=should_send_fn,
        )

    @classmethod
    def _create_and_send_emails_sync(
        cls,
        session: Session,
        type_id: str,
        email_context: dict | None,
        recipient_user_ids: List[str],
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> List[str]:
        """
        Synchronous version of email creation and sending.

        Args:
            session: Sync database session
            type_id: EmailingType ID
            email_context: Context data for the email template
            recipient_user_ids: Resolved list of user IDs
            should_send_fn: Optional callback to filter recipients

        Returns:
            List of created Emailing IDs
        """
        user_entity = cls.app_manager.get_entity("user")
        emailing_service = cls.app_manager.get_service("emailing")
        created_ids = []

        for user_id in recipient_user_ids:
            if should_send_fn is not None and not should_send_fn(user_id):
                continue

            user = session.get(user_entity, user_id)
            if not user or not hasattr(user, "email_address") or not user.email_address:
                logger.warning(f"EmailingBatch: user {user_id} not found or has no email, skipping")
                continue

            # Enrich context with per-recipient user data
            recipient_context = dict(email_context or {})
            if hasattr(user, "private_data") and user.private_data:
                recipient_context["private_data"] = {
                    "first_name": user.private_data.first_name,
                    "last_name": user.private_data.last_name,
                }

            emailing = emailing_service.entity_class(
                email_address=user.email_address.id,
                type_id=type_id,
                language_id=user.language_id or "fr",
                context=recipient_context,
            )
            session.add(emailing)
            session.flush()

            emailing_service.send_email(str(emailing.id))
            created_ids.append(str(emailing.id))

        return created_ids
