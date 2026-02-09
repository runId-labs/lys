"""
Unit tests for core services module logic.

Tests Service base class and EntityService value comparison methods.
"""

import asyncio
from unittest.mock import MagicMock

from lys.core.entities import Entity
from lys.core.services import EntityService, Service


class TestServiceOnInitializeOnShutdown:

    def test_on_initialize_is_noop(self):
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(Service.on_initialize())
            assert result is None
        finally:
            loop.close()

    def test_on_shutdown_is_noop(self):
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(Service.on_shutdown())
            assert result is None
        finally:
            loop.close()


class TestValuesDiffer:

    def test_different_strings(self):
        assert EntityService._values_differ("a", "b") is True

    def test_same_strings(self):
        assert EntityService._values_differ("a", "a") is False

    def test_none_old_entity_new(self):
        mock_entity = MagicMock(spec=Entity)
        mock_entity.id = "id1"
        assert EntityService._values_differ(None, mock_entity) is True

    def test_entity_different_ids(self):
        old_entity = MagicMock(spec=Entity)
        old_entity.id = "id1"
        new_entity = MagicMock(spec=Entity)
        new_entity.id = "id2"
        assert EntityService._values_differ(old_entity, new_entity) is True

    def test_entity_same_ids(self):
        old_entity = MagicMock(spec=Entity)
        old_entity.id = "id1"
        new_entity = MagicMock(spec=Entity)
        new_entity.id = "id1"
        assert EntityService._values_differ(old_entity, new_entity) is False

    def test_list_different_lengths(self):
        assert EntityService._values_differ([1, 2], [1, 2, 3]) is True

    def test_string_old_list_new(self):
        assert EntityService._values_differ("old", [1, 2]) is True


class TestListValuesDiffer:

    def test_old_not_list(self):
        assert EntityService._list_values_differ("not_a_list", [1, 2]) is True

    def test_different_lengths(self):
        assert EntityService._list_values_differ([1], [1, 2]) is True

    def test_same_entity_lists(self):
        e1 = MagicMock(spec=Entity)
        e1.id = "id1"
        e2 = MagicMock(spec=Entity)
        e2.id = "id2"
        old_list = [e1, e2]

        e3 = MagicMock(spec=Entity)
        e3.id = "id1"
        e4 = MagicMock(spec=Entity)
        e4.id = "id2"
        new_list = [e3, e4]

        assert EntityService._list_values_differ(old_list, new_list) is False

    def test_different_entity_lists(self):
        e1 = MagicMock(spec=Entity)
        e1.id = "id1"
        old_list = [e1]

        e2 = MagicMock(spec=Entity)
        e2.id = "id2"
        new_list = [e2]

        assert EntityService._list_values_differ(old_list, new_list) is True

    def test_same_primitive_lists(self):
        assert EntityService._list_values_differ([1, 2, 3], [3, 2, 1]) is False

    def test_different_primitive_lists(self):
        assert EntityService._list_values_differ([1, 2], [3, 4]) is True
