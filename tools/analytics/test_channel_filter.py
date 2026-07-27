"""#993 — per-channel view filtering conveniences (a lens on the charts, not a lifecycle
state). The per-channel toggle already existed; #993 adds the two missing moves for the
maintainer's "hone in on a pair" forensics: a Show-all reset, and double-click-to-solo.
"""

from __future__ import annotations

from tools.analytics.dashboard import TEMPLATE

_H = TEMPLATE.read_text(encoding="utf-8")


def test_show_all_reset_exists_and_is_conditional() -> None:
    # the filter was one-way (re-click each to un-filter); #993 adds the reset.
    assert "function showAllChannels(" in _H
    assert "Show all" in _H
    assert "activeChannels.size < ids.length" in _H  # only shown when actually filtered


def test_double_click_solos_without_conflicting_with_toggle() -> None:
    # hone-in: double-click a chip focuses it alone; a debounced single-click keeps the
    # toggle from firing first (so the two gestures don't fight).
    assert "function soloChannel(" in _H
    assert "new Set([sid])" in _H  # solo = show only this one
    assert "__chanClickT" in _H and "'dblclick'" in _H  # debounce + double-click bound


def test_filter_stays_a_lens_never_touches_collection() -> None:
    # collection/lifecycle are untouched — solo/show-all only re-render the charts.
    solo = _H[_H.index("function soloChannel(") : _H.index("function showAllChannels(")]
    assert "applyStaticChannels()" in solo and "refresh()" in solo
    assert "registry/apply" not in solo and "lifecycle" not in solo
