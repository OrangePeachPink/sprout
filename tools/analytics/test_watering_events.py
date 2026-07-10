"""Tests for the event-annotated watering dose->response view (#835).

Fixture-based (synthetic per-plant captures mirroring the 2026-07-06/07 packet shape)
so the header parse, the measured-dose annotation, the suspect flag, and the DuckDB
annotated view are deterministic and decoupled from the live evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import watering_events as we


def _capture(path: Path, header: str, rows: list[tuple]) -> None:
    body = "ts_utc,device_seq,raw,band\n" + "".join(
        f"{ts},{seq},{raw},{band}\n" for ts, seq, raw, band in rows
    )
    path.write_text(f"# {header}\n{body}", encoding="utf-8")


def _fixture_dir(tmp_path: Path) -> Path:
    d = tmp_path / "captures"
    d.mkdir()
    _capture(
        d / "p03-pothos-xl.csv",
        "plant=p03 Pothos (XL) sensor=s4 ip=192.168.68.85 dose_ml=177.0",
        [
            ("2026-07-07T02:05:00+00:00", 100, 2334, "needs water"),
            ("2026-07-07T02:05:30+00:00", 101, 2240, "needs water"),
            ("2026-07-07T02:06:00+00:00", 102, 2053, "OK"),
        ],
    )
    _capture(
        d / "p03-pothos-xl-d2.csv",
        "plant=p03 Pothos (XL) d2 sensor=s4 ip=192.168.68.85 dose_ml=118.0",
        [("2026-07-07T14:00:00+00:00", 200, 1961, "needs water")],
    )
    # the maintainer-flagged p02 dose-3 fault window (raw physically impossible)
    _capture(
        d / "p02-pothos-xxl-d3.csv",
        "plant=p02 Pothos (XXL) d3 sensor=s2 ip=192.168.68.87 dose_ml=237.0",
        [
            ("2026-07-07T02:00:00+00:00", 300, 661, "submerged"),
            ("2026-07-07T02:23:00+00:00", 301, 2840, "dry"),
        ],
    )
    # a cross-plant snapshot must be EXCLUDED (different, one-row-per-plant shape)
    (d / "22h-snapshot-2026-07-07.csv").write_text("plant,raw\np03,1961\n", "utf-8")
    return d


def test_capture_files_are_the_per_plant_captures_not_snapshots(tmp_path: Path) -> None:
    files = we.capture_files(_fixture_dir(tmp_path))
    names = {p.name for p in files}
    assert names == {
        "p02-pothos-xxl-d3.csv",
        "p03-pothos-xl.csv",
        "p03-pothos-xl-d2.csv",
    }
    assert not any(n.startswith("22h") for n in names)  # snapshot excluded


def test_parse_capture_reads_the_dose_header_and_rows(tmp_path: Path) -> None:
    cap = we.parse_capture(_fixture_dir(tmp_path) / "p03-pothos-xl.csv")
    assert cap["plant_id"] == "p03"
    assert cap["plant"] == "Pothos (XL)"  # spaced name captured whole
    assert cap["sensor"] == "s4"
    assert cap["dose_ml"] == 177.0
    assert cap["dose_n"] == 1
    assert len(cap["rows"]) == 3
    assert cap["rows"][0]["raw"] == "2334"


def test_dose_number_and_name_from_the_d2_suffix(tmp_path: Path) -> None:
    cap = we.parse_capture(_fixture_dir(tmp_path) / "p03-pothos-xl-d2.csv")
    assert cap["dose_n"] == 2
    assert cap["plant"] == "Pothos (XL)"  # the " d2" marker stripped from the name


def test_dose_rows_carry_measured_cups_and_window(tmp_path: Path) -> None:
    caps = [we.parse_capture(p) for p in we.capture_files(_fixture_dir(tmp_path))]
    doses = {(d["plant_id"], d["dose_n"]): d for d in we.dose_rows(caps)}
    d1 = doses[("p03", 1)]
    assert d1["dose_ml"] == 177.0
    assert d1["dose_cups"] == 0.75  # 177 / 236.588
    assert d1["window_start_utc"] == "2026-07-07T02:05:00+00:00"
    assert d1["window_end_utc"] == "2026-07-07T02:06:00+00:00"
    assert d1["n_samples"] == 3
    assert d1["suspect"] is False


def test_p02_dose3_is_flagged_suspect_but_kept_verbatim(tmp_path: Path) -> None:
    caps = [we.parse_capture(p) for p in we.capture_files(_fixture_dir(tmp_path))]
    dose = next(
        d for d in we.dose_rows(caps) if d["plant_id"] == "p02" and d["dose_n"] == 3
    )
    assert dose["suspect"] is True
    assert dose["suspect_reason"]  # a stated reason, not a silent drop
    # the impossible raw values are KEPT (they are the evidence of the fault)
    reads = [r for r in we.reading_rows(caps) if r["plant_id"] == "p02"]
    assert {r["raw"] for r in reads} == {661, 2840}
    assert all(r["suspect"] for r in reads)  # each fault-window row inherits the flag


def test_build_store_and_annotated_view(tmp_path: Path) -> None:
    out = tmp_path / "store.duckdb"
    summary = we.build_store(_fixture_dir(tmp_path), out)
    assert summary["plants"] == 2
    assert summary["doses"] == 3
    assert summary["readings"] == 6
    assert summary["suspect_doses"] == 1

    # the view carries each reading next to the dose that produced it
    rows = we.query(
        "SELECT raw, band, dose_cups, dose_n, suspect FROM watering_annotated "
        "WHERE plant_id = 'p03' AND dose_n = 1 ORDER BY ts_utc",
        out,
    )
    assert [r["raw"] for r in rows] == [2334, 2240, 2053]
    assert all(r["dose_cups"] == 0.75 for r in rows)  # dose annotation joined in
    assert all(r["suspect"] is False for r in rows)

    # a suspect reading is queryable AND self-labelled in the view
    susp = we.query(
        "SELECT raw, suspect, suspect_reason FROM watering_annotated WHERE suspect",
        out,
    )
    assert {r["raw"] for r in susp} == {661, 2840}
    assert all(r["suspect_reason"] for r in susp)
