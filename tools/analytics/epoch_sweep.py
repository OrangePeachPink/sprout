#!/usr/bin/env python3
"""#1330 — the production epoch stamp + the admissibility sweep.

**The epoch is ratified: `2026-07-06T00:00:06Z`** — the first row of the continuous
production feed. Everything before it is bench-learning evidence, not observation, and
its embedded plant mapping is known-wrong (the frozen ``@origplant`` firmware header —
the real-world case ADR-0036 exists to end).

It is also **self-evidencing**: that instant is literally the first row of
``y9d41p_20260706_000006.csv``, and no log file straddles the boundary, so every rule
below is expressible per FILE rather than per row.

Two jobs, both in the migration tool's shape — **plan → rendered dry-run → maintainer
approval → execute**:

1. **Stamp the epoch as real ``start_ts``** on the open assignments. Not a config
   constant: it is the field the (#1331) interval join reads, so writing it makes the
   epoch self-documenting and closes the all-null ``start_ts`` gap in one pass.
2. **The admissibility sweep**, in the ratified order **resolve citations → archive →
   delete**, against the ratified rules: *unwired → delete* · *pre-epoch → lab record
   only* · *nothing pre-epoch in dashboards/models/charts* · *wired-but-unused streams
   stay admissible*.

Safety posture, all enforced in code rather than remembered:

- **The committed example registry is refused.** In a worktree the model-discovery
  ladder lands on ``devices.example.json`` (fictional assignments); stamping a
  production epoch there would write a real timestamp into a public fixture and touch
  zero real assignments. An explicit path is required.
- **Delete is last, gated, and archive-first.** Nothing is removed unless the caller
  passes ``approved=True``, the plan is clean, every citation resolves, and the file
  was archived successfully first.
- **A wired board is never a delete candidate**, whatever its dates — pre-epoch
  production data is lab record. Only *unwired* output is noise.
- **Dry-run writes nothing** (asserted by test).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from parse_v1 import parse_file  # noqa: E402  (the ONE parse boundary, ADR-0021)

# Ratified 2026-07-06 (maintainer-confirmed after the commissioning-record untangle).
PRODUCTION_EPOCH = datetime(2026, 7, 6, 0, 0, 6, tzinfo=timezone.utc)

# Admissibility classes — what a log file IS, which decides what may happen to it.
KEEP_ADMISSIBLE = "admissible"  # post-epoch, wired: production observation
KEEP_LAB_RECORD = "lab-record"  # pre-epoch, wired: evidence, never a delete candidate
DELETE_UNWIRED = "unwired"  # never registered / never wired: noise, ruled DELETE
UNKNOWN = "unknown"  # anything we cannot classify — reported, never swept

_LOG_CITE = re.compile(r"logs/([A-Za-z0-9_.\-]+\.csv(?:\.gz)?)")


def _registry_device_ids(registry) -> set:
    return {d.device_id for d in getattr(registry, "devices", []) or []}


def _wired_device_ids(registry) -> set:
    """Devices with at least one channel bound to a plant — 'wired' in the ruling's
    sense. A registered-but-channel-less bench board is NOT wired."""
    out = set()
    for d in getattr(registry, "devices", []) or []:
        for ch in d.channels or {}:
            if (d.plant_for(ch) or {}).get("plant_id"):
                out.add(d.device_id)
                break
    return out


def classify_file(path: Path, wired: set, known: set) -> dict:
    """One log file's admissibility, from its PARSED rows (never its filename —
    rotation names lie, store contract §2)."""
    devices, first, last, n = set(), None, None, 0
    for r in parse_file(str(path)).readings:
        if r.record_type != "plants.soil" or r.timestamp_utc is None:
            continue
        n += 1
        if r.device_id:
            devices.add(r.device_id)
        first = r.timestamp_utc if first is None or r.timestamp_utc < first else first
        last = r.timestamp_utc if last is None or r.timestamp_utc > last else last
    # ORDER MATTERS, and this order is the safety property. Pre-epoch is tested
    # FIRST, before any wired/unwired judgement:
    #
    # The archive holds pre-epoch files under LEGACY device identities
    # (`plants_esp32_f4e9d4`, `classic`, `c5off1`) minted before ADR-0027 stable ids.
    # `c5off1` is `8gtt1h`'s own former name per the #995 derivation record — but the
    # registry's #602 `previous_ids` coalesce field is empty, so nothing in DATA links
    # them. An unwired-first order therefore classifies a production board's own bench
    # history as "never registered" and proposes DELETING it — including the very rows
    # the ratified band ladder was derived from.
    #
    # The ratified rules already settle it without needing the identity resolved:
    # *pre-epoch -> lab record only*. So nothing pre-epoch is ever a delete candidate,
    # whatever name it reported under. Only POST-epoch unwired output is noise.
    if not devices:
        klass = UNKNOWN
    elif last is not None and last < PRODUCTION_EPOCH:
        klass = KEEP_LAB_RECORD  # pre-epoch: evidence, never swept
    elif not (devices & known) or not (devices & wired):
        klass = DELETE_UNWIRED  # post-epoch AND unwired: noise (the n3jhsp case)
    else:
        klass = KEEP_ADMISSIBLE
    return {
        "file": path.name,
        "path": str(path),
        "devices": sorted(devices),
        "rows": n,
        "first": first.isoformat() if first else None,
        "last": last.isoformat() if last else None,
        "straddles_epoch": bool(first and last and first < PRODUCTION_EPOCH <= last),
        "class": klass,
    }


def citations(docs_dir: Path, logs_dir: Path, archive_dir: Path) -> list[dict]:
    """Every ``logs/<file>`` a doc cites, and whether it still resolves. An
    unresolvable citation BLOCKS the sweep: the ratified order is resolve-then-delete,
    and a dangling reference cannot be resolved after the fact."""
    out: list[dict] = []
    for doc in sorted(docs_dir.rglob("*")):
        if doc.suffix.lower() not in (".md", ".json") or not doc.is_file():
            continue
        try:
            text = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for name in sorted(set(_LOG_CITE.findall(text))):
            here = (logs_dir / name).is_file() or (archive_dir / name).is_file()
            # Ruling A (#1330): a citation is ALSO resolved when the doc itself
            # states the slice is unavailable. The ratified order is resolve-then-
            # delete, and "resolve" means the reference is no longer dangling —
            # either the file is there, or the record honestly says it is not.
            # Without this, an amended doc still reads as unresolved forever and the
            # sweep can never unblock.
            amended = False
            for i, line in enumerate(lines):
                if name in line:
                    window = " ".join(lines[i : i + 6]).lower()
                    amended = "slice unavailable" in window or (
                        "unavailable" in window and "cannot be resolved" in window
                    )
                    if amended:
                        break
            out.append(
                {
                    "doc": str(doc.relative_to(docs_dir.parent)),
                    "cites": name,
                    "resolves": here or amended,
                    "resolution": (
                        "file-present"
                        if here
                        else ("amended-unavailable" if amended else "dangling")
                    ),
                }
            )
    return out


def plan_epoch_stamp(model, registry_path: Path) -> dict:
    """The ``start_ts`` stamp plan for the open assignments.

    Refuses the committed example outright — see the module docstring; this is the
    guard that keeps a production timestamp out of a public fixture."""
    if registry_path.name.endswith(".example.json"):
        return {
            "ok": False,
            "reason": "refused: that is the COMMITTED EXAMPLE, not a real registry",
            "stamps": [],
        }
    stamps, conflicts = [], []
    for a in model.open_assignments():
        if a.start_ts in (None, ""):
            stamps.append(
                {
                    "plant_id": a.plant_id,
                    "device_id": a.device_id,
                    "channel": a.channel,
                    "sensor_id": a.sensor_id,
                    "start_ts": PRODUCTION_EPOCH.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
        else:
            conflicts.append({"plant_id": a.plant_id, "existing": a.start_ts})
    return {"ok": True, "stamps": stamps, "already_stamped": conflicts}


def plan_sweep(
    logs_dir: Path,
    archive_dir: Path,
    docs_dir: Path,
    registry,
) -> dict:
    """The full ordered plan: citations → archive → delete.

    Classifies **both** surfaces the tier ingests — the live ``logs/`` directory AND
    the rotated archive. Sweeping only ``logs/`` would have been a false negative on
    exactly the interesting case: the pre-epoch production files rotate to the archive
    as ``.csv.gz``, so a logs-only pass reports "no pre-epoch data" while the tier is
    still full of it."""
    wired, known = _wired_device_ids(registry), _registry_device_ids(registry)
    sources: list[Path] = []
    for d in (logs_dir, archive_dir):
        if d.is_dir():
            sources += sorted(d.glob("*.csv")) + sorted(d.glob("*.csv.gz"))
    files = [classify_file(p, wired, known) for p in sources]
    cites = citations(docs_dir, logs_dir, archive_dir)
    unresolved = [c for c in cites if not c["resolves"]]
    # A file that ALREADY LIVES IN THE ARCHIVE is not a delete candidate: the archive
    # IS the preservation destination, so "archive then delete" on it would mean
    # copying it onto itself and then removing the only copy. The sweep's job is to
    # clear the LIVE surfaces (logs/, and through them the tier); the archived record
    # stays. Caught in the live #1330 run, where the self-copy failed loudly on
    # Windows rather than quietly destroying the preserved rows.
    archived_names = (
        {p.name for p in archive_dir.glob("*")} if archive_dir.is_dir() else set()
    )
    to_delete = [
        f
        for f in files
        if f["class"] == DELETE_UNWIRED
        and Path(f["path"]).parent.resolve() != archive_dir.resolve()
    ]
    already_archived = [
        f
        for f in files
        if f["class"] == DELETE_UNWIRED
        and f["file"] in archived_names
        and Path(f["path"]).parent.resolve() == archive_dir.resolve()
    ]
    # A cited file is never deleted, whatever its class — the citation outranks it.
    cited_names = {c["cites"] for c in cites}
    blocked_by_citation = [f for f in to_delete if f["file"] in cited_names]
    return {
        "epoch": PRODUCTION_EPOCH.isoformat(),
        "files": files,
        "citations": cites,
        "unresolved_citations": unresolved,
        "to_archive": [f for f in to_delete if f["file"] not in cited_names],
        "already_archived": already_archived,
        "to_delete": [f for f in to_delete if f["file"] not in cited_names],
        "blocked_by_citation": blocked_by_citation,
        "straddling": [f for f in files if f["straddles_epoch"]],
        "pre_epoch_wired": [f for f in files if f["class"] == KEEP_LAB_RECORD],
    }


def apply_epoch_stamps(
    registry_path: Path, stamp_plan: dict, *, approved: bool = False
) -> dict:
    """Write the ratified epoch as real ``start_ts`` on the open assignments.

    Additive by construction: it only fills assignments whose ``start_ts`` is null,
    and touches no other field — so an already-stamped or differently-stamped
    assignment is left exactly as found rather than overwritten. Backs the registry
    up first (same restore path as #1315). Refuses without ``approved=True``."""
    if not approved:
        return {"written": False, "reason": "not approved — the dry-run is the gate"}
    if not stamp_plan.get("ok"):
        return {"written": False, "reason": stamp_plan.get("reason", "plan not ok")}
    if not stamp_plan["stamps"]:
        return {"written": False, "reason": "nothing to stamp"}
    path = Path(registry_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    # The stamp MUST land on the temporal `assignments[]` — that is the record the
    # interval join reads (#1331 / contract §3). Writing it onto the static
    # `devices[].channels[]` shape instead produces an INERT stamp: the file looks
    # stamped, `open_assignments()` still reports null, and every reading keeps
    # resolving against an unbounded assignment exactly as before. Caught in the live
    # #1330 run by the Home-verify gate — hence the refusal rather than a silent
    # best-effort write.
    if not isinstance(doc.get("assignments"), list):
        return {
            "written": False,
            "reason": (
                "refused: this config has no temporal `assignments[]`, so a stamp "
                "would be inert — migrate it to the temporal shape first"
            ),
        }
    want = {(s["device_id"], s["channel"]): s["start_ts"] for s in stamp_plan["stamps"]}
    stamped = 0
    for a in doc["assignments"]:
        if not isinstance(a, dict) or a.get("end_ts"):
            continue  # closed assignments are history — never re-stamped
        key = (a.get("device_id"), a.get("channel"))
        if key in want and not a.get("start_ts"):
            a["start_ts"] = want[key]
            stamped += 1
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak-epoch-{ts}")
    shutil.copy2(path, backup)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return {"written": True, "stamped": stamped, "backup": str(backup)}


def write_tombstone(plan: dict, dest: Path, *, authority: str, ruling: str) -> dict:
    """The tombstone manifest — written BEFORE anything is removed (#1330 execution
    order). Records for every file leaving: path, size, SHA-256, the admissibility
    rule applied, plus the epoch ruling and the approving authority.

    A deletion that leaves no record is indistinguishable from data loss; this is
    what makes the removal auditable after the fact."""
    import hashlib

    entries = []
    for f in plan["to_delete"]:
        p = Path(f["path"])
        digest = None
        if p.is_file():
            h = hashlib.sha256()
            h.update(p.read_bytes())
            digest = h.hexdigest()
        entries.append(
            {
                "file": f["file"],
                "path": f["path"],
                "size_bytes": p.stat().st_size if p.is_file() else None,
                "sha256": digest,
                "devices": f["devices"],
                "rows": f["rows"],
                "first": f["first"],
                "last": f["last"],
                "rule_applied": (
                    "unwired -> delete (ADR-0037 §2): post-epoch output from a device "
                    "never registered/wired to a plant is noise, not evidence"
                ),
            }
        )
    doc = {
        "tombstone_utc": datetime.now(timezone.utc).isoformat(),
        "issue": "#1330",
        "epoch_ruling": {
            "production_epoch": PRODUCTION_EPOCH.isoformat(),
            "source": "ADR-0037 (maintainer-ratified)",
        },
        "approving_authority": authority,
        "citation_ruling": ruling,
        "removed": entries,
        "n_removed": len(entries),
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def sweep_is_executable(plan: dict) -> bool:
    """The gate ``execute_sweep`` will not cross: every citation resolves, nothing
    straddles the epoch, and no delete candidate is cited."""
    return (
        not plan["unresolved_citations"]
        and not plan["straddling"]
        and not plan["blocked_by_citation"]
    )


def execute_sweep(
    plan: dict, archive_dir: Path, *, approved: bool = False, log=print
) -> dict:
    """Archive-then-delete the unwired files. **Refuses** unless the plan is
    executable AND ``approved=True`` — her dry-run approval is a parameter, never an
    assumption. A file is deleted only after its archive copy verifies."""
    if not approved:
        return {"executed": False, "reason": "not approved — the dry-run is the gate"}
    if not sweep_is_executable(plan):
        return {"executed": False, "reason": "plan blocked"}
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived, deleted, failures = [], [], []
    for f in plan["to_delete"]:
        src = Path(f["path"])
        dest = archive_dir / src.name
        try:
            shutil.copy2(src, dest)
            if dest.stat().st_size != src.stat().st_size:  # verify BEFORE removing
                failures.append(f"{src.name}: archive size mismatch")
                continue
            archived.append(str(dest))
            src.unlink()
            deleted.append(src.name)
        except OSError as exc:
            failures.append(f"{src.name}: {exc}")
            log(f"ARCHIVE/DELETE FAILED {src.name}: {exc}")
    return {
        "executed": True,
        "archived": archived,
        "deleted": deleted,
        "failures": failures,
    }


def render_dry_run(stamp_plan: dict, plan: dict) -> str:
    out: list[str] = []
    out.append("PRODUCTION EPOCH + ADMISSIBILITY SWEEP — DRY RUN (nothing written)")
    out.append("")
    out.append(f"  epoch: {plan['epoch']}  (ratified; the first row of the feed)")
    out.append("")
    out.append("  1. EPOCH STAMP — start_ts on the open assignments")
    if not stamp_plan["ok"]:
        out.append(f"      {stamp_plan['reason']}")
    else:
        for s in stamp_plan["stamps"]:
            out.append(
                f"      {s['plant_id']}  {s['device_id']}/{s['channel']}"
                f"  start_ts: (null) -> {s['start_ts']}"
            )
        for c in stamp_plan["already_stamped"]:
            out.append(f"      {c['plant_id']}: already {c['existing']} — left alone")
        if not stamp_plan["stamps"]:
            out.append("      (nothing to stamp)")
    out.append("")
    out.append("  2. CITATIONS (resolve first — the ratified order)")
    for c in plan["citations"]:
        mark = "ok " if c["resolves"] else "!! "
        out.append(f"      {mark}{c['cites']}  <- {c['doc']}")
    if not plan["citations"]:
        out.append("      (no doc cites a logs/ file)")
    out.append("")
    out.append("  3. ARCHIVE then DELETE (unwired only — noise, not evidence)")
    for f in plan["to_delete"]:
        out.append(
            f"      {f['file']}  {','.join(f['devices'])}  {f['rows']} rows"
            f"  {(f['first'] or '?')[:16]} -> {(f['last'] or '?')[:16]}"
        )
    if not plan["to_delete"]:
        out.append("      (nothing classified unwired)")
    for f in plan["blocked_by_citation"]:
        out.append(f"      HELD {f['file']} — a doc cites it; citation outranks")
    out.append("")
    out.append("  4. PRE-EPOCH ON WIRED BOARDS — lab record, never deleted")
    for f in plan["pre_epoch_wired"]:
        out.append(
            f"      {f['file']}  {','.join(f['devices'])}  {f['rows']} rows"
            f"  (kept as evidence; excluded from models by the tier filter)"
        )
    if not plan["pre_epoch_wired"]:
        out.append("      (none)")
    out.append("")
    if plan["straddling"]:
        for f in plan["straddling"]:
            out.append(f"  !! {f['file']} STRADDLES the epoch — per-file rules unsafe")
    ok = sweep_is_executable(plan)
    out.append(
        "  RESULT: clean. Awaiting approval; nothing written."
        if ok
        else "  RESULT: BLOCKED — resolve the flagged items first."
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1330 epoch stamp + admissibility sweep")
    ap.add_argument("--registry", required=True, help="the REAL devices.local.json")
    ap.add_argument("--logs", required=True)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--docs", default=str(_HERE.parents[1] / "docs" / "experiments"))
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--execute", action="store_true", help="requires --approved")
    ap.add_argument("--approved", action="store_true")
    args = ap.parse_args(argv)

    from device_registry import load_registry
    from registry_model import load_model

    registry_path = Path(args.registry)
    registry = load_registry(str(registry_path))
    model = load_model(str(registry_path))
    stamp_plan = plan_epoch_stamp(model, registry_path)
    plan = plan_sweep(Path(args.logs), Path(args.archive), Path(args.docs), registry)
    print(render_dry_run(stamp_plan, plan))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"stamp": stamp_plan, "sweep": plan}, indent=2), encoding="utf-8"
        )
        print(f"\n  wrote {args.json_out}")
    if not args.execute:
        return 0
    result = execute_sweep(plan, Path(args.archive), approved=args.approved)
    print(f"\n  execute: {result}")
    return 0 if result.get("executed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
