"""
Integration tests for LanguageService.

These tests use a real SQLite in-memory database to test actual
CRUD operations that cannot be tested with mocks.
"""

import pytest

from lys.apps.base.modules.language.services import LanguageService


class TestLanguageServiceIntegration:
    """Integration tests for LanguageService CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_language(self, db_session):
        """Test creating a language entity."""
        # Create a language
        language = await LanguageService.create(
            db_session,
            id="en",
            enabled=True
        )

        # Verify entity was created
        assert language is not None
        assert language.id == "en"
        assert language.enabled is True
        assert language.created_at is not None
        assert language.code == "en"  # ParametricEntity property

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session_commit):
        """Test retrieving a language by ID."""
        # Create a language
        created = await LanguageService.create(
            db_session_commit,
            id="fr",
            enabled=True
        )
        await db_session_commit.commit()

        # Retrieve it
        found = await LanguageService.get_by_id("fr", db_session_commit)

        # Verify
        assert found is not None
        assert found.id == "fr"
        assert found.enabled is True

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db_session):
        """Test retrieving a non-existent language returns None."""
        result = await LanguageService.get_by_id("nonexistent", db_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all(self, db_session_commit):
        """Test retrieving all languages."""
        # Create multiple languages
        await LanguageService.create(db_session_commit, id="en", enabled=True)
        await LanguageService.create(db_session_commit, id="fr", enabled=True)
        await LanguageService.create(db_session_commit, id="es", enabled=False)
        await db_session_commit.commit()

        # Get all
        languages = await LanguageService.get_all(db_session_commit, limit=10)

        # Verify
        assert len(languages) == 3
        language_ids = {lang.id for lang in languages}
        assert "en" in language_ids
        assert "fr" in language_ids
        assert "es" in language_ids

    @pytest.mark.asyncio
    async def test_get_all_with_pagination(self, db_session_commit):
        """Test get_all with limit and offset."""
        # Create 5 languages
        for i in range(5):
            await LanguageService.create(
                db_session_commit,
                id=f"lang{i}",
                enabled=True
            )
        await db_session_commit.commit()

        # Get first 2
        page1 = await LanguageService.get_all(db_session_commit, limit=2, offset=0)
        assert len(page1) == 2

        # Get next 2
        page2 = await LanguageService.get_all(db_session_commit, limit=2, offset=2)
        assert len(page2) == 2

        # Verify no overlap
        page1_ids = {lang.id for lang in page1}
        page2_ids = {lang.id for lang in page2}
        assert len(page1_ids & page2_ids) == 0  # No intersection

    @pytest.mark.asyncio
    async def test_update(self, db_session_commit):
        """Test updating a language."""
        # Create
        await LanguageService.create(db_session_commit, id="de", enabled=True)
        await db_session_commit.commit()

        # Update
        updated = await LanguageService.update(
            "de",
            db_session_commit,
            enabled=False
        )

        # Verify
        assert updated is not None
        assert updated.id == "de"
        assert updated.enabled is False
        assert updated.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, db_session):
        """Test updating a non-existent language returns None."""
        result = await LanguageService.update(
            "nonexistent",
            db_session,
            enabled=False
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, db_session_commit):
        """Test deleting a language."""
        # Create
        await LanguageService.create(db_session_commit, id="it", enabled=True)
        await db_session_commit.commit()

        # Delete
        deleted = await LanguageService.delete("it", db_session_commit)
        assert deleted is True

        # Verify deleted
        found = await LanguageService.get_by_id("it", db_session_commit)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db_session):
        """Test deleting a non-existent language returns False."""
        result = await LanguageService.delete("nonexistent", db_session)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_multiple_by_ids(self, db_session_commit):
        """Test retrieving multiple languages by IDs."""
        # Create languages
        await LanguageService.create(db_session_commit, id="en", enabled=True)
        await LanguageService.create(db_session_commit, id="fr", enabled=True)
        await LanguageService.create(db_session_commit, id="es", enabled=True)
        await LanguageService.create(db_session_commit, id="de", enabled=True)
        await db_session_commit.commit()

        # Get multiple by IDs
        languages = await LanguageService.get_multiple_by_ids(
            ["en", "fr", "nonexistent"],
            db_session_commit
        )

        # Verify
        assert len(languages) == 2  # Only en and fr found
        language_ids = {lang.id for lang in languages}
        assert "en" in language_ids
        assert "fr" in language_ids
        assert "nonexistent" not in language_ids

    @pytest.mark.asyncio
    async def test_get_multiple_by_ids_empty(self, db_session):
        """Test get_multiple_by_ids with empty list returns empty list."""
        result = await LanguageService.get_multiple_by_ids([], db_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_check_and_update(self, db_session_commit):
        """Test check_and_update helper method."""
        # Create
        language = await LanguageService.create(
            db_session_commit,
            id="pt",
            enabled=True
        )
        await db_session_commit.commit()

        # Test with same value (no update)
        updated_lang, is_updated = await LanguageService.check_and_update(
            language,
            enabled=True  # Same value
        )
        assert is_updated is False

        # Test with different value (should update)
        updated_lang, is_updated = await LanguageService.check_and_update(
            language,
            enabled=False  # Different value
        )
        assert is_updated is True
        assert updated_lang.enabled is False
