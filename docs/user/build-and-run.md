# Build & run — kit to first reading

You've got the parts. Here's the path from "box on the table" to "Sprout is reading my soil" —
no coding, no jargon you don't need. If you haven't checked what's in your kit yet, start with
**[What you need](what-you-need.md)** first. 🌱

## 1. Unbox and lay it out

Before touching a wire, spread out what you'll use for **Tier 0 — Watch**: the board, one (or
more) capacitive soil sensor, and a USB cable. *(A pump, relay, and reservoir are Tier 1 — set
those aside for now; this guide gets you reading soil first.)*

## 2. Wire your sensor

Sprout only needs three connections per sensor — no soldering:

| Sensor wire | Goes to |
| --- | --- |
| **Power** (often red) | the board's `3V3` pin |
| **Ground** (often black) | the board's `GND` pin |
| **Signal / AOUT** (often yellow) | one analog input pin |

**Before you trust the "signal" wire's label — check it.** A lot of these cheap sensors ship with
a **mislabeled silkscreen** (the printed text on the board), most often swapping `AOUT` for a
lookalike misprint. Read **[Can you trust your sensor?](trust-your-sensor.md)** — it's a 3-minute
check, and it's worth doing *before* you wire, not after you get a strange reading.

Wiring more than one sensor? Every sensor's power and ground can share the same `3V3`/`GND` rail
(a breadboard row works fine); only the signal wires need their own separate pin.

## 3. Flash Sprout onto the board (the setup step)

You'll need a computer plugged in for this:

1. Plug the board in with a **USB data cable** (not a charge-only cable).
2. Open the flasher page in **Chrome or Edge** on a desktop or laptop — not Safari, not a phone
   (they can't talk to USB this way).
3. Click **Install**.

Full walkthrough, including what the browser prompts mean: **[FLASHING.md](../FLASHING.md)**.

After this, Sprout runs on its own — but keep the cable: for now, updating means re-flashing from this page,
since automatic over-the-air updates aren't shipped yet.

## 4. See your first reading

Run Sprout on your computer:

```sh
just start
```

This opens Sprout's dashboard in your browser — the same one-command entry the whole project
uses (no separate app to install). Within a few seconds you should see your sensor's raw reading
change as you touch the probe or move it between dry air and a cup of water.

**What that number means (and what it doesn't):** the raw reading isn't a percentage — a soil
sensor can't measure moisture as precisely as a number like "42%" implies. Sprout instead sorts
readings into honest **bands** (dry, ideal, wet, and so on). Read
**[What Sprout is telling you](what-sprout-is-telling-you.md)** to understand the bands and know
when a reading means what it says.

## What's next: watering

Sprout can already take an **operator-commanded** watering action — you can tell it to run a pump
for a moment. But the automatic "water this plant when it's dry" loop is intentionally **not
turned on yet**: the safety checks that make unattended watering trustworthy come first, in order
(that's Sprout's rule — *make watering correct before it's possible*). This section grows as that
work lands; for now, this guide gets you to a live, honest reading, which is the real foundation
everything else builds on.

## If something looks off

A reading that never changes, jumps around, or shows up in the wrong band almost always traces
back to the sensor itself, not your setup. **[Friendly troubleshooting](friendly-troubleshooting.md)**
covers the common cases in plain language.

---

*Build & run guide ([#141](https://github.com/OrangePeachPink/sprout/issues/141), part of the
[User Front Door epic](https://github.com/OrangePeachPink/sprout/issues/134)). Builds on the
project's wiring/bring-up history — see [STATUS.md](../STATUS.md) for current firmware standing.
The watering section is a placeholder by design, not an oversight — it fills in once the
autonomous watering loop (#94) is safety-gated and live. Content by DX; a later Design pass dresses
it in Sprout tokens + voice, matching the other three user-facing guides.*
