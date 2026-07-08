"""Local-time-first formatting for bench-facing surfaces (#328).

Bench actions — watering, skylight position, interventions — are tied to Veronica's
**local** time (Chicago). UTC stays as secondary metadata for machine joins. This is
the one formatter every render surface consumes (dashboard, monitor, lab notes, chart
labels) so the convention is consistent; the display convention itself is documented
in ``docs/time-display-convention.md`` (AC #5).

Honest timezone handling — no fabricated zone labels:

* with a ``tz_name`` (IANA, e.g. ``America/Chicago``) we render the **true**
  abbreviation (``CDT`` / ``CST``, DST-correct) via stdlib ``zoneinfo``;
* with only a numeric ``tz_offset_hours`` we render the **offset** (``UTC-05:00``)
  rather than guess an abbreviation a bare offset can't determine;
* with neither, UTC only.

To show ``CDT`` the location config needs a ``tz_name`` field (today it carries only
``tz_offset_hours`` — see #365); until then surfaces show the offset, which is honest.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _as_utc(dt: datetime) -> datetime:
    """Coerce to an aware UTC datetime; a naive input is assumed to already be UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _offset_label(off: timedelta | None) -> str:
    total = int((off or timedelta(0)).total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"UTC{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def _abbrev_zone(name: str) -> str:
    """Abbreviate a verbose OS zone name to its initials so a human surface reads a
    clean **local** label, not a UTC offset (#840): ``Central Daylight Time`` ->
    ``CDT``, ``Eastern Standard Time`` -> ``EST``. Returns ``""`` for anything that
    isn't the standard ``<Region> <Standard|Daylight> Time`` shape, so the caller
    can fall back honestly rather than invent an abbreviation."""
    w = name.split()
    if len(w) == 3 and w[1] in ("Standard", "Daylight") and w[2] == "Time":
        return (w[0][0] + w[1][0] + w[2][0]).upper()
    return ""


def _localize(
    u: datetime, tz_name: str | None, tz_offset_hours: float | None
) -> tuple[datetime, str]:
    """(local datetime, zone label). Prefers a real IANA abbreviation, then a numeric
    offset, then UTC — degrading honestly if the tz database is unavailable."""
    if tz_name:
        try:
            from zoneinfo import ZoneInfo

            loc = u.astimezone(ZoneInfo(tz_name))
            return loc, (loc.tzname() or _offset_label(loc.utcoffset()))
        except Exception:
            pass  # no tz database (e.g. bare Windows w/o tzdata) -> fall back honestly
    if tz_offset_hours is not None:
        loc = u.astimezone(timezone(timedelta(hours=tz_offset_hours)))
        return loc, _offset_label(loc.utcoffset())
    return u, "UTC"


def _utc_tail(u: datetime, local: datetime, seconds: bool) -> str:
    if local.date() == u.date():
        utc_s = u.strftime("%H:%M:%SZ" if seconds else "%H:%MZ")
    else:
        utc_s = u.strftime("%Y-%m-%d %H:%MZ")
    return f" · UTC {utc_s}"


def local_first(
    utc_dt: datetime,
    *,
    tz_name: str | None = None,
    tz_offset_hours: float | None = None,
    seconds: bool = False,
    utc_secondary: bool = True,
) -> str:
    """Render a timestamp **local-first**.

    E.g. ``2026-06-28 13:14 CDT · UTC 18:14Z``. With ``utc_secondary=False`` the
    ``· UTC …Z`` tail is dropped for a clean local-only label (#840) — the canonical
    ``*_utc`` data is unchanged; this is display only. The UTC date is shown only
    when it differs from the local date (a midnight crossing), so the tail stays terse.
    """
    u = _as_utc(utc_dt)
    local, zone = _localize(u, tz_name, tz_offset_hours)
    tfmt = "%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M"
    local_s = local.strftime(tfmt)
    tail = _utc_tail(u, local, seconds) if utc_secondary else ""
    return f"{local_s} {zone}{tail}"


def local_first_system(
    utc_dt: datetime, *, seconds: bool = False, utc_secondary: bool = True
) -> str:
    """Local-first using the **host's** local timezone — for surfaces viewed on the rig
    (the live dashboard, the Lab Notebook). Renders the OS abbreviation when crisp
    (``CDT``), abbreviates a verbose OS name to its initials (``Central Daylight
    Time`` -> ``CDT``, #840), else the offset; a UTC-only host reads ``UTC``.
    ``utc_secondary=False`` drops the ``· UTC …Z`` tail for a clean local label."""
    u = _as_utc(utc_dt)
    local = u.astimezone()  # the host's local timezone
    zone = local.tzname() or ""
    if " " in zone:  # a verbose OS name (Windows) -> initials, else crisp offset
        zone = _abbrev_zone(zone) or _offset_label(local.utcoffset())
    elif not zone:
        zone = _offset_label(local.utcoffset())
    tfmt = "%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M"
    local_s = local.strftime(tfmt)
    tail = _utc_tail(u, local, seconds) if utc_secondary else ""
    return f"{local_s} {zone}{tail}"
