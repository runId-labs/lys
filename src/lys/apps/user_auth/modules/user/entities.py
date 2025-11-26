from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship, backref

from lys.apps.base.modules.one_time_token.entities import OneTimeToken
from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS
from lys.apps.user_auth.utils import AuthUtils
from lys.core.abstracts.email_address import AbstractEmailAddress
from lys.core.entities import ParametricEntity, Entity
from lys.core.registries import register_entity
from lys.core.utils.datetime import now_utc


@register_entity()
class UserStatus(ParametricEntity):
    """
    User status entity
    """
    __tablename__ = "user_status"


@register_entity()
class Gender(ParametricEntity):
    """
    Gender parametric entity for GDPR-protected user data
    """
    __tablename__ = "gender"


@register_entity()
class UserAuditLogType(ParametricEntity):
    """
    User audit log type entity.

    Types:
    - STATUS_CHANGE: Automatic log when user status changes
    - ANONYMIZATION: Automatic log when user is anonymized (GDPR)
    - OBSERVATION: Manual observation/note added by administrators
    """
    __tablename__ = "user_audit_log_type"


@register_entity()
class UserEmailAddress(AbstractEmailAddress):
    __tablename__ = "user_email_address"

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete='CASCADE'))

    def accessing_users(self):
        return []

    def accessing_organizations(self):
        return {}


@register_entity()
class User(Entity):
    """
    User entity
    """
    __tablename__ = "user"

    password: Mapped[str] = mapped_column(nullable=True)
    is_super_user: Mapped[bool] = mapped_column(nullable=False, default=False)
    status_id: Mapped[str] = mapped_column(ForeignKey("user_status.id"), default=ENABLED_USER_STATUS)
    language_id: Mapped[str] = mapped_column(ForeignKey("language.id"), nullable=False)

    @declared_attr
    def email_address(self):
        return relationship(
            "user_email_address",
            # create inverse function
            backref="user",
            # one-to-one,
            uselist=False,
            lazy='selectin'
        )

    @declared_attr
    def status(self):
        return relationship("user_status", lazy='selectin')

    @declared_attr
    def language(self):
        return relationship("language", lazy='selectin')

    @declared_attr
    def private_data(self):
        return relationship(
            "user_private_data",
            back_populates="user",
            uselist=False,
            lazy='selectin'
        )

    @staticmethod
    def login_name() -> str:
        """
        login attribute is based on the email address by default (overwrite if needed)
        :return:
        """
        return "email_address"

    def accessing_users(self):
        return [self]

    def accessing_organizations(self):
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id: str):
        return stmt, [cls.id == user_id]


@register_entity()
class UserPrivateData(Entity):
    """
    GDPR-protected user private data.

    This entity stores sensitive personal information separately from the User entity
    to facilitate GDPR compliance (right to be forgotten, data minimization, etc.).

    Personal data stored here:
    - first_name: User's first name
    - last_name: User's last name
    - gender_id: User's gender reference

    GDPR features:
    - anonymized_at: Timestamp when data was anonymized (right to be forgotten)
    - Separate table allows selective data retrieval (data minimization)
    - Easy to delete/anonymize without affecting user account
    """
    __tablename__ = "user_private_data"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user.id", ondelete='CASCADE'),
        unique=True,
        comment="One-to-one relationship with User"
    )

    first_name: Mapped[str] = mapped_column(nullable=True, comment="User's first name")
    last_name: Mapped[str] = mapped_column(nullable=True, comment="User's last name")
    gender_id: Mapped[str] = mapped_column(ForeignKey("gender.id"), nullable=True, comment="User's gender")

    anonymized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when private data was anonymized (GDPR right to be forgotten)"
    )

    @declared_attr
    def user(self):
        return relationship("user", back_populates="private_data", lazy='selectin')

    @declared_attr
    def gender(self):
        return relationship("gender", lazy='selectin')

    def accessing_users(self):
        """
        Only the user themselves can access their private data.
        Super users can access via permission check in the node/webservice.
        """
        return [self.user] if self.user else []

    def accessing_organizations(self):
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id: str):
        """
        Filter to show only the user's own private data.
        """
        return stmt, [cls.user_id == user_id]


