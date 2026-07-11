"""#979 + #980 — the recording-honesty cluster (template contract).

The cluster law (Design-QA): the #980 button face, the #974 status line, and the #979
banner are three views of ONE state (`st.collecting`), and must never disagree. These
assert the template wires exactly that: one dual-state button, and a banner that fires
only on the stopped-but-live state.
"""

from __future__ import annotations

from pathlib import Path

_TPL = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(
    encoding="utf-8"
)


def _script() -> str:
    import re

    return "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", _TPL, re.S))


# --------------------------------------------------------------------------- #
# #980 — one dual-state button, its face IS the state
# --------------------------------------------------------------------------- #


def test_one_toggle_button_replaces_the_two_button_pair() -> None:
    assert _TPL.count('id="collToggle"') == 1
    # the old two-button pair is gone from the markup (no dead disabled Stop button)
    assert 'id="collStart"' not in _TPL
    assert 'id="collStop"' not in _TPL


def test_button_face_is_driven_by_collecting_state() -> None:
    js = _script()
    # collRender reads st.collecting and picks the face from it
    assert "collToggle" in js
    assert "Stop logging" in js and "Start logging" in js  # both faces
    # Stop is neutral, not danger-red (stopping logging isn't destructive)
    assert "'btn' + (on ? '' : ' primary')" in js


def test_transitional_faces_are_present_and_disabled() -> None:
    js = _script()
    assert "starting…" in js and "stopping…" in js
    assert "_collTransition" in js  # the transitional helper disables the button


def test_a_refusal_shows_in_the_status_line_not_on_the_button() -> None:
    # DesignQA: the button face stays a clean state readout; errors go to collStatus
    js = _script()
    assert "capstatus err" in js  # the refusal styling targets the status box


# --------------------------------------------------------------------------- #
# #979 — the recording banner, only on stopped-but-live
# --------------------------------------------------------------------------- #


def test_banner_element_and_render_exist() -> None:
    assert 'id="recBanner"' in _TPL
    assert "function renderRecordingBanner" in _script()


def test_banner_fires_only_when_stopped_and_live_rows_present() -> None:
    js = _script()
    # the exact trigger: collection stopped (__collecting false) AND rows on screen -
    # never on 'unknown' (pre-poll null), never while recording.
    assert "__collecting === false && rows > 0" in js


def test_banner_carries_the_locked_copy_and_the_unsaved_honesty() -> None:
    js = _script()
    assert "Viewing live sensors — not recording." in js
    assert "Start logging to save." in js
    assert "unsaved" in js  # the word that does the count honesty (never a bare count)


def test_banner_is_calm_not_a_fault() -> None:
    # the recbanner styling uses the muted/info register, never the fault alarm color
    assert ".recbanner" in _TPL
    css = _TPL[_TPL.index(".recbanner") : _TPL.index(".recbanner") + 500]
    assert "var(--muted)" in css


def test_cluster_shares_one_source() -> None:
    js = _script()
    # __collecting is set in collRender (the one place status resolves) and read by the
    # banner — so button + banner can't disagree.
    assert "__collecting = on" in js
    assert "renderRecordingBanner()" in js  # collRender keeps the banner in lockstep


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
