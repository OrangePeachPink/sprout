"""#995 — the per-physical-sensor health readout (grill Q8), grounded in SENSOR_QA.md.

Proves the computable QA signals: out-of-envelope (wetter-than-water / drier-than-air),
stuck/stale runs (the Issue-3 symptom), drift, dropouts, device faults, and the
conservative inspect-for-corrosion PROMPT — including its honest-absence behavior when a
sensor is uncalibrated (envelope checks report None, never a false "clean").
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.analytics.parse_v1 import Reading
from tools.analytics.sensor_health import STUCK_RUN, fleet_health, sensor_health

_T0 = datetime(2026, 7, 12, tzinfo=timezone.utc)


def _r(
    raw: int | None,
    *,
    sensor: str = "s01",
    minute: int = 0,
    flag: str = "OK",
    record_type: str = "plants.soil",
) -> Reading:
    """A minimal soil Reading — only the fields sensor_health reads carry meaning."""
    return Reading(
        record_type=record_type,
        timestamp_utc=_T0 + timedelta(minutes=minute),
        timestamp_local=None,
        sample_id=minute,
        session_id="sess1",
        device_id="y9d41p",
        firmware_version="0.7.0",
        logger_version="30000",
        millis_ms=minute * 60000,
        sensor_model="UMLIFE_v2_TLC555",
        sensor_id=sensor,
        sensor_position="",
        channel="s1",
        raw_value=raw,
        value=None,
        unit="",
        quality_flag=flag,
        payload={},
    )


def _series(values: list[int], *, sensor: str = "s01", step_min: int = 30) -> list:
    return [_r(v, sensor=sensor, minute=i * step_min) for i, v in enumerate(values)]


# --------------------------------------------------------------------------- #
# a clean sensor is 'ok' and prompts nothing
# --------------------------------------------------------------------------- #
def test_a_healthy_calibrated_sensor_is_ok() -> None:
    # readings that drift gently within the envelope — normal drying, no flags
    raws = list(range(1200, 1260)) + list(range(1260, 1200, -1))
    h = sensor_health(_series(raws), anchors={"air": 2600, "water": 1000})
    assert h.status == "ok"
    assert not h.inspect_for_corrosion and h.reasons == []
    assert h.drier_than_air == 0 and h.wetter_than_water == 0
    assert h.out_of_envelope_rate == 0.0


# --------------------------------------------------------------------------- #
# out of envelope (needs anchors); honest-absence when uncalibrated
# --------------------------------------------------------------------------- #
def test_out_of_envelope_counts_both_rails() -> None:
    raws = [2800, 2700] + [1500] * 10 + [800]  # 2 drier-than-air, 1 wetter-than-water
    h = sensor_health(_series(raws), anchors={"air": 2600, "water": 1000})
    assert h.drier_than_air == 2
    assert h.wetter_than_water == 1
    assert h.out_of_envelope_rate == round(3 / 13, 4)


def test_uncalibrated_envelope_is_none_never_a_false_clean() -> None:
    h = sensor_health(_series([2800, 800, 1500]))  # no anchors
    assert h.drier_than_air is None
    assert h.wetter_than_water is None
    assert h.out_of_envelope_rate is None  # honest: uncalibrated, not "zero problems"


# --------------------------------------------------------------------------- #
# stuck / stale reads — the Issue-3 symptom (SENSOR_QA)
# --------------------------------------------------------------------------- #
def test_a_long_identical_run_is_stuck_and_prompts_inspection() -> None:
    # the contaminated-P11-s3 class: a probe that jams at one value.
    raws = [1500] * 30  # far past STUCK_RUN, every read identical
    h = sensor_health(_series(raws), anchors={"air": 2600, "water": 1000})
    assert h.longest_stuck_run == 30
    assert h.stuck_rate >= 0.20
    assert h.inspect_for_corrosion and h.status == "inspect"
    assert any("stuck" in r for r in h.reasons)


def test_a_short_repeat_is_not_stuck() -> None:
    raws = [1500] * (STUCK_RUN - 1) + list(range(1501, 1530))
    h = sensor_health(_series(raws), anchors={"air": 2600, "water": 1000})
    assert h.longest_stuck_run == STUCK_RUN - 1
    assert h.stuck_rate == 0.0


# --------------------------------------------------------------------------- #
# implausible-wet floor (#670) and wetter-than-water rate → corrosion prompt
# --------------------------------------------------------------------------- #
def test_implausible_wet_reads_prompt_corrosion_inspection() -> None:
    raws = [1500] * 20 + [200, 150]  # two reads below the physical wet rail (500)
    h = sensor_health(_series(raws), anchors={"air": 2600, "water": 1000})
    assert h.implausible_wet == 2
    assert h.inspect_for_corrosion
    assert any("wet rail" in r for r in h.reasons)


# --------------------------------------------------------------------------- #
# drift — only judged against the envelope, and only with enough samples
# --------------------------------------------------------------------------- #
def test_large_baseline_drift_against_the_envelope_prompts() -> None:
    # first window ~1200, last window ~1700: +500 raw on a 1600-wide envelope (~31%)
    raws = [1200] * 25 + [1700] * 25
    h = sensor_health(_series(raws), anchors={"air": 2600, "water": 1000})
    assert h.drift_raw is not None and h.drift_raw >= 450
    assert h.inspect_for_corrosion
    assert any("drifted" in r for r in h.reasons)


def test_drift_is_none_without_two_full_windows() -> None:
    h = sensor_health(_series([1200, 1300, 1400]), anchors={"air": 2600, "water": 1000})
    assert h.drift_raw is None  # never invented from a handful of reads


# --------------------------------------------------------------------------- #
# device-declared faults + dropouts
# --------------------------------------------------------------------------- #
def test_device_flagged_faults_are_counted_and_prompt() -> None:
    reads = _series([1500] * 18)
    reads += [_r(1500, minute=600 + i, flag="SENSOR_FAULT") for i in range(2)]
    h = sensor_health(reads, anchors={"air": 2600, "water": 1000})
    assert h.faults == 2
    assert h.inspect_for_corrosion and any("fault" in r for r in h.reasons)


def test_dropouts_are_gaps_beyond_the_sensors_own_cadence() -> None:
    reads = _series(list(range(1500, 1510)), step_min=30)  # steady 30-min cadence
    reads.append(_r(1510, minute=10 * 30 + 600))  # a 10-hour gap after the last
    h = sensor_health(reads, anchors={"air": 2600, "water": 1000})
    assert h.dropouts == 1


# --------------------------------------------------------------------------- #
# fleet grouping
# --------------------------------------------------------------------------- #
def test_fleet_health_groups_and_sorts_by_sensor() -> None:
    reads = _series([1500] * 5, sensor="s02") + _series([1500] * 30, sensor="s01")
    fleet = fleet_health(
        reads,
        anchors_by_sensor={"s01": {"air": 2600, "water": 1000}},  # s02 uncalibrated
    )
    assert [h.sensor_id for h in fleet] == ["s01", "s02"]
    s01, s02 = fleet
    assert s01.inspect_for_corrosion  # 30 stuck reads
    assert s02.out_of_envelope_rate is None  # honest: no anchors for s02


def test_no_readings_is_UNKNOWN_not_ok() -> None:
    """#1626 corrects this test's own premise. It used to assert `ok` for a sensor with
    no readings at all, which is the claim "this hardware is fine" made from zero
    evidence. Live, three non-soil instruments (spectral, temp/humidity, die temp) run
    through the soil-probe model on `readings: 0` — and every rate divided by a
    fabricated `n = len(raws) or 1`. Absent is its own answer."""
    h = sensor_health([])
    assert h.readings == 0 and h.status == "unknown"
    assert h.inspect_for_corrosion is False
    assert "nothing to assess" in " ".join(h.reasons)
    assert h.first_utc is None and h.drift_raw is None


# --------------------------------------------------------------------------- #
# #1626 — the three ungated signals: a rate, not "ever"
# --------------------------------------------------------------------------- #
def test_one_below_rail_read_in_a_long_history_is_not_a_corrosion_prompt() -> None:
    """The ratchet, in one case. `if h.implausible_wet:` fired on a single occurrence
    over unbounded history, so one bad read made a sensor `inspect` FOREVER — and every
    sensor converges there as the log grows. Measured on the live greenhouse the four
    classic channels sat at 0.87-1.96%, every one of them `inspect`."""
    raws = [0, *range(1200, 1400)]  # 1 below-rail read in 201
    h = sensor_health(_series(raws))
    assert h.implausible_wet == 1  # the COUNT is still reported — truth is unchanged
    assert h.status == "ok" and h.inspect_for_corrosion is False


def test_a_genuinely_shorted_probe_still_prompts() -> None:
    """The gate must not disarm the signal: at 5% of reads below the physical wet rail
    this is the short / water-ingress case the prompt exists for."""
    raws = [0] * 20 + list(range(1200, 1380))  # 10%
    h = sensor_health(_series(raws))
    assert h.status == "inspect" and h.inspect_for_corrosion is True
    assert "below the physical wet rail" in " ".join(h.reasons)


def test_one_stuck_run_in_a_long_history_is_not_a_watch() -> None:
    """Six consecutive identical raws is what healthy, slow-moving soil looks like at a
    30 s cadence — and `longest_stuck_run` only ever grows. The rated sibling asks the
    real question: how much of this sensor's life is stuck, not whether it ever was."""
    raws = [1300] * STUCK_RUN + list(range(1301, 1500))
    h = sensor_health(_series(raws))
    assert h.longest_stuck_run >= STUCK_RUN  # still measured and reported
    assert h.stuck_rate < 0.05
    assert h.status == "ok"


