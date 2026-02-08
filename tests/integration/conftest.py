"""
Pytest configuration for integration tests.

Integration tests are run in forked subprocesses to ensure complete isolation
from unit tests. This prevents the LysAppRegistry singleton and Python module
cache from polluting test state across test suites.

When coverage is active (--cov), forked child processes are patched to start
and save their own coverage data, allowing proper coverage collection.
"""

import os

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


def pytest_configure(config):
    """
    Patch pytest-forked to collect coverage inside forked child processes.

    Without this patch, coverage data from forked subprocesses is lost because
    os.fork() copies the parent process memory but the child exits via os._exit()
    without saving coverage data. This patch wraps the test execution in each
    child process with coverage.start() / coverage.stop() / coverage.save().
    """
    # Only patch when coverage collection is requested
    cov_source = getattr(getattr(config, "option", None), "cov_source", None)
    if not cov_source:
        return

    try:
        import pytest_forked
        import coverage as coverage_mod
    except ImportError:
        return

    _original_forked_run_report = pytest_forked.forked_run_report

    def _coverage_forked_run_report(item):
        from _pytest import runner
        from _pytest.runner import runtestprotocol
        from pytest_forked import serialize_report
        import marshal
        import py

        EXITSTATUS_TESTEXIT = 4
        config_file = str(item.config.rootpath / "pyproject.toml")

        def runforked():
            cov = coverage_mod.Coverage(
                data_suffix=True,
                config_file=config_file,
            )
            cov.start()
            try:
                reports = runtestprotocol(item, log=False)
            except KeyboardInterrupt:
                cov.stop()
                cov.save()
                os._exit(EXITSTATUS_TESTEXIT)
            cov.stop()
            cov.save()
            return marshal.dumps([serialize_report(x) for x in reports])

        ff = py.process.ForkedFunc(runforked)
        result = ff.waitfinish()
        if result.retval is not None:
            report_dumps = marshal.loads(result.retval)
            return [runner.TestReport(**x) for x in report_dumps]
        else:
            if result.exitstatus == EXITSTATUS_TESTEXIT:
                pytest.exit(f"forked test item {item} raised Exit")
            return pytest_forked.report_process_crash(item, result)

    pytest_forked.forked_run_report = _coverage_forked_run_report
