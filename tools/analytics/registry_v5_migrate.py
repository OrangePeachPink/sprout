#!/usr/bin/env python3
"""#1315 — the one-shot registry migration that gates the v5 flash: channel keys
``s1..s4`` (on-wire port tokens) → ``ch0..ch3`` (ADR-0036 / #1042).

**Why this exists.** The registry keys channels by the token the port *emitted*; a v5
board emits ``ch0..ch3``. Without this migration, at first v5 flash every row resolves
to NO plant — no names, cards, bands, or forecasts, fleet-wide.

**The mapping is STATED, never inferred** (🔧 Firmware, #1315, read from the rename
commit's parent — `firmware/include/config.h` pre-rename)::

    constexpr const char *SENSOR_NAMES[NUM_SENSORS] = {"s3", "s4", "s1", "s2"};

There was **no board guard** on that line — one global ``constexpr``, compiled
identically into every target — so classic and C5 emitted the *identical* order and
the same mapping applies to both. The order is **not sequential**: positional/JSON
key-order inference would have produced ``s1→ch0``, wrong for all four channels.

**The conflation caution** (Firmware, #1315; registry ``_note``; ADR-0027 §5): the
registry's ``channels{}`` keys are **on-wire port tokens, never probe stickers**. Key
``s1`` means *"the port that emitted s1"* = **ch2** — it does not mean probe-sticker
s1. A migration reading those keys as stickers mis-maps even with the table correct.

**Three independent sources agree** on the mapping: the firmware constant above, the
bench-time registry ``_note``, and — the belt-and-braces axis Firmware handed over —
the per-board GPIO from ``board_capability``, cross-checked here against the GPIO
actually emitted in her telemetry (``validate_against_gpio``).

**Safety posture.** This module builds a PLAN and renders a DRY-RUN diff. Writing is a
separate, explicitly-flagged call that refuses unless the plan is clean AND the GPIO
cross-check passes, and it backs the file up first. The maintainer approves the
dry-run before anything writes (#1315 option A); execution is hers, not this tool's.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from parse_v1 import board_class, parse_file  # noqa: E402

# The stated constant (#1315) — channel index -> the token that channel emitted.
SENSOR_NAMES: tuple[str, ...] = ("s3", "s4", "s1", "s2")

# The derived rename: registry key (on-wire token) -> the v5 channel token.
KEY_TO_CHANNEL: dict[str, str] = {tok: f"ch{i}" for i, tok in enumerate(SENSOR_NAMES)}

# The belt-and-braces axis (#1315): board_capability soil pins, SAME channel order.
BOARD_GPIO: dict[str, tuple[int, ...]] = {
    "classic": (36, 39, 34, 35),
    "c5": (1, 4, 5, 6),
}


def observed_token_gpio(log_files) -> dict[str, dict[str, set]]:
    """``{device_id: {wire_token: {gpio,...}}}`` from real emitted rows — the third,
    independent corroboration of the stated table. Read-only."""
    seen: dict[str, dict[str, set]] = {}
    for f in log_files:
        for r in parse_file(str(f)).readings:
            if r.record_type != "plants.soil" or not r.device_id:
                continue
            gpio = (r.payload or {}).get("gpio")
            if gpio is None:
                continue
            seen.setdefault(r.device_id, {}).setdefault(r.sensor_id, set()).add(
                str(gpio)
            )
    return seen


def validate_against_gpio(registry, observed: dict) -> list[str]:
    """Cross-check each device's registry keys against the GPIO its ports actually
    emitted. A finding here means the stated table and the hardware disagree for that
    board — which must BLOCK the write, not be explained away. Devices with no GPIO
    evidence yield an explicit 'unverified' finding: honest, never a silent pass."""
    findings: list[str] = []
    for dev in registry.devices:
        keys = list((dev.channels or {}).keys())
        if not keys:
            continue
        cls = board_class(dev.board)
        pins = BOARD_GPIO.get(cls)
        dev_obs = observed.get(dev.device_id) or {}
        if not dev_obs:
            findings.append(
                f"unverified {dev.device_id} [{cls}]: no GPIO evidence in the "
                f"supplied logs — mapping rests on the stated constant alone"
            )
            continue
        for key in keys:
            ch = KEY_TO_CHANNEL.get(key)
            if ch is None or pins is None:
                continue
            expected = str(pins[int(ch[2:])])
            got = dev_obs.get(key)
            if got is None:
                findings.append(
                    f"unverified {dev.device_id}/{key}: token never seen emitting GPIO"
                )
            elif got != {expected}:
                findings.append(
                    f"MISMATCH {dev.device_id}/{key} -> {ch}: stated GPIO {expected}, "
                    f"observed {sorted(got)} — the table and the hardware disagree"
                )
    return findings


def plan_migration(registry) -> dict:
    """Per device: the key renames, in channel order, plus any anomaly. **Fail-closed
    per device** — a device with ANY anomaly is marked ``blocked`` and is not written,
    rather than partially migrated into a half-renamed state."""
    devices: list[dict] = []
    for dev in registry.devices:
        chans = dev.channels or {}
        entry: dict = {
            "device_id": dev.device_id,
            "board": dev.board,
            "board_class": board_class(dev.board),
            "renames": [],
            "anomalies": [],
            "status": "ok",
        }
        if not chans:
            entry["status"] = "skip-no-channels"
            devices.append(entry)
            continue
        already = [k for k in chans if k.startswith("ch")]
        unknown = [
            k for k in chans if k not in KEY_TO_CHANNEL and not k.startswith("ch")
        ]
        if already and len(already) == len(chans):
            entry["status"] = "already-migrated"
            devices.append(entry)
            continue
        if already:
            entry["anomalies"].append(
                f"mixed vocabulary: {sorted(already)} already chN while "
                f"{sorted(k for k in chans if k not in already)} are still tokens"
            )
        for k in unknown:
            entry["anomalies"].append(
                f"unknown channel key {k!r} — not in the stated table"
            )
        targets: dict[str, str] = {}
        for key in chans:
            ch = KEY_TO_CHANNEL.get(key)
            if ch is None:
                continue
            if ch in chans and ch not in already:
                entry["anomalies"].append(
                    f"collision: {key!r} -> {ch!r} which already exists"
                )
            if ch in targets:
                entry["anomalies"].append(
                    f"collision: {key!r} and {targets[ch]!r} both map to {ch!r}"
                )
            targets[ch] = key
            meta = chans.get(key) or {}
            entry["renames"].append(
                {
                    "from": key,
                    "to": ch,
                    "plant_id": meta.get("plant_id"),
                    "plant_name": meta.get("plant_name"),
                }
            )
        entry["renames"].sort(key=lambda r: r["to"])
        if entry["anomalies"]:
            entry["status"] = "blocked"
        devices.append(entry)
    return {
        "stated_constant": list(SENSOR_NAMES),
        "mapping": dict(KEY_TO_CHANNEL),
        "devices": devices,
        "blocked": [d["device_id"] for d in devices if d["status"] == "blocked"],
    }


def render_dry_run(plan: dict, findings: list[str]) -> str:
    """The artifact the maintainer approves (or rejects) before anything writes."""
    out: list[str] = []
    out.append("REGISTRY v5 CHANNEL-KEY MIGRATION — DRY RUN (nothing written)")
    out.append("")
    out.append(
        f"  stated SENSOR_NAMES (#1315): {{{', '.join(SENSOR_NAMES)}}}"
        "  — not sequential"
    )
    out.append("  mapping applied to BOTH boards (the constant had no board guard):")
    for i, tok in enumerate(SENSOR_NAMES):
        out.append(f"    key {tok!r:>5}  ->  ch{i}   (the port that emitted {tok})")
    out.append("")
    for d in plan["devices"]:
        head = f"  {d['device_id']} [{d['board_class']}] — {d['status']}"
        out.append(head)
        for r in d["renames"]:
            who = r["plant_name"] or r["plant_id"] or "(unassigned)"
            out.append(f"      {r['from']:>4}  ->  {r['to']:<4}   {who}")
        for a in d["anomalies"]:
            out.append(f"      ! {a}")
        out.append("")
    out.append("  GPIO cross-check (the third, independent axis):")
    if not findings:
        out.append(
            "      PASS — every key's stated channel matches the GPIO it emitted"
        )
    else:
        for f in findings:
            out.append(f"      {f}")
    out.append("")
    blocked = plan["blocked"]
    if blocked:
        out.append(f"  RESULT: BLOCKED — {blocked} would not be written (fail-closed).")
    elif any(f.startswith("MISMATCH") for f in findings):
        out.append("  RESULT: BLOCKED — a GPIO mismatch outranks the stated table.")
    else:
        out.append(
            "  RESULT: clean. Awaiting the maintainer's approval; nothing written."
        )
    return "\n".join(out)


def is_writable(plan: dict, findings: list[str]) -> bool:
    """The gate ``apply_migration`` refuses to cross: no blocked device, no GPIO
    mismatch. 'unverified' does NOT block (a board may simply have no GPIO in the
    supplied logs) but it is always rendered, never hidden."""
    return not plan["blocked"] and not any(f.startswith("MISMATCH") for f in findings)


def apply_migration(
    registry_path: Path, plan: dict, findings: list[str], *, approved: bool = False
) -> dict:
    """Rewrite the registry's channel keys in place. **Refuses unless** the plan is
    clean, the GPIO check has no mismatch, AND ``approved=True`` — the maintainer's
    dry-run approval (#1315 option A) is a parameter, not an assumption. Backs the
    file up first; values are carried verbatim, only keys move."""
    if not approved:
        return {"written": False, "reason": "not approved — the dry-run is the gate"}
    if not is_writable(plan, findings):
        return {"written": False, "reason": "plan blocked or GPIO mismatch"}
    path = Path(registry_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    by_id = {d["device_id"]: d for d in plan["devices"]}
    touched = 0
    for dev in doc.get("devices", []):
        entry = by_id.get(dev.get("device_id"))
        if not entry or entry["status"] != "ok":
            continue
        chans = dev.get("channels") or {}
        dev["channels"] = {r["to"]: chans[r["from"]] for r in entry["renames"]}
        touched += 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak-v5-{stamp}")
    shutil.copy2(path, backup)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return {"written": True, "devices": touched, "backup": str(backup)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1315 registry v5 channel-key migration")
    ap.add_argument(
        "--registry", default=None, help="devices.local.json (default: discovery)"
    )
    ap.add_argument("--logs", default=None, help="log dir for the GPIO cross-check")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="WRITE (requires --approved and a clean plan); default is dry-run",
    )
    ap.add_argument(
        "--approved",
        action="store_true",
        help="the maintainer approved this exact dry-run (#1315 option A)",
    )
    args = ap.parse_args(argv)

    from device_registry import load_registry

    registry = load_registry(args.registry) if args.registry else load_registry()
    logs = sorted(Path(args.logs).glob("*.csv")) if args.logs else []
    observed = observed_token_gpio(logs)
    plan = plan_migration(registry)
    findings = validate_against_gpio(registry, observed)
    print(render_dry_run(plan, findings))
    if not args.apply:
        return 0
    result = apply_migration(
        Path(args.registry), plan, findings, approved=args.approved
    )
    print(f"\n  apply: {result}")
    return 0 if result.get("written") else 1


if __name__ == "__main__":
    raise SystemExit(main())
