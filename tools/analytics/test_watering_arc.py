"""Tests for the per-plant watering dose->response arc (#836).

Fixture-based (synthetic captures mirroring the 2026-07-06/07 packet shape) so the
baseline->wettest->settle arc, the measured-cup label, the honest gap, the snapshot
exclusion, and the suspect-window guard are deterministic and decoupled from the live
evidence.
"""

from __future__ import annotations

import xml.dom.minidom as minidom
from pathlib import Path

from tools.analytics import watering_arc as wa


def _capture(path: Path, header: str, raws: list[int]) -> None:
    body = "ts_utc,device_seq,raw,band\n" + "".join(
        f"2026-07-07T02:{i:02d}:00+00:00,{100 + i},{r},dry\n"
        for i, r in enumerate(raws)
    )
    path.write_text(f"# {header}\n{body}", encoding="utf-8")


def _fixture_dir(tmp_path: Path) -> Path:
    d = tmp_path / "captures"
    d.mkdir()
    _capture(
        d / "p10-pothos-office.csv",
        "plant=p10 Pothos (office) sensor=s1 ip=192.168.68.85 dose_ml=118.0",
        [2446, 1900, 1400, 1734],  # baseline -> wettest 1400 -> settle 1734
    )
    _capture(
        d / "p10-pothos-office-d2.csv",  # a later dose — NOT the base arc
        "plant=p10 Pothos (office) d2 sensor=s1 ip=192.168.68.85 dose_ml=59.0",
        [1734, 1600],
    )
    # a base capture with a header but no data rows -> honest gap, no column
    (d / "p99-empty.csv").write_text(
        "# plant=p99 Empty sensor=s1 dose_ml=0.0\nts_utc,device_seq,raw,band\n", "utf-8"
    )
    # a cross-plant snapshot must be excluded
    (d / "24h-final-2026-07-08.csv").write_text("plant,raw\np10,1734\n", "utf-8")
    return d


def test_build_arcs_from_base_captures_only(tmp_path: Path) -> None:
    arcs = wa.build_arcs(_fixture_dir(tmp_path))
    assert [a["plant_id"] for a in arcs] == ["p10"]  # d2, empty, snapshot all excluded
    a = arcs[0]
    assert a["plant"] == "Pothos (office)"
    assert a["probe"] == "s1"
    assert a["dose_cups"] == 0.5  # 118 / 236.588
    assert a["baseline"] == 2446  # first raw
    assert a["wettest"] == 1400  # lowest raw = wettest reached
    assert a["settle"] == 1734  # last raw
    assert a["n"] == 4
    assert a["suspect"] is False


def test_render_svg_is_wellformed_with_markers_and_dose(tmp_path: Path) -> None:
    svg = wa.render_svg(wa.build_arcs(_fixture_dir(tmp_path)))
    minidom.parseString(svg)  # raises if not well-formed XML
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "p10" in svg
    assert "0.5c" in svg  # the measured-cup dose annotation
    assert "no invented %" in svg  # the honest-data caption


_ARC_POLYLINE = (
    'stroke-opacity="0.3" stroke-width="1.5"'  # the baseline->wettest->settle line
)


def test_suspect_arc_is_greyed_not_drawn_as_a_response() -> None:
    # a suspect window renders as a greyed, labelled column — never a real arc
    suspect = {
        "plant_id": "p02",
        "plant": "Pothos (XXL)",
        "probe": "s2",
        "dose_cups": 1.0,
        "baseline": 661,
        "wettest": 661,
        "settle": 2840,
        "n": 2,
        "suspect": True,
    }
    svg = wa.render_svg([suspect])
    minidom.parseString(svg)
    assert "suspect &#183; see README" in svg  # labelled as suspect
    assert _ARC_POLYLINE not in svg  # the dose->response line is NOT drawn for a fault


def test_normal_arc_draws_the_response_polyline() -> None:
    normal = {
        "plant_id": "p10",
        "plant": "Pothos (office)",
        "probe": "s1",
        "dose_cups": 0.5,
        "baseline": 2446,
        "wettest": 1400,
        "settle": 1734,
        "n": 4,
        "suspect": False,
    }
    assert _ARC_POLYLINE in wa.render_svg([normal])  # a real response IS drawn


def test_empty_arc_list_still_renders(tmp_path: Path) -> None:
    # zero dosed plants -> the ladder still renders (no divide-by-zero)
    svg = wa.render_svg([])
    minidom.parseString(svg)
    assert "<svg" in svg
