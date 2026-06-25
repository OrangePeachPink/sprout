#!/usr/bin/env python3
"""Standalone tests for the Experiment-mode capture (#65).

Runnable without pytest (the repo has no Python suite yet):

    python tools/capture/test_experiment_capture.py

Proves the slice's gate-critical guarantees: a synthetic capture writes a valid
schema_version=2 file into an isolated ``experiments/`` tree with a fail-safe
auto-stop and transport-error counts, and — the never-stitch guarantee — the
monitor dashboard's ``gather_inputs()`` cannot auto-discover it.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for p in (_HERE, _REPO / "tools" / "analytics"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import experiment_capture as ec  # noqa: E402
from parse_v1 import parse_files  # noqa: E402

_FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        _FAILS.append(msg)


def test_capture_and_schema() -> None:
    print("end-to-end synthetic capture + schema_version=2:")
    tmp = Path(tempfile.mkdtemp(prefix="expcap_"))
    try:
        duration = 0.4
        t0 = time.monotonic()
        manifest = ec.run_capture(
            ec.SyntheticReader(seed=7),
            tmp,
            experiment_id="t_common-cup",
            subject="common-cup",
            rate_s=0.03,
            duration_s=duration,
            labels={"s1": "control", "s2": "treatment"},
        )
        elapsed = time.monotonic() - t0

        check(elapsed < duration + 1.0, f"fail-safe auto-stop (~{elapsed:.2f}s)")
        f = tmp / "t_common-cup" / "t_common-cup.csv"
        check(f.exists(), "experiment file written under experiments/<id>/")
        check((tmp / "t_common-cup" / "manifest.json").exists(), "manifest written")

        text = f.read_text(encoding="utf-8")
        check("schema_version=2" in text, "header declares schema_version=2")
        check("mode=experiment" in text, "header declares mode=experiment")
        header_cols = next(
            ln for ln in text.splitlines() if ln.startswith("record_type")
        )
        for col in ("mode", "subject", "experiment_id", "sample_rate_s", "label"):
            check(col in header_cols, f"additive column present: {col}")

        t = manifest["transport"]
        check(
            t["rows"] > 0 and t["sweeps"] > 0,
            f"rows/sweeps recorded ({t['rows']}/{t['sweeps']})",
        )
        check(
            (t["idle_noise"] + t["crc_fail"]) > 0,
            f"transport errors counted (noise={t['idle_noise']} crc={t['crc_fail']})",
        )

        data = parse_files([str(f)])
        check(
            2 in {s.schema_version for s in data.segments},
            "parse_v1 reads it as schema 2",
        )
        soil = [r for r in data.readings if r.record_type == "plants.soil"]
        check(
            bool(soil) and all(r.raw_value is not None for r in soil),
            "raw_value parses",
        )
        check(
            all(r.row.get("mode") == "experiment" for r in soil),
            "every row carries mode=experiment (the discriminator)",
        )
        labels = {r.sensor_id: r.row.get("label") for r in soil}
        check(labels.get("s1") == "control", "per-probe label persisted (s1=control)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_never_stitch_gate() -> None:
    print("never-stitch gate — gather_inputs() cannot auto-discover experiments:")
    from dashboard import gather_inputs  # local import: after sys.path is set

    real_root = _REPO / "experiments"
    exp_id = "_nevstitch_gate_test"
    created_root = not real_root.exists()
    try:
        ec.run_capture(
            ec.SyntheticReader(seed=1),
            real_root,
            experiment_id=exp_id,
            subject="gate-test",
            rate_s=0.02,
            duration_s=0.2,
            labels={},
        )
        produced = real_root / exp_id / f"{exp_id}.csv"
        check(produced.exists(), "wrote a real experiment file under experiments/")
        discovered = gather_inputs()
        leaked = [p for p in discovered if "experiments" in Path(p).as_posix()]
        check(
            not leaked,
            f"gather_inputs() excludes experiments/ "
            f"({len(discovered)} monitor sources)",
        )
    finally:
        shutil.rmtree(real_root / exp_id, ignore_errors=True)
        if created_root and real_root.exists() and not any(real_root.iterdir()):
            real_root.rmdir()


if __name__ == "__main__":
    test_capture_and_schema()
    test_never_stitch_gate()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): " + "; ".join(_FAILS))
        raise SystemExit(1)
    print("All checks passed.")
