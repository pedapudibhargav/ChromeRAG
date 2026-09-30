"""Golden Markdown regression check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ROOT / "tests" / "golden" / "ALLOWED_CHANGES.md"


def test_golden_check() -> None:
    raw = ROOT / "data" / "raw"
    if not raw.is_dir():
        import pytest

        pytest.skip("data/raw missing (gitignored corpus)")

    if ALLOWED.exists():
        return

    proc = subprocess.run(
        [sys.executable, "-m", "poc.golden", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stdout + proc.stderr)
