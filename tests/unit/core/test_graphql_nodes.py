import inspect
from typing import Generic

import pytest


class TestServiceNodeMixinStructure:
    """Verify ServiceNodeMixin class exists and has the expected interface."""

    def test_class_exists(self):
        from lys.core.graphql.nodes import ServiceNodeMixin

        assert inspect.isclass(ServiceNodeMixin)

    def test_has_get_node_by_name_classmethod(self):
        from lys.core.graphql.nodes import ServiceNodeMixin

        assert hasattr(ServiceNodeMixin, "get_node_by_name")
        method = getattr(ServiceNodeMixin, "get_node_by_name")
        assert isinstance(inspect.getattr_static(ServiceNodeMixin, "get_node_by_name"), classmethod)

    def test_get_node_by_name_signature(self):
        from lys.core.graphql.nodes import ServiceNodeMixin

        sig = inspect.signature(ServiceNodeMixin.get_node_by_name)
        param_names = list(sig.parameters.keys())
        assert "name" in param_names

    def test_has_get_effective_node_classmethod(self):
        from lys.core.graphql.nodes import ServiceNodeMixin

        assert hasattr(ServiceNodeMixin, "get_effective_node")
        assert isinstance(inspect.getattr_static(ServiceNodeMixin, "get_effective_node"), classmethod)

    def test_get_node_by_name_is_sync(self):
        from lys.core.graphql.nodes import ServiceNodeMixin

        assert not inspect.iscoroutinefunction(ServiceNodeMixin.get_node_by_name)

    def test_get_effective_node_is_sync(self):
        from lys.core.graphql.nodes import ServiceNodeMixin

        assert not inspect.iscoroutinefunction(ServiceNodeMixin.get_effective_node)


class TestServiceNodeStructure:
    """Verify ServiceNode class exists and uses Generic."""

    def test_class_exists(self):
        from lys.core.graphql.nodes import ServiceNode

        assert inspect.isclass(ServiceNode)

    def test_uses_generic(self):
        from lys.core.graphql.nodes import ServiceNode

        # Check that ServiceNode has Generic in its MRO or origin
        origin_bases = getattr(ServiceNode, "__orig_bases__", ())
        has_generic = any(
            getattr(base, "__origin__", None) is Generic
            or (hasattr(base, "__origin__") and base.__origin__ is Generic)
            or base is Generic
            for base in origin_bases
        ) or Generic in ServiceNode.__mro__
        # If the class itself is Generic[T], the __orig_bases__ will contain it
        assert has_generic or any("Generic" in str(b) for b in origin_bases)

    def test_inherits_from_service_node_mixin(self):
        from lys.core.graphql.nodes import ServiceNode, ServiceNodeMixin

        assert issubclass(ServiceNode, ServiceNodeMixin)

    def test_has_init_subclass(self):
        from lys.core.graphql.nodes import ServiceNode

        # __init_subclass__ is defined on ServiceNode (not just inherited from object)
        assert "__init_subclass__" in ServiceNode.__dict__


