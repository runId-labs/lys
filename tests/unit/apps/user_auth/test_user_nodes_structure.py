"""
Unit tests for user_auth user module node classes.

Tests class existence, strawberry type definitions, field presence,
and async method structure for all GraphQL node classes without
requiring a database or external services.
"""

import inspect


def _is_async_strawberry_field(cls, field_name):
    """
    Check if a strawberry field on a class has an async resolver.

    Strawberry's @strawberry.field decorator converts async methods into
    StrawberryField descriptors. The original async function is stored in
    the descriptor's base_resolver.wrapped_func attribute.

    Args:
        cls: The class containing the strawberry field.
        field_name: The name of the field to check.

    Returns:
        True if the field has an async resolver, False otherwise.
    """
    attr = cls.__dict__.get(field_name)
    if attr is None:
        return False
    if hasattr(attr, "base_resolver") and attr.base_resolver is not None:
        return inspect.iscoroutinefunction(attr.base_resolver.wrapped_func)
    return inspect.iscoroutinefunction(attr)


class TestUserStatusNodeStructure:
    """Tests for UserStatusNode class existence."""

    def test_class_exists(self):
        """Test UserStatusNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import UserStatusNode
        assert UserStatusNode is not None


class TestGenderNodeStructure:
    """Tests for GenderNode class existence."""

    def test_class_exists(self):
        """Test GenderNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import GenderNode
        assert GenderNode is not None


class TestUserAuditLogTypeNodeStructure:
    """Tests for UserAuditLogTypeNode class existence."""

    def test_class_exists(self):
        """Test UserAuditLogTypeNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogTypeNode
        assert UserAuditLogTypeNode is not None


class TestUserEmailAddressNodeStructure:
    """Tests for UserEmailAddressNode class existence and strawberry type definition."""

    def test_class_exists(self):
        """Test UserEmailAddressNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import UserEmailAddressNode
        assert UserEmailAddressNode is not None

    def test_has_strawberry_type_definition(self):
        """Test UserEmailAddressNode has a strawberry type definition."""
        from lys.apps.user_auth.modules.user.nodes import UserEmailAddressNode
        assert hasattr(UserEmailAddressNode, "__strawberry_definition__")

    def test_has_id_field(self):
        """Test UserEmailAddressNode has id annotation."""
        from lys.apps.user_auth.modules.user.nodes import UserEmailAddressNode
        assert "id" in UserEmailAddressNode.__annotations__

    def test_has_address_field(self):
        """Test UserEmailAddressNode has address annotation."""
        from lys.apps.user_auth.modules.user.nodes import UserEmailAddressNode
        assert "address" in UserEmailAddressNode.__annotations__


class TestUserNodeStructure:
    """Tests for UserNode class existence, strawberry type, and async field resolvers."""

    def test_class_exists(self):
        """Test UserNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert UserNode is not None

    def test_has_strawberry_type_definition(self):
        """Test UserNode has a strawberry type definition."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert hasattr(UserNode, "__strawberry_definition__")

    def test_has_email_address_field(self):
        """Test UserNode has email_address field."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert hasattr(UserNode, "email_address")

    def test_email_address_is_async(self):
        """Test UserNode.email_address has an async resolver."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert _is_async_strawberry_field(UserNode, "email_address")

    def test_has_status_field(self):
        """Test UserNode has status field."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert hasattr(UserNode, "status")

    def test_status_is_async(self):
        """Test UserNode.status has an async resolver."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert _is_async_strawberry_field(UserNode, "status")

    def test_has_language_field(self):
        """Test UserNode has language field."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert hasattr(UserNode, "language")

    def test_language_is_async(self):
        """Test UserNode.language has an async resolver."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert _is_async_strawberry_field(UserNode, "language")

    def test_has_private_data_field(self):
        """Test UserNode has private_data field."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert hasattr(UserNode, "private_data")

    def test_private_data_is_async(self):
        """Test UserNode.private_data has an async resolver."""
        from lys.apps.user_auth.modules.user.nodes import UserNode
        assert _is_async_strawberry_field(UserNode, "private_data")


class TestUserPrivateDataNodeStructure:
    """Tests for UserPrivateDataNode class existence and async gender field."""

    def test_class_exists(self):
        """Test UserPrivateDataNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import UserPrivateDataNode
        assert UserPrivateDataNode is not None

    def test_has_strawberry_type_definition(self):
        """Test UserPrivateDataNode has a strawberry type definition."""
        from lys.apps.user_auth.modules.user.nodes import UserPrivateDataNode
        assert hasattr(UserPrivateDataNode, "__strawberry_definition__")

    def test_has_gender_field(self):
        """Test UserPrivateDataNode has gender field."""
        from lys.apps.user_auth.modules.user.nodes import UserPrivateDataNode
        assert hasattr(UserPrivateDataNode, "gender")

    def test_gender_is_async(self):
        """Test UserPrivateDataNode.gender has an async resolver."""
        from lys.apps.user_auth.modules.user.nodes import UserPrivateDataNode
        assert _is_async_strawberry_field(UserPrivateDataNode, "gender")


