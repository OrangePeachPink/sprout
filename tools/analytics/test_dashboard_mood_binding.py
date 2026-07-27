"""The card-chip mood is bound 1:1 to the design system's single source of truth.

Ruling #638 (from the #596 finding): the dashboard's chip mood word had drifted
from ``mood-band-map.json`` on 3 of 7 bands, all toward drama
(submerged/overwatered/air-dry read Drowning/Soggy/Critical instead of the map's
soaked/refreshed/faint). The fix binds the chip to the map so the vocabulary has
a single source and cannot be re-authored (and re-drift) in ``dashboard.py``.

These tests lock that bind: the mood comes from the map, the map's calm words win,
and ``BAND_UI`` no longer carries an authored mood word.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.analytics.dashboard import BAND_UI, MOOD_BY_BAND

_MAP_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "design"
    / "components"
    / "mood-band-map.json"
)


def _map_moods() -> dict[str, str]:
    data = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
    return {b["fwLevel"]: b["mood"] for b in data["bands"]}


def test_mood_is_read_from_the_map_verbatim() -> None:
    # every fw level's chip mood equals the map's word, 1:1 - no transcription.
    assert _map_moods() == MOOD_BY_BAND


def test_band_ui_carries_no_authored_mood() -> None:
    # BAND_UI is (ui-name, color) only; the mood lives in the map, not here, so it
    # can't be edited into drama again without touching the design source.
    assert all(len(v) == 2 for v in BAND_UI.values())


def test_the_three_divergent_bands_are_back_on_map() -> None:
    assert MOOD_BY_BAND["submerged"] == "soaked"
    assert MOOD_BY_BAND["overwatered"] == "refreshed"
    assert MOOD_BY_BAND["air-dry"] == "faint"  # names the ambiguity, never death


def test_no_drama_words_survive() -> None:
    assert not ({"Drowning", "Soggy", "Critical"} & set(MOOD_BY_BAND.values()))


def test_every_ui_band_has_a_mood() -> None:
    # coverage: no band renders a chip with an empty mood half.
    assert all(MOOD_BY_BAND.get(fw) for fw in BAND_UI)
