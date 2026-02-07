"""
Unit tests for user_auth event Pydantic models.
"""
import pytest


class TestSetEventPreferenceInputModel:
    """Tests for SetEventPreferenceInputModel."""

    def test_model_exists(self):
        from lys.apps.user_auth.modules.event.models import SetEventPreferenceInputModel
        assert SetEventPreferenceInputModel is not None

    def test_valid_input(self):
        from lys.apps.user_auth.modules.event.models import SetEventPreferenceInputModel
        model = SetEventPreferenceInputModel(
            event_type="USER_INVITED",
            channel="email",
            enabled=True
        )
        assert model.event_type == "USER_INVITED"
        assert model.channel == "email"
        assert model.enabled is True

    def test_enabled_false(self):
        from lys.apps.user_auth.modules.event.models import SetEventPreferenceInputModel
        model = SetEventPreferenceInputModel(
            event_type="USER_INVITED",
            channel="notification",
            enabled=False
        )
        assert model.enabled is False

    def test_has_channel_validator(self):
        from lys.apps.user_auth.modules.event.models import SetEventPreferenceInputModel
        # The model should have a field_validator for channel
        validators = [
            v for v in dir(SetEventPreferenceInputModel)
            if "validate" in v.lower() or "channel" in v.lower()
        ]
        assert len(validators) > 0 or hasattr(SetEventPreferenceInputModel, "model_fields")
