"""#827: parse-once, serve-from-memory. The cache must be a drop-in for parse_files
(identical merged LogData) while re-reading only files whose (size, mtime) changed -
so the immutable corpus is parsed once and the active tail stays fresh, never a stale
snapshot presented as live.
"""

from __future__ import annotations

import collections
from pathlib import Path

from tools.analytics.parse_cache import ParseCache
from tools.analytics.parse_v1 import parse_file, parse_files

_HEADER = (
    "# fw=0.7.0  git=cachetest  run=r1\n"
    "# device_id=plants_esp32_test  schema_version=1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(i: int, raw: int) -> str:
    ts = f"2026-06-28T00:{i // 60:02d}:{i % 60:02d}.000Z"
    return f"plants.soil,{ts},{ts[:-1]},sess1,s1,{raw},OK,level=OK\n"


def _write(p: Path, rows: list[str]) -> None:
    p.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")


def _counting():
    calls: collections.Counter = collections.Counter()

    def parse_one(path):
        calls[str(path)] += 1
        return parse_file(path)

    return calls, parse_one


def test_load_matches_parse_files_exactly(tmp_path: Path) -> None:
    _write(tmp_path / "a.csv", [_row(i, 1500 + i) for i in range(5)])
    _write(tmp_path / "b.csv", [_row(i, 2000 + i) for i in range(3)])
    got = ParseCache().load([str(tmp_path)])
    ref = parse_files([str(tmp_path)])
    assert [r.raw_value for r in got.readings] == [r.raw_value for r in ref.readings]
    assert len(got.segments) == len(ref.segments)
    assert got.sources == ref.sources


def test_unchanged_corpus_is_parsed_once(tmp_path: Path) -> None:
    _write(tmp_path / "a.csv", [_row(i, 1500 + i) for i in range(4)])
    _write(tmp_path / "b.csv", [_row(i, 2000 + i) for i in range(4)])
    calls, parse_one = _counting()
    cache = ParseCache(parse_one=parse_one)
    cache.load([str(tmp_path)])
    assert sum(calls.values()) == 2  # each file parsed once
    cache.load([str(tmp_path)])
    cache.load([str(tmp_path)])
    assert sum(calls.values()) == 2  # ...and never again while unchanged


def test_only_the_grown_file_is_reparsed_and_new_rows_appear(tmp_path: Path) -> None:
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    _write(a, [_row(i, 1500 + i) for i in range(4)])
    _write(b, [_row(i, 2000 + i) for i in range(4)])
    calls, parse_one = _counting()
    cache = ParseCache(parse_one=parse_one)
    cache.load([str(tmp_path)])
    # the active file grows by a poll (append two rows -> size changes -> new sig)
    with a.open("a", encoding="utf-8") as fh:
        fh.write(_row(10, 1600) + _row(11, 1601))
    out = cache.load([str(tmp_path)])
    # #859: a grown file is TAIL-appended, NOT fully re-parsed -> parse_one stays at 1
    assert calls[str(a)] == 1  # NOT re-parsed whole; only the tail bytes were read
    assert calls[str(b)] == 1  # b reused from memory (unchanged)
    assert 1601 in [r.raw_value for r in out.readings]  # the fresh rows are served


def test_new_session_file_is_picked_up(tmp_path: Path) -> None:
    _write(tmp_path / "a.csv", [_row(i, 1500 + i) for i in range(3)])
    cache = ParseCache()
    assert cache.stats()["files"] == 0
    cache.load([str(tmp_path)])
    assert cache.stats()["files"] == 1
    _write(tmp_path / "b.csv", [_row(i, 2000 + i) for i in range(3)])  # a rotation
    out = cache.load([str(tmp_path)])
    assert cache.stats()["files"] == 2
    assert 2002 in [r.raw_value for r in out.readings]


def test_truncated_file_is_reparsed_not_half_read(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    _write(a, [_row(i, 1500 + i) for i in range(8)])
    calls, parse_one = _counting()
    cache = ParseCache(parse_one=parse_one)
    first = cache.load([str(tmp_path)])
    assert len(first.readings) == 8
    _write(a, [_row(i, 1500 + i) for i in range(2)])  # shrank (rotation/rewrite)
    second = cache.load([str(tmp_path)])
    assert calls[str(a)] == 2  # size shrank -> re-parsed
    assert len(second.readings) == 2  # honest: not the stale 8


def test_vanished_file_is_evicted(tmp_path: Path) -> None:
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    _write(a, [_row(i, 1500 + i) for i in range(3)])
    _write(b, [_row(i, 2000 + i) for i in range(3)])
    cache = ParseCache()
    cache.load([str(tmp_path)])
    assert cache.stats()["files"] == 2
    b.unlink()  # archived / cleaned up
    out = cache.load([str(tmp_path)])
    assert cache.stats()["files"] == 1  # footprint tracks the live corpus
    assert all(r.raw_value < 2000 for r in out.readings)  # b's rows gone


# --------------------------------------------------------------------------- #
# #859: byte-offset tail-append — correctness fence = tail == full parse
# --------------------------------------------------------------------------- #


def _reads(data) -> list[tuple]:
    return [(r.timestamp_utc, r.sensor_id, r.raw_value) for r in data.readings]


def test_tail_append_matches_a_full_parse_of_the_grown_file(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    _write(a, [_row(i, 1500 + i) for i in range(5)])
    cache = ParseCache()
    cache.load([str(tmp_path)])  # full parse, anchors the tail
    with a.open("a", encoding="utf-8") as fh:  # a poll appends rows
        for i in range(5, 12):
            fh.write(_row(i, 1500 + i))
    tailed = cache.load([str(tmp_path)])  # tail-append only the new bytes
    full = parse_files([str(tmp_path)])  # ground truth
    assert _reads(tailed) == _reads(full)  # row-for-row identical
    assert len(tailed.segments) == len(full.segments)


def test_tail_handles_a_new_segment_header_appended(tmp_path: Path) -> None:
    # a mid-file re-init (fresh header block + rows) must be captured, not skipped
    a = tmp_path / "a.csv"
    _write(a, [_row(i, 1500 + i) for i in range(3)])
    cache = ParseCache()
    cache.load([str(tmp_path)])
    with a.open("a", encoding="utf-8") as fh:
        fh.write(_HEADER + _COLS + "".join(_row(i, 1700 + i) for i in range(3)))
    tailed = cache.load([str(tmp_path)])
    full = parse_files([str(tmp_path)])
    assert _reads(tailed) == _reads(full)
    assert len(tailed.segments) == len(full.segments)  # the new segment is captured


def test_partial_trailing_line_is_deferred_then_completed(tmp_path: Path) -> None:
    # a half-written row (no trailing newline) must not be served; when the writer
    # finishes the line it lands, and the result matches a full parse.
    a = tmp_path / "a.csv"
    _write(a, [_row(i, 1500 + i) for i in range(3)])
    cache = ParseCache()
    cache.load([str(tmp_path)])
    with a.open("a", encoding="utf-8") as fh:
        fh.write(_row(9, 1999).rstrip("\n"))  # a mid-write: no newline yet
    mid = cache.load([str(tmp_path)])
    assert 1999 not in [r.raw_value for r in mid.readings]  # not served half-written
    with a.open("a", encoding="utf-8") as fh:
        fh.write("\n")  # the writer completes the row
    done = cache.load([str(tmp_path)])
    assert 1999 in [r.raw_value for r in done.readings]  # now it lands
    assert _reads(done) == _reads(parse_files([str(tmp_path)]))


def test_repeated_polls_tail_incrementally(tmp_path: Path) -> None:
    # several poll-sized appends in a row, each staying consistent with a full parse
    a = tmp_path / "a.csv"
    _write(a, [_row(0, 1500)])
    cache = ParseCache()
    cache.load([str(tmp_path)])
    for i in range(1, 6):
        with a.open("a", encoding="utf-8") as fh:
            fh.write(_row(i, 1500 + i))
        got = cache.load([str(tmp_path)])
        assert _reads(got) == _reads(parse_files([str(tmp_path)]))
