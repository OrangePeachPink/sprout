# Can you trust your sensor? A 3-minute board check

Sprout's whole promise is **honest data** — but a cheap capacitive soil-moisture sensor can lie *before*
Sprout ever sees the number. A large share of the inexpensive boards sold online ship with a known functional
flaw, and many carry silkscreen printing errors too. If your board is one of the bad ones, "honest" readings
are honestly wrong.

So before you trust a reading, spend three minutes learning to trust — or distrust — the hardware in your hand.
You need your eyes and a cheap multimeter. That's it.

> **The short version:** look for a `662K` regulator and a `TLC555` timer chip, then meter about 1 MΩ between
> the `GND` and `AOUT` pins. If all three check out, your board is the well-made kind.

## Why this matters

These boards measure how much water is near two copper plates (a capacitor) and turn that into a voltage Sprout
can read. **More water means lower voltage**, so dry reads *high* and wet reads *low* — it feels backwards until
it clicks. A well-made board caps its output around 0–3.0 V, which is why it reads cleanly on a 3.3 V board with
no extra parts.

Capacitive sensors beat the older *resistive* probes because no metal touches the soil, so nothing corrodes
away in a few days. But "capacitive" alone does not mean "good" — the three flaws below are what separate a
trustworthy board from a pretty paperweight.

## Step 1 — Identify (eyes only, about 60 seconds)

Hold the board up and find two parts near the cable end:

- **The voltage regulator** — a tiny 3-pin chip marked **`662K`**.
  - *Present* means good: your readings stay put even as a battery drains.
  - *Missing* (you will see two solder pads bridged instead) means the output drifts with the supply voltage.
    Fine on a steady USB rail, unreliable on a battery. *(This is Flaw 1.)*
- **The timer chip** — the 8-pin chip; read the text printed on top.
  - **`TLC555`** is good: it runs down to about 3 V, so it is happy on a 3.3 V board.
  - **`NE555`** is trouble: it needs about 4.5 V, so it is unreliable (or dead) at 3.3 V. *(This is Flaw 2.)*

**Ignore the version number.** `v1.2` vs `v2.0` printed on the board is *marketing, not quality* — per the
Flaura teardown they're often the exact same product from one of ~five factories. Judge a board by its parts
(regulator + timer + the meter test), never by its printed version.

> Sprout's own four sensors carry the `662K` regulator **and** a genuine `TLC555` — the well-made variant. We
> checked all four; see [`SENSOR_QA.md`](../../SENSOR_QA.md).

## Step 2 — Meter the hidden flaw (multimeter, about 90 seconds)

The third flaw is invisible: a misplaced connection can leave a 1 MΩ resistor's ground side floating. A board
like that returns the **same stale number** read after read — it *looks* like it is working, which is exactly
what makes it dangerous. You cannot see this one; you measure it:

1. Unplug the sensor. Set the multimeter to resistance (the **Ω** mode), around the 2 MΩ range.
2. Touch one probe to the **`GND`** pin and one to the **`AOUT`** pin on the 3-pin header.
3. Let the number settle for a second (a small capacitor charges off the meter).
4. Read it:
   - A steady **~1 MΩ** means the resistor is grounded. **PASS.**
   - **Open** (the meter shows `OL`) in *both* probe directions means the ground link is broken. **FAIL.**
     *(This is Flaw 3.)*

> Sprout's four boards metered **0.993–1.000 MΩ** — essentially nominal, and the tight cluster is itself a sign
> of a good batch.

## Step 3 — Understand what each flaw does, and decide

Which flaw actually bites depends on how you power the board:

| Flaw | On a 3.3 V board / battery | On a 5 V board (steady supply) | If your board has it |
| --- | --- | --- | --- |
| 1 — no `662K` regulator | **Matters** (worse on a battery) | Minor | Give it a clean, steady voltage |
| 2 — `NE555` timer | **Fatal** — will not run at 3.3 V | Usually fine (≥ 4.5 V) | Run it at ≥ 4.5 V, or replace it |
| 3 — floating 1 MΩ resistor | **Matters** | **Matters** (supply does not help) | Fix it (below), or replace it |

If a board fails, you have three honest choices:

