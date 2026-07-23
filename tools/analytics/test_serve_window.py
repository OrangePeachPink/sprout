"""#918 — range-aware file windowing + a bounded default range, so the dashboard
opens fast: a 7d view never parses the whole multi-week corpus, and a bare request
(no `range`) defaults to the window the client opens with, not all-history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tools.analytics import serve
from tools.analytics.dashboard import RANGE_HOURS

_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)


def _touch(d: Path, *names: str) -> None:
    for n in names:
        (d / n).write_text("x\n", encoding="utf-8")


def _names(paths: list) -> set[str]:
    return {Path(p).name for p in paths}


def test_default_range_is_bounded_not_all() -> None:
    # the fix: a bare request defaults to a bounded window, never all-history
    assert serve._DEFAULT_RANGE == "7d"
    assert RANGE_HOURS[serve._DEFAULT_RANGE] is not None  # a real window, not None/all


def test_all_range_parses_everything_unchanged(tmp_path: Path) -> None:
    # range=all (hours=None) must serve the full corpus on demand — no fidelity loss
    _touch(tmp_path, "devA_20260101_000000.csv", "devA_20260709_000000.csv")
    assert serve._window_inputs([str(tmp_path)], None, _NOW) == [str(tmp_path)]


def test_window_drops_files_entirely_before_the_window(tmp_path: Path) -> None:
    # window = 7d from 07-10 -> starts 07-03. Files fully before it (with a newer
    # straddler present) are skipped; the straddler + in-window files are kept.
    _touch(
        tmp_path,
        "devA_20260620_000000.csv",  # fully before -> dropped
        "devA_20260625_000000.csv",  # the straddler (newest starting <= 07-03)
        "devA_20260709_000000.csv",  # in window
    )
    out = _names(serve._window_inputs([str(tmp_path)], RANGE_HOURS["7d"], _NOW))
    assert "devA_20260620_000000.csv" not in out
    assert out == {"devA_20260625_000000.csv", "devA_20260709_000000.csv"}


def test_straddler_kept_so_no_in_window_row_is_dropped(tmp_path: Path) -> None:
    # a single old file that is still the newest for its device holds current rows —
    # it must never be dropped (it straddles the window boundary).
    _touch(tmp_path, "devA_20260101_000000.csv")
    out = _names(serve._window_inputs([str(tmp_path)], RANGE_HOURS["7d"], _NOW))
    assert out == {"devA_20260101_000000.csv"}


def test_windows_each_device_independently(tmp_path: Path) -> None:
    # devA rotates often (drop its oldest), devB has one old active file (keep it)
    _touch(
        tmp_path,
        "devA_20260601_000000.csv",
        "devA_20260628_000000.csv",  # devA straddler
        "devA_20260709_000000.csv",
        "devB_20260210_000000.csv",  # devB's only/active file -> kept
    )
    out = _names(serve._window_inputs([str(tmp_path)], RANGE_HOURS["7d"], _NOW))
    assert "devA_20260601_000000.csv" not in out
    assert "devB_20260210_000000.csv" in out  # never drop a device's newest file
    assert {"devA_20260628_000000.csv", "devA_20260709_000000.csv"} <= out


def test_undated_files_always_kept(tmp_path: Path) -> None:
    # a file with no parseable date can't be windowed safely -> always parsed
    _touch(
        tmp_path,
        "nodate.csv",
        "devA_20260601_000000.csv",
        "devA_20260628_000000.csv",
        "devA_20260709_000000.csv",
    )
    out = _names(serve._window_inputs([str(tmp_path)], RANGE_HOURS["7d"], _NOW))
    assert "nodate.csv" in out
