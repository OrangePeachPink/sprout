#!/usr/bin/env python3
"""#675 — the plant/pot/site profile loader (ADR-0029, Accepted): the inference
DIMENSION, keyed by the stable ``plant_id`` (ADR-0027).

- **Dimension, not telemetry** (§2): a slowly-changing lookup the analysis tier joins
  facts to on ``plant_id`` — never on the wire, never per-row.
- **Storage mirrors the device registry** (§3): committed schema/loader (this file) +
  the committed placeholder ``config/plant_profiles.example.json``; the REAL instance
  is gitignored ``config/plant_profiles.local.json`` (pot sizes + home placement =
  the maintainer's windowsill, ADR-0015).
- **Placement is referenced, never duplicated** (§3): a wired plant's device/channel/
  side resolve through the device registry via ``placement_for``; only a SENSORLESS
  plant carries placement here (it has no device binding).
- **Every field is absent-safe** (ADR-0028): a minimal profile is ``plant_id`` (+
  ``label``); everything else sharpens prediction. Validation collects findings and
  still loads — human-asserted reference data degrades honestly, it never crashes the
  tier. A guess is labelled a guess; observations are dated (§5).

Consumers (§6 caveats travel): the #1243 Predict bridge + the #25 predictor condition
on this AFTER per-channel calibration; where ``probe_reading_caveat`` is set, the
channel's raw is distrusted as a proxy for the plant's true water state.
"""

from __future__ import annotations

import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent

_REPO = _HERE.parents[1]
_LOCAL = _REPO / "config" / "plant_profiles.local.json"
_EXAMPLE = _REPO / "config" / "plant_profiles.example.json"

# ADR-0029 §4 vocabularies — validated when present; unknown FIELDS are tolerated
# (dimensions are extend-as-needed by design), unknown ENUM VALUES are findings.
ENUMS: dict[str, tuple] = {
    "species_confidence": ("low", "medium", "high"),
    "placement.ledge": ("left", "right"),
    "pot.shape": ("standard", "wide-shallow"),
    "pot.depth_class": ("normal", "shallow"),
    "pot.material": ("terracotta", "plastic"),
    "pot.outer_pot_seal": ("none", "loose", "watertight-tight"),
    "soil_root.root_bound": ("none", "likely", "hard"),
    "soil_root.decorative_top": ("none", "moss"),
    "hydrology.water_delivery_path": (
        "topsoil",
        "inner-outer-gap-sip",
        "inner-outer-gap-stagnate",
        "drip-tray-resoak",
    ),
    "hydrology.retention_class": (
        "chronically-waterlogged",
        "good",
        "poor-wicking-drought-cycled",
        "resoak-buffered",
    ),
    "hydrology.probe_contact_quality": ("poor", "good", "best"),
    "soil_condition": (
        "well-wicking",
        "clumpy-retentive",
        "hydrophobic-non-wicking",
    ),
    "care.care_origin": ("office", "home"),
}

# probe_reading_caveat: the named tokens are validated; anything else is a free note
# (the ADR keeps the field open — the tell must be expressible even when unnamed).
_CAVEAT_TOKENS = (
    "represents",
    "may-underread-standing-water",
    "may-miss-gap-reservoir",
)


def _get(profile: dict, dotted: str):
    cur = profile
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def load_profiles(path: str | Path | None = None) -> tuple[dict, list[str]]:
    """Load the profile dimension: ``({plant_id: profile-dict}, findings)``. Discovery
    is local -> example -> empty (the same ladder as the device registry). Findings
    (enum violations, duplicate/missing ids, unreadable file) are collected — the
    dimension still loads; reference data degrades honestly."""
    findings: list[str] = []
    src = None
    if path is not None:
        src = Path(path)
    elif _LOCAL.is_file():
        src = _LOCAL
    elif _EXAMPLE.is_file():
        src = _EXAMPLE
    if src is None:
        return {}, findings
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"unreadable profile file {src.name}: {exc}"]
    out: dict = {}
    for i, p in enumerate(doc.get("plants", []) or []):
        pid = (p.get("plant_id") or "").strip() if isinstance(p, dict) else ""
        if not pid:
            findings.append(f"plants[{i}]: missing plant_id — entry skipped")
            continue
        if pid in out:
            findings.append(f"plants[{i}]: duplicate plant_id {pid} — first kept")
            continue
        for dotted, allowed in ENUMS.items():
            val = _get(p, dotted)
            if val is not None and val not in allowed:
                findings.append(f"{pid}.{dotted}: {val!r} not in {allowed}")
        caveat = _get(p, "hydrology.probe_reading_caveat")
        if caveat is not None and caveat not in _CAVEAT_TOKENS:
            pass  # a free-text caveat note is legal by design (ADR-0029 §4)
        out[pid] = p
    return out, findings


def profile_for(plant_id: str, profiles: dict | None = None) -> dict | None:
    """One plant's profile (or None — a plant is fully monitored with no profile)."""
    if profiles is None:
        profiles, _ = load_profiles()
    return profiles.get(plant_id)


def placement_for(plant_id: str, profiles: dict, registry) -> dict:
    """ADR-0029 §3: wired ⇒ placement RESOLVES through the device registry (never
    duplicated here); sensorless ⇒ the profile carries it. Returns a dict with
    ``source`` = 'device-registry' | 'profile' | 'unknown'."""
    for dev in getattr(registry, "devices", []) or []:
        for channel, meta in (getattr(dev, "channels", None) or {}).items():
            if (meta or {}).get("plant_id") == plant_id:
                return {
                    "source": "device-registry",
                    "device": dev.device_id,
                    "channel": channel,
                    "side": getattr(dev, "side", None) or (meta or {}).get("side"),
                }
    prof = profiles.get(plant_id) or {}
    placement = prof.get("placement") or {}
    if placement.get("sensorless"):
        return {
            "source": "profile",
            "side": placement.get("ledge"),
            "window": placement.get("window"),
        }
    return {"source": "unknown"}
