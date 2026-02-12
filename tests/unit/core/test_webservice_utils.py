"""
Unit tests for core utils webservice module.

Tests check_webservice_config and generate_webservice_fixture.
"""
import pytest

from lys.core.utils.webservice import (
    check_webservice_config,
    generate_webservice_fixture,
    PUBLIC_WEBSERVICE_CONFIG_ERROR_MESSAGE_1,
    PUBLIC_WEBSERVICE_CONFIG_ERROR_MESSAGE_2,
    CONNECTED_ACCESS_LEVEL_WEBSERVICE_CONFIG_ERROR_MESSAGE,
)
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, INTERNAL_SERVICE_ACCESS_LEVEL


class TestCheckWebserviceConfig:
    """Tests for check_webservice_config function."""

    def test_public_with_access_levels_returns_error(self):
        """Test that public webservice with access levels returns error."""
        result = check_webservice_config(
            is_public=True,
            access_levels={"CONNECTED"},
            is_licenced=False
        )
        assert result == PUBLIC_WEBSERVICE_CONFIG_ERROR_MESSAGE_1

    def test_public_with_licenced_returns_error(self):
        """Test that public webservice with licenced returns error."""
        result = check_webservice_config(
            is_public=True,
            access_levels=set(),
            is_licenced=True
        )
        assert result == PUBLIC_WEBSERVICE_CONFIG_ERROR_MESSAGE_2

    def test_connected_with_other_levels_returns_error(self):
        """Test that CONNECTED with non-INTERNAL_SERVICE levels returns error."""
        result = check_webservice_config(
            is_public=False,
            access_levels={CONNECTED_ACCESS_LEVEL, "OWNER"},
            is_licenced=False
        )
        assert result == CONNECTED_ACCESS_LEVEL_WEBSERVICE_CONFIG_ERROR_MESSAGE

    def test_connected_with_internal_service_is_valid(self):
        """Test that CONNECTED + INTERNAL_SERVICE is valid."""
        result = check_webservice_config(
            is_public=False,
            access_levels={CONNECTED_ACCESS_LEVEL, INTERNAL_SERVICE_ACCESS_LEVEL},
            is_licenced=False
        )
        assert result is None

    def test_connected_alone_is_valid(self):
        """Test that CONNECTED alone is valid."""
        result = check_webservice_config(
            is_public=False,
            access_levels={CONNECTED_ACCESS_LEVEL},
            is_licenced=False
        )
        assert result is None

    def test_valid_config_returns_none(self):
        """Test that valid non-public config returns None."""
        result = check_webservice_config(
            is_public=False,
            access_levels={"OWNER"},
            is_licenced=False
        )
        assert result is None

    def test_public_no_access_no_licence_is_valid(self):
        """Test that public webservice with no access levels and no licence is valid."""
        result = check_webservice_config(
            is_public=True,
            access_levels=set(),
            is_licenced=False
        )
        assert result is None


class TestGenerateWebserviceFixture:
    """Tests for generate_webservice_fixture function."""

    def test_invalid_config_raises_exception(self):
        """Test that invalid config raises Exception."""
        with pytest.raises(Exception, match="Wrong configuration"):
            generate_webservice_fixture(
                webservice_name="test_ws",
                enabled=True,
                is_public=True,
                access_levels=["CONNECTED"],
                is_licenced=False,
            )

    def test_disconnected_public_type(self):
        """Test that is_public='disconnected' produces uppercase public_type."""
        result = generate_webservice_fixture(
            webservice_name="test_ws",
            enabled=True,
            is_public="disconnected",
            access_levels=None,
            is_licenced=False,
        )
        assert result.attributes.public_type == "DISCONNECTED"

    def test_true_public_type(self):
        """Test that is_public=True produces NO_LIMITATION public_type."""
        from lys.core.consts.webservices import NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE
        result = generate_webservice_fixture(
            webservice_name="test_ws",
            enabled=True,
            is_public=True,
            access_levels=None,
            is_licenced=False,
        )
        assert result.attributes.public_type == NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE

    def test_false_public_type(self):
        """Test that is_public=False produces None public_type."""
        result = generate_webservice_fixture(
            webservice_name="test_ws",
            enabled=True,
            is_public=False,
            access_levels=["OWNER"],
            is_licenced=False,
        )
        assert result.attributes.public_type is None

    def test_none_access_levels_becomes_empty_set(self):
        """Test that None access_levels becomes empty list in result."""
        result = generate_webservice_fixture(
            webservice_name="test_ws",
            enabled=True,
            is_public=False,
            access_levels=None,
            is_licenced=False,
        )
        assert result.attributes.access_levels == []

    def test_fixture_has_correct_id(self):
        """Test that fixture id matches webservice_name."""
        result = generate_webservice_fixture(
            webservice_name="my_webservice",
            enabled=True,
            is_public=False,
            access_levels=["OWNER"],
            is_licenced=True,
        )
        assert result.id == "my_webservice"
        assert result.attributes.is_licenced is True
        assert result.attributes.enabled is True
