"""#1330 — the epoch stamp + admissibility sweep: the ratified rules encoded, and
the classification-order property that keeps bench evidence out of the delete set."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_registry import Device, Registry
from epoch_sweep import (
    DELETE_UNWIRED,
    KEEP_ADMISSIBLE,
    KEEP_LAB_RECORD,
    PRODUCTION_EPOCH,
    classify_file,
    execute_sweep,
    plan_epoch_stamp,
    plan_sweep,
    sweep_is_executable,
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
