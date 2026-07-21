#!/usr/bin/env python3
"""Sprout's recommended soil pinout per board class — a layer-0 leaf (ADR-0038 §1).

**Why the host holds a copy at all.** The adoption surface (#1027 §5.2) offers Sprout's
own pinout as a one-tap default, so the values have to be readable host-side. They are
*mirrored* from the firmware headers that own them —
`firmware/include/board_capability.h` — never authored here. A seam test asserts this
table against those headers, so a firmware rewire that did not reach the host fails a
test instead of quietly offering a stale pin map to someone wiring a board.

**`verified` is the load-bearing field, not the pins.** Only the classic's map has real
bench endpoints; the S3 and C5 maps are *anticipated* — entered from datasheets with
`cal_verified=false` and never bench-confirmed. Offering an unverified map as "Sprout's
recommendation" would present a guess in the same voice as a measurement, on the one
surface where being wrong means someone wires a probe to a strapping pin and spends an
evening on a board that will not boot.

So the flag exists to be *consulted*, not merely recorded: a caller offering a one-tap
default should offer only where `verified` is true, and elsewhere ask rather than
suggest. That is the same distinction the declaration itself carries between a default
we assumed and a fact she stated — a recommendation nobody has measured is not a
recommendation, it is a hypothesis with good manners.
"""

from __future__ import annotations

# Keyed by ADR-0036 §6's ratified `board_class` tokens — qualified and mutually
# non-prefixing (`esp32-classic`, never bare `esp32`, which is simultaneously a specific
# chip and the family prefix of every other token). Firmware owns the enumeration; this
# is a consumer of it, and the seam test asserts the name→pins pairing straight out of
# board_capability.h rather than trusting this comment.
RECOMMENDED_SOIL_PINS: dict[str, tuple[int, ...]] = {
    "esp32-classic": (36, 39, 34, 35),  # ADC1 input-only; the shipping map
    "esp32-s3": (1, 2, 4, 5),  # ADC1, non-strapping (GPIO3 dropped 2026-07-03)
    "esp32-c5": (1, 4, 5, 6),  # the only four non-strapping ADC1 pins on the C5
}

# True only where real bench endpoints exist. See the module docstring: this is the
# field that decides whether a surface may *suggest* rather than *ask*.
PINOUT_VERIFIED: dict[str, bool] = {
    "esp32-classic": True,
    "esp32-s3": False,
    "esp32-c5": False,
}


def recommended_pins(board_class: str) -> tuple[int, ...] | None:
    """Sprout's soil pin map for this board class, or ``None`` if we have none.

    ``None`` is a first-class answer (ADR-0028): an unknown board is not a broken one,
    and a surface that has no recommendation should say so rather than fall back to the
    classic's pins — which do not physically exist on a C5, and would be offered with
    total confidence to someone holding a board that cannot use them.

    Takes the **firmware-emitted** token (ADR-0036 §6). Do not pass the registry's
    ``board`` string: that is a display label — *"esp32-c5-devkitc-1 (official)"* — and
    §6 rules it must never be parsed. Humans get the prose; machines get the token.
    """
    return RECOMMENDED_SOIL_PINS.get(board_class)


def is_verified(board_class: str) -> bool:
    """Whether this board class's map has been bench-verified. Unknown ⇒ False: the
    safe default for "may I present this as a recommendation?" is no."""
    return PINOUT_VERIFIED.get(board_class, False)
