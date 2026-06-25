"""Legacy serial-monitor log -> schema-v1 CSV converter (s3 pre-CSV history).

Before the host CSV pipeline existed, the controller printed readings to the
serial monitor and they were captured to a fixed-width ``.log`` file - e.g.
``firmware/logs/device-monitor-260621-224356.log``: ~41 h of the *single*
co-located probe (Rung 3, ``s3`` on GPIO36, firmware 0.3.2) **before** the other
three sensors were added. That capture is the only record of how ``s3`` behaved
*before and after* its neighbours were powered in - but it is in a format the
schema-v1 reader (``parse_v1.py``) cannot read, and its timestamps are device
*uptime*, not host wall-clock.

This tool converts that legacy capture into a faithful **schema-v1 CSV** so it
can be loaded *optionally* alongside the live logs to draw a continuous ~4-day
``s3`` trajectory. It does two jobs, and only two:

1. **Recover the raw data** - parse the fixed-width rows (``# uptime raw moist%
   level role spr health``), tolerating the serial-glitch bytes that corrupt
   some lines, and carry ``raw`` through untouched (raw is the truth; B2/C2).
2. **Align the timestamps** - anchor device uptime to wall-clock. ``uptime 0``
   is anchored to the capture start (default: parsed from the filename's
   ``YYMMDD-HHMMSS`` stamp, which lands the *last* row within ~1 min of the
   file's mtime - a self-consistency check). A ``--utc-offset`` (default -5,
   America/Chicago CDT) converts local -> UTC.

Honesty guarantees (per project doctrine):

* The output is clearly marked **CONVERTED / ANCHORED** in its ``#`` provenance
  header and given a distinct ``session_id`` (``legacy-...``) and
  ``logger_version`` (``legacy-convert``) so it can never be mistaken for
  host-stamped data.
* ``firmware_version`` (0.3.2) and the *as-flashed* legacy cal bounds are
  preserved in the header. Only **raw counts** are comparable across the
  firmware change; ``value``/``moist%`` and the band labels are carried through
  as the device emitted them, never recomputed to fake continuity.
* It is **read-only on the source** ``.log`` and writes outside ``logs/`` (the
  default ``logs/legacy/`` is not auto-discovered by ``gather_inputs()``), so
  loading it is always an explicit opt-in.

Usage::

    # convert (defaults: anchor from filename, UTC-5, sensor s3/GPIO36)
    python tools/analytics/legacy_log.py firmware/logs/device-monitor-260621-224356.log

    # then load it *optionally* next to the live logs (explicit inputs):
    python tools/analytics/serve.py logs/ logs/legacy/*.csv
    python tools/analytics/dashboard.py logs/ logs/legacy/*.csv -o reports/s3_4day.html
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from parse_v1 import CANONICAL_COLUMNS  # noqa: E402  (sibling; keeps columns in sync)

_REPO = _HERE.parents[1]

# Current rig channel map (ch index -> sensor_id) by GPIO, so the converted
# rows carry the same sensor_id the live logs use and merge into one trajectory.
GPIO_TO_SENSOR = {36: "s3", 39: "s4", 34: "s1", 35: "s2"}
GPIO_TO_CHANNEL = {36: "ch0", 39: "ch1", 34: "ch2", 35: "ch3"}

# A fixed-width reading row, matched anywhere in the line so a leading run of
# serial-glitch bytes (decoded to U+FFFD) does not defeat the match:
#   "    37  +0d 00:18:30        1356    81%  well watered      disp    52  ok"
_ROW_RE = re.compile(
    r"(?P<idx>\d+)\s+\+(?P<d>\d+)d\s+(?P<h>\d+):(?P<m>\d+):(?P<s>\d+)\s+"
    r"(?P<raw>\d+)\s+(?P<moist>-?\d+)%\s+(?P<level>.+?)\s+(?P<role>\S+)\s+"
    r"(?P<spr>\d+)\s+(?P<health>\S+)\s*$"
)
# A line that *looks* like a reading (so we can count true drops, not headers).
_ROWISH_RE = re.compile(r"\+\d+d\s+\d+:\d+:\d+\s+\d+\s+-?\d+%")
# Filename timestamp: device-monitor-YYMMDD-HHMMSS.log
_FNAME_RE = re.compile(r"(\d{6})-(\d{6})")
_REPLACEMENT = "�"
_ADC_MAX = 4095  # 12-bit; reject impossible raw from a corrupted line

SENSOR_MODEL = "UMLIFE_v2_TLC555"
SENSOR_POSITION = "origplant"
DEVICE_ID = "plants_esp32_f4e9d4"
CADENCE_MS = 30000


def anchor_from_name(path: Path) -> datetime | None:
    """Parse the capture-start wall-clock from the ``YYMMDD-HHMMSS`` filename."""
    m = _FNAME_RE.search(path.stem)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%y%m%d%H%M%S")
    except ValueError:
        return None


def read_header(lines: list[str]) -> dict[str, str]:
    """Pull firmware / GPIO / cal-bounds / cfg from the capture's banner."""
    info: dict[str, str] = {}
    for ln in lines[:80]:
        s = ln.strip()
        if s.startswith("firmware version:"):
            info["fw"] = s.split(":", 1)[1].strip()
        elif s.startswith("sensor on GPIO"):
            m = re.search(r"GPIO(\d+)", s)
            if m:
                info["gpio"] = m.group(1)
        elif s.startswith("cal bounds"):
            info.setdefault("cal", s)
        elif s.startswith("cfg:"):
            info.setdefault("cfg", s)
        elif "Rung" in s or "single soil sensor" in s:
            info.setdefault("banner", s)
    return info


