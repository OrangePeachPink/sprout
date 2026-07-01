# What you need to build your Sprout

Sprout runs on cheap, common parts — but *which* parts depends on what you want it to do, what board you have,
and what sensor you grabbed. Answer three quick questions and you'll know exactly what your parts bin can build.
No dense spec sheet — just follow the path. 🌱

> **One thing first, whatever you build: the single setup moment.** Sprout's brain (the board) gets flashed
> *once*. That's the only time you need a computer: plug the board in with a USB cable, open the flasher page in
> **Chrome or Edge**, and click **Install** — no Arduino IDE, no code. After that, updates arrive over Wi-Fi
> (over-the-air), so you never plug in again. *(A computer + cable + Chrome/Edge — not Safari or an iPhone, which
> can't talk to USB.)*

## 1. What do you want Sprout to do? → your tier

Each tier is the one before it, plus a little more. Start where you like and climb later.

- **Tier 0 — Watch.** Just read soil moisture and see it. **You need:** a board + one soil sensor. *(No pump, no
  water — nothing to spill.)*
- **Tier 1 — Water.** Everything in Tier 0, plus automatic watering. **Add:** a small pump, a relay, a little
  reservoir, and tubing. *(The watering safety gate comes built in.)*
- **Tier N — Grow.** More plants and zones, a tank-level sensor, ambient sensors. **Add** these as you go.

## 2. What board do you have? → how you'll talk to it

- **A Wi-Fi board (an ESP32).** The full no-cables experience: flash once (above), then set Sprout up from your
  **phone** and check it from any browser. *Recommended* — it's the windowsill-and-phone dream.
- **A board without Wi-Fi (a classic Arduino — Uno, Nano).** It still works, but it can't go online: you read it
  on a small screen wired to it, or keep it plugged into a computer. No phone setup, no remote dashboard. Worth
  knowing **before** you buy.

If you want Sprout untethered, get an **ESP32** — they're a few dollars and Wi-Fi is built in.

## 3. What sensor did you get? → how much to trust it

- **Capacitive (recommended).** No exposed metal, so it doesn't corrode away in a few days. The catch: a lot of
  the cheap ones ship with a real flaw — so run the 3-minute check before you rely on one:
  **[Can you trust your sensor?](trust-your-sensor.md)**
- **Resistive (cheapest).** Two metal prongs; corrodes and drifts within weeks. Fine to *learn* with, not for
  the long haul. If that's what you have, start with it — then move to capacitive when you can.

## Putting it together (your kit, by tier)

- **Tier 0 — Watch:** an **ESP32** + **1 capacitive sensor** + a **USB cable** + a computer with **Chrome/Edge**
  (just for the one-time flash). That's it — phone setup is next.
- **Tier 1 — Water:** all of the above, **plus** a small **pump**, a **relay**, a **reservoir**, and **tubing**.
- **Tier N — Grow:** Tier 1 plus more sensors/zones, added when you want them.

(On a no-Wi-Fi board, swap "phone setup + browser dashboard" for "a small wired screen.")

## What happens once you have the parts

1. **Flash once** — USB cable + Chrome/Edge + click Install.
2. **Meet Sprout on your phone** — it makes its own Wi-Fi hotspot; connect, pick your home Wi-Fi, name your
   plants.
3. **Walk away** — from then on it reads, reports, and (Tier 1+) waters on its own; updates come over Wi-Fi.

## Onward

- **[Can you trust your sensor?](trust-your-sensor.md)** — the 3-minute board check (do this before you rely on
  a capacitive sensor).
- **[Build & run — kit to first reading](build-and-run.md)** — wiring, the one-click flash, and your first
  live reading.

---

*The "what you need" onboarding guide ([#272](https://github.com/OrangePeachPink/plants/issues/272)), a slice of
PRD-0005 (Untethered Sprout). Content by DX; a later Design pass dresses it in Sprout tokens + voice.*
