"""
Unit tests for SSO module nodes.
"""
from lys.apps.sso.modules.sso_link.nodes import (
    UserSSOLinkNode,
    SSOProviderNode,
    SSOProvidersNode,
    UserSSOLinksNode,
    SSOSessionNode,
)


class TestUserSSOLinkNode:
    def test_exists(self):
        assert UserSSOLinkNode is not None

    def test_has_provider_field(self):
        assert "provider" in UserSSOLinkNode.__annotations__

    def test_has_external_email_field(self):
        assert "external_email" in UserSSOLinkNode.__annotations__

    def test_has_linked_at_field(self):
        assert "linked_at" in UserSSOLinkNode.__annotations__

    def test_has_user_id_method(self):
        assert hasattr(UserSSOLinkNode, "user_id")


class TestSSOProviderNode:
    def test_exists(self):
        assert SSOProviderNode is not None

    def test_has_provider_id_field(self):
        assert "provider_id" in SSOProviderNode.__annotations__

    def test_has_name_field(self):
        assert "name" in SSOProviderNode.__annotations__

    def test_has_login_url_field(self):
        assert "login_url" in SSOProviderNode.__annotations__


class TestSSOProvidersNode:
    def test_exists(self):
        assert SSOProvidersNode is not None

    def test_has_providers_field(self):
        assert "providers" in SSOProvidersNode.__annotations__


class TestUserSSOLinksNode:
    def test_exists(self):
        assert UserSSOLinksNode is not None

    def test_has_links_field(self):
        assert "links" in UserSSOLinksNode.__annotations__


class TestSSOSessionNode:
    def test_exists(self):
        assert SSOSessionNode is not None

    def test_has_email_field(self):
        assert "email" in SSOSessionNode.__annotations__

    def test_has_first_name_field(self):
        assert "first_name" in SSOSessionNode.__annotations__

    def test_has_last_name_field(self):
        assert "last_name" in SSOSessionNode.__annotations__

    def test_has_provider_field(self):
        assert "provider" in SSOSessionNode.__annotations__
