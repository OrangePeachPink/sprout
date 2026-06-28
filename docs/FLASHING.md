# Flashing Sprout — the web-flasher path (#271)

The goal: a newcomer gets our firmware onto an ESP32 **without the Arduino IDE and without a
toolchain** — plug in USB, open a page, click **Install**. This is the firmware side of that
(the factory image + manifest); DX owns the actual flasher page (#261/#271).

## First flash — from a browser

1. Plug the ESP32 into a **computer** with a **USB data cable**.
2. Open the flasher page in **Chrome or Edge** (desktop).
3. Click **Install** → pick the serial port → it flashes the factory image.

That's it — no IDE, no `pio`, no compiler. ESP Web Tools talks to the board over the browser's
**Web Serial API**.

### What you need (and what won't work)

| Need | Why |
|---|---|
| A **desktop/laptop** (Windows, macOS, Linux) | Web Serial is desktop-only |
| **Chrome or Edge** (any Chromium browser) | Web Serial isn't in **Safari** or **Firefox** |
| A **USB *data* cable** (not charge-only) | the board enumerates as a serial port |

**Won't work:** **Safari**, **iOS / iPadOS** (no browser there has Web Serial), or Android. The
first flash needs a real computer + Chromium browser. (After the first flash, updates go over
WiFi — see OTA below — so the computer is a one-time thing.)

## What the flash looks like — the prompts (pre-explain these)

The flow has a couple of browser prompts that surprise first-timers. In order:

1. **Click Install** → the browser shows a **serial-port chooser**: *"&lt;site&gt; wants to connect to
   a serial port"* with a list. Pick the ESP32 — it's usually labeled by its USB-serial chip, e.g.
   **"CP2102 USB to UART Bridge"** / **"Silicon Labs CP210x"**, or **"USB-SERIAL CH340"**. This is the
   browser's own **Web Serial** permission prompt (not ours), and it's the one step a newcomer needs
   told about: *which* entry to pick.
2. **Connecting…** → ESP Web Tools puts the board into download mode automatically (DTR/RTS) on most
   dev boards — no BOOT button needed; a few clones need BOOT held while connecting.
3. **"Erase device?"** → our manifest sets `new_install_prompt_erase`, so a first install offers a
   clean **erase + install**. Confirm it for a fresh board.
4. **Installing…** progress → **"installation complete"** → the board reboots running Sprout (you'll
   see telemetry on a serial monitor at 19200 baud).

**Driver note:** the USB-serial chip may need a driver — macOS/Linux usually have it built in, Windows
10/11 usually auto-installs, but **CH340** boards sometimes need the WCH driver. If **no port appears**
in step 1, that's the cause.

## The firmware artifacts (how the image is built)

`pio run -e esp32dev` produces three files in `firmware/.pio/build/esp32dev/` via the post-build
[`scripts/factory_bin.py`](../firmware/scripts/factory_bin.py):

- **`sprout-esp32-factory.bin`** — bootloader + partitions + boot_app0 + app **merged into one
  image, flashed at offset `0x0`**. Built with the same `esptool` (4.11.0) a real upload uses, so
  the merge matches a hardware flash exactly.
- **`manifest.json`** — the [ESP Web Tools](https://esphome.github.io/esp-web-tools/) manifest
  (`chipFamily: ESP32`, the factory image at offset 0; `version` is read from `PLANTS_FW_VERSION`
  in `config.h`, so it never drifts). It also carries a **`provenance`** block — `sha256`, `bytes`,
  and `git` of the exact image — that the flasher page reads to show real provenance **before**
  Install (ESP Web Tools ignores the extra field). **#271 / Design.**
- **`sprout-esp32-factory.bin.sha256`** — the checksum sidecar (`sha256sum -c`-friendly) for release
  attachment + CLI verification.

> The `.bin` embeds `GIT_REV` + a build timestamp, so its SHA256 is **per-build** — always read the
> hash from the build's own `manifest.json` / `.sha256`, generated against that exact image. (A
> byte-reproducible build is a later option if we want a fixed published hash per commit.)

Both are **build artifacts** (git-ignored), never committed. To publish a flashable release: build,
then attach `sprout-esp32-factory.bin` + `manifest.json` as **release assets** (or copy them next to
the flasher page); the page points `<esp-web-install-button manifest="manifest.json">` at the
manifest, which points at the binary. **(→ DX / release: that hosting plus the page is the DX half
of this slice.)** Automating the build-and-attach in CI is a sensible fast-follow (mind the Actions
cost — `pio run` pulls the full platform; cache `~/.platformio`).

## Updates after the first flash — OTA over WiFi

The plan (PRD-0005): once the device is on WiFi, updates are **wireless** (ArduinoOTA / a web
update) — the USB cable is a one-time onboarding step, not a living dependency.

> **Status: not live yet.** OTA needs the firmware on WiFi, and the WiFi / captive-portal slice
> isn't built. **Until WiFi lands, "update" = re-run the web-flasher** (plug USB, browser, Install).
> This is acceptance criterion 2 of #271 and it's **gated on the WiFi slice** — see the routing
> note on #271. The web-flasher path (criteria 1 + 3) is independent and works today.

## Developer note (not the newcomer path)

Contributors with PlatformIO can still flash directly over USB — `pio run -e esp32dev -t upload` —
or the watchdog bench build `pio run -e esp32dev_wdttest -t upload` (#191). The web-flasher exists so
a *user* never has to install any of that.
