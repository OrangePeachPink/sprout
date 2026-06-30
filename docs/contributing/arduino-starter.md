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

---

*Arduino beginner on-ramp ([#387](https://github.com/OrangePeachPink/plants/issues/387)) — the framing + copy.
The actual starter `.ino` (sensor read + the tunable-constants block) is a separate future piece, coordinated
with Firmware/Sage; this doc is the warm, honest voice it ships in. DX owns the words.*
