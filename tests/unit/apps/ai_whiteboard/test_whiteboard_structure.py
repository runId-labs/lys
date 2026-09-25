"""
Unit tests for the whiteboard entities, inputs, nodes and webservices: structure and the
small pieces of logic that live in them.
"""

import inspect
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from strawberry import relay

from lys.apps.ai_whiteboard.modules.whiteboard.entities import Whiteboard
from lys.apps.ai_whiteboard.modules.whiteboard.models import SaveWhiteboardSceneInputModel


class TestEntity:
    def test_table_name_is_singular(self):
        assert Whiteboard.__tablename__ == "whiteboard"

    def test_access_is_the_owner_only(self):
        board = Whiteboard.__new__(Whiteboard)
        board.user_id = "u1"
        assert board.accessing_users() == ["u1"]
        assert board.accessing_organizations() == {}

    def test_no_owner_means_nobody_has_access(self):
        board = Whiteboard.__new__(Whiteboard)
        board.user_id = None
        assert board.accessing_users() == []


class TestInputModel:
    def test_expected_revision_is_required(self):
        with pytest.raises(ValidationError):
            SaveWhiteboardSceneInputModel(scene={"elements": []})

    def test_negative_revision_is_refused(self):
        with pytest.raises(ValidationError):
            SaveWhiteboardSceneInputModel(scene={"elements": []}, expected_revision=-1)

    def test_valid_input(self):
        model = SaveWhiteboardSceneInputModel(scene={"elements": []}, expected_revision=0)
        assert model.expected_revision == 0


class TestWhiteboardNode:
    @pytest.fixture
    def node(self):
        from lys.apps.ai_whiteboard.modules.whiteboard.nodes import WhiteboardNode
        entity = SimpleNamespace(scene_json=None, revision=3, user_id="u1")
        instance = WhiteboardNode.__new__(WhiteboardNode)
        instance._entity = entity
        return instance

    def test_node_is_registered_under_the_name_signals_use(self):
        from lys.apps.ai_whiteboard.modules.whiteboard.consts import WHITEBOARD_NODE_NAME
        from lys.apps.ai_whiteboard.modules.whiteboard.nodes import WhiteboardNode
        assert WhiteboardNode.__name__ == WHITEBOARD_NODE_NAME

    def test_missing_scene_reads_as_empty(self, node):
        assert node.scene.base_resolver.wrapped_func(node) == {}

    def test_revision_and_owner(self, node):
        assert node.revision.base_resolver.wrapped_func(node) == 3
        assert node.user_id.base_resolver.wrapped_func(node) == relay.GlobalID("UserNode", "u1")

    def test_order_by_map(self):
        from lys.apps.ai_whiteboard.modules.whiteboard.nodes import WhiteboardNode
        assert set(WhiteboardNode.order_by_attribute_map) == {"created_at", "updated_at", "title"}


class TestConversationNode:
    def test_whiteboard_id_is_a_global_id(self):
        from lys.apps.ai_whiteboard.modules.conversation.nodes import AIConversationNode
        node = AIConversationNode.__new__(AIConversationNode)
        node._entity = SimpleNamespace(whiteboard_id="w1")
        resolver = AIConversationNode.whiteboard_id.base_resolver.wrapped_func
        assert resolver(node) == relay.GlobalID("WhiteboardNode", "w1")

    def test_no_board_is_null(self):
        from lys.apps.ai_whiteboard.modules.conversation.nodes import AIConversationNode
        node = AIConversationNode.__new__(AIConversationNode)
        node._entity = SimpleNamespace(whiteboard_id=None)
        assert AIConversationNode.whiteboard_id.base_resolver.wrapped_func(node) is None


class TestWebservices:
    def test_query_and_mutation_expose_the_operations(self):
        from lys.apps.ai_whiteboard.modules.whiteboard.webservices import WhiteboardMutation, WhiteboardQuery
        assert hasattr(WhiteboardQuery, "whiteboard")
        assert hasattr(WhiteboardQuery, "all_whiteboards")
        assert hasattr(WhiteboardMutation, "save_whiteboard_scene")
        assert hasattr(WhiteboardMutation, "delete_whiteboard")

    def test_operations_are_async(self):
        from lys.apps.ai_whiteboard.modules.whiteboard.webservices import WhiteboardMutation, WhiteboardQuery
        assert inspect.iscoroutinefunction(WhiteboardQuery.all_whiteboards)
        assert inspect.iscoroutinefunction(WhiteboardMutation.save_whiteboard_scene)
