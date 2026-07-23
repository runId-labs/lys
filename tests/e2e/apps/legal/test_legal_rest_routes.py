"""
E2E tests for the public REST PDF routes, including the route-ordering fix that keeps
`/legal/versions/{id}` reachable (it must be declared before the generic
`/legal/{type}/{language}`).
"""
import pytest

pytestmark = pytest.mark.asyncio


class TestLegalRestRoutes:

    async def test_specific_version_route_redirects(self, legal_client, legal_manager):
        """`/legal/versions/{id}` is reachable and 302-redirects to a presigned URL —
        it is NOT shadowed by the generic `/legal/{type}/{language}` route."""
        version_id = legal_manager._e2e_version_id
        resp = await legal_client.get(f"/legal/versions/{version_id}", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"].startswith("https://storage.example/")
        # Proves it did not fall through to current_legal_pdf(type_id="versions", ...).
        assert "legal/TERMS_OF_USE/en/1.pdf" in resp.headers["location"]

    async def test_unknown_version_returns_404(self, legal_client):
        resp = await legal_client.get(
            "/legal/versions/00000000-0000-0000-0000-000000000000", follow_redirects=False
        )
        assert resp.status_code == 404

    async def test_malformed_version_id_returns_404_not_500(self, legal_client):
        """A non-UUID id is validated to a clean 404, never a backend 500 (F3)."""
        resp = await legal_client.get("/legal/versions/not-a-uuid", follow_redirects=False)
        assert resp.status_code == 404

    async def test_current_route_redirects(self, legal_client):
        resp = await legal_client.get("/legal/TERMS_OF_USE/en", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"].startswith("https://storage.example/")

    async def test_missing_language_returns_404(self, legal_client):
        """Strict resolution — no language fallback (publication gap surfaces as 404)."""
        resp = await legal_client.get("/legal/TERMS_OF_USE/de", follow_redirects=False)
        assert resp.status_code == 404
