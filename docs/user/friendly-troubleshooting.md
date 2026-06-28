# Friendly troubleshooting

Something doesn't look right? Start here. These are the most common "my plant says X" cases — each with a
plain-language cause and a clear next step. Sprout is designed to be honest; most odd readings have an
honest explanation.

> Can't find your symptom here? Check the **[seven bands guide](what-sprout-is-telling-you.md)** for band
> meanings, or the **[sensor board check](trust-your-sensor.md)** if readings seem systematically wrong.

---

## "The reading never changes"

The band and number stay the same no matter how wet or dry the soil gets.

**Likely cause:** a hidden hardware flaw on the sensor board — a 1 MΩ resistor whose ground connection is
floating. The board looks fine from the outside: it powers up, it has an analog output. But internally it's
reading from a disconnected node, so it returns the same stale value on every read. This is **Flaw 3** in
the sensor board check.

**Next step:** run the **[3-minute board check](trust-your-sensor.md)** — specifically Step 2, the resistance
meter test. A board with this flaw will read open (OL) on the meter instead of ~1 MΩ. The fix is a single
solder bridge or a clip-on jumper resistor, or swap for a board that passes.

---

## "It reads dry right after I watered"

The band says **Dry** or **Drying** even though you just watered thoroughly.

**Likely causes (in order to check):**

1. **The sensor is reading the right thing — water takes time to reach it.** Capacitive sensors need the water
   to actually *arrive* at the probe. If the pot drains fast or the water ran straight through to the saucer,
   the soil around the probe may still be dry. Wait 30–60 minutes after a thorough watering before reading.
2. **Probe placement.** A probe wedged into a corner, near the drainage hole, or not in contact with soil
   through its whole sensing area will read the moisture where it *is*, not where you watered. Reseat it so the
   full sensing length sits in the main root zone.
3. **Calibration needs updating.** If this happens consistently (not just after a first watering), the dry
   anchor may have drifted — especially after repotting, seasonal changes, or soil compaction around the probe.
   Re-run the dry-air and wet-soil anchors.

> One thing that's *not* wrong: **dry reads high, wet reads low** is how capacitive sensors work (higher raw
> ADC count = less water near the plates). Sprout handles this inversion internally — the band you see is
> already corrected. If you've been comparing raw numbers between sensors and they seem backwards, that's why.

---

## "The numbers jump around"

The reading swings rapidly through bands (or the number bounces by large amounts between reads), without
anything changing in the pot.

**Likely causes:**

1. **Loose connector.** The 3-pin PH2.0 cable can back out slightly, especially if the sensor was nudged.
   Unplug and reseat it firmly — it should click into place. Check the cable isn't tugging on the connector.
2. **Power gating on the sensor line.** If the firmware is cutting power to the sensor between reads (a
   current-saving pattern), the sensor needs a short warm-up before its output settles. The timing is handled
   in the firmware; if you see jumps only on the first reading after a long sleep, this is expected and
   averages out.
3. **Electrical noise on the ADC line.** A loose ground, a wire running next to a power cable, or other sources
   of EMI can inject noise. Keep sensor cables away from pump and relay wiring; confirm the GND connection is
   clean at both ends.
4. **Probe spread fault.** Sprout's classifier flags a health warning when the spread of raw samples across a
   single reading is too wide — a sign of a noisy or unstable reading. If the dashboard shows a health warning,
   the connector and wiring are the first places to look.

---

## "Sprout won't start / the dashboard won't open"

The command ran but nothing appeared, or the page errors out.

**Next step:** check the launcher's own output first — Sprout prints its status as it starts, including what
went wrong. The messages are written to be self-explanatory: a missing serial port, a port already in use, a
logger that couldn't reach the board.

If `just start` printed an error, read that message before anything else. The build-and-run guide (coming
soon) covers the full startup sequence and the common first-run issues. If the guide isn't published yet,
`just` (no arguments) lists every available command, and `just check` confirms the dev environment is set up
correctly.

---

## "A band I've never seen appeared"

**Saturated** appeared after a deep watering, or **Parched** appeared when the soil looks fine.

- **Saturated** is expected right after heavy watering or if a pot is sitting in water. It clears on its own
  as the soil drains. If it persists for hours in a well-draining pot, check for blocked drainage.
- **Parched** means the sensor is reading near air-dry levels. This is either very dry soil *or* a probe that's
  lost contact with soil (shifted out of the pot, or the soil has shrunk away from it as it dried). Check
  probe placement first. The [seven bands guide](what-sprout-is-telling-you.md) has more on what these
  diagnostic bands signal.

---

*Friendly troubleshooting guide for the User Front Door, voiced for the plant owner (issue #144). Links in
parentheses that say "coming soon" or "#N" are real issues that land after this file. A Design pass will
add visual treatment — the words are here.*
