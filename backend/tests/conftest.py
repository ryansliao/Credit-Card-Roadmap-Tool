"""Shared pytest configuration.

Exposes a `--snapshot-update` CLI flag used by snapshot tests to rewrite
their committed fixtures in place instead of asserting against them.
"""
from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--snapshot-update",
        action="store_true",
        default=False,
        help="Rewrite committed snapshot fixtures with current output instead of asserting.",
    )


@pytest.fixture
def snapshot_update(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--snapshot-update"))
