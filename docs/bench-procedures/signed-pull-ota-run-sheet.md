# Signed-pull OTA run sheet (#1284 AC5)

**One execution-ordered sheet for the maintainer's bench slot** — prove the signed pull path end to
end on a real board: a genuine update applies, and a **mis-signed or wrong-board image is refused**
with the board left on its running slot. The bindings (AC4) are on `main`; this is their on-device
proof, and it is the gate that unblocks #1340 (retire push) and #271 (web-flasher).

Refs #1284 (AC5) · #302 (the S-wave) · ADR-0026 (D1 pull / D2 sign / D3 rollback / D4
curation) · #1340 · #271 · #1227 (verify from the device, not the transfer)

> **Why this is safe to test over OTA.** Every rejection path lands the candidate image in the
> **inactive** A/B slot and never switches the boot pointer. Even a verify we somehow got wrong is
> caught by **D3 confirmed-boot rollback** (`esp_ota_mark_app_valid`, already live). So the
> wrong-board and mis-signed checks are *two minutes and reversible*, not a bench trip risked on a
> brick — the point made on the #1284 thread.

---

## §0 Provision (one-time, the bench build)

The pull path is **dark by construction** — it exists only when a feed is provisioned at build time
(mirrors the push password, #1333).

- [ ] In the gitignored `firmware/platformio_local.ini`, add the feed URL to `build_flags`:
      `-D OTA_FEED_URL='"https://<pages-host>/ota/feed.txt"'` (the curated Pages feed, #1258).
- [ ] Flash a board with an **older** version so the feed can offer it something newer:
      `pio run -e esp32dev -t upload`.
- [ ] Confirm the boot banner says **`# OTA: signed-pull ARMED (feed provisioned)`** and note the
      running `git=`/`fw=` from the banner. A public build prints `signed-pull OFF` — that is the
      wrong build for this sheet.
- [ ] Board on WiFi (`!wifi` provisioned), reachable, serial monitor open @ 19200.

## §1 Happy path — a genuine update applies (D1 + D2)

- [ ] Serve a feed offering **this board** a **newer** signed image + its `.sig` — for example:

```text
# sprout-ota-feed v1
board=esp32-classic version=<newer> image=https://.../sprout-esp32-factory.bin sig=https://.../...bin.sig
```

- [ ] Send **`!otapull`**. Expect `# otapull updated` then `# otapull: verified image staged -
      rebooting to it`, and the board reboots on its own.
- [ ] **Verify from the DEVICE, not the transfer (#1227):** after reboot, read the boot banner's
      **`git=`/`fw=`** — it must show the **new** version. A 200-OK download is not proof; the echo is.
- [ ] Confirm D3: the banner (or the OTA line) shows the running image was **marked valid** on a
      healthy boot — the rollback safety is armed for next time.

## §2 Mis-signed refusal — the fence holds (D2)

- [ ] Serve a feed pointing at an image whose `.sig` is **tampered/wrong** (flip a byte in the sig,
      or point `sig=` at a different image's signature).
- [ ] Send `!otapull`. Expect **`# otapull rejected`**.
- [ ] **Verify the board did NOT switch:** the banner still shows the **old** `git=`. The candidate
      landed in the inactive slot and was never booted (`ota_gate` returned a non-ACCEPT verdict, so
      `esp_ota_set_boot_partition` was never called).

## §3 Wrong-board refusal — the chip-binding check (D2, the board-swap variant)

The feed is unsigned; the signature covers the image bytes, not the `(board → image)` binding. Point
a board's line at **another chip's** genuinely-signed image and confirm it is still refused.

- [ ] Serve a feed where `board=esp32-classic` points at the **C5's** signed image
      (`sprout-esp32c5-factory.bin` + its real `.sig`).
- [ ] On the **classic**, send `!otapull`. The image is genuinely signed by us but wrong for the
      hardware. Expect a rejection (`rejected` / the gate refuses), board stays on the classic image.
- [ ] Confirm the classic did **not** boot a C5 image — banner still classic `git=`, no boot-loop.
      (If it ever did land, D3 rolls it back on the failed confirm-boot.)

## §4 Downgrade / curation — D4's remediation actually works

D4 declined anti-rollback; the remediation for a bad release is **pull it from the feed, serve the
fixed (possibly older) one.** That only works if a device applies an *older* signed image.

- [ ] With the board now on the newer version (from §1), serve a feed offering an **older** signed
      version (the one it started on).
- [ ] Send `!otapull`. Expect **`# otapull updated`** — the rule is **different-not-newer**, so a
      curated downgrade applies. After reboot the banner `git=` shows the older version.
- [ ] This proves the ADR-0026 D4 curation path end to end: a newer-only check would have refused
      this and stranded every device on a bad release.

## §5 Up-to-date + no-artifact (the quiet paths)

- [ ] Feed offers the board its **current** version → `!otapull` → `# otapull up-to-date`, no reboot.
- [ ] Feed lists **only other** board classes → `# otapull no-artifact`, no reboot.
- [ ] Feed URL unreachable (kill WiFi or point at a dead host) → `# otapull feed-unavailable` — the
      board stays put; a network blip is NOT read as "the feed offers nothing" (#1227 seam).

## §6 Evidence + unblocks

- [ ] Capture the serial log of each §1–§5 sequence (the `!otapull` verdict + the post-reboot banner
      `git=`) into `docs/evidence/<date>-signed-pull-ota/` and link on **#1284**.
- [ ] **On §1–§3 passing, #1284 AC5 is met** → **#1340** (retire the push receiver) and **#271**
      (web-flasher) unblock; their unblock wording already names this proof.

**Gate outcome:** the happy path applies from the device's own echo, and both the mis-signed and
wrong-board images are refused with the running slot intact. That is the whole signed-pull promise —
the feed is a pointer, the signature is the authority, and the boot slot moves only for our bytes on
this chip.
