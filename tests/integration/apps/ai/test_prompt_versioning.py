"""
Integration tests for AI prompt versioning.

Covers AIService.on_initialize() / _upsert_prompt_version() / get_prompt_version_id()
against a real database, and the resulting wiring into AIMessage.prompt_version_id
and its relationship.
"""

import hashlib
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from lys.apps.ai.modules.conversation.consts import AIMessageRole
from lys.apps.ai.modules.core.consts import ROUTES_MANIFEST_PURPOSE
from lys.apps.ai.utils.providers.abstracts import AIResponse
from lys.apps.ai.utils.providers.config import AIConfig, AIEndpointConfig


@pytest.fixture(autouse=True)
def _reset_ai_service_caches(ai_app_manager):
    """AIService._config_cache / _prompt_version_ids / _routes_manifest_cache are
    class-level and outlive a single test; reset them around every test so a test
    that seeds them doesn't leak into the next one regardless of execution order.

    Also (re-)binds AIService.app_manager to this fixture's AppManager: that binding
    normally happens during full app startup (initialize_services), which this
    lightweight entities+services-only fixture never runs, so a stale binding from
    elsewhere in the process can otherwise point on_initialize()'s DB session at the
    wrong database.
    """
    ai_service = ai_app_manager.get_service("ai")
    original_app_manager = ai_service.app_manager
    original_config = ai_service._config_cache
    original_versions = dict(ai_service._prompt_version_ids)
    original_manifest = ai_service._routes_manifest_cache
    ai_service.app_manager = ai_app_manager
    ai_service._config_cache = None
    ai_service._prompt_version_ids = {}
    ai_service._routes_manifest_cache = {}
    yield
    ai_service.app_manager = original_app_manager
    ai_service._config_cache = original_config
    ai_service._prompt_version_ids = original_versions
    ai_service._routes_manifest_cache = original_manifest


