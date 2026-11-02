"""Regression test for `snapforge.main --self-test`.

This is deliberately a subprocess test, not a direct function call: the
whole point of `--self-test` (see its docstring in `main.py`) is to be run
against a real, separately-launched process — including a packaged
PyInstaller binary, which this can't invoke from inside the test suite
itself. Running it as a subprocess here at least catches the common case:
a code change that breaks `--self-test` before it ever reaches a packaging
step in CI or a release checklist.
"""

from __future__ import annotations

import os
import subprocess
import sys


def test_self_test_entrypoint_passes():
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    result = subprocess.run(
        [sys.executable, "-m", "snapforge.main", "--self-test"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"--self-test exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "[self-test] PASS" in result.stdout
