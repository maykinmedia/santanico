import pytest

MEMRAY_MARKERS = ("limit_memory", "limit_leaks")


def pytest_runtest_setup(item):
    if any(
        item.get_closest_marker(m) for m in MEMRAY_MARKERS
    ) and not item.config.getoption("--memray", False):
        pytest.skip("Test requires --memray flag to profile memory usage")
