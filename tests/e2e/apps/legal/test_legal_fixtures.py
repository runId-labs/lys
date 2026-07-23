"""
E2E check that the shipped LegalDocumentType fixture seeds the gating flags
(requires_acceptance) — the e2e app loads FIXTURES in DEV.
"""
import pytest

pytestmark = pytest.mark.asyncio


class TestLegalTypeFixture:

    async def test_seeds_requires_acceptance_flags(self, legal_manager):
        type_service = legal_manager.get_service("legal_document_type")
        async with legal_manager.database.get_session() as session:
            tou = await type_service.get_by_id("TERMS_OF_USE", session)
            sales = await type_service.get_by_id("SALES_TERMS", session)
            privacy = await type_service.get_by_id("PRIVACY_POLICY", session)
        assert tou.requires_acceptance is True
        assert sales.requires_acceptance is True
        assert privacy.requires_acceptance is False

    async def test_required_types_reflects_fixture(self, legal_manager):
        type_service = legal_manager.get_service("legal_document_type")
        async with legal_manager.database.get_session() as session:
            required = await type_service.required_types(session)
        assert set(required) == {"TERMS_OF_USE", "SALES_TERMS"}
