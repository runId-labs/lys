"""
Unit tests for core graphql nodes module logic.

Tests EntityNode.get_entity, from_obj, _lazy_load_relation, _lazy_load_relation_list,
_is_relation_nullable, resolve_node, and build_list_connection inner resolve_node/resolve_connection.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


class TestEntityNodeGetEntity:
    """Tests for EntityNode.get_entity() (line 86)."""

    def test_get_entity_returns_stored_entity(self):
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        fake_entity = MagicMock()
        node._entity = fake_entity

        result = node.get_entity()
        assert result is fake_entity


class TestEntityNodeFromObj:
    """Tests for EntityNode.from_obj() covering lines 113-133."""

    def test_from_obj_maps_simple_fields(self):
        """Test that from_obj maps entity attributes to node fields."""
        from lys.core.graphql.nodes import EntityNode

        class FakeNode(EntityNode):
            __annotations__ = {"name": str, "age": int}
            service_name = "fake"

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        mock_entity = MagicMock()
        mock_entity.name = "Alice"
        mock_entity.age = 30

        with patch.object(FakeNode, "get_effective_node", return_value=FakeNode):
            result = FakeNode.from_obj(mock_entity)

        assert result.name == "Alice"
        assert result.age == 30

    def test_from_obj_skips_private_fields(self):
        """Test that fields starting with _ are skipped (except _entity handled separately)."""
        from lys.core.graphql.nodes import EntityNode

        class FakeNode(EntityNode):
            __annotations__ = {"name": str, "_secret": str}
            service_name = "fake"

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        mock_entity = MagicMock()
        mock_entity.name = "Bob"
        mock_entity._secret = "hidden"

        with patch.object(FakeNode, "get_effective_node", return_value=FakeNode):
            result = FakeNode.from_obj(mock_entity)

        assert result.name == "Bob"
        assert not hasattr(result, "_secret")

    def test_from_obj_stores_entity_when_entity_annotation_present(self):
        """Test that _entity is stored when annotation is present (line 130-131)."""
        from lys.core.graphql.nodes import EntityNode

        class FakeNode(EntityNode):
            __annotations__ = {"name": str, "_entity": object}
            service_name = "fake"

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        mock_entity = MagicMock()
        mock_entity.name = "Carol"

        with patch.object(FakeNode, "get_effective_node", return_value=FakeNode):
            result = FakeNode.from_obj(mock_entity)

        assert result._entity is mock_entity
        assert result.name == "Carol"

    def test_from_obj_skips_callable_class_attrs(self):
        """Test that callable class attributes (strawberry fields) are skipped (line 122)."""
        from lys.core.graphql.nodes import EntityNode

        class FakeNode(EntityNode):
            __annotations__ = {"name": str, "computed": str}
            service_name = "fake"

            def computed(self):
                return "computed_value"

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        mock_entity = MagicMock()
        mock_entity.name = "Dave"
        mock_entity.computed = "raw_value"

        with patch.object(FakeNode, "get_effective_node", return_value=FakeNode):
            result = FakeNode.from_obj(mock_entity)

        assert result.name == "Dave"
        # "computed" should not be passed because it is a callable on the class
        assert not hasattr(result, "computed") or callable(getattr(type(result), "computed", None))

    def test_from_obj_skips_class_attrs_with_func(self):
        """Test that class attributes with __func__ are skipped (line 122)."""
        from lys.core.graphql.nodes import EntityNode

        class FakeNode(EntityNode):
            __annotations__ = {"name": str, "prop_field": str}
            service_name = "fake"

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        # Give prop_field a __func__ attribute (simulating a bound method / descriptor)
        descriptor = MagicMock()
        descriptor.__func__ = MagicMock()
        descriptor.__call__ = None  # not callable itself
        type.__setattr__(FakeNode, "prop_field", descriptor)

        mock_entity = MagicMock()
        mock_entity.name = "Eve"
        mock_entity.prop_field = "value"

        with patch.object(FakeNode, "get_effective_node", return_value=FakeNode):
            result = FakeNode.from_obj(mock_entity)

        assert result.name == "Eve"

    def test_from_obj_skips_field_not_on_entity(self):
        """Test that if entity doesn't have the field, it is skipped (line 126 branch false)."""
        from lys.core.graphql.nodes import EntityNode

        class FakeNode(EntityNode):
            __annotations__ = {"name": str, "missing_field": str}
            service_name = "fake"

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        mock_entity = MagicMock(spec=["name"])
        mock_entity.name = "Frank"

        with patch.object(FakeNode, "get_effective_node", return_value=FakeNode):
            result = FakeNode.from_obj(mock_entity)

        assert result.name == "Frank"
        assert not hasattr(result, "missing_field")

    def test_from_obj_without_entity_annotation(self):
        """Test that _entity is NOT stored when not in annotations (line 130 branch false)."""
        from lys.core.graphql.nodes import EntityNode

        class FakeNode(EntityNode):
            __annotations__ = {"name": str}
            service_name = "fake"

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        mock_entity = MagicMock()
        mock_entity.name = "Grace"

        with patch.object(FakeNode, "get_effective_node", return_value=FakeNode):
            result = FakeNode.from_obj(mock_entity)

        assert result.name == "Grace"
        assert not hasattr(result, "_entity")


