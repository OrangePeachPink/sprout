"""#1551 B1 — the stop control exists on Home, in BOTH states."""

from __future__ import annotations

from pathlib import Path

_TPL = Path(__file__).resolve().parent / "home_template.html"
_H = _TPL.read_text(encoding="utf-8")


def test_the_stop_control_is_page_chrome_not_painted_content() -> None:
    """The zero state returns early from paint(), so a control painted with the cards
    would be MISSING on first run -- the moment someone most needs to stop an app they
    started to look at nothing. It lives in the static chrome, outside <main>."""
    assert 'id="quitBtn"' in _H
    chrome = _H[_H.index("<body>") : _H.index("<script>")]
    assert 'id="quitBtn"' in chrome  # present before any JS runs
    assert '<footer class="dangerzone">' in chrome
    # and it is NOT inside the element paint() clears
    main = chrome[chrome.index("<main") : chrome.index("</main>") + 7]
    assert "quitBtn" not in main


def test_it_is_two_step_never_a_one_click_kill() -> None:
    body = _H[_H.index("function stopServer(") : _H.index("function paint(")]
    assert "_quitArmed" in body
    assert "Press again to confirm" in body
    assert "4000" in body  # an armed button auto-cancels; never left hot
    # the POST only happens on the SECOND press -- after the armed early return
    arm_return = body.index("return;")
    assert body.index('fetch("/quit"') > arm_return


def test_it_cancels_the_poll_before_shutting_down() -> None:
    """A refresh racing the shutdown paints a network error over a deliberate action."""
    assert "var _poll = setInterval(refresh, 90000);" in _H
    body = _H[_H.index("function stopServer(") : _H.index("function paint(")]
    assert body.index("clearInterval(_poll)") < body.index('fetch("/quit"')


def test_the_danger_colour_is_the_confirm_signal_not_the_resting_state() -> None:
    """--st-fault is spent at the decision point, not before it."""
    assert ".btn.danger.armed { background: var(--st-fault)" in _H
    resting = _H[_H.index(".btn.danger {") : _H.index(".btn.danger:hover")]
    assert "--st-fault" not in resting
