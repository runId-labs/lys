from datetime import datetime

from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship, backref

from lys.apps.base.modules.one_time_token.entities import OneTimeToken
from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS
from lys.apps.user_auth.utils import AuthUtils
from lys.core.abstracts.email_address import AbstractEmailAddress
from lys.core.entities import ParametricEntity, Entity
from lys.core.registers import register_entity


@register_entity()
class UserStatus(ParametricEntity):
    """
    User status entity
    """
    __tablename__ = "user_status"


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
        DateTime,
        comment="define when the token will be expired",
        nullable=True
    )

    connection_expire_at: Mapped[datetime] = mapped_column(
        DateTime,
        comment="define when the connection will be expired"
    )

    revoked_at: Mapped[datetime] = mapped_column(
        DateTime,
        comment="define when the token has been revoked",
        nullable=True
    )

    used_at: Mapped[datetime] = mapped_column(
        DateTime,
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
        now = datetime.now()

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
        return stmt, [cls.user.id == user_id]


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