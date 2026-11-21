"""Repository-root conftest: pytest puts this directory on sys.path, so tests can import the
evaluation helpers in poc/ with a plain `pytest -q` (as in README.md and CI).

Tests marked `baselines` drive the comparison tools from the optional `baselines` extra
(`pip install -e ".[dev,baselines]"`); they are skipped, with the reason shown, when those tools
are not installed. The `ci` workflow installs the extra, so they run there.
"""

from __future__ import annotations

import importlib.util

import pytest

BASELINE_TOOLS = ("trafilatura", "markitdown")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "baselines: needs the optional baselines extra (trafilatura, markitdown)"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    missing = [t for t in BASELINE_TOOLS if importlib.util.find_spec(t) is None]
    if not missing:
        return
    skip = pytest.mark.skip(reason="baselines extra not installed: " + ", ".join(missing))
    for item in items:
        if "baselines" in item.keywords:
            item.add_marker(skip)
