"""
Unit tests for legal webservice helpers: presigning error translation.
"""
import pytest

from lys.apps.legal.errors import LEGAL_STORAGE_ERROR
from lys.apps.legal.modules.legal_document.webservices import _presigned_url
from lys.core.errors import LysError
from lys.core.utils.storage import StorageError

pytestmark = pytest.mark.asyncio


class _OkService:
    async def get_presigned_url(self, object_key, expires_in=300):
        return f"https://storage.example/{object_key}"


class _FailingService:
    async def get_presigned_url(self, object_key, expires_in=300):
        raise StorageError("bad credentials", "presign")


class TestPresignedUrl:

    async def test_returns_url_on_success(self):
        url = await _presigned_url(_OkService(), "legal/x.pdf")
        assert url == "https://storage.example/legal/x.pdf"

    async def test_wraps_storage_error_as_domain_500(self):
        with pytest.raises(LysError) as exc:
            await _presigned_url(_FailingService(), "legal/x.pdf")
        # Config/credentials failure → honest 500 (not a 503 "outage": presigning is offline).
        assert exc.value.status_code == LEGAL_STORAGE_ERROR[0] == 500