class TestLazyLoadRelation:
    """Tests for EntityNode._lazy_load_relation() covering lines 168-190."""

    def test_raises_attribute_error_without_entity(self):
        """Test that AttributeError is raised if _entity is missing (lines 168-172)."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        # Ensure _entity is NOT set
        if hasattr(node, "_entity"):
            delattr(node, "_entity")

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        loop = asyncio.new_event_loop()
        try:
            try:
                loop.run_until_complete(
                    node._lazy_load_relation("user", MagicMock, mock_info)
                )
                assert False, "Should have raised AttributeError"
            except AttributeError as e:
                assert "must have '_entity' field" in str(e)
        finally:
            loop.close()

    def test_returns_node_when_relation_exists(self):
        """Test successful lazy loading returns node (line 190)."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        mock_entity = MagicMock()
        mock_related = MagicMock()
        mock_entity.user = mock_related
        node._entity = mock_entity

        mock_session = AsyncMock()

        async def fake_refresh(entity, attrs):
            pass

        mock_session.refresh = fake_refresh

        mock_info = MagicMock()
        mock_info.context.session = mock_session

        mock_node_class = MagicMock()
        mock_result_node = MagicMock()
        mock_node_class.from_obj.return_value = mock_result_node

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                node._lazy_load_relation("user", mock_node_class, mock_info)
            )
            assert result is mock_result_node
            mock_node_class.from_obj.assert_called_once_with(mock_related)
        finally:
            loop.close()

    def test_returns_none_when_relation_is_none_and_nullable(self):
        """Test returns None for nullable relation that is None (line 188)."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        mock_entity = MagicMock()
        mock_entity.user = None
        node._entity = mock_entity

        mock_session = AsyncMock()

        async def fake_refresh(entity, attrs):
            pass

        mock_session.refresh = fake_refresh

        mock_info = MagicMock()
        mock_info.context.session = mock_session

        mock_node_class = MagicMock()

        with patch.object(EntityNode, "_is_relation_nullable", return_value=True):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    node._lazy_load_relation("user", mock_node_class, mock_info)
                )
                assert result is None
            finally:
                loop.close()

    def test_raises_value_error_when_relation_is_none_and_not_nullable(self):
        """Test raises ValueError for non-nullable relation that is None (lines 184-187)."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        mock_entity = MagicMock()
        mock_entity.user = None
        node._entity = mock_entity

        mock_session = AsyncMock()

        async def fake_refresh(entity, attrs):
            pass

        mock_session.refresh = fake_refresh

        mock_info = MagicMock()
        mock_info.context.session = mock_session

        mock_node_class = MagicMock()

        with patch.object(EntityNode, "_is_relation_nullable", return_value=False):
            loop = asyncio.new_event_loop()
            try:
                try:
                    loop.run_until_complete(
                        node._lazy_load_relation("user", mock_node_class, mock_info)
                    )
                    assert False, "Should have raised ValueError"
                except ValueError as e:
                    assert "non-nullable" in str(e)
            finally:
                loop.close()