def test_a_sensor_stuck_most_of_its_life_is_still_caught() -> None:
    raws = [1300] * 100 + list(range(1301, 1320))
    h = sensor_health(_series(raws))
    assert h.status in ("watch", "inspect") and h.stuck_rate >= 0.05


def test_one_dropout_in_a_long_history_is_not_a_permanent_watch() -> None:
    rows = _series(list(range(1200, 1400)))
    rows += [_r(1400, minute=len(rows) * 30 + 600)]  # one long gap, then back to normal
    rows += [_r(1400 + i, minute=len(rows) * 30 + 600 + i * 30) for i in range(50)]
    h = sensor_health(rows)
    assert h.dropouts and h.dropouts >= 1  # counted, honestly
    assert h.dropout_rate is not None and h.dropout_rate < 0.05
    assert h.status == "ok"


# --------------------------------------------------------------------------- #
# #1626 — the cadence must be LOCAL, or a cadence CHANGE reads as lost data
# --------------------------------------------------------------------------- #
def test_a_logging_cadence_change_is_not_fifty_thousand_dropouts() -> None:
    """The live classic board's history spans a 5 s bench stretch and 30 s production
    either side. A global median over the pooled log lands at 5 s, so every ordinary
    30 s production gap exceeded 4x it — 52,219 "dropouts" (47.6%) where nothing was
    lost at all. A local window follows the regime instead of averaging across it."""
    rows = []
    t = 0.0
    for i in range(400):  # the bench stretch: 5 s cadence
        rows.append(_r(1200 + (i % 50), minute=t))
        t += 5 / 60
    for i in range(200):  # then production: 30 s — a settings change, not a fault
        rows.append(_r(1250 + (i % 50), minute=t))
        t += 30 / 60
    h = sensor_health(rows)
    assert h.dropout_rate is not None
    # exactly one boundary gap can look odd; anything approaching the old 47.6% means
    # the estimator is still measuring the log's history rather than lost readings.
    assert h.dropout_rate < 0.02, h.dropout_rate
    assert h.status == "ok"


def test_a_real_outage_is_still_a_dropout_after_the_change() -> None:
    """The local window must not blunt the signal: a genuine multi-hour silence in an
    otherwise steady stream is still counted."""
    rows = [_r(1200 + i, minute=i * 30) for i in range(60)]
    rows += [_r(1300 + i, minute=60 * 30 + 600 + i * 30) for i in range(60)]
    h = sensor_health(rows)
    assert h.dropouts and h.dropouts >= 1
