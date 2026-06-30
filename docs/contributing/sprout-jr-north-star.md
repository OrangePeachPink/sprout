# Sprout Jr — the DX North Star 🌱

*Owned by DX (#387). This is the direction the team builds the beginner on-ramp to. The warm, user-facing
copy lives in [`arduino-starter.md`](arduino-starter.md); this is the **why and the what-good-looks-like**
behind it.*

---

## The North Star

> **A complete beginner plugs in three wires, and within one sitting they watch the soil come alive on a
> graph, teach the board what *their* dry and wet look like, and hear their plant say one of three honest
> things. They leave thinking: *"I just did embedded. I want more of this."***

Sprout Jr's job is not to water a plant. It's to turn "I've never touched a microcontroller" into "I'm an
embedded engineer who hasn't realized it yet" — and to make the jump to **Sprout Full** feel like the obvious
next step, not a cliff. We are in the business of delight and momentum.

---

## Who walks in the door

Our starting user is a curious person — a maker, a hobbyist, a plant person, a bored developer, a
purple-haired art student who just bought a $2 sensor on a whim. Assume they know **next to nothing** about
the hardware, and assume they are **smart, excited, and easily lost.** Specifically:

**What they probably DON'T know:**

- The difference between an Arduino, an ESP32, and "a microcontroller." (They may use the words
  interchangeably.)
- What an **ADC** is, or that a sensor speaks in raw numbers (0–4095), not "percent wet."
- That a capacitive sensor needs **calibration** — that the same soil reads differently on every probe, and
  there is no universal "wet number."
- What "flashing" or "uploading" means, or that the Serial Monitor / Serial Plotter exist.
- That **higher raw reading = drier** (it's counter-intuitive — bigger number, *less* water).

**What they probably DO know (build on this):**

- "Plants need water, and I forget." The motivation is real and personal.
- They can copy-paste, plug in a USB cable, and follow exact clicks.
- They've seen a graph. A line going up and down is instantly legible.
- They want a **win they can feel** in the first sitting, or they're gone.

**What they're afraid of:** soldering, "breaking" something, a wall of jargon, a tutorial that assumes step 4
when they're on step 1. We remove every one of those fears.

---

## The landscape (and the gap we fill)

There is a lot out there. None of it is a real on-ramp.

| What exists | What's good | Why it's not the on-ramp |
| --- | --- | --- |
| **[Adafruit STEMMA soil sensor](https://learn.adafruit.com/adafruit-stemma-soil-sensor-i2c-capacitive-moisture-sensor/overview)** | Gorgeous guides; corrosion-proof; I²C | A chip **abstracts the raw signal away** (returns 200–2000 via a library). You never *feel* calibration. I²C + a library + CircuitPython culture = more concepts on day one, and it's not the cheap sensor most people actually bought. |
| **[SparkFun hookup guides](https://learn.sparkfun.com/tutorials/soil-moisture-sensor-hookup-guide/all)** | Excellent "measure dry, measure wet, calibrate" narrative | Teaches `map()` → a moisture **percentage** (the thing we call a lie); spread across a parts catalog, not one path. |
| **ESP32 GitHub projects** ([nclman](https://github.com/nclman/esp32-soil-moisture), [Plantwatery](https://github.com/Lumics/Plantwatery), [garduino](https://github.com/thijstriemstra/garduino)) | Real, complete watering systems | Every one **leaps straight to WiFi + pump + Firebase/MQTT/Home Assistant.** That's the deep end at hour one. Overwhelming, and a giant tail to maintain. |
| **The generic tutorials** ([Maker Portal](https://makersportal.com/blog/2020/5/26/capacitive-soil-moisture-calibration-with-arduino), [DFRobot](https://wiki.dfrobot.com/sen0193/docs/18036)) | Use the real $2 sensor; teach `map()` | All of them end at **"now it's a percentage."** None teach that a percentage is dishonest. |

**The gap — and our wedge:** every existing path either hides the raw signal, or buries the beginner in
WiFi/pump/cloud, or teaches them a comforting **lie** (moisture %). Sprout Jr does the opposite of all three:

> **It shows the raw signal honestly, stays radically small, and even at the beginner level refuses the lie —
> it teaches *bands*, not a fake percentage.** Bands are the truth, and they are the conceptual seed of Sprout
> Full's seven-band honest-data system. *Even our on-ramp is honest.* That's the soul of the project, present
> from the first sitting.

---

## The decision: ESP32 (not Arduino Uno)

You have both, so this is a deliberate DX call, and I'm planting the flag on **ESP32**. Reasons, in order:

1. **It's the board Sprout Full runs on.** Graduation becomes *"you already know this hardware,"* not *"throw
   away your Uno and learn a new board."* The on-ramp's entire purpose is the jump to Full — don't break
   hardware continuity.
2. **The numbers transfer 1:1.** Sprout Full reads this sensor on the same 3.3 V, 12-bit ADC and sees
   ~**900 wet / ~3150 dry** raw. On an ESP32, *the dry and wet numbers a beginner calibrates by hand in Jr are
   literally the numbers Sprout Full uses.* Their first calibration **is** the real thing. (On a 5 V, 10-bit
   Uno the range is squeezed into ~0–600 and the numbers don't carry over — a worse teaching story.)
3. **Delight headroom without the tail.** WiFi is built in, so a future "see it on your phone" stretch exists
   on the *same* board — but we keep it firmly **out** of core Jr (see Scope).

**The one cost — a 5-minute first-time setup** (install the ESP32 board package + a USB driver). We don't
hand-wave it; we script it with exact clicks. That's the only place Uno would've been easier, and continuity
is worth it.

**Inclusive fallback:** the sketch should run on an Uno too with **one constant changed** (`ADC_MAX` 4095 →
1023, and the pin). Recommend ESP32; never block the person who only has an Uno. One sketch, board-agnostic
where it's trivial — no more.

**Tool:** the **Arduino IDE** — on purpose. Sprout Full dropped it, but the Arduino IDE *is the beginner's
first tool*, and its **Serial Plotter is our delight engine.** This is exactly why Jr exists.

---

## What we build: one sketch, three knobs-blocks, three bands

**One `.ino` file. No libraries. Raw `analogRead`.** That's the whole artifact.

### The knobs (the tunable constants block)

The beginner edits *only this block* — it's the entire interface, and every knob is a teaching moment:

```cpp
// ===== TUNE ME — this is the whole control panel =====
const int  SENSOR_PIN    = 34;     // the analog pin your sensor's signal wire goes to
const long READ_EVERY_MS = 1000;   // how often I check the soil (try 200 — watch it speed up!)
const int  SAMPLES       = 8;      // readings I average each check (smooths the jitter)

// --- Calibrate these two to YOUR probe (the fun part — go measure!) ---
const int  DRY_READING   = 3150;   // what you saw with the probe in dry AIR
const int  WET_READING    = 900;   // what you saw with the probe in a CUP OF WATER

// --- Where the 3 bands split (between your two numbers above) ---
const int  THIRSTY_ABOVE = 2400;   // drier (bigger) than this  -> "thirsty"
const int  SOAKED_BELOW  = 1400;   // wetter (smaller) than this -> "just watered"
//                         (anything in between -> "all good")

const bool BLINK_WHEN_THIRSTY = true;  // pulse the onboard LED when it needs water
```

Why these knobs, specifically:

- `SENSOR_PIN` teaches "the board has named pins; the sensor lives on one."
- `READ_EVERY_MS` + `SAMPLES` are pure play — change them, watch the behavior change. Teaches cadence and
  noise without naming them.
- `DRY_READING` / `WET_READING` are the **heart of the lesson**: you go measure two numbers and type them in.
  That *is* calibration. The defaults are Sprout Full's real anchors, so it works out of the box and the
  numbers are honest.
- `THIRSTY_ABOVE` / `SOAKED_BELOW` are **raw thresholds, not a percentage** — deliberately. The beginner sees
  that bands are just "where you draw the lines between your dry and wet marks." No `map()`, no lie. (Good
  defaults derived from the anchors mean they only *have* to touch the two calibration numbers to start.)

### The three bands (the conceptual foundation)

Exactly three, in Sprout's voice — the baby version of Full's seven:

| Band | Condition | What the plant says |
| --- | --- | --- |
| **All good** | between the two thresholds | `🌱 Comfy. Nothing to do — I'm happy.` |
| **High and dry** | drier than `THIRSTY_ABOVE` | `🚰 I'm parched! Grab the watering can.` |
| **Just watered** | wetter than `SOAKED_BELOW` | `💧 Ahh, just drank — let me soak it up. (If the outer pot's swimming, tip the extra out.)` |

Three is the magic number: enough to be *useful and alive*, few enough to hold in your head, and a clean
ladder to Full's seven. The "tip out the excess" line is pure care — it teaches that *more water isn't better*,
which is the seed of Full's "overwatered" band.

---

## The on-ramp arc (the delight sequence)

Every step is designed to land a felt win and set up the next. This is the choreography the build serves:

1. **Three wires + plug in** (`GND`, `3V3`, signal→`GPIO34`). ~90 seconds. *"That's it? That's the whole
   circuit?"* — fear of hardware, gone.
2. **Flash the sketch** (Arduino IDE → paste → Upload). *"I made the chip do a thing."*
3. **Open the Serial Monitor** → numbers stream by. *"I'm reading the real world."*
4. **Open the Serial Plotter** → a live line. **Lift the probe out of the water cup → watch the line LEAP.**
   This is **the** moment — the soil becomes *visible*. Hook set.
5. **Calibrate** → jot the dry number (in air) and the wet number (in water), type them into the two
   constants, re-upload. *"I just taught it what my soil feels like."* Empowerment.
6. **It speaks** → the Serial Monitor now prints one of the three band lines. *"It's alive and it's talking to
   me."* Payoff.
7. **It acts** *(optional, one line)* → the onboard LED pulses when thirsty. *"It does something in the
   world."*
8. **The graduation beat** → *"You just hand-built the heart of Sprout: **read → calibrate → band → speak.**
   Sprout Full does this automatically — across seven bands, four plants, a real pump, and a live dashboard —
   on this exact board. Come meet Sprout Full."*

---

## Why they'll want Sprout Full

Jr deliberately leaves them wanting — each ceiling is a Full headline:

- They calibrated **one** probe by hand → Full calibrates **four**, per-channel, and locks them.
- They drew **three** lines → Full has **seven** honest bands and a plant with moods.
- They typed numbers into a file → Full *remembers* calibration and shows a **dashboard**.
- They watched a Serial Plotter → Full **logs every reading** and lets them explore the history.
- The LED blinked → Full drives a **real pump**, safely, with an arm-gate.

Crucially, the **values** carry over intact: Jr taught them that a percentage is a lie and bands are the
truth. Full is just that lesson, all the way up. They don't graduate to a *different* philosophy — they
graduate to *more* of the one they already fell in love with.

---

## Scope guardrails (the no-architectural-tail contract)

This is the part I hold the line on. Sprout Jr is **one `.ino` + one doc, forever.** What it is **NOT**, and
must never grow into:

- ❌ No WiFi, no phone app, no cloud, no MQTT/Firebase/Home Assistant.
- ❌ No pump, no relay, no actuation — it observes and speaks, nothing more.
- ❌ No libraries, no dependencies (`analogRead` only).
- ❌ No persistence — calibration lives in the constants block by hand. *That's the teaching*, not a gap.
- ❌ No display required — the Serial Monitor / Plotter and the onboard LED are the entire UI.
- ❌ **Not** compatible with Sprout Full, and we say so plainly (per #387). It's a porch, not a wing.

If a feature would add a dependency, a second file, or a thing we have to keep working as Full evolves — it
belongs in **Full**, and it becomes a graduation hook instead. The tail we accept is exactly: *one sketch, one
doc.*

---

## DX direction — what the team aims for

- **DX (owns the North Star + the experience):** this direction, the [user-facing copy](arduino-starter.md),
  the exact-clicks setup, the calibration walkthrough, the three band lines in Sprout's voice, and the
  graduation beat. The words and the felt arc are mine.
- **Firmware + Sage (build + verify the sketch):** the actual `.ino` — `analogRead` + `SAMPLES` averaging,
  the three-band compare, the optional LED, and the board-agnostic `ADC_MAX` constant. Sage sanity-checks the
  default anchors against real bench probes so the out-of-box defaults are honest. Coordinated on #387; DX
  hands them this spec, they own the firmware.
- **Design (a later pass, optional):** if the copy ever gets a styled page, Design dresses it — but Jr ships
  in plain Markdown first; no Design dependency to start.
- **Glossary:** Jr's terms (Sprout Jr, the three bands, "calibrate by hand") land in the **User-facing 👤**
  section of [`GLOSSARY.md`](../GLOSSARY.md) when the sketch ships — keeping Jr and Full speaking one language.

---

*The measure of success isn't a watered plant — it's the message a stranger sends a week later: "I built the
thing, and now I'm reading the AS7263 datasheet for fun. What's next?" That's a new embedded engineer. That's
the whole point. — DX 🌱*
