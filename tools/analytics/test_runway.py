"""Tests for the basin depletion -> runway estimate (PRD-0006 R1, #478).

Covers the human-terms banding, the pump-cycle accounting draw, honest confidence
labelling (assumed vs measured rate), and the honest-degradation edges (no draw,
empty basin, over-full clamp).
"""

from __future__ import annotations

from tools.analytics import runway as rw


def test_daily_draw_from_schedule() -> None:
    # 2 L/hr for 60 s/cycle x 12 cycles/day = 12 min/day on = 0.2 h x 2 = 0.4 L/day.
    assert rw.daily_draw_from_schedule(2.0, 60.0, 12.0) == 0.4


def test_daily_draw_nonpositive_inputs_are_zero() -> None:
    assert rw.daily_draw_from_schedule(0.0, 60.0, 12.0) == 0.0
    assert rw.daily_draw_from_schedule(2.0, 0.0, 12.0) == 0.0
    assert rw.daily_draw_from_schedule(2.0, 60.0, 0.0) == 0.0


def test_bands_across_runway() -> None:
    # capacity 5 L; vary daily draw to land each human band.
    assert rw.estimate_runway(5.0, 5.0, 6.0).band == "act-today"  # ~0.83 d
    assert rw.estimate_runway(5.0, 5.0, 2.0).band == "a-couple-days"  # 2.5 d
    assert rw.estimate_runway(5.0, 5.0, 1.0).band == "about-a-week"  # 5 d
    assert rw.estimate_runway(5.0, 5.0, 0.5).band == "plenty"  # 10 d


def test_confidence_is_low_until_rate_measured() -> None:
    assumed = rw.estimate_runway(5.0, 3.0, 1.0)
    assert assumed.confidence == "low"
    assert any("datasheet" in c or "assumption" in c for c in assumed.caveats)
    measured = rw.estimate_runway(5.0, 3.0, 1.0, rate_measured=True)
    assert measured.confidence == "moderate"
    assert "measured rate" in measured.label


def test_no_draw_is_indeterminate_not_act_today() -> None:
    est = rw.estimate_runway(5.0, 3.0, None)
    assert est.days_remaining is None
    assert est.band == "plenty" and est.confidence == "low"
    assert any("indeterminate" in c for c in est.caveats)


def test_empty_basin_is_act_today() -> None:
    est = rw.estimate_runway(5.0, 0.0, 1.0)
    assert est.band == "act-today"
    assert "empty" in est.human


def test_overfull_level_clamped_to_capacity() -> None:
    est = rw.estimate_runway(5.0, 7.0, 1.0)
    assert est.liters_remaining == 5.0
    assert any("exceeds capacity" in c for c in est.caveats)


def test_labelled_derived_value_shape() -> None:
    # AC: a clearly-labelled derived value with honest fields (no false precision).
    d = rw.estimate_runway(5.0, 4.0, 1.0).as_dict()
    assert set(d) >= {"band", "human", "confidence", "label", "days_remaining"}
    assert d["days_remaining"] == 4.0
    assert "derived runway estimate" in d["label"]


def test_cli_reports_human_terms(capsys) -> None:
    rc = rw.main(
        [
            "--capacity",
            "5",
            "--level",
            "5",
            "--rate",
            "2",
            "--cycle-seconds",
            "60",
            "--cycles-per-day",
            "12",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "runway:" in out and "confidence" in out


def test_cli_rate_without_cycle_args_errors(capsys) -> None:
    rc = rw.main(["--capacity", "5", "--level", "5", "--rate", "2"])
    assert rc == 2
    assert "cycle-seconds" in capsys.readouterr().err