def _iso_utc(dt: datetime) -> str:
    # uptime is whole seconds -> .000; mark Z to match the live logs' UTC column
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z"


def _iso_local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S") + ".000"


def convert(
    src: Path,
    anchor_local: datetime,
    utc_offset_hours: float,
    sensor_id: str,
    gpio: int,
    session_id: str,
) -> tuple[list[dict[str, str]], Counter, tuple[datetime, datetime] | None]:
    """Parse the legacy capture into schema-v1 row dicts + parse statistics."""
    text = src.read_text(encoding="utf-8", errors="replace")
    offset = timedelta(hours=utc_offset_hours)
    channel = GPIO_TO_CHANNEL.get(gpio, "ch0")
    rows: list[dict[str, str]] = []
    stats: Counter = Counter()
    span: list[datetime] = []
    last_up = -1.0

    for ln in text.splitlines():
        m = _ROW_RE.search(ln)
        if not m:
            if _ROWISH_RE.search(ln):
                stats["dropped"] += 1  # looked like a reading but unparseable
            continue
        raw = int(m.group("raw"))
        if not (0 <= raw <= _ADC_MAX):
            stats["implausible_raw"] += 1
            continue

        up = timedelta(
            days=int(m.group("d")),
            hours=int(m.group("h")),
            minutes=int(m.group("m")),
            seconds=int(m.group("s")),
        )
        up_s = up.total_seconds()
        if up_s + 1 < last_up:  # uptime went backwards => an un-anchored reboot
            stats["reboot_seen"] += 1
        last_up = up_s

        local_dt = anchor_local + up
        utc_dt = local_dt - offset  # local = UTC + offset  =>  UTC = local - offset
        span.append(local_dt)

        glitched = _REPLACEMENT in ln
        health = m.group("health").strip().lower()
        if glitched:
            quality = "SUSPECT"
            stats["recovered_glitch"] += 1
        elif health == "ok":
            quality = "OK"
        else:
            quality = health.upper()
        stats["parsed"] += 1

        level = m.group("level").strip()
        spr = m.group("spr")
        role = m.group("role").strip()
        payload = f"level={level};role={role};spread={spr};gpio={gpio}"

        row = dict.fromkeys(CANONICAL_COLUMNS, "")
        row.update(
            record_type="plants.soil",
            timestamp_utc=_iso_utc(utc_dt),
            timestamp_local=_iso_local(local_dt),
            sample_id=m.group("idx"),
            session_id=session_id,
            device_id=DEVICE_ID,
            firmware_version="0.3.2",
            logger_version="legacy-convert",
            millis_ms=str(int(up_s * 1000)),
            sensor_model=SENSOR_MODEL,
            sensor_id=sensor_id,
            sensor_position=SENSOR_POSITION,
            channel=channel,
            raw_value=str(raw),
            value=m.group("moist"),
            unit="pct",
            quality_flag=quality,
            payload=payload,
        )
        rows.append(row)

    span_range = (min(span), max(span)) if span else None
    return rows, stats, span_range


def _header_block(
    src: Path,
    anchor_local: datetime,
    utc_offset_hours: float,
    sensor_id: str,
    gpio: int,
    session_id: str,
    hdr: dict[str, str],
    stats: Counter,
    span: tuple[datetime, datetime] | None,
) -> list[str]:
    off = utc_offset_hours
    sign = "-" if off < 0 else "+"
    off_str = f"{sign}{int(abs(off)):02d}:{int(abs(off) % 1 * 60):02d}"
    try:
        rel = src.resolve().relative_to(_REPO)
        src_str = str(rel).replace("\\", "/")
    except ValueError:
        src_str = src.name
    span_str = (
        f"{span[0].strftime('%Y-%m-%d %H:%M')}..{span[1].strftime('%Y-%m-%d %H:%M')}"
        if span
        else "none"
    )
    cal = hdr.get("cal", "cal bounds: (unknown - not in capture banner)")
    cfg = hdr.get("cfg", "cfg: (unknown)")
    fw = hdr.get("fw", "0.3.2")
    return [
        "# plants telemetry log - schema_version=1 - CONVERTED FROM LEGACY "
        "SERIAL-MONITOR CAPTURE",
        "# DO NOT treat as host-stamped data: timestamps are ANCHORED "
        "(device uptime + anchor), not host-clock UTC.",
        "# Only raw_value is comparable across the 0.3.2 -> 0.7.0 firmware "
        "change; value/moist% and band labels are as-emitted by fw 0.3.2.",
        f"# source_log: {src_str}",
        "# converter: tools/analytics/legacy_log.py",
        f"# schema_version=1 fw={fw} device_id={DEVICE_ID} session_id={session_id} "
        f"logger=legacy-convert cadence_ms={CADENCE_MS}",
        f"# anchor_local={anchor_local.strftime('%Y-%m-%d %H:%M:%S')} "
        f"utc_offset={off_str}",
        f"# sensors: {GPIO_TO_CHANNEL.get(gpio, 'ch0')}=GPIO{gpio}/{sensor_id}",
        f"# {cal}",
        f"# {cfg} (as-flashed {fw})",
        f"# rows: parsed={stats.get('parsed', 0)} "
        f"recovered_glitch={stats.get('recovered_glitch', 0)} "
        f"dropped={stats.get('dropped', 0)} span_local={span_str}",
    ]


