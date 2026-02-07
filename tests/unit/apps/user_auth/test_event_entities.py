"""
Unit tests for user_auth event entities.
"""
import inspect

from sqlalchemy.orm.properties import MappedColumn


class TestUserEventPreferenceEntity:
    """Tests for UserEventPreference entity."""

    def test_entity_exists(self):
        from lys.apps.user_auth.modules.event.entities import UserEventPreference
        assert UserEventPreference is not None

    def test_tablename(self):
        from lys.apps.user_auth.modules.event.entities import UserEventPreference
        assert UserEventPreference.__tablename__ == "user_event_preference"

    def test_inherits_from_entity(self):
        from lys.apps.user_auth.modules.event.entities import UserEventPreference
        from lys.core.entities import Entity
        assert issubclass(UserEventPreference, Entity)

    def test_has_user_id_column(self):
        from lys.apps.user_auth.modules.event.entities import UserEventPreference
        attr = inspect.getattr_static(UserEventPreference, "user_id")
        assert isinstance(attr, MappedColumn)

    def test_has_event_type_column(self):
        from lys.apps.user_auth.modules.event.entities import UserEventPreference
        attr = inspect.getattr_static(UserEventPreference, "event_type")
        assert isinstance(attr, MappedColumn)

    def test_has_channel_column(self):
        from lys.apps.user_auth.modules.event.entities import UserEventPreference
        attr = inspect.getattr_static(UserEventPreference, "channel")
        assert isinstance(attr, MappedColumn)

    def test_has_enabled_column(self):
        from lys.apps.user_auth.modules.event.entities import UserEventPreference
        attr = inspect.getattr_static(UserEventPreference, "enabled")
        assert isinstance(attr, MappedColumn)

    def test_has_accessing_users_method(self):
        from lys.apps.user_auth.modules.event.entities import UserEventPreference
        assert hasattr(UserEventPreference, "accessing_users")

    def test_has_accessing_organizations_method(self):
        from lys.apps.user_auth.modules.event.entities import UserEventPreference
        assert hasattr(UserEventPreference, "accessing_organizations")
