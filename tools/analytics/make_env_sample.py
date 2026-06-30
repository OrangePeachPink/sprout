#!/usr/bin/env python3
"""Synthetic plants.env + plants.soil sample — the #376 host pre-validation fixture.

Emits a realistic mixed monitor log exactly as the firmware `esp32dev_env` build
would: per sweep, the four soil channels (raw-only) plus the SHT45 ambient pair
(calibrated value/unit) and the AS7263 six-band NIR row-per-channel (raw counts),
all per the ratified plants.env mapping (TELEMETRY_SCHEMA.md §4, #373/#374).

It is **the proven host path**: Firmware's #376 rebase can validate its real
device output against this, and the host (parse_v1 + the dashboard) is tested
against it here — so the env integration lands onto a known-good target.

    python tools/analytics/make_env_sample.py            # -> docs/sample_env_log.csv
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_OUT = _REPO / "docs" / "sample_env_log.csv"

# A focused canonical-column subset (parse_v1 maps by name, so this is valid).
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,firmware_version,"
    "sensor_model,sensor_id,sensor_position,channel,raw_value,value,unit,"
    "quality_flag,payload"
)
_HEADER = (
    "# fw=0.7.0  git=env0001  run=env-sample\n"
    "# device_id=plants_esp32_env  schema_version=1  "
    "cadence_ms=30000  cadence_src=nvs\n"
    "# sensors: ch0=GPIO36/s3 ch1=GPIO39/s4 ch2=GPIO34/s1 ch3=GPIO35/s2\n"
    "# env: SHT45@0x44 (ambient temp/RH)  AS7263@0x49 (NIR 610-860nm)  "
    "mount=breadboard_near_esp32\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)

_SOIL = ("s1", "s2", "s3", "s4")
_NIR = ("nir_610", "nir_680", "nir_730", "nir_760", "nir_810", "nir_860")
_POS = "breadboard_near_esp32"


def _row(rt, ts, sid, model, pos, channel, raw, value, unit, qf, payload):
    local = ts.replace("Z", "")
    return (
        f"{rt},{ts},{local},envs01,plants_esp32_env,0.7.0,"
        f"{model},{sid},{pos},{channel},{raw},{value},{unit},{qf},{payload}\n"
    )


def env_sample_text(n_sweeps: int = 8) -> str:
    """The mixed soil+env log as CSV text (header + n_sweeps of every channel)."""
    out = [_HEADER, _COLS + "\n"]
    t0 = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(n_sweeps):
        ts = (t0 + timedelta(seconds=30 * i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        # 4 soil channels — raw-only (value/unit empty), drying slowly
        for j, sid in enumerate(_SOIL):
            raw = 1500 + j * 40 + i * 3
            qf = "SUSPECT" if (i == 4 and sid == "s2") else "OK"  # exercise the enum
            out.append(
                _row(
                    "plants.soil",
                    ts,
                    sid,
                    "UMLIFE_v2_TLC555",
                    "origplant",
                    "soil_moisture",
                    raw,
                    "",
                    "",
                    qf,
                    "level=well watered;role=disp;spread=24;gpio=36",
                )
            )
        # SHT45 — calibrated ambient (value/unit POPULATED), warming with the beam
        temp = round(23.0 + i * 0.3, 1)
        rh = round(48.0 - i * 0.4, 1)
        out.append(
            _row(
                "plants.env",
                ts,
                "env",
                "SHT45",
                _POS,
                "ambient_temp",
                "",
                temp,
                "degC",
                "OK",
                "mount=breadboard_near_esp32",
            )
        )
        out.append(
            _row(
                "plants.env",
                ts,
                "env",
                "SHT45",
                _POS,
                "ambient_rh",
                "",
                rh,
                "pctRH",
                "OK",
                "mount=breadboard_near_esp32",
            )
        )
        # AS7263 — six NIR bands, raw counts (value/unit empty), one row per band
        pay = "gain=16;itime_ms=50;aim=skylight_beam;not_canopy"
        for k, band in enumerate(_NIR):
            count = 800 + k * 220 + i * 12
            qf = "SATURATED" if (i == 6 and band == "nir_860") else "OK"
            out.append(
                _row(
                    "plants.env",
                    ts,
                    "env",
                    "AS7263",
                    _POS,
                    band,
                    count,
                    "",
                    "",
                    qf,
                    pay,
                )
            )
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(env_sample_text(), encoding="utf-8", newline="\n")
    print(f"wrote {_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
