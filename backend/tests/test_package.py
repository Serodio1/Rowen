"""Smoke test: proves the package is installed and the test toolchain runs.

It is replaced by real engine tests in Phase 1.
"""

import rowen


def test_package_is_importable() -> None:
    assert rowen.__name__ == "rowen"
