"""Tests for the fresh-checkout empty state (#543): `/` and `/data.json` used to
500 with "no readings parsed from []" the moment a genuinely fresh checkout (no
`logs/` yet) served the dashboard - blocking #186's "clean machine -> it works"
promise. This covers both the pure-function contract and the real HTTP behavior.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from serve import NoDataYet, _context, _empty_state_html

_SERVE = Path(__file__).resolve().parent / "serve.py"

_HEADER = "# fw=0.7.0  git=test123  run=t\n"
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)
_ROW = (
    "plants.soil,2026-06-28T00:00:30.000Z,2026-06-28T00:00:30.000,"
    "sess1,s1,1500,OK,level=well watered;gpio=36\n"
)


# --------------------------------------------------------------------------- #
# _context() / NoDataYet - pure-function contract
# --------------------------------------------------------------------------- #


def test_empty_dir_raises_no_data_yet_not_had_any_logged(tmp_path: Path) -> None:
    raised = None
    try:
        _context([str(tmp_path)])
    except NoDataYet as exc:
        raised = exc
    assert raised is not None, "an empty dir must raise NoDataYet, not a bare 500"
    assert raised.had_any_logged is False


def test_filtered_to_zero_raises_had_any_logged_true(tmp_path: Path) -> None:
    log = tmp_path / "a.csv"
    log.write_text(_HEADER + _COLS + _ROW, encoding="utf-8")
    raised = None
    try:
        # a channel that doesn't exist in this log - filters everything out, but
        # real data DID exist, so this must not claim "fresh checkout"
        _context([str(log)], channels=["s9"])
    except NoDataYet as exc:
        raised = exc
    assert raised is not None
    assert raised.had_any_logged is True


def test_real_data_does_not_raise(tmp_path: Path) -> None:
    log = tmp_path / "a.csv"
    log.write_text(_HEADER + _COLS + _ROW, encoding="utf-8")
    ctx = _context([str(log)])
    assert ctx["sensors"]  # normal path unaffected


# --------------------------------------------------------------------------- #
# _empty_state_html() - copy must not overclaim
# --------------------------------------------------------------------------- #


def test_fresh_checkout_copy_says_nothing_logged() -> None:
    html = _empty_state_html(had_any_logged=False)
    assert "fresh checkout" in html
    assert "filter" not in html.lower()


def test_filtered_copy_does_not_claim_fresh_checkout() -> None:
    html = _empty_state_html(had_any_logged=True)
    assert "fresh checkout" not in html
    assert "filter" in html.lower()


# --------------------------------------------------------------------------- #
# _empty_state_html() - the install-day launchpad (#644)
# --------------------------------------------------------------------------- #


def test_fresh_checkout_carries_a_working_start_control() -> None:
    # the operator's "one Start" must be reachable at zero data (chicken-and-egg
    # before #644: the shell's button only rendered once data existed).
    html = _empty_state_html(had_any_logged=False)
    assert 'id="collStart"' in html
    assert "Start logging" in html  # #923: one collection action, consistent vocab
    # and it wires to ADR-0014's one action, not a dead button
    assert "/collection/start" in html


def test_filtered_state_has_no_start_control() -> None:
    # data already exists in the filtered case - the fix is to clear the filter,
    # not to start collecting, so no Start button belongs there.
    html = _empty_state_html(had_any_logged=True)
    assert "collStart" not in html
    assert 'href="/"' in html  # a real way back to the unfiltered view


def test_empty_state_uses_a_real_font_token() -> None:
    # regression: the page referenced var(--font-body), which sprout-tokens.css
    # does not define, so first-run text fell back to an off-brand serif (#644).
    for html in (
        _empty_state_html(had_any_logged=False),
        _empty_state_html(had_any_logged=True),
    ):
        assert "var(--font-body)" not in html
        assert "var(--font-ui)" in html


# --------------------------------------------------------------------------- #
# End-to-end: the literal #543 repro against a real running server
# --------------------------------------------------------------------------- #


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_fresh_checkout_serves_200_not_500(tmp_path: Path) -> None:
    port = _free_port()
    # --no-autostart (#872): keep the e2e hermetic — don't probe serial/fleet on launch
    proc = subprocess.Popen(
        [
            sys.executable,
            str(_SERVE),
            str(tmp_path),
            "--port",
            str(port),
            "--no-autostart",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        up = False
        for _ in range(60):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    up = True
                    break
            except OSError:
                time.sleep(0.1)
        assert up, "server must come up even with zero logs to discover"

        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
                assert resp.status == 200
                body = resp.read().decode("utf-8")
                assert "fresh checkout" in body
                # #644: the install-day Start control survives the real HTTP path,
                # not just the pure function - the "one Start" is reachable here.
                assert 'id="collStart"' in body
                assert "/collection/start" in body
        except urllib.error.HTTPError as exc:
            raise AssertionError(f"/ must not 500 on a fresh checkout: {exc}") from exc

        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/data.json", timeout=5
            ) as resp:
                assert resp.status == 200
                doc = json.loads(resp.read().decode("utf-8"))
                assert doc["empty"] is True
                assert doc["had_any_logged"] is False
        except urllib.error.HTTPError as exc:
            raise AssertionError(
                f"/data.json must not 500 on a fresh checkout: {exc}"
            ) from exc
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    import tempfile

    for fn in (
        test_empty_dir_raises_no_data_yet_not_had_any_logged,
        test_filtered_to_zero_raises_had_any_logged_true,
        test_real_data_does_not_raise,
    ):
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    test_fresh_checkout_copy_says_nothing_logged()
    print("  PASS  test_fresh_checkout_copy_says_nothing_logged")
    test_filtered_copy_does_not_claim_fresh_checkout()
    print("  PASS  test_filtered_copy_does_not_claim_fresh_checkout")
    with tempfile.TemporaryDirectory() as d:
        test_fresh_checkout_serves_200_not_500(Path(d))
    print("  PASS  test_fresh_checkout_serves_200_not_500")
    print("All checks passed.")
