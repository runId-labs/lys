"""
Integration tests for LicensingUserQuery.all_client_users: the statement it builds, run on the database.

Covers the owner exclusion (include_owners) and the ids filter.
"""
import importlib
import inspect
import sys
from types import SimpleNamespace

import pytest
from strawberry import relay

from tests.integration.apps.licensing.conftest import create_license_profile_users

pytest.importorskip("mollie", reason="mollie package not installed")

MODULE_NAME = "lys.apps.licensing.modules.user.webservices"


def _resolver():
    """The undecorated all_client_users: lys_connection keeps it in its wrapper's closure."""
    module = sys.modules.get(MODULE_NAME)
    if module is None:
        try:
            module = importlib.import_module(MODULE_NAME)
        except ValueError:  # singleton webservice registry already holds the name
            module = sys.modules[MODULE_NAME]
    wrapper = module.LicensingUserQuery.all_client_users
    return next(
        cell.cell_contents for cell in wrapper.__closure__
        if inspect.iscoroutinefunction(cell.cell_contents) and cell.cell_contents.__name__ == "all_client_users"
    )


async def _user_ids(app_manager, **kwargs) -> set[str]:
    info = SimpleNamespace(context=SimpleNamespace(app_manager=app_manager))
    stmt = await _resolver()(None, info, **kwargs)
    async with app_manager.database.get_session() as session:
        return {user.id for user in (await session.execute(stmt)).scalars().all()}


def _gid(user_id: str) -> relay.GlobalID:
    return relay.GlobalID("UserNode", user_id)


class TestAllClientUsersOwners:
    """include_owners: owners are excluded by default."""

    @pytest.mark.asyncio
    async def test_owner_excluded_by_default(self, licensing_app_manager):
        users = await create_license_profile_users(licensing_app_manager)

        ids = await _user_ids(licensing_app_manager, client_id=relay.GlobalID("ClientNode", users["client"]))

        assert ids == {users["licensed_member"], users["unlicensed_member"]}

    @pytest.mark.asyncio
    async def test_owner_returned_with_include_owners(self, licensing_app_manager):
        users = await create_license_profile_users(licensing_app_manager)

        ids = await _user_ids(
            licensing_app_manager, client_id=relay.GlobalID("ClientNode", users["client"]), include_owners=True
        )

        assert ids == {users["owner"], users["licensed_member"], users["unlicensed_member"]}


class TestAllClientUsersIds:
    """ids: keeps only the given users; an empty list keeps none."""

    @pytest.mark.asyncio
    async def test_ids_keeps_only_the_given_users(self, licensing_app_manager):
        users = await create_license_profile_users(licensing_app_manager)

        ids = await _user_ids(licensing_app_manager, ids=[_gid(users["licensed_member"])])

        assert ids == {users["licensed_member"]}

    @pytest.mark.asyncio
    async def test_empty_ids_returns_none(self, licensing_app_manager):
        await create_license_profile_users(licensing_app_manager)

        assert await _user_ids(licensing_app_manager, ids=[]) == set()

    @pytest.mark.asyncio
    async def test_ids_do_not_bypass_the_owner_exclusion(self, licensing_app_manager):
        users = await create_license_profile_users(licensing_app_manager)
        requested = [_gid(users["owner"]), _gid(users["unlicensed_member"])]

        assert await _user_ids(licensing_app_manager, ids=requested) == {users["unlicensed_member"]}
        assert await _user_ids(licensing_app_manager, ids=requested, include_owners=True) == {
            users["owner"], users["unlicensed_member"]
        }

    @pytest.mark.asyncio
    async def test_ids_skip_users_outside_any_client(self, licensing_app_manager):
        users = await create_license_profile_users(licensing_app_manager)

        assert await _user_ids(licensing_app_manager, ids=[_gid(users["outsider"])]) == set()
