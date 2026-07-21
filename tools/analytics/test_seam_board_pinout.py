#!/usr/bin/env python3
"""#1338-pattern seam — **firmware pin maps ↔ the host's mirrored table**.

`board_pinouts.py` holds a copy of Sprout's recommended soil pinout so the adoption
surface (#1027 §5.2) can offer it as a one-tap default. A copy is a second source of
truth unless something checks it, and this is that something: the values are asserted
against `firmware/include/board_capability.h`, which owns them.

**Why this seam is worth a test rather than a comment.** The failure is silent and
physical. Firmware moves a pin — as it already did once, dropping strapping GPIO3 from
the S3 map on 2026-07-03 — the host keeps offering the old map, and the person who taps
"use Sprout's pinout" wires a probe to a pin that no longer works. Nothing errors; the
board simply reads wrong, or does not boot, and the evening goes to debugging hardware
that was wired exactly as the app instructed.

**The `verified` flags are checked too, and they matter more than the pins.** Two of the
three maps are *anticipated* — datasheet-derived, `cal_verified=false`, never bench
confirmed. A host that forgot which is which would present a guess in the same voice as
a measurement.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from board_pinouts import (
    PINOUT_VERIFIED,
    RECOMMENDED_SOIL_PINS,
    is_verified,
    recommended_pins,
)

_HEADER = (
    Path(__file__).resolve().parents[2] / "firmware" / "include" / "board_capability.h"
)


def _header() -> str:
    assert _HEADER.is_file(), "board_capability.h is missing — the pin owner is gone"
    return _HEADER.read_text(encoding="utf-8", errors="replace")


def _header_maps() -> dict[str, tuple[int, ...]]:
    """The header's own ``board_class -> soil pins`` pairing.

    Pairing them beats matching loose ``{a,b,c,d}`` literals anywhere in the file: a
    map attached to the WRONG board is the dangerous drift — the pins all still exist
    in the header, so a bare set-membership check would pass while the surface offered
    the S3's map to a C5.
    """
    text = _header()
    out: dict[str, tuple[int, ...]] = {}
    for m in re.finditer(r'\{"(esp32-[a-z0-9]+)"', text):
        tail = text[m.end() : m.end() + 1200]
        nums = re.search(r"\{\s*(\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*\d+)\s*\}", tail)
        if nums:  # the FIRST four-int array after the name is soil (relay follows)
            out[m.group(1)] = tuple(
                int(n) for n in nums.group(1).replace(" ", "").split(",")
            )
    return out


# --------------------------------------------------------------------------- #
# The mirror itself
# --------------------------------------------------------------------------- #
def test_each_host_pin_map_matches_its_own_board_in_the_firmware_header() -> None:
    """The mirror check, pinned per board rather than per value."""
    maps = _header_maps()
    assert maps, (
        "no board->pins pairs found in the header — the parse broke, not the pins"
    )
    for cls, pins in RECOMMENDED_SOIL_PINS.items():
        assert cls in maps, (
            f"the host offers a map for {cls!r}, a board_class the firmware does not "
            "declare — ADR-0036 §6: firmware owns the enumeration"
        )
        assert maps[cls] == pins, (
            f"{cls}: firmware says {maps[cls]}, the host offers {pins} — a pin moved "
            "and the host kept recommending the old one"
        )


def test_the_tokens_are_adr_0036_s6_qualified_and_non_prefixing() -> None:
    """§6's seven-character argument: `esp32-classic`, never bare `esp32`, which is
    both a specific chip and the family prefix of every other token. Exact matching
    makes that safe today; the qualified form makes a careless `startswith` somewhere
    downstream structurally unable to brick a board."""
    assert all(c.startswith("esp32-") for c in RECOMMENDED_SOIL_PINS)
    assert "esp32" not in RECOMMENDED_SOIL_PINS
    for a in RECOMMENDED_SOIL_PINS:
        others = [b for b in RECOMMENDED_SOIL_PINS if b != a]
        assert not any(b.startswith(a) for b in others), f"{a} prefixes another token"


def test_the_classic_map_is_the_shipping_one() -> None:
    """The classic is the baseline BOARDS.md marks *"do not change"*, and the only map
    with real bench endpoints. Pinned explicitly so a sweeping edit has to argue with
    a named expectation rather than slip past a generic check."""
    assert RECOMMENDED_SOIL_PINS["esp32-classic"] == (36, 39, 34, 35)


def test_the_s3_map_excludes_the_strapping_pin_that_was_dropped() -> None:
    """The 2026-07-03 refinement: GPIO3 is an S3 strapping pin, and a capacitive probe
    holding it during reset can disturb boot. This is the concrete instance of the
    drift this seam exists to catch — it has happened once already."""
    assert 3 not in RECOMMENDED_SOIL_PINS["esp32-s3"]


def test_the_c5_map_uses_only_pins_that_exist_on_a_c5() -> None:
    """The C5 has GPIO0-28. The classic's map (36/39/34/35) does not physically exist
    there — offering it would be confidently wrong, which is the worst kind."""
    assert all(0 <= p <= 28 for p in RECOMMENDED_SOIL_PINS["esp32-c5"])
    assert RECOMMENDED_SOIL_PINS["esp32-c5"] != RECOMMENDED_SOIL_PINS["esp32-classic"]


# --------------------------------------------------------------------------- #
# The verification flags — the field that decides suggest-vs-ask
# --------------------------------------------------------------------------- #
def test_only_the_classic_is_bench_verified() -> None:
    """The header is explicit: *"cal_verified: true ONLY for a board with real bench
    endpoints (today: classic)"*. If a flag here ever flipped without a bench session,
    the surface would start recommending a datasheet guess."""
    assert PINOUT_VERIFIED == {
        "esp32-classic": True,
        "esp32-s3": False,
        "esp32-c5": False,
    }
    assert "cal_verified" in _header()


def test_an_unknown_board_class_is_unverified_and_unrecommended() -> None:
    """Absence is first-class (ADR-0028). An unknown board must not fall back to the
    classic's pins — they may not exist on it, and they would be offered with total
    confidence."""
    assert recommended_pins("someone-elses-board") is None
    assert is_verified("someone-elses-board") is False


# --------------------------------------------------------------------------- #
# The vocabulary tie — the leaf cannot import, so the pairing is asserted here
# --------------------------------------------------------------------------- #
def test_the_registry_display_label_is_not_a_key() -> None:
    """§6: the registry's `board` string is a **display label and must never be
    parsed** — `'esp32-c5-devkitc-1 (official)'` is prose. This leaf must therefore be
    unusable with one, so a caller reaching for the wrong value gets None rather than
    a plausible-looking wrong pinout.

    Note for whoever picks up the §6 migration: `parse_v1.board_class()` still derives
    `classic`/`c5` by parsing exactly that display string, which §6 now forbids. It is
    pre-existing, cross-cutting (cal anchors and ceilings key off it), and not this
    change's to rewrite — flagged on #1027 rather than silently bridged here, because
    a quiet bridge would leave two board vocabularies alive and looking reconciled."""
    for label in ("esp32-c5-devkitc-1 (official)", "esp32dev", "classic", "c5"):
        assert recommended_pins(label) is None


def test_every_class_with_pins_has_a_verification_verdict() -> None:
    """The two tables must not drift apart: a pin map with no verdict would be
    silently treated as unverified, which is safe — but a verdict with no pins is a
    recommendation for a board we cannot describe."""
    assert set(RECOMMENDED_SOIL_PINS) == set(PINOUT_VERIFIED)