class TestUserOneTimeTokenNodeStructure:
    """Tests for UserOneTimeTokenNode class existence and async user field."""

    def test_class_exists(self):
        """Test UserOneTimeTokenNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import UserOneTimeTokenNode
        assert UserOneTimeTokenNode is not None

    def test_has_strawberry_type_definition(self):
        """Test UserOneTimeTokenNode has a strawberry type definition."""
        from lys.apps.user_auth.modules.user.nodes import UserOneTimeTokenNode
        assert hasattr(UserOneTimeTokenNode, "__strawberry_definition__")

    def test_has_user_field(self):
        """Test UserOneTimeTokenNode has user field."""
        from lys.apps.user_auth.modules.user.nodes import UserOneTimeTokenNode
        assert hasattr(UserOneTimeTokenNode, "user")

    def test_user_is_async(self):
        """Test UserOneTimeTokenNode.user has an async resolver."""
        from lys.apps.user_auth.modules.user.nodes import UserOneTimeTokenNode
        assert _is_async_strawberry_field(UserOneTimeTokenNode, "user")


class TestPasswordResetRequestNodeStructure:
    """Tests for PasswordResetRequestNode class existence and fields."""

    def test_class_exists(self):
        """Test PasswordResetRequestNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import PasswordResetRequestNode
        assert PasswordResetRequestNode is not None

    def test_has_success_annotation(self):
        """Test PasswordResetRequestNode has success field annotation."""
        from lys.apps.user_auth.modules.user.nodes import PasswordResetRequestNode
        assert "success" in PasswordResetRequestNode.__annotations__

    def test_has_message_annotation(self):
        """Test PasswordResetRequestNode has message field annotation."""
        from lys.apps.user_auth.modules.user.nodes import PasswordResetRequestNode
        assert "message" in PasswordResetRequestNode.__annotations__


class TestResetPasswordNodeStructure:
    """Tests for ResetPasswordNode class existence."""

    def test_class_exists(self):
        """Test ResetPasswordNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import ResetPasswordNode
        assert ResetPasswordNode is not None

    def test_has_success_annotation(self):
        """Test ResetPasswordNode has success field annotation."""
        from lys.apps.user_auth.modules.user.nodes import ResetPasswordNode
        assert "success" in ResetPasswordNode.__annotations__


class TestVerifyEmailNodeStructure:
    """Tests for VerifyEmailNode class existence."""

    def test_class_exists(self):
        """Test VerifyEmailNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import VerifyEmailNode
        assert VerifyEmailNode is not None

    def test_has_success_annotation(self):
        """Test VerifyEmailNode has success field annotation."""
        from lys.apps.user_auth.modules.user.nodes import VerifyEmailNode
        assert "success" in VerifyEmailNode.__annotations__


class TestActivateUserNodeStructure:
    """Tests for ActivateUserNode class existence."""

    def test_class_exists(self):
        """Test ActivateUserNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import ActivateUserNode
        assert ActivateUserNode is not None

    def test_has_success_annotation(self):
        """Test ActivateUserNode has success field annotation."""
        from lys.apps.user_auth.modules.user.nodes import ActivateUserNode
        assert "success" in ActivateUserNode.__annotations__


class TestAnonymizeUserNodeStructure:
    """Tests for AnonymizeUserNode class existence."""

    def test_class_exists(self):
        """Test AnonymizeUserNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import AnonymizeUserNode
        assert AnonymizeUserNode is not None

    def test_has_success_annotation(self):
        """Test AnonymizeUserNode has success field annotation."""
        from lys.apps.user_auth.modules.user.nodes import AnonymizeUserNode
        assert "success" in AnonymizeUserNode.__annotations__


