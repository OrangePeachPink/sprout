"""Cross-board comparability guard (#832) — raw is not comparable across boards.

Status: legacy — the prohibition this module guarded was PROMOTED, not dropped: it
now lives in ADR constants and the seam suite, and the comparison capability ships
in #832's renderings. Kept because the rule still holds and this is where its
reasoning is written down (#1388). Marked legacy so the protection reads as
promoted rather than abandoned — the distinction a bare "unused" would destroy.

Different boards have different ADCs (the classic ESP32 and the C5 differ in
reference / attenuation / dynamic range), so a raw ADC count — and anything derived
from it on one shared ruler, like the ``dryness`` scalar (a single ``mrange`` maps
raw → 0..1) — is NOT comparable across boards without per-board cal mediating
(ADR-0019 / #170). Applying the classic-endpoint ``mrange`` to a C5 reading mislabels
it (#832: p03 read "dry · parched" on classic endpoints when on its own #667 anchors
it is dry, not parched).

The honest cross-board layer is the calibrated **band** word (Saturated … Air-dry): a
plant's band is comparable across boards; its raw / ``dryness`` is comparable only to
another probe on the **same** board. We deliberately do NOT invent a normalized 0-100
"% watered" to force probes onto one axis (ADR-0004, ADR-0007 §5) — band is the
comparison; raw/dryness stays per-board.

Use this before any cross-board comparison of raw or dryness (e.g. ordering the fleet
by urgency): within a board, order by dryness; across boards, compare by band only.
"""

from __future__ import annotations

from collections.abc import Iterable

# The calibrated band is the honest cross-board layer; raw and dryness are not.
BAND_IS_THE_CROSS_BOARD_LAYER = True


def _distinct_boards(device_ids: Iterable[str | None]) -> set[str]:
    """The set of real board identities (each device_id is one board; None dropped)."""
    return {d for d in device_ids if d}


def raw_comparable(device_ids: Iterable[str | None]) -> bool:
    """True only when every reading is from ONE board.

    Raw (and the ``dryness`` scalar derived from a single ``mrange``) is comparable
    within a board, never across boards with different ADCs (ADR-0019 / #170). Zero or
    one distinct board ⇒ comparable (nothing cross-board to get wrong)."""
    return len(_distinct_boards(device_ids)) <= 1


# dryness rides one mrange ruler, so it inherits raw's cross-board incomparability.
dryness_comparable = raw_comparable


def cross_board(device_ids: Iterable[str | None]) -> bool:
    """True when readings span more than one board — the un-mediated-comparison case a
    fleet raw/dryness ordering must guard against (compare by band instead)."""
    return len(_distinct_boards(device_ids)) > 1
