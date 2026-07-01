# Evidence photos - plants controller bring-up

Visual evidence captured during bring-up of the **plants** ESP32 auto-watering controller, organized by
subject. Cross-referenced from [`../../SENSOR_QA.md`](../../SENSOR_QA.md), [`../WIRING.md`](../WIRING.md),
and [`../BRINGUP.md`](../BRINGUP.md).

> The short `.mov` clips that iOS auto-attached to some stills have been removed; only the JPEG/PNG
> stills are kept here.

## board_photos/ - NodeMCU-32S dev board (ESP-32D / WROOM-32 class)

| File | What it shows | Key readable text |
| --- | --- | --- |
| IMG_0538.JPEG | Top (component) side, full board, vertical. | Module "ESP..." + "CE"; "I00" by a button (rest reflective). |
| IMG_0539.JPEG | Top side, light catching the shield for a readable module label. | "ESP-32D WIFI+BT+BLE MCU"; "FCC ID:2AS4N-ESP32"; "ISM2.4G 802.11b/g/n". |
| IMG_0539_enhanced.JPEG | High-contrast B/W enhancement of IMG_0539 (clearest module-label shot). | Same module text as IMG_0539, plus a QR code. |
| IMG_0540.JPEG | Close-up of the USB-serial area (USB-UART bridge, regulator, EN button). | "SILABs CP2102"; regulator "1117 33" (AMS1117-3.3); "J3", "EN". |
| IMG_0541.JPEG | Angled close-up of the ESP32 module + a tantalum cap. | "ESP-32D ... 802.11b/g/n"; cap "5161". |
| IMG_0542.JPEG | Bottom (silkscreen) side, full board - BOTH pin-label rows legible. | "NODEMCU ESP-32S V1.1"; full pin map (rows below). |
| IMG_0543.JPEG | Bottom side, alternate framing; pin labels legible. | Same two label rows as IMG_0542. |
| IMG_0544.JPEG | Bottom side, landscape, one header row in sharp focus. | CLK SD0 SD1 P15 P2 P0 P4 P16 P17 P5 P18 P19 GND P21 RX TX P22 P23 GND. |
| IMG_0545.JPEG | Bottom side, landscape, the opposite header row. | 3V3 EN SVP SVN P34 P35 P32 P33 P25 P26 P27 P14 P12 GND P13 SD2 SD3 [GND] 5V - the `[GND]` nearest 5V is silk-labeled GND but measures +3.3 V (mislabeled; see WIRING.md). |

**Pinout takeaway (sensor edge):** `3V3` and `SVP` (GPIO36) sit at one corner of one long edge; `5V` is the
*opposite* corner of that same edge. Keep sensor power on `3V3`, never `5V`. **WARNING: the pad silk-labeled
`GND` next to `5V` is mislabeled - it measures +3.3 V, not ground (bench-verified at Rung 3). Use the
mid-edge `GND` instead.**

## sensor_photos/ - capacitive soil-moisture sensors

> **Two variants were photographed.** The project's QA-passed units are **V2.0.0 / TLC555** - their
> connector silkscreen misprints the signal pad as **`AUOT`** (a typo for `AOUT`). A second, older
> **v1.2** board with a different timer and a `D1` diode is also pictured; its connector correctly reads
> **`AOUT`**. The build uses **4x V2.0.0** units; the single v1.2 is an **unused spare** - defect-checked
> but set aside (it doesn't match the V2.0.0 boards, and the relay is only 4-channel).

| File | What it shows | Key readable text |
| --- | --- | --- |
| IMG_0526.JPEG | Macro of the 8-pin timer IC (V2.0.0 board). | "TLC555 / 2542K / XBLW". |
| IMG_0527.JPEG | Macro of the U2 regulator (V2.0.0), slightly blurry. | "U2"; regulator "662K". |
| IMG_0528.JPEG | Electronics-end close-up (V2.0.0): connector + timer + resistors. | Connector "GND VCC AUOT"; "TLC555"; R1-R4; "20240201". |
| IMG_0529.JPEG | Full probe, front silkscreen (V2.0.0). | "Capacitive Soil Moisture Sensor V2.0.0"; "HW-390"; "20240201". |
| IMG_0530.JPEG | Macro of the connector + R2/R3/R4 cluster (V2.0.0). | Connector "GND VCC AUOT"; R3/R4 "LEE"/"S0L"; R2 "162"; "20240201". |
| IMG_0534.JPEG | Macro of the R2/R3/R4 + timer cluster (V2.0.0). | R3 R4 R2; "LEE"/"S0L"/"162"; "20240201". |
| IMG_0535.JPEG | Electronics-end close-up of the **v1.2** variant (U1 timer + D1 diode). | Connector "GND VCC AOUT"; "U1", "D1", R1 "E0L", R2 "222". |
| IMG_0536.JPEG | Fuller electronics view of the v1.2 variant. | "GND VCC AOUT"; U1/U2, C1-C6, R1-R4, "222". |
| IMG_0537.JPEG | Macro of the v1.2 electronics: NE555 timer (U1) + D1 diode, R1, C1/C2 (not a full-probe silkscreen). | "NE555 55A~"; "D1"; R1 "E0L"; "C1"/"C2". |

## relay_photos/ - CW-022 4-channel relay board

| File | What it shows | Key readable text |
| --- | --- | --- |
| IMG_0531.JPEG | Top side, full board: 4 relays, 4 screw terminals, opto-isolators, control header. | "SONGLE SRD-05VDC-SL-C"; "10A 250VAC ..."; "4 Relay Module". |
| IMG_0532.JPEG | Angled view of the control-header end + power-select jumper. | Header "GND IN1 IN2 IN3 IN4 VCC"; "JD-VCC"; relay ratings. |
| IMG_0533.JPEG | Reverse/bottom angle showing the PCB model silkscreen. | Model "CW-022"; "GND IN1..IN4 VCC"; "SONGLE SRD-05VDC-SL-C". |

## driver_photos/ - Silicon Labs CP210x driver (Windows Device Manager, 2026-06-21)

All seven are the CP210x Properties dialog on host `MICRODEV`, device "Silicon Labs CP210x USB to UART
Bridge (COM6)".

| File | Device Manager view | Key readable text |
| --- | --- | --- |
| Screenshot 2026-06-21 123241.png | Device tree + Driver tab. | Driver v11.5.0.417, date 12/10/2025, signed "Microsoft Windows Hardware Compatibility Publisher". |
| Screenshot 2026-06-21 123445.png | General tab. | "Ports (COM & LPT)"; Manufacturer "Silicon Labs"; "This device is working properly." |
| Screenshot 2026-06-21 123448.png | Port Settings tab. | 9600 / 8 / None / 1 / None (driver defaults; the serial monitor overrides to 115200). |
| Screenshot 2026-06-21 123452.png | Driver tab (full). | Provider "Silicon Laboratories Inc."; date 12/10/2025; v11.5.0.417. |
| Screenshot 2026-06-21 123456.png | Details tab (Device description). | "Silicon Labs CP210x USB to UART Bridge". |
| Screenshot 2026-06-21 123459.png | Events tab. | "Driver service added (silabser)"; "USB\VID_10C4&PID_EA60". |
| Screenshot 2026-06-21 123502.png | Power Management tab. | "Allow the computer to turn off this device to save power" (checked). |