class TestConnectedUserSessionNodeStructure:
    """Tests for ConnectedUserSessionNode class existence and fields."""

    def test_class_exists(self):
        """Test ConnectedUserSessionNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import ConnectedUserSessionNode
        assert ConnectedUserSessionNode is not None

    def test_has_access_token_expire_in_annotation(self):
        """Test ConnectedUserSessionNode has access_token_expire_in field annotation."""
        from lys.apps.user_auth.modules.user.nodes import ConnectedUserSessionNode
        assert "access_token_expire_in" in ConnectedUserSessionNode.__annotations__

    def test_has_xsrf_token_annotation(self):
        """Test ConnectedUserSessionNode has xsrf_token field annotation."""
        from lys.apps.user_auth.modules.user.nodes import ConnectedUserSessionNode
        assert "xsrf_token" in ConnectedUserSessionNode.__annotations__

    def test_has_success_annotation(self):
        """Test ConnectedUserSessionNode has success field annotation."""
        from lys.apps.user_auth.modules.user.nodes import ConnectedUserSessionNode
        assert "success" in ConnectedUserSessionNode.__annotations__


class TestUserAuditLogNodeStructure:
    """Tests for UserAuditLogNode class existence and async relation fields."""

    def test_class_exists(self):
        """Test UserAuditLogNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogNode
        assert UserAuditLogNode is not None

    def test_has_strawberry_type_definition(self):
        """Test UserAuditLogNode has a strawberry type definition."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogNode
        assert hasattr(UserAuditLogNode, "__strawberry_definition__")

    def test_has_target_user_field(self):
        """Test UserAuditLogNode has target_user field."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogNode
        assert hasattr(UserAuditLogNode, "target_user")

    def test_target_user_is_async(self):
        """Test UserAuditLogNode.target_user has an async resolver."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogNode
        assert _is_async_strawberry_field(UserAuditLogNode, "target_user")

    def test_has_author_user_field(self):
        """Test UserAuditLogNode has author_user field."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogNode
        assert hasattr(UserAuditLogNode, "author_user")

    def test_author_user_is_async(self):
        """Test UserAuditLogNode.author_user has an async resolver."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogNode
        assert _is_async_strawberry_field(UserAuditLogNode, "author_user")

    def test_has_log_type_field(self):
        """Test UserAuditLogNode has log_type field."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogNode
        assert hasattr(UserAuditLogNode, "log_type")

    def test_log_type_is_async(self):
        """Test UserAuditLogNode.log_type has an async resolver."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogNode
        assert _is_async_strawberry_field(UserAuditLogNode, "log_type")

    def test_has_message_annotation(self):
        """Test UserAuditLogNode has message field annotation."""
        from lys.apps.user_auth.modules.user.nodes import UserAuditLogNode
        assert "message" in UserAuditLogNode.__annotations__


class TestDeleteUserObservationNodeStructure:
    """Tests for DeleteUserObservationNode class existence and from_obj classmethod."""

    def test_class_exists(self):
        """Test DeleteUserObservationNode class can be imported."""
        from lys.apps.user_auth.modules.user.nodes import DeleteUserObservationNode
        assert DeleteUserObservationNode is not None

    def test_has_success_annotation(self):
        """Test DeleteUserObservationNode has success field annotation."""
        from lys.apps.user_auth.modules.user.nodes import DeleteUserObservationNode
        assert "success" in DeleteUserObservationNode.__annotations__

    def test_has_from_obj_classmethod(self):
        """Test DeleteUserObservationNode has from_obj as a classmethod."""
        from lys.apps.user_auth.modules.user.nodes import DeleteUserObservationNode
        assert hasattr(DeleteUserObservationNode, "from_obj")
        assert isinstance(
            DeleteUserObservationNode.__dict__["from_obj"],
            classmethod
        )

    def test_from_obj_signature(self):
        """Test DeleteUserObservationNode.from_obj accepts entity parameter."""
        from lys.apps.user_auth.modules.user.nodes import DeleteUserObservationNode
        sig = inspect.signature(DeleteUserObservationNode.from_obj)
        params = list(sig.parameters.keys())
        assert "entity" in params
