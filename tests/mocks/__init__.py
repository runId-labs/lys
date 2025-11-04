"""
Mock utilities for lys framework testing.

This package provides mocks and utilities to simplify unit testing
of lys components that depend on app_manager.
"""

from tests.mocks.app_manager import MockAppManager
from tests.mocks.utils import configure_classes_for_testing

__all__ = [
    "MockAppManager",
    "configure_classes_for_testing",
]
