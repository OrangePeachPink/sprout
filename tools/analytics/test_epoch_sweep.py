"""#1330 — the epoch stamp + admissibility sweep: the ratified rules encoded, and
the classification-order property that keeps bench evidence out of the delete set."""

from __future__ import annotations

import json
from pathlib import Path

from tools.analytics.device_registry import Device, Registry
from tools.analytics.epoch_sweep import (
    DELETE_UNWIRED,
    KEEP_ADMISSIBLE,
    KEEP_LAB_RECORD,
    PRODUCTION_EPOCH,
    apply_epoch_stamps,
    classify_file,
    execute_sweep,
    plan_epoch_stamp,
    plan_sweep,
    sweep_is_executable,
    write_tombstone,
)

_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _log(d: Path, name: str, device: str, stamps: list[str]) -> Path:
    p = d / name
    rows = "".join(
        f"plants.soil,{ts},x,s1,{device},s1,1500,OK,level=OK\n" for ts in stamps
    )
    p.write_text(
        f"# schema_version=4  fw=0.8.0  git=t  device_id={device}  session_id=s1\n"
        + _COLS
        + rows,
        encoding="utf-8",
    )
    return p


def _registry() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="y9d41p",
                board="esp32dev",
                label="classic",
                channels={"s1": {"plant_id": "p11", "plant_name": "corn"}},
            ),
            Device(device_id="bench1", board="esp32c5", label="b", channels={}),
        ]
    )


WIRED, KNOWN = {"y9d41p"}, {"y9d41p", "bench1"}
POST = "2026-07-07T01:09:57.000000Z"  # after the epoch
EPOCH_S = "2026-07-06T00:00:06Z"


def test_epoch_is_the_ratified_instant() -> None:
    assert PRODUCTION_EPOCH.isoformat() == "2026-07-06T00:00:06+00:00"


def test_pre_epoch_legacy_identity_is_lab_record_never_deleted(tmp_path: Path) -> None:
    # THE regression. The archive holds pre-epoch files under legacy device names
    # (c5off1 / plants_esp32_f4e9d4) minted before ADR-0027; the registry's #602
    # previous_ids coalesce field is empty, so an unwired-FIRST classification calls
    # a production board's own bench history "never registered" and proposes deleting
    # it — including the rows the ratified band ladder was derived from.
    f = _log(
        tmp_path,
        "c5off1_20260704_000433.csv",
        "c5off1",
        ["2026-07-04T00:04:33.000000Z", "2026-07-04T04:59:00.000000Z"],
    )
    got = classify_file(f, WIRED, KNOWN)
    assert got["class"] == KEEP_LAB_RECORD  # NOT DELETE_UNWIRED
    assert got["devices"] == ["c5off1"]  # an unknown id, and still protected


def test_post_epoch_unwired_is_the_delete_case(tmp_path: Path) -> None:
    f = _log(
        tmp_path,
        "n3jhsp_20260707_010957.csv",
        "n3jhsp",
        ["2026-07-07T01:09:57.000000Z"],
    )
    assert classify_file(f, WIRED, KNOWN)["class"] == DELETE_UNWIRED


def test_post_epoch_wired_is_admissible(tmp_path: Path) -> None:
    f = _log(
        tmp_path,
        "y9d41p_20260710_000000.csv",
        "y9d41p",
        ["2026-07-10T00:00:00.000000Z"],
    )
    assert classify_file(f, WIRED, KNOWN)["class"] == KEEP_ADMISSIBLE


def test_a_registered_but_never_wired_bench_board_post_epoch_deletes(tmp_path) -> None:
    f = _log(
        tmp_path,
        "bench1_20260710_000000.csv",
        "bench1",
        ["2026-07-10T00:00:00.000000Z"],
    )
    assert classify_file(f, WIRED, KNOWN)["class"] == DELETE_UNWIRED


def test_the_committed_example_registry_is_refused(tmp_path: Path) -> None:
    # stamping a production epoch into a public fixture would be worse than a no-op
    class _M:
        def open_assignments(self):
            raise AssertionError("must refuse before reading assignments")

    got = plan_epoch_stamp(_M(), Path("config/devices.example.json"))
    assert got["ok"] is False and "EXAMPLE" in got["reason"]


