import logging

import strawberry

from lys.apps.organization.modules.client.inputs import CreateClientInput
from lys.apps.organization.modules.client.nodes import ClientNode
from lys.core.contexts import Info
from lys.core.graphql.create import lys_creation
from lys.core.graphql.registers import register_mutation
from lys.core.graphql.types import Mutation

logger = logging.getLogger(__name__)


@register_mutation("graphql")
@strawberry.type
class ClientMutation(Mutation):
    @lys_creation(
        ensure_type=ClientNode,
        is_public=True,
        is_licenced=False,
        description="Create a new client with an owner user. The owner will have full administrative access."
    )
    async def create_client(
        self,
        inputs: CreateClientInput,
        info: Info
    ):
        """
        Create a new client organization with an owner user.

        This webservice creates:
        1. A new user account (the owner)
        2. A new client organization
        3. A ClientUser relationship linking the owner to the client

        The owner automatically receives full administrative access to the client
        without requiring explicit role assignments (via client.owner_id check in permissions).

        Args:
            inputs: Input containing:
                - client_name: Name of the client organization
                - email: Email address for the owner user
                - password: Password for the owner user
                - language_code: Language code for the owner user
                - first_name: Optional first name of the owner (GDPR-protected)
                - last_name: Optional last name of the owner (GDPR-protected)
                - gender_code: Optional gender code (MALE, FEMALE, OTHER)
            info: GraphQL context

        Returns:
            Client: The created client (access owner via client.owner relationship)
        """
        # Convert Strawberry input to Pydantic model for validation
        input_data = inputs.to_pydantic()

        session = info.context.session
        client_service = info.context.app_manager.get_service("client")

        # Delegate all business logic to the service
        client = await client_service.create_client_with_owner(
            session=session,
            client_name=input_data.client_name,
            email=input_data.email,
            password=input_data.password,
            language_id=input_data.language_code,
            send_verification_email=True,
            background_tasks=info.context.background_tasks,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_code
        )

        logger.info(f"Client created: {input_data.client_name} with owner: {input_data.email}")

        return client