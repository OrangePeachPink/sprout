"""Band casing is canonicalized at the parse boundary (#655).

Older firmware emits `dry` (lowercase) where the canon is `DRY`; case-sensitive
lookups (BAND_UI, the band index) missed and rendered a bare `?`. Normalizing the
DERIVED `Reading.band` fixes every consumer at once, while the raw payload stays
untouched.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=t  run=casing\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(sid: str, raw: int, level: str) -> str:
    ts = "2026-07-04T00:00:30.000Z"
    return (
        f"plants.soil,{ts},{ts[:-1]},sess1,classic,{sid},{raw},OK,"
        f"level={level};gpio=36\n"
    )


def _parse_body(body: str):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.csv"
        p.write_text(_HEADER + _COLS + body, encoding="utf-8")
        return parse_files([str(p)]).readings


def _read_one(level: str):
    return _parse_body(_row("s1", 2900, level))[0]


# --------------------------------------------------------------------------- #
# Reading.band - canonical casing, raw untouched
# --------------------------------------------------------------------------- #


def test_lowercase_dry_canonicalizes_to_DRY() -> None:
    r = _read_one("dry")
    assert r.band == "DRY"  # the canonical token, not the wire casing
    assert r.payload["level"] == "dry"  # ...but the raw payload is untouched


def test_already_canonical_bands_are_unchanged() -> None:
    assert _read_one("DRY").band == "DRY"
    assert _read_one("air-dry").band == "air-dry"
    assert _read_one("OK").band == "OK"


def test_mixed_case_maps_to_canonical() -> None:
    assert _read_one("Well Watered").band == "well watered"
    assert _read_one("Air-Dry").band == "air-dry"


def test_unknown_band_passes_through_unchanged() -> None:
    # no invented mapping - an unrecognized value stays as-is (renders '?' honestly)
    assert _read_one("banana").band == "banana"


def test_missing_level_is_none() -> None:
    body = "plants.soil,2026-07-04T00:00:30.000Z,x,sess1,classic,s1,2900,OK,gpio=36\n"
    assert _parse_body(body)[0].band is None


# --------------------------------------------------------------------------- #
# the AC: level=dry renders the Dry · parched chip, not '?'
# --------------------------------------------------------------------------- #


def test_lowercase_dry_renders_the_dry_chip_not_a_question_mark(tmp_path: Path) -> None:
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={"s2": {"plant_id": "p01", "plant_name": "Monstera"}},
            )
        ]
    )
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + _row("s2", 2900, "dry"), encoding="utf-8")
    s = build_context(parse_files([str(p)]), registry=reg)["sensors"][0]
    # #1234 one-vocabulary: band_ui IS the capitalized mood (derived from the
    # mood-band-map, #638); the lowercase mood field rides unchanged.
    assert s["band_ui"] == "Parched" and s["mood"] == "parched"
    assert s["band_ui"] != "?"
    assert s["band_color"] == "#E8703A"  # the real DRY colour, not the '?' grey


def test_band_ui_is_the_capitalized_mood_one_vocabulary() -> None:
    # #1234 (Design-QA ruling, ADR-0035): the rendered band word IS the mood word,
    # capitalized, DERIVED from mood-band-map (never a second authored copy — #638).
    # Same word, same meaning as the Home; the fw level stays the wire layer.
    from dashboard import BAND_UI, MOOD_BY_BAND

    assert MOOD_BY_BAND, "the design map must be present in a full checkout"
    for fw, (word, _color) in BAND_UI.items():
        assert word == MOOD_BY_BAND[fw].capitalize()
    assert BAND_UI["DRY"][0] == "Parched"  # the wilt band carries the alarming word
    assert BAND_UI["submerged"][0] == "Soaked"
    assert BAND_UI["air-dry"][0] == "Faint"
