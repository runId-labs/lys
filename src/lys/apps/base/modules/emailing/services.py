import pathlib
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.emailing.consts import SENT_EMAILING_STATUS, ERROR_EMAILING_STATUS
from lys.apps.base.modules.emailing.entities import Emailing, EmailingType, EmailingStatus
from lys.core.entities import Entity
from lys.core.registries import register_service
from lys.core.services import EntityService

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
                message["Subject"] = emailing.type.subject

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