class TestEntityNodeStructure:
    """Verify EntityNode class exists, uses Generic, and has the expected methods."""

    def test_class_exists(self):
        from lys.core.graphql.nodes import EntityNode

        assert inspect.isclass(EntityNode)

    def test_uses_generic(self):
        from lys.core.graphql.nodes import EntityNode

        origin_bases = getattr(EntityNode, "__orig_bases__", ())
        assert any("Generic" in str(b) for b in origin_bases)

    def test_inherits_from_service_node_mixin(self):
        from lys.core.graphql.nodes import EntityNode, ServiceNodeMixin

        assert issubclass(EntityNode, ServiceNodeMixin)

    def test_has_from_obj_classmethod(self):
        from lys.core.graphql.nodes import EntityNode

        assert hasattr(EntityNode, "from_obj")
        assert isinstance(inspect.getattr_static(EntityNode, "from_obj"), classmethod)

    def test_from_obj_signature(self):
        from lys.core.graphql.nodes import EntityNode

        sig = inspect.signature(EntityNode.from_obj)
        param_names = list(sig.parameters.keys())
        assert "entity" in param_names

    def test_has_lazy_load_relation_method(self):
        from lys.core.graphql.nodes import EntityNode

        assert hasattr(EntityNode, "_lazy_load_relation")

    def test_lazy_load_relation_is_async(self):
        from lys.core.graphql.nodes import EntityNode

        assert inspect.iscoroutinefunction(EntityNode._lazy_load_relation)

    def test_lazy_load_relation_signature(self):
        from lys.core.graphql.nodes import EntityNode

        sig = inspect.signature(EntityNode._lazy_load_relation)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "relation_name" in param_names
        assert "node_class" in param_names
        assert "info" in param_names

    def test_has_lazy_load_relation_list_method(self):
        from lys.core.graphql.nodes import EntityNode

        assert hasattr(EntityNode, "_lazy_load_relation_list")

    def test_lazy_load_relation_list_is_async(self):
        from lys.core.graphql.nodes import EntityNode

        assert inspect.iscoroutinefunction(EntityNode._lazy_load_relation_list)

    def test_lazy_load_relation_list_signature(self):
        from lys.core.graphql.nodes import EntityNode

        sig = inspect.signature(EntityNode._lazy_load_relation_list)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "relation_name" in param_names
        assert "node_class" in param_names
        assert "info" in param_names

    def test_has_is_relation_nullable_method(self):
        from lys.core.graphql.nodes import EntityNode

        assert hasattr(EntityNode, "_is_relation_nullable")

    def test_is_relation_nullable_is_sync(self):
        from lys.core.graphql.nodes import EntityNode

        assert not inspect.iscoroutinefunction(EntityNode._is_relation_nullable)

    def test_is_relation_nullable_signature(self):
        from lys.core.graphql.nodes import EntityNode

        sig = inspect.signature(EntityNode._is_relation_nullable)
        param_names = list(sig.parameters.keys())
        assert "self" in param_names
        assert "relation_name" in param_names

    def test_has_resolve_node_classmethod(self):
        from lys.core.graphql.nodes import EntityNode

        assert hasattr(EntityNode, "resolve_node")
        assert isinstance(inspect.getattr_static(EntityNode, "resolve_node"), classmethod)

    def test_resolve_node_is_async(self):
        from lys.core.graphql.nodes import EntityNode

        # resolve_node is a classmethod, so we inspect it directly
        assert inspect.iscoroutinefunction(EntityNode.resolve_node)

    def test_resolve_node_signature(self):
        from lys.core.graphql.nodes import EntityNode

        sig = inspect.signature(EntityNode.resolve_node)
        param_names = list(sig.parameters.keys())
        assert "node_id" in param_names

    def test_has_build_list_connection_classmethod(self):
        from lys.core.graphql.nodes import EntityNode

        assert hasattr(EntityNode, "build_list_connection")
        assert isinstance(inspect.getattr_static(EntityNode, "build_list_connection"), classmethod)

    def test_build_list_connection_is_sync(self):
        from lys.core.graphql.nodes import EntityNode

        assert not inspect.iscoroutinefunction(EntityNode.build_list_connection)

    def test_has_init_subclass(self):
        from lys.core.graphql.nodes import EntityNode

        assert "__init_subclass__" in EntityNode.__dict__


class TestParametricNodeFunction:
    """Verify parametric_node function exists and is callable."""

    def test_function_exists(self):
        from lys.core.graphql.nodes import parametric_node

        assert callable(parametric_node)

    def test_is_function(self):
        from lys.core.graphql.nodes import parametric_node

        assert inspect.isfunction(parametric_node)

    def test_signature_has_service_class_param(self):
        from lys.core.graphql.nodes import parametric_node

        sig = inspect.signature(parametric_node)
        param_names = list(sig.parameters.keys())
        assert "service_class" in param_names

    def test_is_not_async(self):
        from lys.core.graphql.nodes import parametric_node

        assert not inspect.iscoroutinefunction(parametric_node)


class TestSuccessNodeStructure:
    """Verify SuccessNode class exists and has expected attributes."""

    def test_class_exists(self):
        from lys.core.graphql.nodes import SuccessNode

        assert inspect.isclass(SuccessNode)

    def test_has_succeed_attribute(self):
        from lys.core.graphql.nodes import SuccessNode

        annotations = {}
        for cls in SuccessNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "succeed" in annotations

    def test_succeed_attribute_is_bool(self):
        from lys.core.graphql.nodes import SuccessNode

        annotations = {}
        for cls in SuccessNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert annotations["succeed"] is bool

    def test_has_message_attribute(self):
        from lys.core.graphql.nodes import SuccessNode

        annotations = {}
        for cls in SuccessNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "message" in annotations

    def test_message_attribute_is_optional_str(self):
        import typing
        from lys.core.graphql.nodes import SuccessNode

        annotations = {}
        for cls in SuccessNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        msg_type = annotations["message"]
        # Check that it is Optional[str] (Union[str, None] or Optional[str])
        origin = getattr(msg_type, "__origin__", None)
        if origin is typing.Union:
            args = msg_type.__args__
            assert str in args
            assert type(None) in args
        else:
            # In newer Python, Optional[str] might be str | None
            assert "str" in str(msg_type)