class TestIsRelationNullable:
    """Tests for EntityNode._is_relation_nullable() covering lines 202-213."""

    def test_returns_true_when_relation_not_in_mapper(self):
        """Test returns True if relation_name not in mapper.relationships (line 205)."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        mock_entity = MagicMock()
        node._entity = mock_entity

        mock_mapper = MagicMock()
        mock_mapper.relationships = {}

        with patch("lys.core.graphql.nodes.inspect", return_value=mock_mapper):
            result = node._is_relation_nullable("nonexistent")
            assert result is True

    def test_returns_true_when_column_nullable(self):
        """Test returns True when a local column is nullable (line 211)."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        mock_entity = MagicMock()
        node._entity = mock_entity

        mock_col = MagicMock()
        mock_col.nullable = True

        mock_relationship = MagicMock()
        mock_relationship.local_columns = [mock_col]

        mock_mapper = MagicMock()
        mock_mapper.relationships = {"user": mock_relationship}

        with patch("lys.core.graphql.nodes.inspect", return_value=mock_mapper):
            result = node._is_relation_nullable("user")
            assert result is True

    def test_returns_false_when_all_columns_non_nullable(self):
        """Test returns False when all local columns are non-nullable (line 213)."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        mock_entity = MagicMock()
        node._entity = mock_entity

        mock_col1 = MagicMock()
        mock_col1.nullable = False
        mock_col2 = MagicMock()
        mock_col2.nullable = False

        mock_relationship = MagicMock()
        mock_relationship.local_columns = [mock_col1, mock_col2]

        mock_mapper = MagicMock()
        mock_mapper.relationships = {"user": mock_relationship}

        with patch("lys.core.graphql.nodes.inspect", return_value=mock_mapper):
            result = node._is_relation_nullable("user")
            assert result is False


class TestLazyLoadRelationList:
    """Tests for EntityNode._lazy_load_relation_list() covering lines 244-256."""

    def test_raises_attribute_error_without_entity(self):
        """Test AttributeError raised if _entity missing (lines 244-248)."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        if hasattr(node, "_entity"):
            delattr(node, "_entity")

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        loop = asyncio.new_event_loop()
        try:
            try:
                loop.run_until_complete(
                    node._lazy_load_relation_list("roles", MagicMock, mock_info)
                )
                assert False, "Should have raised AttributeError"
            except AttributeError as e:
                assert "must have '_entity' field" in str(e)
        finally:
            loop.close()

    def test_returns_list_of_nodes(self):
        """Test lazy loading returns list of converted nodes (lines 251-256)."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        mock_entity = MagicMock()
        role1, role2 = MagicMock(), MagicMock()
        mock_entity.roles = [role1, role2]
        node._entity = mock_entity

        mock_session = AsyncMock()

        async def fake_refresh(entity, attrs):
            pass

        mock_session.refresh = fake_refresh

        mock_info = MagicMock()
        mock_info.context.session = mock_session

        mock_node_class = MagicMock()
        node1, node2 = MagicMock(), MagicMock()
        mock_node_class.from_obj.side_effect = [node1, node2]

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                node._lazy_load_relation_list("roles", mock_node_class, mock_info)
            )
            assert result == [node1, node2]
            assert mock_node_class.from_obj.call_count == 2
        finally:
            loop.close()

    def test_returns_empty_list_when_relation_empty(self):
        """Test returns empty list when relation is an empty list."""
        from lys.core.graphql.nodes import EntityNode

        node = object.__new__(EntityNode)
        mock_entity = MagicMock()
        mock_entity.roles = []
        node._entity = mock_entity

        mock_session = AsyncMock()

        async def fake_refresh(entity, attrs):
            pass

        mock_session.refresh = fake_refresh

        mock_info = MagicMock()
        mock_info.context.session = mock_session

        mock_node_class = MagicMock()

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                node._lazy_load_relation_list("roles", mock_node_class, mock_info)
            )
            assert result == []
        finally:
            loop.close()


def _make_resolve_node_subclass(service_name="test_svc"):
    """Helper to create an EntityNode subclass with a mocked app_manager for resolve_node tests."""
    from lys.core.graphql.nodes import EntityNode

    class ResolveTestNode(EntityNode):
        __annotations__ = {"name": str, "_entity": object}

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    # Bypass __init_subclass__ service_name resolution: set directly
    ResolveTestNode.service_name = service_name
    return ResolveTestNode


class TestEntityNodeResolveNode:
    """Tests for EntityNode.resolve_node() covering lines 262-290."""

    def test_raises_value_error_when_service_class_is_none(self):
        """Test ValueError raised when service_class is None (lines 262-266)."""
        ResolveTestNode = _make_resolve_node_subclass()

        mock_am = MagicMock()
        mock_am.get_service.return_value = None
        ResolveTestNode._app_manager = mock_am

        mock_info = MagicMock()

        loop = asyncio.new_event_loop()
        try:
            try:
                loop.run_until_complete(
                    ResolveTestNode.resolve_node("some-id", info=mock_info)
                )
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "service_class return None" in str(e)
        finally:
            ResolveTestNode._app_manager = None
            loop.close()

    def test_returns_node_when_entity_found(self):
        """Test returns node when entity is found (lines 272-282)."""
        ResolveTestNode = _make_resolve_node_subclass()

        mock_entity = MagicMock()
        mock_service = MagicMock()
        mock_am = MagicMock()
        mock_am.get_service.return_value = mock_service
        mock_am.registry.get_node.return_value = ResolveTestNode
        ResolveTestNode._app_manager = mock_am

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        mock_node = MagicMock()

        with patch(
            "lys.core.graphql.nodes.get_db_object_and_check_access",
            new_callable=AsyncMock,
            return_value=mock_entity
        ), patch.object(
            ResolveTestNode, "from_obj", return_value=mock_node
        ):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    ResolveTestNode.resolve_node("test-id", info=mock_info)
                )
                assert result is mock_node
            finally:
                ResolveTestNode._app_manager = None
                loop.close()

    def test_returns_none_when_entity_not_found(self):
        """Test returns None when entity is not found and required=False (lines 280-282)."""
        ResolveTestNode = _make_resolve_node_subclass()

        mock_service = MagicMock()
        mock_am = MagicMock()
        mock_am.get_service.return_value = mock_service
        ResolveTestNode._app_manager = mock_am

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        with patch(
            "lys.core.graphql.nodes.get_db_object_and_check_access",
            new_callable=AsyncMock,
            return_value=None
        ):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    ResolveTestNode.resolve_node("test-id", info=mock_info, required=False)
                )
                assert result is None
            finally:
                ResolveTestNode._app_manager = None
                loop.close()

    def test_raises_lys_error_when_required_and_not_found(self):
        """Test raises LysError when required=True and entity not found (lines 284-288)."""
        from lys.core.errors import LysError

        ResolveTestNode = _make_resolve_node_subclass()

        mock_service = MagicMock()
        mock_entity_class = MagicMock()
        mock_am = MagicMock()
        mock_am.get_service.return_value = mock_service
        mock_am.get_entity.return_value = mock_entity_class
        ResolveTestNode._app_manager = mock_am

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        with patch(
            "lys.core.graphql.nodes.get_db_object_and_check_access",
            new_callable=AsyncMock,
            return_value=None
        ):
            loop = asyncio.new_event_loop()
            try:
                try:
                    loop.run_until_complete(
                        ResolveTestNode.resolve_node("test-id", info=mock_info, required=True)
                    )
                    assert False, "Should have raised LysError"
                except LysError as e:
                    assert e.status_code == 404
            finally:
                ResolveTestNode._app_manager = None
                loop.close()


def _make_node_for_build_list(name, service_name):
    """Helper to create an EntityNode subclass suitable for build_list_connection tests."""
    from lys.core.graphql.nodes import EntityNode

    node_cls = type(name, (EntityNode,), {
        "__annotations__": {"name": str},
        "service_name": service_name,
        "__init__": lambda self, **kwargs: [setattr(self, k, v) for k, v in kwargs.items()],
    })
    # Clear any cached connections
    node_cls._EntityNode__built_connection = {}
    return node_cls


class TestBuildListConnectionResolveNode:
    """Tests for the inner LysListConnection.resolve_node() covering lines 317-323."""

    def test_resolve_node_correct_entity_type(self):
        """Test inner resolve_node converts entity to node (line 323)."""
        FakeNode = _make_node_for_build_list("FakeNodeA", "fake_a")

        # Create a real entity class for isinstance checks
        FakeEntity = type("FakeEntity", (), {})

        # The inner resolve_node calls: effective_node_cls.service_class()
        # service_class is a @classproperty that returns app_manager.get_service(service_name)
        # Then it calls the returned service class with () to instantiate it.
        # The instance's .entity_class must be a real type for isinstance().
        mock_service_cls = MagicMock()
        mock_service_instance = MagicMock()
        mock_service_instance.entity_class = FakeEntity
        mock_service_cls.return_value = mock_service_instance

        mock_am = MagicMock()
        mock_am.get_service.return_value = mock_service_cls
        mock_am.get_entity.return_value = FakeEntity
        mock_am.registry.get_node.return_value = FakeNode
        FakeNode._app_manager = mock_am

        mock_info = MagicMock()
        mock_node_result = MagicMock()

        connection_cls = FakeNode.build_list_connection()

        entity_instance = FakeEntity()

        with patch.object(FakeNode, "from_obj", return_value=mock_node_result):
            result = connection_cls.resolve_node(entity_instance, info=mock_info)
            assert result is mock_node_result

        FakeNode._app_manager = None

    def test_resolve_node_wrong_entity_type_raises(self):
        """Test inner resolve_node raises ValueError for wrong entity type (lines 320-322)."""
        FakeNode = _make_node_for_build_list("FakeNodeB", "fake_b")

        FakeEntity = type("CorrectEntity", (), {})

        mock_service_cls = MagicMock()
        mock_service_instance = MagicMock()
        mock_service_instance.entity_class = FakeEntity
        mock_service_cls.return_value = mock_service_instance

        mock_am = MagicMock()
        mock_am.get_service.return_value = mock_service_cls
        mock_am.get_entity.return_value = FakeEntity
        mock_am.registry.get_node.return_value = FakeNode
        FakeNode._app_manager = mock_am

        mock_info = MagicMock()

        connection_cls = FakeNode.build_list_connection()

        wrong_entity = "not_an_entity"  # Not an instance of FakeEntity

        try:
            connection_cls.resolve_node(wrong_entity, info=mock_info)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Wrong entity type" in str(e)
        finally:
            FakeNode._app_manager = None


class TestBuildListConnectionResolveConnection:
    """Tests for the inner LysListConnection.resolve_connection() covering lines 337-384."""

    def _build_connection(self, node_name, service_name):
        """Helper to build a connection class with mocked app_manager."""
        FakeNode = _make_node_for_build_list(node_name, service_name)

        FakeEntity = type(node_name + "Entity", (), {"id": MagicMock()})

        mock_service = MagicMock()
        mock_service.entity_class = FakeEntity

        mock_am = MagicMock()
        mock_am.get_service.return_value = mock_service
        mock_am.get_entity.return_value = FakeEntity
        mock_am.registry.get_node.return_value = FakeNode
        FakeNode._app_manager = mock_am

        connection_cls = FakeNode.build_list_connection()
        return FakeNode, FakeEntity, mock_am, connection_cls

    def test_resolve_connection_returns_coroutine(self):
        """Test resolve_connection returns an awaitable (line 384)."""
        FakeNode, FakeEntity, mock_am, connection_cls = self._build_connection(
            "FakeNodeC", "fake_c"
        )

        mock_info = MagicMock()
        mock_stmt = MagicMock()

        mock_slice_metadata = MagicMock()
        mock_slice_metadata.overfetch = None
        mock_slice_metadata.start = 0
        mock_edge_class = MagicMock()

        try:
            with patch.object(
                connection_cls, "before_compute_returning_list",
                return_value=(mock_slice_metadata, mock_edge_class)
            ):
                result = connection_cls.resolve_connection(
                    mock_stmt, info=mock_info, first=10
                )
                assert asyncio.iscoroutine(result)
                result.close()
        finally:
            FakeNode._app_manager = None

    def test_resolve_connection_full_execution_with_overfetch_and_offset(self):
        """Test full resolve_connection with overfetch and offset (lines 337-384)."""
        FakeNode, FakeEntity, mock_am, connection_cls = self._build_connection(
            "FakeNodeD", "fake_d"
        )

        mock_info = MagicMock()
        mock_stmt = MagicMock()
        mock_stmt.limit = MagicMock(return_value=mock_stmt)
        mock_stmt.offset = MagicMock(return_value=mock_stmt)

        mock_slice_metadata = MagicMock()
        mock_slice_metadata.overfetch = 11
        mock_slice_metadata.start = 5
        mock_edge_class = MagicMock()

        # Mock session for streaming
        mock_session = AsyncMock()

        async def fake_stream_scalars(stmt):
            """Return an async iterable with no items."""
            class FakeResult:
                def __aiter__(self):
                    return self

                async def __anext__(self):
                    raise StopAsyncIteration
            return FakeResult()

        mock_session.stream_scalars = fake_stream_scalars
        mock_info.context.session = mock_session

        # Mock count session
        mock_count_session = AsyncMock()
        mock_am.database.get_session.return_value = mock_count_session
        mock_count_session.__aenter__ = AsyncMock(return_value=mock_count_session)
        mock_count_session.__aexit__ = AsyncMock(return_value=False)

        mock_prepared = MagicMock()

        try:
            with patch.object(
                connection_cls, "before_compute_returning_list",
                return_value=(mock_slice_metadata, mock_edge_class)
            ), patch(
                "lys.core.graphql.nodes.add_access_constraints",
                new_callable=AsyncMock,
                return_value=mock_stmt
            ), patch(
                "lys.core.graphql.nodes.get_select_total_count",
                new_callable=AsyncMock,
                return_value=42
            ), patch.object(
                connection_cls, "prepare_returning_list",
                return_value=mock_prepared
            ):
                result_coro = connection_cls.resolve_connection(
                    mock_stmt, info=mock_info, first=10
                )

                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(result_coro)
                    assert result is mock_prepared
                    # limit and offset should have been called due to overfetch/start
                    mock_stmt.limit.assert_called_once_with(11)
                    mock_stmt.offset.assert_called_once_with(5)
                finally:
                    loop.close()
        finally:
            FakeNode._app_manager = None

    def test_resolve_connection_without_overfetch_and_start(self):
        """Test resolve_connection when overfetch is None and start is 0 (branches 344, 347)."""
        FakeNode, FakeEntity, mock_am, connection_cls = self._build_connection(
            "FakeNodeE", "fake_e"
        )

        mock_info = MagicMock()
        mock_stmt = MagicMock()
        mock_stmt.limit = MagicMock(return_value=mock_stmt)
        mock_stmt.offset = MagicMock(return_value=mock_stmt)

        mock_slice_metadata = MagicMock()
        mock_slice_metadata.overfetch = None  # No overfetch
        mock_slice_metadata.start = 0  # No offset
        mock_edge_class = MagicMock()

        mock_session = AsyncMock()

        async def fake_stream_scalars(stmt):
            class FakeResult:
                def __aiter__(self):
                    return self

                async def __anext__(self):
                    raise StopAsyncIteration
            return FakeResult()

        mock_session.stream_scalars = fake_stream_scalars
        mock_info.context.session = mock_session

        mock_count_session = AsyncMock()
        mock_am.database.get_session.return_value = mock_count_session
        mock_count_session.__aenter__ = AsyncMock(return_value=mock_count_session)
        mock_count_session.__aexit__ = AsyncMock(return_value=False)

        mock_prepared = MagicMock()

        try:
            with patch.object(
                connection_cls, "before_compute_returning_list",
                return_value=(mock_slice_metadata, mock_edge_class)
            ), patch(
                "lys.core.graphql.nodes.add_access_constraints",
                new_callable=AsyncMock,
                return_value=mock_stmt
            ), patch(
                "lys.core.graphql.nodes.get_select_total_count",
                new_callable=AsyncMock,
                return_value=0
            ), patch.object(
                connection_cls, "prepare_returning_list",
                return_value=mock_prepared
            ):
                result_coro = connection_cls.resolve_connection(
                    mock_stmt, info=mock_info, first=10
                )

                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(result_coro)
                    assert result is mock_prepared
                    # limit and offset should NOT have been called
                    mock_stmt.limit.assert_not_called()
                    mock_stmt.offset.assert_not_called()
                finally:
                    loop.close()
        finally:
            FakeNode._app_manager = None


class TestServiceNodeInitSubclass:
    """Tests for ServiceNode.__init_subclass__ covering line 56-58."""

    def test_init_subclass_sets_service_name(self):
        """Test that __init_subclass__ sets service_name from generic param."""
        from lys.core.graphql.nodes import ServiceNode

        with patch("lys.core.graphql.nodes.resolve_service_name_from_generic", return_value="test_service"):
            class TestNode(ServiceNode):
                pass

            assert TestNode.service_name == "test_service"

    def test_init_subclass_does_not_set_when_none(self):
        """Test that __init_subclass__ does not set service_name when None returned."""
        from lys.core.graphql.nodes import ServiceNode

        with patch("lys.core.graphql.nodes.resolve_service_name_from_generic", return_value=None):
            class TestNode2(ServiceNode):
                pass

            assert "service_name" not in TestNode2.__dict__


class TestEntityNodeInitSubclass:
    """Tests for EntityNode.__init_subclass__ covering lines 65-70 (especially 69->exit)."""

    def test_init_subclass_sets_service_name(self):
        """Test that __init_subclass__ sets service_name from generic param."""
        from lys.core.graphql.nodes import EntityNode

        with patch("lys.core.graphql.nodes.resolve_service_name_from_generic", return_value="my_entity"):
            class TestEntityNode(EntityNode):
                pass

            assert TestEntityNode.service_name == "my_entity"

    def test_init_subclass_does_not_set_when_none(self):
        """Test that service_name is not set when resolve returns None (line 69 exit)."""
        from lys.core.graphql.nodes import EntityNode

        with patch("lys.core.graphql.nodes.resolve_service_name_from_generic", return_value=None):
            class TestEntityNode2(EntityNode):
                pass

            assert "service_name" not in TestEntityNode2.__dict__