def write_csv(out: Path, header_lines: list[str], rows: list[dict[str, str]]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        for line in header_lines:
            fh.write(line + "\n")  # LF per repo policy
        writer = csv.DictWriter(
            fh, fieldnames=CANONICAL_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Convert a legacy serial-monitor .log into a schema-v1 CSV."
    )
    ap.add_argument("log", help="legacy serial-monitor capture (.log)")
    ap.add_argument(
        "-o", "--out", help="output CSV (default: logs/legacy/<stem>_anchored.csv)"
    )
    ap.add_argument(
        "--anchor",
        help='uptime-0 wall-clock "YYYY-MM-DD HH:MM:SS" (default: from filename)',
    )
    ap.add_argument(
        "--utc-offset",
        type=float,
        default=-5.0,
        help="hours of local vs UTC (default -5 = America/Chicago CDT)",
    )
    ap.add_argument("--sensor", help="sensor_id override (default: from GPIO map)")
    ap.add_argument("--gpio", type=int, help="GPIO override (default: from banner)")
    ap.add_argument("--session", help="session_id override (default: legacy-<stamp>)")
    ap.add_argument("-q", "--quiet", action="store_true", help="suppress the summary")
    args = ap.parse_args(argv)

    src = Path(args.log)
    if not src.is_file():
        print(f"error: no such file: {src}", file=sys.stderr)
        return 2

    raw_lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    hdr = read_header(raw_lines)

    anchor = (
        datetime.strptime(args.anchor, "%Y-%m-%d %H:%M:%S")
        if args.anchor
        else anchor_from_name(src)
    )
    if anchor is None:
        print(
            "error: could not parse an anchor from the filename; pass "
            '--anchor "YYYY-MM-DD HH:MM:SS"',
            file=sys.stderr,
        )
        return 2

    gpio = args.gpio if args.gpio is not None else int(hdr.get("gpio", "36"))
    sensor_id = args.sensor or GPIO_TO_SENSOR.get(gpio, "s3")
    stamp = _FNAME_RE.search(src.stem)
    session_id = args.session or (
        f"legacy-{stamp.group(1)}-{stamp.group(2)}" if stamp else "legacy-import"
    )

    rows, stats, span = convert(
        src, anchor, args.utc_offset, sensor_id, gpio, session_id
    )
    if not rows:
        print("error: no readings parsed from the capture", file=sys.stderr)
        return 1

    out = (
        Path(args.out)
        if args.out
        else _REPO / "logs" / "legacy" / f"{src.stem}_anchored.csv"
    )
    header_lines = _header_block(
        src, anchor, args.utc_offset, sensor_id, gpio, session_id, hdr, stats, span
    )
    write_csv(out, header_lines, rows)

    if not args.quiet:
        idxs = [int(r["sample_id"]) for r in rows]
        expected = max(idxs) - min(idxs) + 1
        print(f"converted {src.name} -> {out}")
        print(f"  sensor: {sensor_id} (GPIO{gpio})  fw={hdr.get('fw', '0.3.2')}")
        print(
            f"  anchor_local={anchor:%Y-%m-%d %H:%M:%S}  "
            f"utc_offset={args.utc_offset:+g}h"
        )
        if span:
            print(
                f"  span (local): {span[0]:%Y-%m-%d %H:%M} -> "
                f"{span[1]:%Y-%m-%d %H:%M}"
            )
        print(
            f"  rows: parsed={stats.get('parsed', 0)} "
            f"recovered_from_glitch={stats.get('recovered_glitch', 0)} "
            f"dropped={stats.get('dropped', 0)} "
            f"implausible_raw={stats.get('implausible_raw', 0)}"
        )
        coverage = 100.0 * stats.get("parsed", 0) / expected if expected else 0.0
        print(
            f"  counter span: #{min(idxs)}..#{max(idxs)} "
            f"({expected} expected, {coverage:.1f}% recovered)"
        )
        if stats.get("reboot_seen"):
            print(
                f"  !! uptime went backwards {stats['reboot_seen']}x - an un-anchored "
                "reboot; later rows may be mis-timed. Split the capture or re-anchor."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
