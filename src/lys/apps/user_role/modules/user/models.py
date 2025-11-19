from typing import List, Optional

from pydantic import BaseModel, Field

from lys.apps.user_auth.modules.user.models import CreateUserInputModel


class CreateUserWithRolesInputModel(CreateUserInputModel):
    """
    Input model for creating a user with role assignments.

    Extends CreateUserInputModel with an optional list of role codes to assign to the new user.
    Used by user_role app's create_user webservice.
    """
    role_codes: Optional[List[str]] = Field(None, description="Optional list of role codes to assign to the user")


class UpdateUserRolesInputModel(BaseModel):
    """
    Input model for updating a user's role assignments.

    Synchronizes the user's roles with the provided list:
    - Adds roles that are in the list but not assigned to the user
    - Removes roles that are assigned to the user but not in the list
    - Empty list removes all roles from the user
    """
    role_codes: List[str] = Field(..., description="List of role codes to assign to the user (empty list removes all roles)")