@register_entity()
class UserRefreshToken(Entity):
    """
        generate after authentication, the refresh token allow to find out the connected user
    """
    __tablename__ = "user_refresh_token"

    auth_utils = AuthUtils()

    ####################################################################################################################
    #                                                      COLUMN
    ####################################################################################################################

    once_expire_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment="define when the token will be expired",
        nullable=True
    )

    connection_expire_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment="define when the connection will be expired"
    )

    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment="define when the token has been revoked",
        nullable=True
    )

    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment="define the last time when the token has been used",
        nullable=True
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete='CASCADE'))

    @declared_attr
    def user(self):
        return relationship("user", lazy="selectin")

    @property
    def enabled(self):
        """
        refresh token is enabled if:
            - the refresh token is not revoked
            - the refresh token is not expired
            - it is defined, the short term is not expired
            - the refresh token can be used multiple times else it is not used
        :return:
        """
        now = now_utc()

        return self.revoked_at is None and \
            now < self.connection_expire_at and \
            (self.once_expire_at is None or now < self.once_expire_at) and \
            (not self.auth_utils.config.get("refresh_token_used_once") or not self.used_at)

    def accessing_users(self):
        return []

    def accessing_organizations(self):
        return {}


@register_entity()
class UserEmailing(Entity):
    __tablename__ = "user_emailing"

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete='CASCADE'))

    @declared_attr
    def user(self):
        return relationship("user", lazy='selectin')

    emailing_id: Mapped[str] = mapped_column(ForeignKey("emailing.id", ondelete='CASCADE'))

    @declared_attr
    def emailing(self):
        return relationship(
            "emailing",
            lazy='selectin',
            backref=backref("user_emailing", uselist=False),
            enable_typechecks = False
        )

    def accessing_users(self):
        return [self.user]

    def accessing_organizations(self):
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id: str):
        return stmt, [cls.user_id == user_id]


@register_entity()
class UserOneTimeToken(OneTimeToken):
    """
    One-time token associated with a user.

    Used for password reset, email verification, etc.
    """
    __tablename__ = "user_one_time_token"

    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete='CASCADE'))

    @declared_attr
    def user(self):
        return relationship("user", lazy='selectin')

    def accessing_users(self):
        return [self.user]

    def accessing_organizations(self):
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id: str):
        return stmt, [cls.user_id == user_id]


@register_entity()
class UserAuditLog(Entity):
    """
    User audit log entity for tracking user-related actions and observations.

    This entity provides a comprehensive audit trail for:
    - Automatic logging of status changes (STATUS_CHANGE)
    - Automatic logging of user anonymization (ANONYMIZATION)
    - Manual observations/notes from administrators (OBSERVATION)

    Features:
    - Soft delete support (deleted_at) for OBSERVATION type logs
    - Only OBSERVATION logs can be modified (by owner) or deleted
    - STATUS_CHANGE and ANONYMIZATION logs are immutable for audit integrity
    - Full traceability with target user, author, and timestamps
    """
    __tablename__ = "user_audit_log"

    target_user_id: Mapped[str] = mapped_column(
        ForeignKey("user.id", ondelete='CASCADE'),
        comment="User being observed or acted upon"
    )

    author_user_id: Mapped[str] = mapped_column(
        ForeignKey("user.id", ondelete='CASCADE'),
        comment="User who created this log entry"
    )

    log_type_id: Mapped[str] = mapped_column(
        ForeignKey("user_audit_log_type.id"),
        nullable=False,
        comment="Type of log: STATUS_CHANGE, ANONYMIZATION, or OBSERVATION"
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Log message or observation (supports up to 1000 words)"
    )

    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft delete timestamp (only for OBSERVATION type)"
    )

    @declared_attr
    def target_user(self):
        return relationship(
            "user",
            foreign_keys=[self.target_user_id],
            lazy='selectin'
        )

    @declared_attr
    def author_user(self):
        return relationship(
            "user",
            foreign_keys=[self.author_user_id],
            lazy='selectin'
        )

    @declared_attr
    def log_type(self):
        return relationship("user_audit_log_type", lazy='selectin')

    def accessing_users(self):
        """
        Returns the author user to enable OWNER access level.
        Super users and users with USER_ADMIN role can access via webservice permissions.
        """
        return [self.author_user] if self.author_user else []

    def accessing_organizations(self):
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id: str):
        """
        Filter audit logs to only show logs authored by the user.
        This enables OWNER access level to work correctly.
        """
        return stmt, [cls.author_user_id == user_id]