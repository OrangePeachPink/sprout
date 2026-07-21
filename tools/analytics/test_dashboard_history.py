"""Tests for the dashboard's long-horizon robustness (#30):
full-history join (live logs + B8 archive, de-duped), time-range windowing, and
downsampling. These are the deep-history deliverables; they had no coverage.
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_context
import dashboard
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.7.0  git=t  run=h\n# device_id=d  schema_version=1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,session_id,sensor_id,raw_value,quality_flag,payload\n"
)


def _seg(ts_list: list[tuple[str, int]]) -> str:
    rows = "".join(
        f"plants.soil,{ts},s1,s1,{raw},OK,level=well watered;gpio=36\n"
        for ts, raw in ts_list
    )
    return _HEADER + _COLS + rows


# --------------------------------------------------------------------------- #
# _dec_idx — downsampling cap
# --------------------------------------------------------------------------- #


def test_dec_idx_under_cap_is_identity() -> None:
    assert card_context._dec_idx(5, 10) == [0, 1, 2, 3, 4]


def test_dec_idx_thins_to_cap() -> None:
    idx = card_context._dec_idx(1000, 100)
    assert len(idx) == 100  # capped
    assert idx[0] == 0
    assert all(0 <= i < 1000 for i in idx)
    assert idx == sorted(idx) and len(set(idx)) == 100  # strictly increasing, unique


def test_max_traj_points_keeps_30d_responsive() -> None:
    # the contract that keeps a 30-day series light enough to render
    assert card_context.MAX_TRAJ_POINTS <= 2000


# --------------------------------------------------------------------------- #
# gather_inputs — full-history join (live logs + B8 .gz archive), de-duped
# --------------------------------------------------------------------------- #


def test_gather_inputs_joins_and_dedupes(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "archive"
    logs = tmp_path / "logs"
    archive.mkdir()
    logs.mkdir()
    # archive holds seg1 + seg2 (gz); logs holds a LIVE seg2 (+ a new seg3)
    (archive / "seg1.csv.gz").write_bytes(gzip.compress(b"x"))
    (archive / "seg2.csv.gz").write_bytes(gzip.compress(b"x"))
    (logs / "seg2.csv").write_text("live", encoding="utf-8")
    (logs / "seg3.csv").write_text("live", encoding="utf-8")
    monkeypatch.setattr(dashboard, "ARCHIVE_DIR", archive)
    monkeypatch.setattr(dashboard, "LOGS_DIR", logs)

    out = dashboard.gather_inputs()
    names = [Path(p).name for p in out]
    # one entry per segment stem, chronological by stem; the LIVE seg2 wins over the .gz
    assert names == ["seg1.csv.gz", "seg2.csv", "seg3.csv"], names


def test_gather_inputs_archive_only(tmp_path: Path, monkeypatch) -> None:
    # history survives after closed segments are pruned from logs/ (only .gz remains)
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "old.csv.gz").write_bytes(gzip.compress(b"x"))
    monkeypatch.setattr(dashboard, "ARCHIVE_DIR", archive)
    monkeypatch.setattr(dashboard, "LOGS_DIR", tmp_path / "no_logs")
    assert [Path(p).name for p in dashboard.gather_inputs()] == ["old.csv.gz"]


# --------------------------------------------------------------------------- #
# filter_since — time-range windowing
# --------------------------------------------------------------------------- #


def test_filter_since_windows_to_recent(tmp_path: Path) -> None:
    log = tmp_path / "span.csv"
    log.write_text(
        _seg(
            [
                ("2026-06-28T00:00:00.000Z", 1500),
                ("2026-06-28T01:00:00.000Z", 1510),
                ("2026-06-28T02:00:00.000Z", 1520),
                ("2026-06-28T03:00:00.000Z", 1530),
            ]
        ),
        encoding="utf-8",
    )
    data = parse_files([str(log)])
    assert len(data.readings) == 4
    # last 1.5 h of a 3 h span -> cutoff at 1.5 h -> keeps the 02:00 and 03:00 readings
    windowed = dashboard.filter_since(data, 1.5)
    assert len(windowed.readings) == 2
    # None = all history, unchanged
    assert len(dashboard.filter_since(data, None).readings) == 4
