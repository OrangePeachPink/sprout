"""End-to-end host pre-validation for plants.env integration (#376).

Proves the proven host path: the synthetic esp32dev_env sample (make_env_sample,
per the ratified schema) flows clean through parse_v1 -> build_context -> render,
with env rows parsed by their class and the soil views uncontaminated. Firmware's
#376 rebase can validate its real device output against this known-good target.
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.dashboard import build_context, render
from tools.analytics.make_env_sample import env_sample_text
from tools.analytics.parse_v1 import parse_files


def _parse(tmp_path: Path):
    log = tmp_path / "env_sample.csv"
    log.write_text(env_sample_text(n_sweeps=8), encoding="utf-8")
    return parse_files([str(log)])


def test_sample_has_both_record_types(tmp_path: Path) -> None:
    data = _parse(tmp_path)
    rts = {}
    for r in data.readings:
        rts[r.record_type] = rts.get(r.record_type, 0) + 1
    assert rts["plants.soil"] == 32  # 4 channels x 8 sweeps
    assert rts["plants.env"] == 64  # (2 SHT45 + 6 AS7263) x 8 sweeps


def test_env_rows_parse_by_class(tmp_path: Path) -> None:
    env = [r for r in _parse(tmp_path).readings if r.record_type == "plants.env"]
    # SHT45 is factory-calibrated -> value/unit populated
    temp = next(r for r in env if r.channel == "ambient_temp")
    assert temp.value == 23.0 and temp.unit == "degC" and temp.raw_value is None
    rh = next(r for r in env if r.channel == "ambient_rh")
    assert rh.unit == "pctRH" and rh.value is not None
    # AS7263 NIR -> raw counts, no fabricated engineering value; six bands present
    bands = sorted(r.channel for r in env if r.channel.startswith("nir_"))
    assert len(set(bands)) == 6 and "nir_610" in bands and "nir_860" in bands
    nir = next(r for r in env if r.channel == "nir_610")
    assert nir.raw_value is not None and nir.value is None and (nir.unit or "") == ""


def test_soil_views_uncontaminated_and_renders(tmp_path: Path) -> None:
    ctx = build_context(_parse(tmp_path))
    # only the four soil channels reach the soil views
    assert sorted(s["id"] for s in ctx["sensors"]) == ["s1", "s2", "s3", "s4"]
    # cross-channel spread is soil-only (~120), NOT polluted by NIR counts (800+).
    # #651: spread is now a per-device list; this fixture is one device.
    assert ctx["spread"], "expected a per-device spread series"
    assert max(s["max"] for s in ctx["spread"]) < 300
    # calibrated env value/unit does not trip the soil raw-only contract (#324)
    assert ctx["provenance"]["contract"]["raw_only"] is True
    # the full dashboard renders without error on the mixed log
    html = render(ctx)
    assert "<html" in html.lower() and len(html) > 10_000


def test_env_quality_flags_survive(tmp_path: Path) -> None:
    # a SUSPECT soil row + a SATURATED NIR row must round-trip (surfaced, not dropped)
    flags = {r.quality_flag for r in _parse(tmp_path).readings}
    assert "SUSPECT" in flags and "SATURATED" in flags
