"""
Pytest configuration for integration tests.

Integration tests are run in forked subprocesses to ensure complete isolation
from unit tests. This prevents the LysAppRegistry singleton and Python module
cache from polluting test state across test suites.
"""

import pytest


def pytest_collection_modifyitems(items):
    """
    Automatically mark all integration tests to run in forked subprocess.

    This ensures that integration tests don't pollute the global state
    (LysAppRegistry singleton, module cache) for unit tests.
    """
    for item in items:
        # Add forked marker to all tests in this directory
        item.add_marker(pytest.mark.forked)
