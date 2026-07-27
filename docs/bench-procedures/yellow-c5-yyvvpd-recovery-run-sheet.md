# Yellow C5 (`yyvvpd`) recovery + spare-MCU inventory run sheet

**One execution-ordered sheet for the maintainer's bench slot** — recover the designated hot-spare
C5 (`yyvvpd`, down since install day) and inventory the spare MCUs. The recovery *mechanics* live in
the [C5/S3 flash-recovery guide](c5-s3-flash-recovery.md); this sheet is the `yyvvpd`-specific
sequence + the inventory step, so no doc-hopping mid-session.

Refs #680 · [c5-s3-flash-recovery.md](c5-s3-flash-recovery.md) (the mechanics) · #443 (C5 bring-up)

> **The failure was electrical/USB, not thermal** (maintainer confirmed normal temps under normal
> firmware). Known `yyvvpd` signature: a flaky **CH340** port, a **`rst:0x15`** USB reset loop, a
> **benign `MSPI Timing`** PSRAM boot note, and no-WiFi-on-brick. **The board boots healthy in the
> ROM log** — it is parked, not dead. Non-urgent; it is a spare.

---

## §0 Pre-flight

- [ ] The **Treedix** cable tester + a **known-good USB-C data cable** — rule the cable out first
      (`yyvvpd`'s original symptom was a flaky port; a bad cable mimics a dead board). See the USB
      cable-test bench note if the port won't enumerate.
- [ ] `pio device list` — note which COM port(s) appear when `yyvvpd` is plugged in. Two C5 USB-C
      ports exist (USB-Serial/JTAG + UART/CH340); try both.
- [ ] Confirm the pinned toolchain is intact: **`pioarduino/platform-espressif32#55.03.39`** (the
      mid-session PlatformIO reload must not have drifted it — [pio dual-install note] if builds wedge).

## §1 Recover — clean re-flash in download mode

The C5's `--after` trap parks it in download mode looking dead; enter/exit deliberately (guide §)
rather than declaring it bricked.

- [ ] **Enter download mode:** hold **BOOT** (`GPIO28`), tap **EN**/reset, release BOOT (`GPIO27`
      must be high). See [c5-s3-flash-recovery.md](c5-s3-flash-recovery.md) §.
- [ ] **Confirm the chip answers:** `esptool --port <COMx> flash_id` → records `flash_id`, proving
      USB + chip are alive (this is the "healthy ROM log" made concrete).
- [ ] **Flash the image** with **C5 defaults, not S3 assumptions** — bootloader offset **`0x2000`**,
      `dio` / 2 MB / 40 m, baud **cannot** be changed (guide §0). Flash the current release image via
      `pio run -e esp32c5 -t upload --upload-port <COMx>`.
- [ ] **Exit download mode** (`--after watchdog-reset`, or power-cycle) — confirm it leaves download
      mode into SPI boot and prints the normal boot banner (not the `rst:0x15` loop).
- [ ] **Verify the toolchain built clean** on the pinned tag (the #680 AC) — note it in the evidence.

## §2 Re-onboard + register

- [ ] **WiFi re-onboard:** provision credentials (`!wifi`), confirm association + a telemetry sweep
      emits (the "healthy boot" that arms D3 + marks the image valid).
- [ ] **Confirm identity:** the banner's `device_id` should still be `yyvvpd` (the minted nonce
      survives a reflash — it is NVS, not the image). If it re-minted, note it (a wiped NVS).
- [ ] **Register** the board back into the fleet registry per the bench-evidence convention, tagged
      as the **hot spare**.

## §3 Spare-MCU inventory

- [ ] Lay out the spare MCUs; for each record: **board class** (classic/S3/C5), USB bridge, a
      `flash_id` probe, and physical condition. Photograph the set.
- [ ] Note which are **flash-ready spares** vs. which need their own recovery, so the fleet has a
      known good-spare count going into the v0.9.0 Water wave.
- [ ] Fold the inventory into `docs/hardware/BOARDS.md` (or the fleet register) and link on **#680**.

## §4 Evidence

- [ ] Capture the `flash_id` probe, the successful flash log, and the post-recovery boot banner into
      `docs/evidence/<date>-yyvvpd-recovery/` and link on **#680**.

**Gate outcome:** `yyvvpd` boots the current image, re-onboards WiFi, and re-registers as the hot
spare; the spare-MCU count is recorded. The fleet has a known-good spare for the Water wave.
