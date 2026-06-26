# Sprout launcher — double-click to start

The no-terminal way to run Sprout. One double-click → the dashboard opens in your browser at the fixed
port. Stop it from the dashboard's **Stop server** button (you can also just close the window).

## Use it

**Once** — create the desktop shortcut:

```text
pwsh tools\launch\Install-SproutShortcut.ps1
```

Then double-click **Sprout** on your Desktop. That's it — no commands, no port to remember.

(You can also double-click [`sprout.cmd`](sprout.cmd) directly, or run `just start` from a terminal.)

## What it does

`sprout.cmd` runs `just start` → `serve.py --open` → opens your browser at the fixed port
(ADR-0005 §5). If `just` isn't installed it falls back to `python tools\analytics\serve.py --open`, so it
works either way. Every path is relative — nothing hardcodes a user path or the port literal.

## The icon

`sprout.ico` is a faithful export of Sprout's living mark (the **thriving** state) from
[`docs/design/components/sprout-mark.js`](../../docs/design/components/sprout-mark.js) — same paths, same
tokens. Regenerate it from [`sprout-icon.svg`](sprout-icon.svg) with ImageMagick:

```text
magick -background none tools\launch\sprout-icon.svg -define icon:auto-resize=256,64,48,32,16 tools\launch\sprout.ico
```

> **Design lane:** this is a first-cut export. The design system has **no canonical app-icon / favicon**
> yet — and the future Pages site will need one too. A proper `sprout.ico` (and a web `favicon`) is a small
> Design follow-up: drop a `sprout.ico` here and the shortcut installer picks it up automatically.