- **Fix it.** For Flaw 3, solder a 1 MΩ resistor across the `AOUT` and `GND` pins, or run a short wire from the
  resistor's floating side to ground.
- **Power it differently.** For Flaw 1, feed it a steady voltage; for Flaw 2, run it at 4.5 V or more.
- **Reorder — carefully.** Zoom all the way into the product photos first and confirm a `662K` regulator, a
  `TLC555` (not an `NE555`), and the small via sitting *between* the two output resistors.

> **A slow sensor isn't automatically trash — try it before buying a replacement.** A board that *fails the meter
> test* (Flaw 3) reacts sluggishly: no quick swing when you push it into wet soil. But soil changes slowly
> and Sprout reads on plant-time (every few hours), not by the second — so if you let each reading settle and
> don't lean on rapid 5-in-a-row averaging, a slow board can still tell "dry" from "watered" usefully. Meter
> it, know its limit, then either live with the slow cadence or do the cheap fix above. *"Use what you have"*
> beats a landfill sensor — just remember the fast-averaging caveat from Flaw 3.

## Match your board's voltage (the kit won't tell you)

A sensor and a microcontroller (MCU) only get along if their voltages agree — and the kit usually says
nothing about either. Two things to check:

- **Your board's logic voltage.** Most modern Wi-Fi boards — **ESP32** (all variants) and **ESP8266** — run
  at **3.3 V**. Classic **Arduino** boards (Uno, Nano, Mega) run at **5 V**. Not all Arduino boards match,
  though — a Nano 33 or a Nano ESP32 is 3.3 V — so check *your* board's spec.
- **What that means for the sensor:**
  - An **`NE555`** sensor needs about **4.5 V**: fine on a 5 V Arduino, **dead on a 3.3 V ESP32** (Flaw 2
    again). A `TLC555` runs on either.
  - A **regulated** board caps its output at ~**0–3.0 V** whatever you feed it, so it reads safely on a
    3.3 V ADC with no extra parts. An **unregulated** board fed 5 V can push its output **above 3.3 V** —
    past an ESP32's input range, which can damage the pin. Regulate it, or use a voltage divider.

A voltage mismatch isn't a defect — it's a pairing problem. Match the parts, or swap one.

## The silkscreen lesson: trust the position, not the label

Beyond the three functional flaws, these boards routinely ship with silkscreen typos — mislabeled printing on
the board itself. The most common one: the analog-output pin is often printed **`AUOT`**, a typo for **`AOUT`**.
It is cosmetic — the pin works fine. Power-pin mislabels happen too.

The lesson for a careful owner: **trust the pin's position and the chip markings, not the printed text** — and
when in doubt, meter it. That habit is the whole point of this guide: trust, or distrust, your own hardware.

## New to the tools?

This guide asks you to use a **multimeter** (Step 2) and, for the fix, a **soldering iron**. If either is new:

- **Using a multimeter** (resistance + continuity — exactly Step 2) — SparkFun's
  [How to Use a Multimeter](https://learn.sparkfun.com/tutorials/how-to-use-a-multimeter).
- **Through-hole soldering** (for the 1 MΩ fix) — Adafruit's
  [Guide to Excellent Soldering](https://learn.adafruit.com/adafruit-guide-excellent-soldering).

The **Flaura teardown video** linked just below is the friendliest ~10-minute intro to how these sensors work —
and why so many are faulty.

## Where this comes from

- [`SENSOR_QA.md`](../../SENSOR_QA.md) — Sprout's own bench checks on its four sensors, the authoritative source
  for every claim above.
- [`docs/RESEARCH_capacitive_soil_moisture_sensors.md`](../RESEARCH_capacitive_soil_moisture_sensors.md) — the
  longer research foundation: defects, diagnosis, fixes, and buying guidance, with citations.
- The Flaura project (Martin Uhlmann), *"Capacitive soil moisture sensors — 82% are faulty"*
  ([video](https://www.youtube.com/watch?v=IGP38bz-K48)) — the originating teardown this all traces back to.

---

*This is the content layer for the Sprout User Front Door's flagship guide (issue #142). A later design pass
will dress it in Sprout's tokens and voice — labeled photos, PASS/FAIL chips — but the words and the
engineering are here.*
