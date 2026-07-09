# The Arduino starter — your first step into Sprout's world

New to microcontrollers? **Welcome — start here.** The full Sprout project uses VS Code + PlatformIO (or
GitHub Codespaces), and that's a wonderful place to end up. But if you've never flashed a board before, you
shouldn't have to learn a whole professional toolchain just to feel your sensor come alive. So here's a tiny
Arduino door you can walk through *today*. 🌱

## First, an honest word about what this is

This starter is **deliberately small and single-purpose**: read your capacitive soil sensor, show the number,
maybe blink something. That's it. It's here so you can do one real thing with your own sensor and
microcontroller in an afternoon — no accounts, no build system, no jargon.

**It is not a small version of Sprout.** The starter and the full Sprout project are *not compatible* — you
can't grow this sketch into Sprout, and you shouldn't try. They're built differently on purpose. Think of the
starter as a friendly front porch, not the first room of the house. We'd rather tell you that plainly now than
let you feel stuck later.

## What you'll get to play with

The starter hands you a clearly-labelled block of **tunable constants** — numbers you're *meant* to change and
watch what happens:

- the **wet** and **dry** reading for your particular sensor (every board reads a little differently)
- how often it takes a reading
- the threshold where "moist enough" becomes "time to water"

Change a number, re-flash, watch the behavior shift. That loop — *tweak, observe, understand* — is the whole
point. There's nothing to break.

## A few words you'll carry forward

The starter quietly teaches the same vocabulary the full project uses, so nothing feels foreign when you
graduate. A handful you'll meet here and see again in the [Sprout glossary](../GLOSSARY.md):

- **Capacitive sensor** — reads moisture without bare metal in the soil (so it doesn't corrode away).
- **Raw reading** — the honest number straight off the sensor, before anyone interprets it. Sprout treats the
  raw reading and the calibrated **band** as the truth, never a polished percentage.
- **Wet / dry calibration** — finding *your* sensor's soaked-soil and bone-dry numbers, so its readings mean
  something. You'll do this by hand here; Sprout does it per-channel later.
- **Moisture band** — turning a raw number into a plain word (dry / ideal / wet) — the same idea Sprout uses to
  decide a plant's mood.

Learn these four here and you're already speaking Sprout.

## When you're ready, come all the way in

The moment you want **more than one plant, real watering, a dashboard, honest logged data, or a project you can
actually contribute to** — that's your cue. Open the full Sprout project in **VS Code + PlatformIO** or in
**GitHub Codespaces** (zero install, right in your browser) and follow the
[developer front door](developer-front-door.copy.md). Same sensors, same words, a real home. We'll be glad to
see you. 🌱

## Other great places to learn — you're welcome anywhere

We're not the only door into this, and we'd never pretend to be. The maker community is generous, and these
folks taught us plenty. If a different voice clicks better for you, go — then come back and show us what you
built:

- **[Adafruit — STEMMA Soil Sensor guide][adafruit]** — beautifully produced, beginner-kind walkthroughs.
  Their sensor is a corrosion-proof I²C version (a little different from the cheap analog one here), and the
  Adafruit Learning System is a gift to every new maker.
- **[SparkFun — Soil Moisture Sensor Hookup Guide][sparkfun]** — a clear, friendly take on the "measure dry,
  measure wet, calibrate" idea, with great diagrams.
- **[DFRobot — Capacitive Soil Moisture Sensor (SEN0193) wiki][dfrobot]** — the docs for the classic,
  inexpensive capacitive sensor most people start with (the same family Sprout uses).
- **[Maker Portal — calibration with Arduino][makerportal]** — a tidy step-by-step on getting your dry/wet
  numbers.
- **Full watering builds on ESP32 (GitHub):** [nclman/esp32-soil-moisture][gh-nclman],
  [Lumics/Plantwatery][gh-lumics], and [thijstriemstra/garduino][gh-garduino] — real, complete plant-watering
  projects (WiFi, pump, dashboards) to explore once the basics feel comfortable.

> *One honest heads-up:* most of these (and most tutorials everywhere) finish by turning the reading into a
> **moisture percentage** with `map()`. That's a fine way to *start* — but here, and in Sprout, we deliberately
> stick to **bands** ("dry / ideal / wet") instead, because a single percentage pretends to a precision the
> sensor doesn't actually have. Both approaches will get you reading soil today; we just think bands tell the
> truth more honestly. Learn from everyone, then decide for yourself.

[adafruit]: https://learn.adafruit.com/adafruit-stemma-soil-sensor-i2c-capacitive-moisture-sensor/overview
[sparkfun]: https://learn.sparkfun.com/tutorials/soil-moisture-sensor-hookup-guide/all
[dfrobot]: https://wiki.dfrobot.com/sen0193/docs/18036
[makerportal]: https://makersportal.com/blog/2020/5/26/capacitive-soil-moisture-calibration-with-arduino
[gh-nclman]: https://github.com/nclman/esp32-soil-moisture
[gh-lumics]: https://github.com/Lumics/Plantwatery
[gh-garduino]: https://github.com/thijstriemstra/garduino

---

*Arduino beginner on-ramp (part of the [Arduino On-Ramp epic](https://github.com/OrangePeachPink/sprout/issues/435))
— the framing + copy. The real sketch, built by Firmware to this spec, lives at
[`arduino-starter/arduino-starter.ino`](../../arduino-starter/arduino-starter.ino) — one file, no libraries,
matching this page's constants and voice exactly. DX owns the words; Sage validates the real bench anchors
before the out-of-box defaults are trusted.*
