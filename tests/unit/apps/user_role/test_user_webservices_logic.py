"""
Unit tests for user_role user webservices logic.

Tests module-level structures and error constants.
Since the webservices module uses override_webservice at module level,
direct import requires registry setup. We test the importable error constants
and input models instead.
"""

import pytest


class TestUserRoleErrors:
    """Tests for user_role error constants."""

    def test_unauthorized_role_assignment_error(self):
        from lys.apps.user_role.errors import UNAUTHORIZED_ROLE_ASSIGNMENT
        code, message = UNAUTHORIZED_ROLE_ASSIGNMENT
        assert code == 403
        assert message == "UNAUTHORIZED_ROLE_ASSIGNMENT"

    def test_cannot_update_super_user_roles_error(self):
        from lys.apps.user_role.errors import CANNOT_UPDATE_SUPER_USER_ROLES
        code, message = CANNOT_UPDATE_SUPER_USER_ROLES
        assert code == 403
        assert message == "CANNOT_UPDATE_SUPER_USER_ROLES"

    def test_supervisor_only_role_error(self):
        from lys.apps.user_role.errors import SUPERVISOR_ONLY_ROLE
        code, message = SUPERVISOR_ONLY_ROLE
        assert code == 403
        assert message == "SUPERVISOR_ONLY_ROLE"


class TestUserRoleInputs:
    """Tests for user_role input models."""

    def test_create_user_input_model_exists(self):
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel
        assert CreateUserWithRolesInputModel is not None

    def test_update_user_roles_input_model_exists(self):
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel
        assert UpdateUserRolesInputModel is not None


class TestUserRoleConsts:
    """Tests for user_role constants."""

    def test_role_access_level(self):
        from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
        assert isinstance(ROLE_ACCESS_LEVEL, str)
        assert len(ROLE_ACCESS_LEVEL) > 0
