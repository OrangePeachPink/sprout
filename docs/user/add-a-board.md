# Add a board — from an empty Sprout to a plant with a pulse

This is the walk-through for the flow Sprout gives you in the app: describe your hardware,
map it to your plants, and stop cleanly when you're done. **No JSON, no config files, no
command line** — everything below happens in the browser tab `just start` opens.

> **Order matters, and it's the friendly way round.** You describe the board *before* you
> flash it. Sprout records your wiring and plant choices straight away, and when the board
> first reports it keeps them — so nothing you set up is lost between "I have a board" and
> "it's reporting".

## Before you start

You need Sprout running (`just start` — see the [README](../../README.md#quick-start)) and a
board in hand. You don't need it flashed yet, and you don't need it plugged in.

## 1 · Open the flow

On a fresh install, the first screen tells you what's missing and gives you the door:

> **No boards yet.** Sprout is running, but nothing is reporting — there's no board set up
> to send readings.

Click **Add a board**. (Later, when you're adding your second board, the same flow lives in
**Plants & Sensors** — it isn't a one-time wizard.)

## 2 · Which board is this?

Pick your board class — **Classic (ESP32-WROOM)**, **ESP32-C5**, or **ESP32-S3**. Each shows
whether Sprout has a *verified* recommended pinout for it:

- **recommended pins ✓** — Sprout has bench-measured wiring for this board and offers it as
  a one-tap default.
- **pins provisional** — the map exists on paper but nobody has confirmed it on a bench, so
  Sprout **asks instead of suggesting**. A recommendation nobody has measured is a
  hypothesis, and this is the one screen where being wrong means wiring a probe to a pin
  that stops the board booting.

## 3 · What will you call it?

Give it a human name — "Windowsill", "Kitchen shelf". You never type a device id; Sprout
mints that itself when the board first reports.

## 4 · How many probes, and where are they wired?

Set how many probes this board carries, then say which pin each one is on. Where the board
has a verified pinout you can take Sprout's recommendation in one tap; otherwise you tell it
what you actually wired.

## 5 · Which plant is on each probe?

Name your plants, or pick ones you already have, and assign each probe to one. This is
recorded as real history from the moment you save it — so if you later move a probe to a
different plant, Sprout keeps both facts straight instead of silently rewriting the past.

## 6 · Put Sprout on the board

The last step hands you the flasher:

- **Classic ESP32** — **Flash it in the browser** opens the web flasher. Plug the board in
  with a USB **data** cable (not a charge-only one), click Install, and come back.
- **ESP32-C5 / ESP32-S3** — the browser flasher is verified for the classic only, so Sprout
  doesn't offer a door that would fail partway. Flash these over USB with `just flash`
  instead (see [FLASHING.md](../FLASHING.md)).

Everything you set up applies the moment the board reports — Sprout matches it to the record
you just made.

## 7 · Watch it arrive

Until the board reports, Sprout says so **by name** — "waiting for Windowsill", not "waiting
for the first reading". When it does report, your plants light up with what you configured.

## Stopping Sprout

Two ways, both clean:

- **In the app** — the **⏻ Stop server** control at the bottom of Home. Press once to arm,
  again to confirm; the two presses are deliberate, since it shuts the app down.
- **In the terminal** — **Ctrl-C** where you ran `just start`. It exits cleanly; that is a
  documented way to stop Sprout, not a crash.

Either way logging pauses until you start Sprout again. To check nothing was left running:
`just processes` (expects none) or `just doctor`.

## If something looks wrong

**`just doctor`** reports what's actually true on your machine — tools, the environment, the
port, whether any board is declared, serial, firmware toolchain — and names the one thing
that's missing instead of leaving you to guess. It reports; it never changes anything.

See also [friendly troubleshooting](friendly-troubleshooting.md).

<!-- #1558 (C2): step 11 of the onboarding definition-of-done — "verify service and
     hardware health" — is deliberately NOT documented here yet. Its surface is B6
     (#1613), which is not on Home at time of writing, and this page documents shipped
     behaviour only. When B6 lands, a "Is my hardware OK?" section joins the Stopping
     section above. Writing it early would describe a screen that does not exist, which is
     the exact failure #1541 was reported for. -->