class TestOnInitializePromptVersioning:
    """AIService.on_initialize() versions each endpoint's system_prompt at boot."""

    @pytest.mark.asyncio
    async def test_creates_a_version_row_and_populates_the_boot_cache(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        prompt_version_entity = ai_app_manager.get_entity("ai_prompt_version")
        ai_service._config_cache = AIConfig(endpoints={
            "chatbot": AIEndpointConfig(
                provider="mistral", model="m", api_key="k",
                system_prompt="You are a helpful assistant.",
            ),
        })

        await ai_service.on_initialize()

        version_id = ai_service.get_prompt_version_id("chatbot")
        assert version_id is not None

        async with ai_app_manager.database.get_session() as session:
            stmt = select(prompt_version_entity).where(prompt_version_entity.id == version_id)
            row = (await session.execute(stmt)).scalar_one()

        assert row.purpose == "chatbot"
        assert row.content == "You are a helpful assistant."
        assert row.hash == hashlib.sha256(b"You are a helpful assistant.").hexdigest()

    @pytest.mark.asyncio
    async def test_purpose_without_system_prompt_stays_unset(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        ai_service._config_cache = AIConfig(endpoints={
            "silent": AIEndpointConfig(provider="mistral", model="m", api_key="k", system_prompt=None),
        })

        await ai_service.on_initialize()

        assert ai_service.get_prompt_version_id("silent") is None

    @pytest.mark.asyncio
    async def test_rebooting_with_the_same_prompt_does_not_duplicate_the_row(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        prompt_version_entity = ai_app_manager.get_entity("ai_prompt_version")
        ai_service._config_cache = AIConfig(endpoints={
            "chatbot": AIEndpointConfig(provider="mistral", model="m", api_key="k", system_prompt="Same prompt."),
        })

        await ai_service.on_initialize()
        first_id = ai_service.get_prompt_version_id("chatbot")

        # Simulate a second boot against the same, already-populated database.
        ai_service._prompt_version_ids = {}
        await ai_service.on_initialize()
        second_id = ai_service.get_prompt_version_id("chatbot")

        assert first_id == second_id

        prompt_hash = hashlib.sha256(b"Same prompt.").hexdigest()
        async with ai_app_manager.database.get_session() as session:
            stmt = select(prompt_version_entity).where(
                prompt_version_entity.purpose == "chatbot",
                prompt_version_entity.hash == prompt_hash,
            )
            rows = (await session.execute(stmt)).scalars().all()

        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_changing_the_prompt_creates_a_new_version(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        ai_service._config_cache = AIConfig(endpoints={
            "chatbot": AIEndpointConfig(provider="mistral", model="m", api_key="k", system_prompt="v1"),
        })
        await ai_service.on_initialize()
        v1_id = ai_service.get_prompt_version_id("chatbot")

        ai_service._config_cache = AIConfig(endpoints={
            "chatbot": AIEndpointConfig(provider="mistral", model="m", api_key="k", system_prompt="v2"),
        })
        ai_service._prompt_version_ids = {}
        await ai_service.on_initialize()
        v2_id = ai_service.get_prompt_version_id("chatbot")

        assert v1_id != v2_id

    @pytest.mark.asyncio
    async def test_missing_ai_config_logs_and_does_not_raise(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        ai_service._config_cache = None  # forces get_config() to re-read an unconfigured plugin

        await ai_service.on_initialize()  # must not raise

        assert ai_service._prompt_version_ids == {}

    @pytest.mark.asyncio
    async def test_a_failure_on_one_purpose_does_not_block_the_others(self, ai_app_manager, monkeypatch):
        import lys.apps.ai.modules.core.services as ai_services_module

        ai_service = ai_app_manager.get_service("ai")
        ai_service._config_cache = AIConfig(endpoints={
            "broken": AIEndpointConfig(provider="mistral", model="m", api_key="k", system_prompt="broken prompt"),
            "chatbot": AIEndpointConfig(provider="mistral", model="m", api_key="k", system_prompt="good prompt"),
        })

        real_sha256 = hashlib.sha256

        def flaky_sha256(data):
            if data == b"broken prompt":
                raise RuntimeError("boom")
            return real_sha256(data)

        monkeypatch.setattr(ai_services_module.hashlib, "sha256", flaky_sha256)

        await ai_service.on_initialize()

        assert ai_service.get_prompt_version_id("broken") is None
        assert ai_service.get_prompt_version_id("chatbot") is not None


class TestRoutesManifestVersioning:
    """The routes manifest is versioned as a single document under ROUTES_MANIFEST_PURPOSE."""

    @pytest.mark.asyncio
    async def test_manifest_is_versioned_as_one_document(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        prompt_version_entity = ai_app_manager.get_entity("ai_prompt_version")
        ai_service._config_cache = AIConfig(endpoints={})
        ai_service._routes_manifest_cache = {
            "globalWebservices": ["SomeService"],
            "routes": [{"name": "HomePage", "webservices": ["OtherService"]}],
        }

        await ai_service.on_initialize()

        async with ai_app_manager.database.get_session() as session:
            stmt = select(prompt_version_entity).where(prompt_version_entity.purpose == ROUTES_MANIFEST_PURPOSE)
            rows = (await session.execute(stmt)).scalars().all()

        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_no_manifest_configured_skips_versioning(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        prompt_version_entity = ai_app_manager.get_entity("ai_prompt_version")
        ai_service._config_cache = AIConfig(endpoints={})
        ai_service._routes_manifest_cache = {}

        await ai_service.on_initialize()

        async with ai_app_manager.database.get_session() as session:
            stmt = select(prompt_version_entity).where(prompt_version_entity.purpose == ROUTES_MANIFEST_PURPOSE)
            rows = (await session.execute(stmt)).scalars().all()

        assert rows == []

    @pytest.mark.asyncio
    async def test_a_failure_versioning_the_manifest_does_not_raise(self, ai_app_manager, monkeypatch):
        import lys.apps.ai.modules.core.services as ai_services_module

        ai_service = ai_app_manager.get_service("ai")
        ai_service._config_cache = AIConfig(endpoints={})
        ai_service._routes_manifest_cache = {"routes": [{"name": "HomePage"}]}

        def failing_dumps(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(ai_services_module.json, "dumps", failing_dumps)

        await ai_service.on_initialize()  # must not raise


class TestUpsertPromptVersion:
    """Focused tests for AIService._upsert_prompt_version() using a real, mapped entity
    class (from the app manager) with a hand-built session stub, so the pre-check-hit and
    concurrent-insert (IntegrityError) branches are exercised deterministically instead of
    depending on real database race timing.

    Regression coverage: the happy insert path must return the created row (not None) —
    it previously fell through without a return statement, which surfaced as an
    AttributeError on `.id` back in on_initialize, silently caught by its broad
    except-and-log and leaving the boot cache never populated.
    """

    @pytest.mark.asyncio
    async def test_pre_check_hit_returns_existing_without_inserting(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        entity = ai_app_manager.get_entity("ai_prompt_version")
        existing_row = entity(purpose="chatbot", content="c", hash="h")

        class StubSession:
            def __init__(self):
                self.added = []

            async def execute(self, stmt):
                class Result:
                    def scalar_one_or_none(self_inner):
                        return existing_row
                return Result()

            def add(self, obj):
                self.added.append(obj)

        session = StubSession()
        result = await ai_service._upsert_prompt_version("chatbot", "c", session=session)

        assert result is existing_row
        assert session.added == []

    @pytest.mark.asyncio
    async def test_insert_returns_the_created_row(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        entity = ai_app_manager.get_entity("ai_prompt_version")

        class NestedTx:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, exc_type, exc, tb):
                return False

        class StubSession:
            def __init__(self):
                self.added = []

            async def execute(self, stmt):
                class Result:
                    def scalar_one_or_none(self_inner):
                        return None
                return Result()

            def add(self, obj):
                self.added.append(obj)

            def begin_nested(self):
                return NestedTx()

        session = StubSession()
        result = await ai_service._upsert_prompt_version("chatbot", "c", session=session)

        assert result is not None
        assert isinstance(result, entity)
        assert result.purpose == "chatbot"
        assert result.content == "c"
        assert result.hash == hashlib.sha256(b"c").hexdigest()
        assert session.added == [result]

    @pytest.mark.asyncio
    async def test_concurrent_insert_returns_the_winning_row(self, ai_app_manager):
        """A same-hash row inserted by a concurrent boot between the pre-check and the
        insert must not be duplicated: the unique constraint fires (simulated here via
        the savepoint's __aexit__, matching where SQLAlchemy actually flushes) and the
        pre-existing winner is returned instead of a fresh one."""
        ai_service = ai_app_manager.get_service("ai")
        entity = ai_app_manager.get_entity("ai_prompt_version")
        winner_row = entity(purpose="chatbot", content="c", hash="h")

        class NestedTx:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, exc_type, exc, tb):
                raise IntegrityError("insert", {}, Exception("unique violation"))

        class StubSession:
            def __init__(self):
                self.calls = 0
                self.added = []

            async def execute(self, stmt):
                self.calls += 1

                class Result:
                    def scalar_one_or_none(self_inner):
                        return None

                    def scalar_one(self_inner):
                        return winner_row
                return Result()

            def add(self, obj):
                self.added.append(obj)

            def begin_nested(self):
                return NestedTx()

        session = StubSession()
        result = await ai_service._upsert_prompt_version("chatbot", "c", session=session)

        assert result is winner_row
        assert session.calls == 2  # pre-check, then the re-check after losing the race


class TestPromptVersionMessageWiring:
    """End-to-end: AIConversationService stamps AIMessage.prompt_version_id from
    AIService's boot cache, and the relationship resolves back to the version row."""

    @pytest.mark.asyncio
    async def test_message_prompt_version_relationship_resolves(self, ai_app_manager):
        ai_service = ai_app_manager.get_service("ai")
        conversation_service = ai_app_manager.get_service("ai_conversation")
        message_service = ai_app_manager.get_service("ai_message")
        message_entity = ai_app_manager.get_entity("ai_message")
        user_id = str(uuid4())

        ai_service._config_cache = AIConfig(endpoints={
            "chatbot": AIEndpointConfig(provider="mistral", model="m", api_key="k", system_prompt="Be nice."),
        })
        await ai_service.on_initialize()
        version_id = ai_service.get_prompt_version_id("chatbot")

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)
            message = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.USER.value,
                content="Hi",
                prompt_version_id=version_id,
            )
            message_id = message.id

        async with ai_app_manager.database.get_session() as session:
            stmt = select(message_entity).where(message_entity.id == message_id)
            reloaded = (await session.execute(stmt)).scalar_one()

            assert reloaded.prompt_version_id == version_id
            assert reloaded.prompt_version.content == "Be nice."

    @pytest.mark.asyncio
    async def test_message_without_a_prompt_version_leaves_the_fk_unset(self, ai_app_manager):
        conversation_service = ai_app_manager.get_service("ai_conversation")
        message_service = ai_app_manager.get_service("ai_message")
        user_id = str(uuid4())

        async with ai_app_manager.database.get_session() as session:
            conversation = await conversation_service.get_or_create(user_id, session)
            message = await message_service.create(
                session,
                conversation_id=conversation.id,
                role=AIMessageRole.USER.value,
                content="Hi",
            )

        assert message.prompt_version_id is None

    @pytest.mark.asyncio
    async def test_chat_convenience_method_stamps_the_user_message(self, ai_app_manager):
        """AIConversationService.chat() — the simple, tool-free convenience entrypoint —
        also stamps its user row from the boot cache, not just the full chatbot pipeline."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        ai_service = ai_app_manager.get_service("ai")
        message_entity = ai_app_manager.get_entity("ai_message")
        user_id = str(uuid4())

        ai_service._config_cache = AIConfig(endpoints={
            "chatbot": AIEndpointConfig(provider="mistral", model="m", api_key="k", system_prompt="Be nice."),
        })
        await ai_service.on_initialize()
        version_id = ai_service.get_prompt_version_id("chatbot")
        assert version_id is not None

        fake_response = AIResponse(content="Hello!", provider="mistral", model="m")
        async with ai_app_manager.database.get_session() as session:
            with patch.object(ai_service, "chat_with_purpose", new_callable=AsyncMock, return_value=fake_response):
                await AIConversationService.chat(user_id, "Hi", session)

            stmt = (
                select(message_entity)
                .where(
                    message_entity.role == AIMessageRole.USER.value,
                    message_entity.content == "Hi",
                )
            )
            user_row = (await session.execute(stmt)).scalar_one()

        assert user_row.prompt_version_id == version_id


class TestPromptSegments:
    """Endpoint config keys declared under ``prompt_segments`` are versioned as ``<purpose>:<key>``."""

    @staticmethod
    def _configure(ai_app_manager, monkeypatch, raw_endpoint):
        from lys.apps.ai.modules.core.consts import AI_PLUGIN_NAME

        ai_service = ai_app_manager.get_service("ai")
        monkeypatch.setitem(ai_app_manager.settings.plugins, AI_PLUGIN_NAME, {"chatbot": raw_endpoint})
        ai_service._config_cache = AIConfig(endpoints={
            "chatbot": AIEndpointConfig(provider="mistral", model="m", api_key="k"),
        })
        return ai_service

    @staticmethod
    async def _purposes(ai_app_manager):
        entity = ai_app_manager.get_entity("ai_prompt_version")
        async with ai_app_manager.database.get_session() as session:
            rows = (await session.execute(select(entity))).scalars().all()
        return {row.purpose: row.content for row in rows}

    @pytest.mark.asyncio
    async def test_declared_segments_are_versioned(self, ai_app_manager, monkeypatch):
        ai_service = self._configure(ai_app_manager, monkeypatch, {
            "prompt_segments": ["summary_header", "dynamic_context_header"],
            "summary_header": "Summary:",
            "dynamic_context_header": "Context:",
            "compaction_threshold": 10,
        })

        await ai_service.on_initialize()

        assert await self._purposes(ai_app_manager) == {
            "chatbot:summary_header": "Summary:",
            "chatbot:dynamic_context_header": "Context:",
        }

    @pytest.mark.asyncio
    async def test_missing_or_non_string_segment_warns_and_is_skipped(self, ai_app_manager, monkeypatch, caplog):
        ai_service = self._configure(ai_app_manager, monkeypatch, {
            "prompt_segments": ["absent", "not_a_string", "ok"],
            "not_a_string": 3,
            "ok": "Fine",
        })

        with caplog.at_level("WARNING"):
            await ai_service.on_initialize()

        assert await self._purposes(ai_app_manager) == {"chatbot:ok": "Fine"}
        assert "'absent'" in caplog.text and "'not_a_string'" in caplog.text

    @pytest.mark.asyncio
    async def test_malformed_declaration_warns_and_versions_nothing(self, ai_app_manager, monkeypatch, caplog):
        ai_service = self._configure(ai_app_manager, monkeypatch, {
            "prompt_segments": "summary_header",
            "summary_header": "Summary:",
        })

        with caplog.at_level("WARNING"):
            await ai_service.on_initialize()

        assert await self._purposes(ai_app_manager) == {}
        assert "must be a list of keys" in caplog.text

    @pytest.mark.asyncio
    async def test_get_prompt_segment_returns_strings_only(self, ai_app_manager, monkeypatch):
        ai_service = self._configure(ai_app_manager, monkeypatch, {"summary_header": "Summary:", "limit": 3})

        assert ai_service.get_prompt_segment("chatbot", "summary_header") == "Summary:"
        assert ai_service.get_prompt_segment("chatbot", "limit") is None
        assert ai_service.get_prompt_segment("chatbot", "absent") is None
        assert ai_service.get_prompt_segment("unknown_purpose", "summary_header") is None
