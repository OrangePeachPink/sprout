"""#1439 — the experimental-board job's "non-blocking" name must be true of EVERY step.

The v0.8.0 window's single red main was the job *named* "experimental board
(esp32s3) — non-blocking" failing the run. Root cause: `continue-on-error` was on
the compile step only, so any OTHER step (uv sync, pip install, cache) failing still
red the job — the name promised non-blocking, the wiring delivered it for one step.
It regressed because nothing tested it.

This is that test. It parses the real workflows and asserts the invariant structurally:
in every workflow that has an `experimental-boards` job, EVERY step is
`continue-on-error: true` — so no step, present or newly-added, can red the run
behind the non-blocking name. The falsehood-family principle: test the guarantee the
surface makes, not just the happy path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_WF = Path(__file__).resolve().parents[2] / ".github" / "workflows"
_FILES = [_WF / "ci.yml", _WF / "weekly-battery.yml"]


def _experimental_steps(path: Path) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    job = doc.get("jobs", {}).get("experimental-boards")
    return job["steps"] if job else []


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.name)
def test_every_step_of_the_nonblocking_job_is_continue_on_error(path: Path) -> None:
    steps = _experimental_steps(path)
    if not steps:
        pytest.skip(f"{path.name} has no experimental-boards job")
    offenders = [
        (s.get("name") or s.get("uses", "?"))
        for s in steps
        if s.get("continue-on-error") is not True
    ]
    assert not offenders, (
        f"{path.name}: these experimental-board steps can red the run despite the "
        f"'non-blocking' name — add `continue-on-error: true` (#1439): {offenders}"
    )


def test_the_job_is_actually_named_non_blocking() -> None:
    """If the name ever drops 'non-blocking', this invariant no longer needs to hold —
    so the two must be checked together, and the guarantee stays honest either way."""
    for path in _FILES:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        job = doc.get("jobs", {}).get("experimental-boards")
        if job:
            assert "non-blocking" in job["name"], path.name


def test_the_job_exists_somewhere() -> None:
    """A regex/parse that matched nothing would pass this file loudly — guard that."""
    assert any(_experimental_steps(p) for p in _FILES)
