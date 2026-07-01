# The Sprout web-flasher page (#271)

`index.html` is the flasher: plug an ESP32 in over USB, open the page in Chrome/Edge, click
**Install** — no Arduino IDE, no toolchain. It's the DX half of #271; Firmware owns the factory image
and the manifest it flashes. See [`docs/FLASHING.md`](../FLASHING.md) for the full first-flash
walkthrough.

## How it works

- The page hosts an [ESP Web Tools](https://esphome.github.io/esp-web-tools/) `<esp-web-install-button>`
  pointed at **`./manifest.json`** (version pinned so behaviour never drifts).
- ESP Web Tools flashes over the browser's **Web Serial API** (Chrome/Edge desktop only) — the page
  gracefully tells Safari / Firefox / phone users to switch browsers.
- Before Install, the page reads the manifest's **`provenance`** block (`sha256` / `git` / `version` /
  `bytes`) and shows exactly what's about to be flashed — honest by default.

## The manifest + image (Firmware's build artifacts)

`pio run -e esp32dev` runs [`firmware/scripts/factory_bin.py`](../../firmware/scripts/factory_bin.py),
which emits into `firmware/.pio/build/esp32dev/`:

- `sprout-esp32-factory.bin` — the merged factory image (flashed at offset `0x0`)
- `manifest.json` — the ESP Web Tools manifest (references the `.bin`, carries the `provenance` block)
- `sprout-esp32-factory.bin.sha256` — the checksum sidecar

These are **git-ignored build outputs** — never committed. The page references `./manifest.json`, so
those two files (`manifest.json` + `sprout-esp32-factory.bin`) must sit **next to `index.html`** when
the page is served — either copied there at publish time, or pointed at their release-asset URLs.

## Test it locally

Web Serial needs HTTPS **or** `localhost`, so a local server is enough (no board needed to check the
page renders; a board is needed to actually flash):

```sh
# from the repo root, after a firmware build:
cp firmware/.pio/build/esp32dev/manifest.json firmware/.pio/build/esp32dev/sprout-esp32-factory.bin docs/flash/
just preview docs/flash/index.html      # serves over http://localhost — Web Serial works there
```

(The two copied artifacts stay git-ignored — `docs/flash/*.bin` / `docs/flash/manifest.json` should be
covered by `.gitignore`; only `index.html` + this README are tracked.)

## Publishing (deferred — needs a maintainer decision)

Making the flasher reachable at a public URL (GitHub Pages, or a release download page) is a
**public-visibility step**, so it's held for the maintainer:

- The repo is currently **private**; a public flasher page means enabling **GitHub Pages** (or an
  equivalent host) and publishing the built `manifest.json` + `.bin` as **release assets**.
- A sensible fast-follow is a small CI job that builds the firmware and attaches those artifacts to a
  release (mind the Actions cost — `pio run` pulls the full platform; cache `~/.platformio`).

Until then, the page is complete and locally testable; the hosting + release-asset wiring is the
remaining step, flagged for the maintainer.
