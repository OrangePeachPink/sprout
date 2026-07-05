# Wave-1 go-live — 8 plants live in soil — 2026-07-04
<!-- cspell:words drydown dracaena anthurium bromeliad pothos succulent cachepot cactus marginata -->
<!-- cspell:words eFuseCal RFC nonce brownout esptool untethered rootball prewire deasserted -->
<!-- cspell:words yyvvpd instrumentable MSPI RSSI rootbound terracotta wicks -->

**Wave-1 is live.** Eight instrumented windowsill plants captured live in soil over WiFi, across two proven
ESP32 boards. This packet is the install-day / go-live record and the session "save": the fleet, the install
map, the live readings, the config decisions, the hardware saga, the prediction cross-check, and the open
items. MAC / USB IDs redacted (identifier-guard #573); RFC1918 IPs are evidence-safe and kept.

Bench arrangement: maintainer = hands (install, power, plants); Firmware lane = brains-on-call (WiFi reads,
verdicts, registry authoring). Boards run **untethered on brick power, served over WiFi**
(served at `/telemetry`, #276 → dashboard #486). No serial at go-live.

## The live fleet (settled)

| Board | `device_id` | IP | Role | Status |
| --- | --- | --- | --- | --- |
| classic | `y9d41p` | 192.168.68.87 | ESP32-D0WD, 4 soil + SHT45 + AS7263, **cal-verified** | live |
| official C5 | `8gtt1h` | 192.168.68.85 | ESP32-C5, 4 soil, **placeholder cal (#443)** | live |
| yellow C5 | `yyvvpd` | (down) | ESP32-C5 KITC-A clone | **deferred — needs recovery** |

Both live boards held their IPs on solid brick power. The yellow was never needed — see config below.

## Install map — 8 instrumented plants

`channels` are keyed by the on-wire `sensor_id` (board **port**); `probe` = the physical sticker seated in it
(ADR-0027 channel≠probe — on the C5, probes s5–s8 sit on ports that emit `s3/s4/s1/s2`).

| Plant | Probe | Board (nonce) | Port | GPIO | Species (confidence) |
| --- | --- | --- | --- | --- | --- |
| p01 | s5 | official C5 (8gtt1h) | s3 | GPIO1 | Pothos, small (genus conf.) |
| p02 | s2 | classic (y9d41p) | s2 | GPIO35 | Pothos, XXL (genus conf.) |
| p03 | s7 | official C5 (8gtt1h) | s4 | GPIO4 | Pothos, XL (genus conf.) |
| p04 | s4 | classic (y9d41p) | s4 | GPIO39 | Dracaena / cane-type (guess) |
| p06 | s3 | classic (y9d41p) | s3 | GPIO36 | Anthurium "Lovable Hearts" (named) |
| p07 | s6 | official C5 (8gtt1h) | s2 | GPIO6 | Bromeliad (described) |
| p10 | s8 | official C5 (8gtt1h) | s1 | GPIO5 | Pothos, office comparator (genus conf.) |
| p11 | s1 | classic (y9d41p) | s1 | GPIO34 | "Miniature corn-plant"-like (described) |

## Live in-soil readings (at go-live)

Classic = cal-verified (bands trustworthy). C5 = provisional cal (#443): reads a *compressed, lower* scale, so
trust relative wetness over absolute band.

| Plant | Board | Raw | Band |
| --- | --- | --- | --- |
| p06 Anthurium | classic | 1462 | well watered |
| p11 corn-plant | classic | 1914 | needs water |
| p04 dracaena? | classic | 2438 | dry |
| p02 Pothos-XXL | classic | 2844 | dry |
| p01 Pothos-sm | C5 | 1586 | OK (moist) |
| p07 Bromeliad? | C5 | 2196 | dry\* |
| p03 Pothos-XL | C5 | 2217 | dry\* |
| p10 Pothos-office | C5 | 2292 | dry\* |

\*C5 provisional. All 8 quality OK, tight spreads (6–37), no floaters — every probe seated and reading honest
in-soil moisture.

## Config — Wave-1 = 8 instrumented + 3 sensorless (ADR-0028)

Eleven windowsill plants; **only eight are honestly probe-able.** The three sensorless are a physical-fit
decision, not a soil-suitability one:

- **p05** — braided *Dracaena marginata*, giant hard rootball (only ~2 probes ever fit; bent a connector last
  time) → rootball too tight to seat a probe without damage.
- **p08** — cactus (moon/grafted), **tiny pot** — no room for a full-time probe.
- **p09** — aloe-like succulent, root-bound **tiny pot**.

Two MCUs × 4 channels = 8 = the entire instrumentable population, **exactly**. The third board was always
headroom (ADR-0028: sensorless plants are first-class "alive, not probed," never degraded). **Current schema
has no dashboard representation for a probe-less plant yet — that is W2 (#20), unbuilt** — so p05/p08/p09 are
documented here and in the plant survey but render no card by design (no probe → no reading).

## Registry

`config/devices.local.json` (gitignored, local) populated with the 8 channel→plant mappings. Validated
end-to-end: `device_registry.load_registry()` + `plant_for(device, sensor_id)` resolve all 8, `all_plants()`
returns 8. Dashboard attributes every channel (no "unassigned" stragglers). Yellow's channels left empty.

## Hardware saga (the honest record)

- **Power was the recurring gremlin.** Both live boards initially wouldn't hold WiFi at the windowsill —
  *marginal phone-brick + cable combos* browned out the radio on transmit (LED looked solid, but WiFi never
  joined). **Fix: a solid brick + good cable** (an Apple 20 W / 3 A charge-only combo). Lesson banked: for
  untethered boards, treat power quality as first-class.
- **DHCP churn:** boards can grab new IPs on power-cycle. Both held (.87/.85) at go-live, but the registry
  `base_url`s may need updating if they move — a DHCP reservation per board would make the fleet solid.
- **Yellow C5 (`yyvvpd`) — deferred.** Multiple distinct failures: flaky CH340 port (wouldn't enumerate),
  native-USB **reset loop** (`rst:0x15 USB_UART`, host-driven), a PSRAM `MSPI Timing` boot error, and no WiFi
  on brick. Board boots healthy in the ROM log — the trouble is USB/connection. **Recovery (non-urgent
  headroom):** clean re-flash in download mode + WiFi re-onboard. Zero launch pressure (Wave-1 = 8, complete).

## Prediction cross-check (data-driven hypothesis, scored live)

Workflow published a drydown extrapolation for tonight's values; the live actuals **scored it 7-of-8**:

- **Confirmed:** the water-tonight anchors (p02/p03/p10 all dry) and the holds (p07 cachepot, p01 moist).
- **Live override:** **p06 Anthurium reads well-watered (1462), not dry** — the drought-stressed plant is
  finally retaining. Prediction said "water"; the probe says **hold.** (Clean reading, not a fault.)
- **Vindication:** **p11** — Data caught a *faulty 07-01 s3* channel (median ~420, below the physical wet rail)
  that had falsely made p11 look "submerged." The live probe reads **1914 / needs-water**, independently
  confirming Data's exclusion and the corrected "normally-watered, now drying" model. This incident is the
  basis for the sensor-fault flag enhancement (**#673**).

Watering verdict (prediction + live): **water p02/p03/p10**, light **p04/p11**, **HOLD p06** + the rest.
(Operator's call; care-rules override a dry sensor for cactus/succulent/marginata.)

## Honest scope

- C5 bands are **provisional** (#443 — the C5's ADC is uncalibrated; only the classic is cal-verified).
- The 3 sensorless plants have **no dashboard card yet** (ADR-0028 W2 / #20, unbuilt).
- The yellow C5 is **down** (deferred recovery).
- Watering predictions are **inference from bench evidence**, not calibration-ratified.

## Power topology & placement

Windowsill right-side outlet (US 110 V, grounded) → ungrounded 2-plug extension to the center-back ledge.
Both boards on **brick power only, no PC USB**:

| MCU | Brick | Cable | Note |
| --- | --- | --- | --- |
| classic (y9d41p) | **Apple 20 W / 3 A** | charge-only | the fix — a marginal phone brick browned out WiFi on TX |
| official C5 (8gtt1h) | **Samsung 5 V / 1.55 A** | USB-A → C | confirmed |
| yellow C5 | (unplugged) | — | shelved spare |

**Insertion-depth rule used:** seat each probe so the **lower ~50% of the blade** is in the root-zone soil —
that's the measuring element (#660 depth sweep). Burying only the tip wastes the sensitive half.

**Placement:** the two boards split the sill — **classic serves the LEFT ledge, official C5 the RIGHT.**

- **Left ledge:** p02, p04, p06, p11 (classic) + **p08 cactus** (sensorless)
- **Right ledge:** p01, p03, p07, p10 (official C5) + **p09 succulent** + **p05 braided Dracaena** (sensorless)

## Pot & soil observations (per plant)

Pot Ø = top-edge diameter, tape-measured across the centerline past the plant (approximate).

| Plant | Ledge | Pot Ø | Soil / root notes |
| --- | --- | --- | --- |
| p01 | R | 6" | home; drought-cycled soil (poor wicking) |
| p02 | L | 10" | largest; home; drought-cycled |
| p03 | R | 9" | home; drought-cycled |
| p04 | L | 8" (shallow, wide) | 2 of 3 original plants died → ~⅔ pot is defunct rootballs (no support); ~1" decorative moss top (minimal aid). **Behaves like a much smaller pot.** |
| p05 | R | 6" | *sensorless* — braided *Dracaena marginata*, hard rootbound; roots grown into the inner/outer-pot gap and sip from water pooled there over the week |
| p06 | L | 5" | Anthurium; drought-stressed but now retaining (live = well-watered) |
| p07 | R | 4.5" | rootbound; **tight watertight outer pot** → water pours into the inner/outer gap and stagnates; **no visible topsoil** (all leaves), no evaporation channel → chronically waterlogged (drainage-first, per Sage) |
| p08 | L | 2" | *sensorless* — cactus; low soil (~50–60% depth), minimal roots, spills on any bump |
| p09 | R | 2" | *sensorless* — succulent; nearly all roots, almost no soil |
| p10 | R | 6" | **terracotta + built-in drip tray** (resoaks within 20–30 min of watering); office plant, 4 yr × ~1 cup/week → **clumpiest / moistest soil, best probe contact of the fleet** |
| p11 | L | 6" | office corn-plant-like; top-core reservoir holds ~⅛ cup |

**Fleet soil context:** the home plants (p01–p09 except p07) have been through repeated **over-dry / drought
cycles**, so their soil no longer diffuses or wicks well across the pot — a real driver of the within-pot
heterogeneity the survey saw. Quarterly **kitchen-sink soak + leaf-rinse** is the maintainer's rejuvenation
routine (home plants). p07 stays waterlogged even after a 3-week skip; p10 (office-cared) is the retention
outlier — its consistent care shows in the soil.

## Board disposition

| Board | `device_id` | Disposition | Why |
| --- | --- | --- | --- |
| classic | y9d41p | **DEPLOYED** | cal-verified, 4 plants + env (SHT45 / AS7263) |
| official C5 | 8gtt1h | **DEPLOYED** | 4 plants; placeholder cal (#443) |
| yellow C5 | yyvvpd | **SHELVED — hot spare** | minted + clean-boot verified (#637); soil continuity **not** completed (blocked today by a flaky CH340 port, a `rst:0x15` USB reset loop, and no-WiFi-on-brick). Needs a clean re-flash + WiFi re-onboard before redeploy. Drop-in third when a reason appears. |
| S3 | (esp32s3) | **AWAITING SOLDER** | header pins not soldered; never a Wave-1 candidate |

**Yellow thermal note:** under normal firmware operation (connected + probed from the PC), the yellow ran at
**normal temps — no thermal issue observed** (maintainer, live). The session's trouble was purely the USB
power / `rst:0x15` reset loop, **not thermal**; the ROM boot log showed a benign `MSPI Timing` PSRAM error
(app boots past it) and no brownout. So the shelved spare carries **no known thermal concern** — a formal
`die_temp` characterization can wait for the recovery pass.

## Known-conditions register (per probe)

| Probe | Stress history | Corrosion (#657) | Cal note |
| --- | --- | --- | --- |
| s1 | water-contaminated (recovered) | minimal (deployed) | — |
| s2 | reverse-polarity (recovered) | **notable** (deployed) | **C1 wet-bias** — gain+offset (calibration.h) |
| s3 | dry-down reference probe | minor (deployed) | — |
| s4 | — | minimal (deployed) | — |
| s5–s12 | new units | **pristine** (never deployed) | provisional per-channel only |

All four deployed probes (s1–s4) show onboard-connector corrosion by degree → **#657 waterproofing before the
pumps (#94)**. New units (s5–s12) are clean.

## Wedge safety check (#599) — NOT run this session

Honest gap: the ~30-second `!wedge` watchdog / fail-safe confirmation was **not run** this session (boards went
straight to untethered brick + WiFi; no serial at go-live). The classic's D1 wedge passed on a *prior* session
(fleet capstone), but there is **no new wedge confirmation** for this install — **#599 stays open.**

## Open items (the save — what's next)

| Item | Ref | Notes |
| --- | --- | --- |
| Official C5 continuity packet | **PR #667** | green, awaiting cert gate |
| Yellow C5 recovery | — | re-flash (download mode) + re-onboard; non-urgent headroom |
| C5 ADC calibration | **#443** | bands provisional until done |
| Per-probe calibration | **#621** | cal that travels with the probe |
| Sensor-fault quality flag | **#673** | filed this session (firmware + parse-boundary) |
| Sensorless plant dashboard | **#20** | ADR-0028 W2 — render p05/p08/p09 honestly |
| WiFi RSSI in telemetry | *(unfiled)* | low-priority diagnostic for install-spot decisions |
| Waterproofing before pumps | **#657** | pre-#94 corrosion mitigation |
| DHCP reservations for fleet | *(unfiled)* | stabilize board IPs so the registry doesn't drift |

## Session provenance

Firmware bench + install session, 2026-07-04 (install day / Wave-1 go-live). Live values are WiFi-observed
(`/telemetry`) at capture time on brick-powered, untethered boards; raw streams and any photos in the
maintainer's local archive.

Refs: #584 · #660 · #667 · #443 · #621 · #673 · #657 · #20 · #631 · #276 · #486 · ADR-0027 · ADR-0028.

— Firmware 🔧
