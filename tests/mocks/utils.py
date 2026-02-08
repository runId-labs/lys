"""
Utility functions for test setup.

Provides helpers to configure multiple components at once
and reduce test boilerplate.
"""

from typing import Type, List

from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.orm.decl_api import MappedColumn


def has_relationship(entity_class: Type, attr_name: str) -> bool:
    """
    Check if a SQLAlchemy entity class has a relationship attribute.

    Inspects the class hierarchy __dict__ directly to avoid triggering
    'Unmanaged access of declarative attribute' warnings
    that occur with hasattr() on non-mapped classes.

    Args:
        entity_class: The SQLAlchemy entity class to inspect.
        attr_name: The relationship attribute name to check.

    Returns:
        True if a relationship with this name exists on the class.
    """
    for cls in entity_class.__mro__:
        if attr_name in cls.__dict__:
            descriptor = cls.__dict__[attr_name]
            if isinstance(descriptor, RelationshipProperty):
                return True
            # Also check for MappedColumn-wrapped or descriptor-based relationships
            if hasattr(descriptor, "property") and isinstance(descriptor.property, RelationshipProperty):
                return True
            # Attribute exists in the class dict (relationship descriptors)
            return True
    return False

# Global tracking of configured classes for automatic cleanup
_test_configured_classes = []


def track_configured_class(cls: Type):
    """
    Track a class that has been configured for testing.

    This is used by conftest.py auto_cleanup_app_managers fixture
    to automatically reset classes after tests.
    """
    if cls not in _test_configured_classes:
        _test_configured_classes.append(cls)


def get_tracked_classes():
    """Get list of tracked classes."""
    return _test_configured_classes.copy()


def clear_tracked_classes():
    """Clear the tracking list."""
    _test_configured_classes.clear()


def configure_classes_for_testing(mock_app_manager, *classes: Type):
    """
    Configure multiple classes to use the mock app_manager.

    This utility calls configure_app_manager_for_testing() on each class,
    reducing boilerplate when testing components that interact with each other.

    IMPORTANT: Classes configured with this function are automatically
    tracked and will be cleaned up after the test completes.

    Args:
        mock_app_manager: MockAppManager instance to inject
        *classes: Variable number of service/node/fixture classes to configure

    Example:
        mock_app = MockAppManager()
        mock_app.register_entity("users", User)
        mock_app.register_service("users", UserService)

        configure_classes_for_testing(
            mock_app,
            UserService,
            EmailService,
            UserNode
        )

        # Now all classes use mock_app
        # Cleanup happens automatically after test!
    """
    for cls in classes:
        if hasattr(cls, "configure_app_manager_for_testing"):
            cls.configure_app_manager_for_testing(mock_app_manager)
            track_configured_class(cls)
        else:
            # Warn if class doesn't support configuration
            class_name = cls.__name__ if hasattr(cls, "__name__") else str(cls)
            print(
                f"Warning: {class_name} does not have configure_app_manager_for_testing() method"
            )


def reset_class_app_managers(*classes: Type):
    """
    Reset app_manager to None for given classes.

    Useful in test teardown to ensure clean state.

    Args:
        *classes: Classes to reset

    Example:
        def teardown():
            reset_class_app_managers(UserService, EmailService)
    """
    for cls in classes:
        if hasattr(cls, "_app_manager"):
            cls._app_manager = None
