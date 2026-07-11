#!/usr/bin/env python3
"""Fleet logger (#582) - the missing write half of the untethered spine.

The fleet live view (#560) renders WiFi devices but persists nothing
(``serve.py`` is read-only by house rule). This process is the poll->persist
wire: every registered device with a ``base_url`` (#485) is polled on a steady
cadence, each reading runs through the ``Store`` dedupe boundary (#521,
``device_seq`` idempotency), and survivors land in the same rotating CSV
pipeline the serial logger writes - so the archive step, the dashboard's file
discovery, and ``parse_v1`` all pick fleet segments up with zero new plumbing.

Usage::

    python tools/logger/fleet_logger.py                 # poll fleet -> logs/
    python tools/logger/fleet_logger.py --cadence-s 30 --logdir ../../logs
    python tools/logger/fleet_logger.py --once          # single poll (smoke)

**The honesty bound, stated out loud (not fine print):** devices serve
latest-reading-only (#276's Tier-0 cache), so collection is continuous **while
this host process runs**. Host off = those hours are gone. On-device
buffering/backfill is Wave-2 territory (the tiered epic); Wave 1's promise is
"collected while the host runs."

The four #582 design decisions, named:

1. **Process home** - a standalone logger-family process (this file), NOT
   serve.py (which stays read-only) and NOT the serial logger's read loop
   (a WiFi-only deployment has no COM port at all; the serial loop blocks on
   one). Both loggers share the writer (``RotatingCsv``) - one write path,
   two transports.
2. **Cadence** - default 30 s, matching the device sweep. Latest-only serving
   means cadence = resolution: polling faster only re-reads the same row
   (``Store`` drops the replay for free), slower loses sweeps.
3. **Restart dedupe** - ``Store`` is per-process memory, so on restart the
   first poll would re-append the row already on disk. Decision: **seed the
   store from recent on-disk segments at startup** (the dup window is only
   each device's *current* latest row - latest-only serving means nothing
   older can ever be re-served - so seeding the recent tail is complete
   protection, not a heuristic).
4. **Provenance** - persisted rows are distinguishable three ways, all riding
   existing surfaces (payload k=v / existing columns - CANONICAL_COLUMNS
   untouched, per the Trellis binding): ``logger_version=fleet_logger_0_1``
   (who wrote the file), payload ``transport=wifi_poll`` (how the bytes
   arrived), and the segment header's ``transport=wifi_poll`` block. **No
   base_url/IP in the persisted file** - device_id is the durable identity;
   LAN addresses stay in the gitignored config (the archive pipeline commits
   segments to the data branch, and network identifiers don't belong in it).

Dedupe honesty (inherited from ``Store``, #521): a row with no ``device_seq``
has no dedupe signal and is ALWAYS appended - so a pre-schema-v2 device gets
its latest row re-appended at poll cadence (visible - identical ``millis_ms`` -
never silent). Real fleet firmware emits ``device_seq`` (#518); the repeat
behavior only appears on firmware that predates it.

Read-side note: once fleet segments exist in ``logs/``, the dashboard's file
discovery reads them AND the live view still polls the same devices - the same
reading arriving via both paths is exactly the store-and-forward replay the
read-side ``FleetAdapter`` dedupe (#560) already drops. History from disk,
the latest sweep from the poll, counted once.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ANALYTICS = os.path.normpath(os.path.join(_HERE, "..", "analytics"))
if _ANALYTICS not in sys.path:
    sys.path.insert(0, _ANALYTICS)

from context_fill import ContextFiller  # noqa: E402
from device_registry import load_registry  # noqa: E402
from fleet_lock import FleetAlreadyRunning, FleetLock  # noqa: E402
from ingest_store import Store  # noqa: E402
from parse_v1 import parse_file  # noqa: E402
from plants_logger import RotatingCsv, _append_payload  # noqa: E402
from source_adapter import DeviceAdapter  # noqa: E402


def _apply_context(row: dict, context: dict) -> dict:
    """Merge a ContextFiller fill into a pre-parsed row the SAME way
    ``plants_logger.stamp_row`` does (#701): value keys land in their reserved
    CANONICAL columns, the ``*_source`` tag keys ride payload k=v (never a new
    column - the shared-core binding). None/empty leaves the row untouched
    (honestly empty). The row keeps its raw truth; only the reserved context
    columns/tags are filled."""
    if not context:
        return row
    for col in ("temp_context_c", "rh_context_pct", "pressure_context_hpa"):
        if context.get(col):
            row[col] = context[col]
    payload = row.get("payload", "")
    for tag_key in ("context_source", "pressure_context_source"):
        if context.get(tag_key):
            payload = _append_payload(payload, tag_key, context[tag_key])
    row["payload"] = payload
    return row


FLEET_LOGGER_VERSION = "fleet_logger_0_1"
DEFAULT_CADENCE_S = 30.0  # decision 2: matches the device sweep
# Decision 3's seed window: only each device's CURRENT latest row can replay
# (latest-only serving), so any window covering the last poll is complete.
# 24 h is generous slack for a host that slept overnight.
SEED_WINDOW_S = 24 * 3600.0

# Optional B8 archive step (same best-effort posture as plants_logger).
_ARCHIVE_DIR = os.path.normpath(os.path.join(_HERE, "..", "archive"))
if _ARCHIVE_DIR not in sys.path:
    sys.path.insert(0, _ARCHIVE_DIR)
try:
    import archive_logs
except Exception:
    archive_logs = None

# The #567 pressure exception rides the persisted rows too (same cache-only
# reader as the live view + the serial logger - never a fetch in this loop).
try:
    from weather_pressure import latest_pressure as _pressure_source
except Exception:
    _pressure_source = None


def _default_logdir() -> str:
    return os.path.normpath(os.path.join(_HERE, "..", "..", "logs"))


def seed_store_from_disk(
    store: Store, logdir: str, *, window_s: float = SEED_WINDOW_S, now=None
) -> int:
    """Decision 3: prime the dedupe store from recent on-disk segments so a
    restart never re-appends a row the previous run already persisted. Returns
    the number of rows seeded. Best-effort: an unreadable file is skipped -
    worst case is one detectable duplicate, never a crash."""
    now = now if now is not None else time.time()
    seeded = 0
    try:
        names = os.listdir(logdir)
    except OSError:
        return 0
    for name in names:
        if not name.endswith(".csv"):
            continue
        path = os.path.join(logdir, name)
        try:
            if now - os.path.getmtime(path) > window_s:
                continue
            for r in parse_file(path).readings:
                store.ingest(r)
                seeded += 1
        except Exception:
            continue  # unreadable/partial file - skip, don't die
    return seeded


class FleetLogger:
    """Poll registered WiFi devices -> dedupe -> persist. Pure logic with
    injectable collaborators (registry, adapter factory, clock/sleep), so the
    whole loop unit-tests without a network or a wall clock."""

    def __init__(
        self,
        logdir: str | None = None,
        *,
        cadence_s: float = DEFAULT_CADENCE_S,
        registry=None,
        adapter_factory=None,
        store: Store | None = None,
        sleep=time.sleep,
        log=print,
    ) -> None:
        self.logdir = logdir or _default_logdir()
        self.cadence_s = cadence_s
        self._registry = registry  # None -> re-load per poll (config edits live)
        self._adapter_factory = adapter_factory or (
            lambda base_url: DeviceAdapter(base_url, pressure_source=_pressure_source)
        )
        self.store = store if store is not None else Store()
        self._sleep = sleep
        self._log = log
        # Persistent per-device state: adapters keep sample_id continuity
        # across polls; writers keep one rolling segment per device.
        self._adapters: dict[str, object] = {}
        self._writers: dict[str, RotatingCsv] = {}
        # #701: one ContextFiller per device - each board's own plant-local SHT45
        # fills only its own soil rows (never cross-fill across boards). Persistent
        # so a soil row can be filled from an env reading observed a poll or two
        # earlier, within the freshness window.
        self._fillers: dict[str, ContextFiller] = {}
        self.appended = 0
        # #900: archival health - a failure/unavailability must surface, never silently
        # swallowed while logs/ grows uncompressed. Counted; notice fires once.
        self._archive_fails = 0
        self._archive_unavailable_warned = False
        self.polls = 0

    def _adapter(self, base_url: str):
        if base_url not in self._adapters:
            self._adapters[base_url] = self._adapter_factory(base_url)
        return self._adapters[base_url]

    def _filler(self, device_id: str) -> ContextFiller:
        # #701: INTERIOR ambient (temp/RH) only - the DeviceAdapter already fills
        # the pressure exception (#572), so pressure_source stays None here to avoid
        # double-filling; the two coexist (adapter=pressure, filler=interior).
        if device_id not in self._fillers:
            self._fillers[device_id] = ContextFiller(pressure_source=None)
        return self._fillers[device_id]

    def _writer(self, device_id: str) -> RotatingCsv:
        if device_id not in self._writers:
            w = RotatingCsv(self.logdir, logger_version=FLEET_LOGGER_VERSION)
            # #602: pin the file lineage to the (canonical) key - otherwise the
            # first row's raw device_id names the file, splitting a renamed
            # board's lineage right back apart.
            w.device_id = device_id
            w.set_header(
                [
                    f"# transport=wifi_poll  poll_cadence_s={self.cadence_s:g}  "
                    f"logger={FLEET_LOGGER_VERSION}",
                    "# collected-while-host-runs: devices serve latest-reading-"
                    "only; a host outage is a data gap, never backfilled (#582)",
                ]
            )
            self._writers[device_id] = w
        return self._writers[device_id]

    def poll_once(self) -> int:
        """One fleet sweep: every served device polled, survivors persisted.
        Returns the number of rows appended."""
        self.polls += 1
        reg = self._registry if self._registry is not None else load_registry()
        canon = reg.canonical_for  # #602: file lineage follows the canonical id
        appended = 0
        for device in reg.served_devices():
            data = self._adapter(device.base_url).load()
            filler = self._filler(canon(device.device_id) or device.base_url)
            # #701 pass 1: warm this device's ambient cache from its env rows
            # BEFORE filling any soil row, so a soil row gets the freshest context
            # from the same poll (mirrors the tethered logger's observe-then-fill).
            for r in data.readings:
                if r.record_type.startswith("plants.env"):
                    filler.observe(r.row)
            # #701 pass 2: dedupe + fill soil-row interior context + persist.
            for r in data.readings:
                if not self.store.ingest(r):
                    continue  # an exact replay of a row already persisted
                row = dict(r.row)
                # Decision 4: the persisted record names its writer + transport.
                row["logger_version"] = FLEET_LOGGER_VERSION
                row["payload"] = _append_payload(
                    row.get("payload", ""), "transport", "wifi_poll"
                )
                # #701: fill soil rows with this board's plant-local ambient (the
                # join-free ADR-0023 deliverable), matching the tethered path.
                if r.record_type.startswith("plants.soil"):
                    row = _apply_context(row, filler.context_for())
                # #602: the WRITER key (file naming/lineage) coalesces to the
                # canonical identity so a renamed board keeps one file lineage;
                # the row itself keeps the id the device truthfully reported.
                new_path = self._writer(
                    canon(row.get("device_id")) or "unknown"
                ).write_row(row, r.timestamp_utc)
                appended += 1
                if new_path:
                    self._log(f"[fleet] -> {new_path}")
                    self._archive(exclude=new_path)
        self.appended += appended
        return appended

    def _archive(self, exclude=None, include_all=False) -> None:
        """Best-effort B8 archive of closed segments; never disrupts polling. #900: a
        failure is LOUD (stderr — the channel that survives the worker's capped log,
        #968; `self._log` defaults to stdout, which is DEVNULL on the background worker)
        and COUNTED, and unavailability is stated once — segments never accumulate in
        logs/ silently."""
        if archive_logs is None:
            if not self._archive_unavailable_warned:
                self._archive_unavailable_warned = True
                print(
                    "[fleet] archival UNAVAILABLE: archive_logs not importable; "
                    "closed segments accumulate in logs/ until restored (B8 skipped)",
                    file=sys.stderr,
                    flush=True,
                )
            return
        try:
            archive_logs.archive(
                logs_dir=self.logdir, exclude=exclude, include_all=include_all
            )
            self._archive_fails = 0  # a clean run clears the failure streak
        except Exception as e:
            self._archive_fails += 1
            print(
                f"[fleet] archive step FAILED (non-fatal, {self._archive_fails}x): {e} "
                "— closed segments accumulate in logs/ until this clears",
                file=sys.stderr,
                flush=True,
            )

    def run(self, *, max_polls: int | None = None, lock: object | None = None) -> bool:
        """The steady loop: take the cross-process singleton, seed the
        restart-dedupe window, then poll forever (or ``max_polls`` times - tests
        and --once use this). Returns True if it ran, False if refused because
        another poller already holds the lock (#493 F2).

        ``lock`` is injectable (a context-like object exposing ``acquire``/
        ``release``); it defaults to a real :class:`FleetLock` keyed on
        ``logdir`` - the mutex WiFi lacks (a COM port can't be double-opened; an
        HTTP poll can, so two loggers would interleave one CSV)."""
        lock = FleetLock(self.logdir) if lock is None else lock
        try:
            lock.acquire()
        except FleetAlreadyRunning as e:
            self._log(f"[fleet] {e}")
            return False
        seeded = seed_store_from_disk(self.store, self.logdir)
        if seeded:
            self._log(f"[fleet] restart dedupe seeded from disk ({seeded} rows)")
        self._log(
            f"[fleet] polling every {self.cadence_s:g}s -> {self.logdir}  "
            "(collection runs while this host process runs - see #582)"
        )
        try:
            while True:
                n = self.poll_once()
                if n:
                    self._log(f"[fleet] poll {self.polls}: +{n} rows")
                if max_polls is not None and self.polls >= max_polls:
                    break
                self._sleep(self.cadence_s)
        except KeyboardInterrupt:
            self._log(
                f"\n[fleet] stopped ({self.appended} rows across "
                f"{self.polls} polls) - data saved."
            )
        finally:
            for w in self._writers.values():
                with contextlib.suppress(Exception):
                    if w.fh:
                        w.fh.close()
            self._archive(include_all=True)  # the active segments are now closed
            with contextlib.suppress(Exception):
                lock.release()
        return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Poll untethered fleet devices and persist to the archive."
    )
    ap.add_argument(
        "--logdir", default=_default_logdir(), help="output dir (default <repo>/logs)"
    )
    ap.add_argument(
        "--cadence-s",
        type=float,
        default=DEFAULT_CADENCE_S,
        help=f"poll cadence in seconds (default {DEFAULT_CADENCE_S:g} = the sweep)",
    )
    ap.add_argument(
        "--once", action="store_true", help="single poll then exit (smoke test)"
    )
    args = ap.parse_args(argv)
    fl = FleetLogger(args.logdir, cadence_s=args.cadence_s)
    ran = fl.run(max_polls=1 if args.once else None)
    return 0 if ran else 1  # refused (another poller live) is a nonzero exit


if __name__ == "__main__":
    sys.exit(main())
