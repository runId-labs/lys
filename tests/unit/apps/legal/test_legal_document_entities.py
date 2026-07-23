"""
Unit tests for legal_document entities, consts, and LegalSettings.
"""
from datetime import datetime, timezone

from lys.apps.legal.modules.legal_document import consts
from lys.apps.legal.modules.legal_document.entities import (
    LegalDocumentAcceptance,
    LegalDocumentType,
    LegalDocumentVersion,
)
from lys.core.configs import LegalSettings
from lys.core.entities import Entity, ParametricEntity


class TestEntities:

    def test_type_is_parametric(self):
        assert issubclass(LegalDocumentType, ParametricEntity)
        assert LegalDocumentType.__tablename__ == "legal_document_type"

    def test_version_is_entity(self):
        assert issubclass(LegalDocumentVersion, Entity)
        assert LegalDocumentVersion.__tablename__ == "legal_document_version"

    def test_acceptance_is_entity(self):
        assert issubclass(LegalDocumentAcceptance, Entity)
        assert LegalDocumentAcceptance.__tablename__ == "legal_document_acceptance"

    def test_version_is_public_non_tenant(self):
        instance = LegalDocumentVersion()
        assert instance.accessing_users() == []
        assert instance.accessing_organizations() == {}

    def test_acceptance_owner_scoped(self):
        instance = LegalDocumentAcceptance()
        instance.user_id = "abc"
        assert instance.accessing_users() == ["abc"]
        instance.user_id = None
        assert instance.accessing_users() == []


class TestConsts:

    def test_storage_plugin_key_matches_file_management(self):
        # Must match file_management's key so both apps resolve the same backend.
        assert consts.FILE_STORAGE_PLUGIN_KEY == "file_storage"


class TestLegalSettings:

    def test_defaults(self):
        settings = LegalSettings()
        assert settings.documents == {}  # type -> {"languages": {lang: source}}
        assert settings.retention_days == 5 * 365
        assert settings.anonymized_users_endpoint is None

    def test_configure_updates_fields(self):
        settings = LegalSettings()
        settings.configure(retention_days=1000, anonymized_users_endpoint="http://x/graphql")
        assert settings.retention_days == 1000
        assert settings.anonymized_users_endpoint == "http://x/graphql"
