#!/usr/bin/env python3
"""Source-adapter seam (#277, PRD-0005/Epic #267) — the dashboard reads through an
adapter interface, not ``gather_inputs()``/``parse_files()`` directly, so a future
untethered/device-served transport can plug in without ``dashboard.py`` or
``serve.py`` needing to change their call sites again.

**Scope of this slice** (see #277's own acceptance criteria):

* AC "tethered still works via the same interface (degenerate hub)" — done here:
  :class:`TetheredAdapter` is a byte-identical wrap of today's serial-logger/host-CSV
  reading path.
* AC "adapter seam is documented for future transports" — done here: this module
  *is* that documentation, in code.
* AC "dashboard shows untethered-device data with no serial logger" — **NOT** done
  here. A device-served adapter needs the on-device serve endpoint (#276) and the
  schema-v2 device-owned-time contract (#268/#300) to read against; neither exists
  yet. This module only defines the seam plus the one adapter that has something
  real to wrap — a device-served adapter is a separate, later slice once #276 lands.

Deliberately dependency-light (only ``parse_v1``): ``TetheredAdapter`` takes its
*discovery* callable (``dashboard.gather_inputs``) as a constructor argument rather
than importing ``dashboard`` directly, so there's no import cycle with the modules
that will construct it.
"""

from __future__ import annotations

from typing import Protocol

from parse_v1 import LogData, parse_files


class SourceAdapter(Protocol):
    """A pluggable telemetry source.

    ``load(inputs)`` returns parsed data for explicit ``inputs`` (file/dir paths),
    or the adapter's own default discovery when ``inputs`` is ``None`` — so a
    caller never needs to know which transport it's reading from."""

    def load(self, inputs: list[str] | None = None) -> LogData: ...


class TetheredAdapter:
    """The current (and, until #276, only) transport: tethered USB serial, read via
    the host logger's written CSV files.

    A behavior-preserving wrap — identical output to calling
    ``gather_inputs()``/``parse_files()`` directly today."""

    def __init__(self, discover=None) -> None:
        # `discover` is the caller's own file-discovery function (dashboard.py's
        # gather_inputs); None means "no auto-discovery" — the caller must always
        # pass explicit inputs, which is a valid, testable configuration on its own.
        self._discover = discover

    def load(self, inputs: list[str] | None = None) -> LogData:
        if inputs is not None:
            resolved = inputs
        elif self._discover is not None:
            resolved = self._discover()
        else:
            resolved = []
        return parse_files(resolved)
