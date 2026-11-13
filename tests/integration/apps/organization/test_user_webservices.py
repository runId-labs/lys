"""
Integration tests for OrganizationUserQuery.all_client_users: the ids filter, run on the database.
"""
import importlib
import inspect
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from strawberry import relay

MODULE_NAME = "lys.apps.organization.modules.user.webservices"


def _resolver():
    """The undecorated all_client_users: lys_connection keeps it in its wrapper's closure."""
    module = sys.modules.get(MODULE_NAME)
    if module is None:
        try:
            module = importlib.import_module(MODULE_NAME)
        except ValueError:  # singleton webservice registry already holds the name
            module = sys.modules[MODULE_NAME]
    wrapper = module.OrganizationUserQuery.all_client_users
    return next(
        cell.cell_contents for cell in wrapper.__closure__
        if inspect.iscoroutinefunction(cell.cell_contents) and cell.cell_contents.__name__ == "all_client_users"
    )


async def _user_ids(app_manager, **kwargs) -> set[str]:
    info = SimpleNamespace(context=SimpleNamespace(app_manager=app_manager))
    stmt = await _resolver()(None, info, **kwargs)
    async with app_manager.database.get_session() as session:
        return {user.id for user in (await session.execute(stmt)).scalars().all()}


async def _create_members(app_manager) -> list[str]:
    """Create a client with two members; return the member ids."""
    client_service = app_manager.get_service("client")
    user_service = app_manager.get_service("user")
    suffix = uuid4().hex[:8]

    async with app_manager.database.get_session() as session:
        client = await client_service.create_client_with_owner(
            session=session,
            client_name=f"Ids-Corp-{suffix}",
            email=f"ids-owner-{suffix}@example.com",
            password="Password123!",
            language_id="en",
            send_verification_email=False,
        )
        members = [
            await user_service.create_client_user(
                session=session, client_id=client.id, email=f"ids-member{i}-{suffix}@example.com", language_id="en"
            )
            for i in range(2)
        ]
        await session.commit()
        return [member.id for member in members]


class TestAllClientUsersIds:
    """ids: keeps only the given users; an empty list keeps none."""

    @pytest.mark.asyncio
    async def test_ids_keeps_only_the_given_users(self, organization_app_manager):
        first, _second = await _create_members(organization_app_manager)

        ids = await _user_ids(organization_app_manager, ids=[relay.GlobalID("UserNode", first)])

        assert ids == {first}

    @pytest.mark.asyncio
    async def test_empty_ids_returns_none(self, organization_app_manager):
        await _create_members(organization_app_manager)

        assert await _user_ids(organization_app_manager, ids=[]) == set()

    @pytest.mark.asyncio
    async def test_no_ids_applies_no_filter(self, organization_app_manager):
        members = await _create_members(organization_app_manager)

        assert set(members) <= await _user_ids(organization_app_manager)
