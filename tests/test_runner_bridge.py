"""Pytest bridge para el runner custom de Eikon.

El runner historico `tests/test_eikon_checks.py` sigue siendo la fuente de
verdad. Este archivo solo permite que `pytest` y CI lo ejecuten como gate.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "tests" / "test_eikon_checks.py"


def _run_runner() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.slow
def test_custom_runner_exits_zero() -> None:
    """El runner custom debe terminar con exit 0."""
    proc = _run_runner()
    assert proc.returncode == 0, (
        f"runner fallo (rc={proc.returncode})\n"
        f"--- stdout ---\n{proc.stdout[-2500:]}\n"
        f"--- stderr ---\n{proc.stderr[-1000:]}"
    )


@pytest.mark.slow
def test_custom_runner_reports_passing_checks() -> None:
    """Sanity: el runner no fue no-op y reporta checks exitosos."""
    proc = _run_runner()
    assert proc.returncode == 0
    assert "Resultado:" in proc.stdout
    assert "✓" in proc.stdout
    assert "0 ✗" in proc.stdout
    assert "Todos los checks pasaron" in proc.stdout
