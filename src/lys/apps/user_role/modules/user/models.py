from typing import List, Optional

from pydantic import Field

from lys.apps.user_auth.modules.user.models import CreateUserInputModel


class CreateUserWithRolesInputModel(CreateUserInputModel):
    """
    Input model for creating a user with role assignments.

    Extends CreateUserInputModel with an optional list of role codes to assign to the new user.
    Used by user_role app's create_user webservice.
    """
    role_codes: Optional[List[str]] = Field(None, description="Optional list of role codes to assign to the user")