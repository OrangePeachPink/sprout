#!/usr/bin/env python3
"""#963 — the owner-cal projection receipt: three honest states, not two.

Option 1 is ratified (Trellis; Firmware ack): **the host owns cal values, the device's
NVS slot is the projection.** That makes "did my cal reach the board?" a real question,
and Firmware's finding is that the obvious answer is wrong on the board that matters
most:

    | board   | class-default tier | projection lost -> wire says | visible? |
    | classic | channel-cal        | channel-cal (unchanged)      | NO       |
    | c5      | (differs)          | a different tier             | yes      |

On her classic — the board with eight probed channels — a rejected or never-arrived
projection is **completely silent on the tier axis**. The plant runs on bench cal,
which is safe, but the host would believe its owner cal was live when it isn't.

``cal_src`` closes it and already ships (`telemetry.c` appends `;cal_src=<provenance>`
to WiFi soil rows): an owner record carries its own provenance string, the class
default carries the bench one. So the confirmation comes from **telemetry**, not from
the push returning 200 — Firmware's suggestion, taken, and the same distinction as
#1346's exact-bytes receipt: *what you sent and what's running are different claims.*

Hence three states rather than the usual two:

- ``stored``    — the host record is written. Always reachable, needs no board. This
                  is what makes the offline bench flow work: cal survives the wizard
                  even if nothing is reachable.
- ``pushed``    — the device accepted the projection. Necessary, NOT sufficient.
- ``confirmed`` — a subsequent WiFi row carries the expected ``cal_src``. The only
                  state that means the board is actually *using* it.

**One stated boundary** (Firmware): ``cal_src`` is gated on ``rssi_present`` — WiFi
rows only. A serial/offline row carries none, so confirmation requires the board to be
on WiFi, which is the same condition as pushing to it. Consistent, but stated here
rather than discovered later: ``confirmed`` is unreachable for a serial-only board, and
``stored`` is the honest terminal state for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent

STORED = "stored"
PUSHED = "pushed"
CONFIRMED = "confirmed"
STATES = (STORED, PUSHED, CONFIRMED)


@dataclass(frozen=True)
class Receipt:
    """What we actually know about one channel's owner cal."""

    state: str
    profile_id: str
    expected_cal_src: str | None = None
    observed_cal_src: str | None = None
    detail: str = ""

    @property
    def is_live(self) -> bool:
        """Only ``confirmed`` means the board is using this cal. ``pushed`` is a
        claim about the transfer, not about what's running."""
        return self.state == CONFIRMED


def expected_cal_src(profile) -> str | None:
    """The ``cal_src`` an owner profile should produce on the wire — its provenance
    string. Absent provenance ⇒ no expectation, so confirmation is impossible and we
    say so rather than inventing a token to match against."""
    prov = getattr(profile, "provenance", None) or {}
    if isinstance(prov, dict):
        who = prov.get("who")
        return str(who) if who else None
    return str(prov) if prov else None


def evaluate(
    profile,
    *,
    pushed: bool,
    observed_cal_src: str | None,
) -> Receipt:
    """Grade one channel's projection against what telemetry actually reports.

    ``observed_cal_src`` is the ``cal_src`` from the most recent WiFi soil row for
    that channel — ``None`` when the board is serial-only, offline, or hasn't reported
    since the push."""
    pid = getattr(profile, "profile_id", "") or ""
    want = expected_cal_src(profile)
    if want and observed_cal_src and observed_cal_src == want:
        return Receipt(
            CONFIRMED, pid, want, observed_cal_src, "telemetry reports the owner cal"
        )
    if not pushed:
        return Receipt(
            STORED, pid, want, observed_cal_src, "host record written; not yet pushed"
        )
    if want is None:
        return Receipt(
            PUSHED,
            pid,
            None,
            observed_cal_src,
            "pushed, but the profile carries no provenance — "
            "nothing to confirm against",
        )
    if observed_cal_src is None:
        return Receipt(
            PUSHED,
            pid,
            want,
            None,
            "pushed; no WiFi row yet (a serial-only board never confirms)",
        )
    return Receipt(
        PUSHED,
        pid,
        want,
        observed_cal_src,
        f"pushed, but the board reports cal_src={observed_cal_src!r} — the "
        f"projection did not land, or was superseded",
    )
