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


# --------------------------------------------------------------------------- #
# #329 — experiment captures preserve firmware git provenance
# --------------------------------------------------------------------------- #

# A boot banner whose provenance line carries git + a space-containing build time.
_BANNER = [
    b"# boot plants controller fw=0.7.0 - Rung 4 schema v1, four soil sensors\n",
    b"# plants telemetry  schema_version=1  contract=docs/TELEMETRY_SCHEMA.md@v1\n",
    b"# fw=0.7.0  git=abc1234  built=Jun 28 2026 12:34:56  run=bench-329\n",
    b"# device_id=plants_esp32_test (default)  chip=ESP32\n",
    b"# session_id=sess99  cadence_ms=1000 (default)\n",
    b"# sensors: ch0=GPIO36/s3  (model=UMLIFE_v2_TLC555 pos=origplant)\n",
]


def _data_line() -> bytes:
    body = (
        "plants.soil,sess99,plants_esp32_test,0.7.0,1000,"
        "UMLIFE_v2_TLC555,s3,origplant,soil_moisture,1312,,,OK,"
        "level=well watered;gpio=36"
    )
    return f"{body}*{ec._nmea_crc(body)}\n".encode()


class _FakeSerial:
    """Scripted serial device: replays banner, acks set_cadence, then streams data."""

    def __init__(self) -> None:
        # a data line at the tail of the banner ends header capture immediately
        # (no 2 s grace wait), and is buffered as the first row.
        self._q = [*_BANNER, _data_line()]
        self._acked = False
        self.writes: list[bytes] = []  # record commands so tests can inspect them

    def readline(self) -> bytes:
        if self._q:
            return self._q.pop(0)
        return _data_line() if self._acked else b""

    def write(self, cmd: bytes) -> int:
        self.writes.append(cmd)
        self._q.append(b"# ack cad=1000\n")  # satisfy set_cadence's await
        self._acked = True
        return len(cmd)

    def close(self) -> None:
        return None


def _fake_serial_reader(tmp: Path) -> ec.SerialReader:
    return ec.SerialReader(
        "COM_TEST",
        115200,
        open_fn=_FakeSerial,
        lock_dir=tmp,
        banner_timeout_s=2.0,
    )


def test_set_cadence_is_session_only() -> None:
    print("experiment cadence is session-only (!cad,<ms>,temp) — can't leak (#322):")
    tmp = Path(tempfile.mkdtemp(prefix="cad_"))
    try:
        fake = _FakeSerial()
        reader = ec.SerialReader(
            "COM_TEST", 115200, open_fn=lambda: fake, lock_dir=tmp, banner_timeout_s=2.0
        )
        reader.acquire()
        try:
            reader.set_cadence(0.5)  # 500 ms
        finally:
            reader.release()
        sent = b"".join(fake.writes).decode("ascii")
        assert "cad,500,temp" in sent, sent  # the ephemeral, NVS-skipping variant
        check(True, "set_cadence sends !cad,500,temp (no NVS write -> no leak)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_serial_banner_provenance() -> None:
    print("serial reader captures fw/git/built/run from the boot banner:")
    tmp = Path(tempfile.mkdtemp(prefix="prov_"))
    try:
        reader = _fake_serial_reader(tmp)
        reader.acquire()
        try:
            prov = reader.firmware_provenance()
        finally:
            reader.release()
        assert prov["fw"] == "0.7.0", prov
        assert prov["git"] == "abc1234", prov
        assert prov["built"] == "Jun 28 2026 12:34:56", prov  # spaces survive parsing
        assert prov["run"] == "bench-329", prov
        check(True, "fw/git/built/run captured (build time with spaces intact)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_experiment_carries_git() -> None:
    print("experiment manifest + CSV header + parse_v1 all carry the git rev:")
    tmp = Path(tempfile.mkdtemp(prefix="prov_"))
    try:
        manifest = ec.run_capture(
            _fake_serial_reader(tmp),
            tmp,
            experiment_id="t_prov",
            subject="prov-test",
            rate_s=0.02,
            duration_s=0.3,
            labels={},
        )
        fw = manifest["firmware"]
        assert fw["version"] == "0.7.0", fw
        assert fw["git"] == "abc1234", fw
        assert fw["built"] == "Jun 28 2026 12:34:56", fw
        check(True, "manifest.firmware carries version + git + built")

        csv = tmp / "t_prov" / "t_prov.csv"
        header = csv.read_text(encoding="utf-8")
        assert "git=abc1234" in header, header[:400]
        assert "built=Jun 28 2026 12:34:56" in header, header[:400]
        check(True, "CSV comment header carries git + build time")

        seg = parse_files([str(csv)]).segments[0]
        assert seg.git == "abc1234", seg.git
        assert seg.firmware_version == "0.7.0", seg.firmware_version
        check(True, "parse_v1 lifts git into the segment header (free reuse)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_synthetic_git_unavailable() -> None:
    print("synthetic capture reports git unavailable, never fabricated:")
    tmp = Path(tempfile.mkdtemp(prefix="prov_"))
    try:
        manifest = ec.run_capture(
            ec.SyntheticReader(seed=3),
            tmp,
            experiment_id="t_synth",
            subject="synth",
            rate_s=0.02,
            duration_s=0.3,
            labels={},
        )
        fw = manifest["firmware"]
        assert fw["version"] == "0.7.0", fw
        assert fw["git"] is None, fw  # genuinely unavailable for a device-free source
        check(True, "synthetic manifest: version present, git=None")

        header = (tmp / "t_synth" / "t_synth.csv").read_text(encoding="utf-8")
        assert "# fw=0.7.0" in header, header[:300]
        assert "git=" not in header, "no fabricated git in the header"
        check(True, "synthetic CSV header has fw, omits git (no fabrication)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_capture_and_schema()
    test_never_stitch_gate()
    test_set_cadence_is_session_only()
    test_serial_banner_provenance()
    test_experiment_carries_git()
    test_synthetic_git_unavailable()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): " + "; ".join(_FAILS))
        raise SystemExit(1)
    print("All checks passed.")
