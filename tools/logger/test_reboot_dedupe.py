"""#703 — pin the reboot-session dedupe invariant on the RESTART SEED path.

The fleet logger's restart-dedupe seeds `Store` from recent on-disk segments
(#585) so a restart never re-appends a persisted row. Its safety rests on
`session_id` being in the dedupe key: a device that reboots mid-run mints a NEW
`session_id` and its `device_seq` resets toward 0, so a post-reboot `device_seq=N`
row has a DIFFERENT key than a pre-reboot `device_seq=N` row sitting in the seed
window - correctly kept, not falsely dropped as a "dup". Without `session_id` in
the key the seed would trade a visible duplicate for a SILENT post-reboot data
loss. This holds today; this test pins it so a future key/seed change can't
silently break it over a long unattended run.
"""

from __future__ import annotations

from pathlib import Path

from tools.logger.fleet_logger import seed_store_from_disk

_ANALYTICS = Path(__file__).resolve().parents[1] / "analytics"
from tools.analytics.ingest_store import Store  # noqa: E402
from tools.analytics.parse_v1 import parse_files  # noqa: E402

_HEADER = (
    "# schema_version=4  fw=0.8.0  git=t  device_id=dev-0\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _soil(session: str, seq: int, raw: int = 1900) -> str:
    ts = "2026-07-05T00:00:30.000Z"
    return (
        f"plants.soil,{ts},{ts[:-1]},{session},dev-0,s1,{raw},OK,"
        f"level=needs water;device_seq={seq}\n"
    )


def _reading(path: Path, session: str, seq: int, raw: int = 1900):
    path.write_text(_HEADER + _COLS + _soil(session, seq, raw), encoding="utf-8")
    return parse_files([str(path)]).readings[0]


def test_post_reboot_row_survives_the_restart_seed(tmp_path: Path) -> None:
    # a pre-reboot segment sits on disk in the seed window (session A, device_seq 3)
    seeddir = tmp_path / "seed"
    seeddir.mkdir()
    (seeddir / "pre.csv").write_text(_HEADER + _COLS + _soil("sessA", 3), "utf-8")
    store = Store()
    seeded = seed_store_from_disk(store, str(seeddir))
    assert seeded >= 1  # the pre-reboot row is in the dedupe window

    # the board reboots: a NEW session (B), device_seq resets and hits 3 again
    post = _reading(tmp_path / "post.csv", "sessB", 3)
    assert store.ingest(post) is True  # KEPT — session_id disambiguates the reboot

    # a genuine store-and-forward replay (same session A, same device_seq 3) IS dropped
    replay = _reading(tmp_path / "replay.csv", "sessA", 3)
    assert store.ingest(replay) is False  # dropped — the dedupe still works


def test_session_id_is_load_bearing_same_seq_different_sessions_both_kept(
    tmp_path: Path,
) -> None:
    # the invariant stated directly: identical device_seq across two sessions are
    # two distinct rows (the reboot case), never collapsed.
    store = Store()
    a = _reading(tmp_path / "a.csv", "sessA", 1)
    b = _reading(tmp_path / "b.csv", "sessB", 1)
    assert store.ingest(a) is True
    assert store.ingest(b) is True  # NOT dropped despite the shared device_seq=1
    assert store.ingest(a) is False  # ...but a true replay of A still is
