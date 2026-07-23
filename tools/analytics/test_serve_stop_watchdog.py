#!/usr/bin/env python3
"""#1392 — Stop must always stop: the shutdown watchdog.

**The reported failure.** A `serve.py` process accepted `POST /quit`, entered the #972
refuse-new-requests state, and then never exited — the port stayed bound answering
``503`` indefinitely, `just processes` reported nothing live, and the next `just start`
saw the bound port and opened a tab to a dead server. DX caught it once in five
validator runs and was explicit that they had no deterministic trigger.

**The specific blocker, found by reading rather than by reproducing.** Every wait on the
stop path is bounded *except* the lock acquisitions inside the controllers' ``stop()``:
``with self._lock:`` takes no timeout, while all the timeouts in that method are on
``proc.wait``. A controller lock held by any concurrent request parks the shutdown
thread before it can reach ``os._exit`` — which fits the evidence exactly, including the
detail that the child processes really were gone (the lock, not a child, is what holds).

**Why the fix is a watchdog and not a patch on that lock.** Bounding one lock fixes the
blocker I happened to find. The defect class is *"a step on the stop path can block
without a deadline"*, and the operator-visible promise — press Stop, the server stops —
must not depend on which lock happens to be free. A deadline armed before any blocking
work holds against every such step, including ones nobody has hit yet.

**What these tests do.** They run the watchdog in a real subprocess against a real
unkillable block (a lock that is never released), because the property under test is
*"this process ceases to exist"* — which cannot be asserted from inside the process
that is supposed to die. The control case runs the identical block with no watchdog and
proves it hangs, so a green result here means the watchdog worked and not that the
scenario was survivable anyway.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
from tools.analytics.serve import (  # noqa: E402, F401
    _SHUTDOWN_DEADLINE_S,
    _arm_shutdown_watchdog,
)

# Short enough to keep the suite quick, long enough that a slow CI runner starting a
# Python process cannot be mistaken for the watchdog failing to fire.
_TEST_DEADLINE_S = 1.5
_PATIENCE_S = 15.0

_BLOCK = """
    import threading
    lock = threading.Lock()
    lock.acquire()
    lock.acquire()  # unbounded, exactly like the controllers' `with self._lock:`
"""


def _run(source: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=str(HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _armed(deadline: float) -> str:
    return f"""
    import sys
    from tools.analytics.serve import _arm_shutdown_watchdog
    _arm_shutdown_watchdog({deadline})
    {_BLOCK}
    """


# --------------------------------------------------------------------------- #
# The property itself
# --------------------------------------------------------------------------- #
def test_a_blocked_stop_path_still_exits() -> None:
    """The whole point: an unbounded block no longer means an immortal process."""
    proc = _run(_armed(_TEST_DEADLINE_S))
    try:
        proc.wait(timeout=_PATIENCE_S)
    except subprocess.TimeoutExpired:  # pragma: no cover - the bug, if it returns
        proc.kill()
        raise AssertionError(
            "the watchdog did not fire — a blocked stop path is immortal again (#1392)"
        ) from None
    assert proc.returncode == 0, (
        "Stop is what the operator asked for; a hard exit after a hang still delivers "
        f"it, so the code must be 0 (got {proc.returncode})"
    )


def test_the_block_really_is_unbounded_without_the_watchdog() -> None:
    """The control case. Without this, a green suite above could mean the scenario was
    never fatal — the test would prove nothing, and say so with a checkmark."""
    proc = _run(_BLOCK)
    try:
        proc.wait(timeout=_TEST_DEADLINE_S * 3)
        raise AssertionError(
            "the control block exited on its own — it no longer models the hang, so "
            "the watchdog test above has stopped proving anything"
        )
    except subprocess.TimeoutExpired:
        pass  # still alive, as the bug report describes
    finally:
        proc.kill()
        proc.wait(timeout=_PATIENCE_S)


def test_the_watchdog_does_not_fire_early() -> None:
    """It must never preempt a legitimately-draining stop — a watchdog that kills the
    cooperative path would turn a rare hang into routine orphaned children."""
    started = time.monotonic()
    proc = _run(_armed(_TEST_DEADLINE_S))
    proc.wait(timeout=_PATIENCE_S)
    assert time.monotonic() - started >= _TEST_DEADLINE_S * 0.8


def test_the_forced_exit_says_why() -> None:
    """A silent hard exit trades one mystery for another; the operator sees a terminal
    that closed for no stated reason. The line names the cause and the consequence."""
    proc = _run(_armed(_TEST_DEADLINE_S))
    _, err = proc.communicate(timeout=_PATIENCE_S)
    assert "forcing exit" in err
    assert "port is released" in err  # the fact that decides their next action


# --------------------------------------------------------------------------- #
# The shipped deadline, as distinct from the test's
# --------------------------------------------------------------------------- #
def test_the_shipped_deadline_clears_the_cooperative_worst_case() -> None:
    """The cooperative path's own budget is three controllers at 5s + a 2s terminate
    fallback, plus the #972 grace. The deadline must sit *past* that, or the watchdog
    would fire on a slow-but-working stop."""
    cooperative_worst_case = 3 * (5.0 + 2.0) + 2.5
    assert cooperative_worst_case < _SHUTDOWN_DEADLINE_S
