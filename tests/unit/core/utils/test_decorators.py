"""
Unit tests for core utils decorators module.

Tests decorator functions.
"""

import pytest


class TestSingletonDecorator:
    """Tests for singleton decorator."""

    def test_decorator_exists(self):
        """Test singleton decorator exists."""
        from lys.core.utils.decorators import singleton
        assert singleton is not None
        assert callable(singleton)

    def test_creates_singleton_instance(self):
        """Test singleton creates only one instance."""
        from lys.core.utils.decorators import singleton

        @singleton
        class TestClass:
            def __init__(self, value):
                self.value = value

        instance1 = TestClass(1)
        instance2 = TestClass(2)
        assert instance1 is instance2

    def test_init_called_only_once(self):
        """Test __init__ is called only once."""
        from lys.core.utils.decorators import singleton

        call_count = 0

        @singleton
        class TestClass:
            def __init__(self):
                nonlocal call_count
                call_count += 1

        TestClass()
        TestClass()
        TestClass()
        assert call_count == 1

    def test_preserves_instance_attributes(self):
        """Test singleton preserves instance attributes."""
        from lys.core.utils.decorators import singleton

        @singleton
        class TestClass:
            def __init__(self, value):
                self.value = value

        instance1 = TestClass(42)
        instance2 = TestClass(100)  # Should not change value
        assert instance1.value == 42
        assert instance2.value == 42

    def test_preserves_class_name(self):
        """Test singleton preserves class name."""
        from lys.core.utils.decorators import singleton

        @singleton
        class MyTestClass:
            pass

        assert MyTestClass.__name__ == "MyTestClass"

    def test_preserves_class_module(self):
        """Test singleton preserves class module."""
        from lys.core.utils.decorators import singleton

        @singleton
        class TestClass:
            pass

        assert TestClass.__module__ == __name__

    def test_has_is_singleton_attribute(self):
        """Test singleton class has __is_singleton__ attribute."""
        from lys.core.utils.decorators import singleton

        @singleton
        class TestClass:
            pass

        assert hasattr(TestClass, "__is_singleton__")
        assert TestClass.__is_singleton__ is True

    def test_raises_on_double_decoration(self):
        """Test singleton raises if class is already singleton."""
        from lys.core.utils.decorators import singleton

        @singleton
        class TestClass:
            pass

        with pytest.raises(Exception) as exc_info:
            singleton(TestClass)
        assert "already a singleton" in str(exc_info.value)

    def test_has_reset_singleton_method(self):
        """Test singleton class has reset_singleton method."""
        from lys.core.utils.decorators import singleton

        @singleton
        class TestClass:
            pass

        assert hasattr(TestClass, "reset_singleton")
        assert callable(TestClass.reset_singleton)

    def test_reset_singleton_allows_new_instance(self):
        """Test reset_singleton allows creating new instance."""
        from lys.core.utils.decorators import singleton

        @singleton
        class TestClass:
            def __init__(self, value):
                self.value = value

        instance1 = TestClass(1)
        TestClass.reset_singleton()
        instance2 = TestClass(2)

        assert instance1 is not instance2
        assert instance1.value == 1
        assert instance2.value == 2

    def test_thread_safety(self):
        """Test singleton is thread-safe."""
        from lys.core.utils.decorators import singleton
        import threading

        @singleton
        class TestClass:
            def __init__(self):
                self.value = 0

        instances = []

        def create_instance():
            instances.append(TestClass())

        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All instances should be the same
        first = instances[0]
        for instance in instances:
            assert instance is first