def test_an_unresolved_citation_blocks_the_sweep(tmp_path: Path) -> None:
    logs, arch, docs = (
        tmp_path / "logs",
        tmp_path / "arch",
        tmp_path / "docs" / "experiments",
    )
    for d in (logs, arch, docs):
        d.mkdir(parents=True)
    _log(logs, "n3jhsp_20260707_010957.csv", "n3jhsp", [POST])
    (docs / "bench.md").write_text(
        "see logs/gone_20260628_183018.csv\n", encoding="utf-8"
    )
    plan = plan_sweep(logs, arch, docs, _registry())
    assert plan["unresolved_citations"] and sweep_is_executable(plan) is False
    assert execute_sweep(plan, arch, approved=True)["executed"] is False


def test_a_cited_file_is_held_back_even_when_unwired(tmp_path: Path) -> None:
    logs, arch, docs = (
        tmp_path / "logs",
        tmp_path / "arch",
        tmp_path / "docs" / "experiments",
    )
    for d in (logs, arch, docs):
        d.mkdir(parents=True)
    _log(logs, "n3jhsp_20260707_010957.csv", "n3jhsp", [POST])
    (docs / "b.md").write_text("logs/n3jhsp_20260707_010957.csv\n", encoding="utf-8")
    plan = plan_sweep(logs, arch, docs, _registry())
    assert [f["file"] for f in plan["blocked_by_citation"]] == [
        "n3jhsp_20260707_010957.csv"
    ]
    assert plan["to_delete"] == []  # the citation outranks the class


def test_execute_refuses_without_approval_and_dry_run_writes_nothing(tmp_path) -> None:
    logs, arch, docs = (
        tmp_path / "logs",
        tmp_path / "arch",
        tmp_path / "docs" / "experiments",
    )
    for d in (logs, arch, docs):
        d.mkdir(parents=True)
    f = _log(
        logs, "n3jhsp_20260707_010957.csv", "n3jhsp", ["2026-07-07T01:09:57.000000Z"]
    )
    plan = plan_sweep(logs, arch, docs, _registry())
    assert sweep_is_executable(plan) is True
    r = execute_sweep(plan, arch, approved=False)
    assert r["executed"] is False and "not approved" in r["reason"]
    assert f.is_file() and not list(arch.iterdir())  # nothing moved, nothing removed


def test_approved_execute_archives_before_it_deletes(tmp_path: Path) -> None:
    logs, arch, docs = (
        tmp_path / "logs",
        tmp_path / "arch",
        tmp_path / "docs" / "experiments",
    )
    for d in (logs, arch, docs):
        d.mkdir(parents=True)
    f = _log(
        logs, "n3jhsp_20260707_010957.csv", "n3jhsp", ["2026-07-07T01:09:57.000000Z"]
    )
    before = f.read_bytes()
    plan = plan_sweep(logs, arch, docs, _registry())
    r = execute_sweep(plan, arch, approved=True)
    assert r["executed"] is True and r["failures"] == []
    assert not f.exists()  # deleted
    assert (arch / f.name).read_bytes() == before  # ...but preserved verbatim first


