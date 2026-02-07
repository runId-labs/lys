import logging
from typing import Annotated, Optional

import strawberry
from sqlalchemy import Select, select

from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL, CLIENT_ADMIN_ROLE
from lys.apps.organization.modules.client.entities import Client
from lys.apps.organization.modules.client.inputs import CreateClientInput, UpdateClientInput
from lys.apps.organization.modules.client.nodes import ClientNode
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation

logger = logging.getLogger(__name__)


@strawberry.type
@register_query()
class ClientQuery(Query):
    @lys_connection(
        ClientNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Search and list all organizations/clients. Use 'search' to filter by name. Supervisor only."
    )
    async def all_clients(
        self,
        info: Info,
        search: Annotated[Optional[str], strawberry.argument(description="Search term to filter by client name")] = None
    ) -> Select:
        """
        Get all clients with optional search filtering.

        This query is accessible to supervisors with ROLE access level only.
        Search filters by client name (case-insensitive).

        Args:
            info: GraphQL context
            search: Optional search string to filter by client name

        Returns:
            Select: SQLAlchemy select statement for clients ordered by creation date
        """
        client_entity = info.context.app_manager.get_entity("client")

        stmt = select(client_entity).order_by(client_entity.created_at.desc())

        if search:
            search_pattern = f"%{search.lower()}%"
            stmt = stmt.where(client_entity.name.ilike(search_pattern))

        return stmt

    @lys_getter(
        ClientNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Get organization/client details by ID. Returns name, owner, and creation date."
    )
    async def client(self, obj: Client, info: Info):
        pass


@register_mutation()
@strawberry.type
class ClientMutation(Mutation):
    @lys_creation(
        ensure_type=ClientNode,
        is_public=True,
        is_licenced=False,
        description="Create a new organization with owner account. Required: client_name, email, password, language_code. Optional: first_name, last_name, gender_code."
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
        2. A new client organization with owner_id set

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

    @lys_edition(
        ensure_type=ClientNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Update organization name. Required: id (organization ID), inputs.name (new name)."
    )
    async def update_client(
        self,
        obj: Client,
        inputs: UpdateClientInput,
        info: Info
    ):
        """
        Update a client's name.

        This webservice is accessible to users with ROLE or ORGANIZATION_ROLE access level
        and CLIENT_ADMIN_ROLE role.

        Args:
            obj: Client entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - name: New name for the client organization
            info: GraphQL context

        Returns:
            Client: The updated client
        """
        input_data = inputs.to_pydantic()

        obj.name = input_data.name

        logger.info(f"Client {obj.id} name updated to: {input_data.name}")

        return obj