def test_stamps_land_on_the_temporal_assignments_and_are_additive(tmp_path) -> None:
    # the stamp must hit `assignments[]` — the record the interval join reads. An
    # already-stamped assignment is left exactly as found; a CLOSED one is history
    # and never re-stamped.
    reg = tmp_path / "devices.local.json"
    reg.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "devices": [{"device_id": "y9d41p", "channels": {"s1": {}, "s2": {}}}],
                "assignments": [
                    {
                        "plant_id": "p11",
                        "device_id": "y9d41p",
                        "channel": "s1",
                        "start_ts": None,
                        "end_ts": None,
                    },
                    {
                        "plant_id": "p02",
                        "device_id": "y9d41p",
                        "channel": "s2",
                        "start_ts": "2026-01-01T00:00:00Z",
                        "end_ts": None,
                    },
                    {
                        "plant_id": "p99",
                        "device_id": "y9d41p",
                        "channel": "s1",
                        "start_ts": None,
                        "end_ts": "2026-05-01T00:00:00Z",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = {
        "ok": True,
        "stamps": [
            {"device_id": "y9d41p", "channel": "s1", "start_ts": EPOCH_S},
            {"device_id": "y9d41p", "channel": "s2", "start_ts": EPOCH_S},
        ],
        "already_stamped": [],
    }
    assert apply_epoch_stamps(reg, plan, approved=False)["written"] is False
    r = apply_epoch_stamps(reg, plan, approved=True)
    assert r["written"] is True and r["stamped"] == 1  # only the open null one
    got = json.loads(reg.read_text(encoding="utf-8"))["assignments"]
    assert got[0]["start_ts"] == EPOCH_S  # stamped
    assert got[1]["start_ts"] == "2026-01-01T00:00:00Z"  # untouched
    assert got[2]["start_ts"] is None  # closed = history, never re-stamped
    assert Path(r["backup"]).is_file()


def test_a_stamp_that_would_be_inert_is_refused(tmp_path: Path) -> None:
    # THE #1330 live-run regression: writing start_ts onto the static
    # devices[].channels[] shape leaves the file looking stamped while
    # open_assignments() still reports null — the interval join sees no change.
    reg = tmp_path / "devices.local.json"
    reg.write_text(
        json.dumps({"devices": [{"device_id": "y9d41p", "channels": {"s1": {}}}]}),
        encoding="utf-8",
    )
    before = reg.read_text(encoding="utf-8")
    plan = {
        "ok": True,
        "stamps": [{"device_id": "y9d41p", "channel": "s1", "start_ts": EPOCH_S}],
        "already_stamped": [],
    }
    r = apply_epoch_stamps(reg, plan, approved=True)
    assert r["written"] is False and "inert" in r["reason"]
    assert reg.read_text(encoding="utf-8") == before  # nothing written


def test_tombstone_records_hashes_before_removal(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    f = _log(logs, "n3jhsp_20260707_010957.csv", "n3jhsp", [POST])
    plan = {
        "to_delete": [
            {
                "file": f.name,
                "path": str(f),
                "devices": ["n3jhsp"],
                "rows": 1,
                "first": None,
                "last": None,
            }
        ]
    }
    dest = tmp_path / "tombstone.json"
    doc = write_tombstone(plan, dest, authority="maintainer (#1330)", ruling="A")
    assert dest.is_file() and doc["n_removed"] == 1
    e = doc["removed"][0]
    assert len(e["sha256"]) == 64 and e["size_bytes"] > 0  # recorded while it EXISTS
    assert "unwired" in e["rule_applied"]
    assert doc["epoch_ruling"]["production_epoch"].startswith("2026-07-06T00:00:06")
    assert f.is_file()  # the tombstone itself removes nothing


def test_a_file_already_in_the_archive_is_never_a_delete_candidate(tmp_path) -> None:
    # the archive IS the preservation destination: "archive then delete" on a file
    # already there would copy it onto itself and then remove the only copy
    logs = tmp_path / "logs"
    arch = tmp_path / "arch"
    docs = tmp_path / "docs" / "experiments"
    for d in (logs, arch, docs):
        d.mkdir(parents=True)
    live = _log(logs, "n3jhsp_20260707_010957.csv", "n3jhsp", [POST])
    kept = _log(arch, "n3jhsp_20260712_000704.csv", "n3jhsp", [POST])
    plan = plan_sweep(logs, arch, docs, _registry())
    names = [f["file"] for f in plan["to_delete"]]
    assert names == ["n3jhsp_20260707_010957.csv"]  # the LIVE one only
    assert [f["file"] for f in plan["already_archived"]] == [kept.name]
    execute_sweep(plan, arch, approved=True)
    assert not live.exists()  # cleared from the live surface
    assert kept.is_file()  # the archived record survives untouched
