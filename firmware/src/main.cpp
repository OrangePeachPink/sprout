/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * RUNG 4 / schema v1 (read-only) - FOUR soil sensors. Every READ_INTERVAL_MS it
 * sweeps all NUM_SENSORS channels one at a time (ADC-settle discards on each
 * switch), runs each through its own moisture_classifier instance, and emits one
 * compact CSV row per sensor on the wire (machine-first). The host logger adds
 * the UTC/sequence columns, writes the rotating CSV file, and renders a pretty
 * console - the B2 split (see docs/TELEMETRY_SCHEMA.md).
 *
 * Device CSV columns (host prepends timestamp_utc,timestamp_local,sample_id,logger_version):
 *   record_type,session_id,device_id,fw,millis_ms,sensor_model,sensor_id,
 *   sensor_position,channel,raw_value,value,unit,quality_flag,payload
 * (value/unit are emitted NULL - raw_value + band are authoritative, #38.)
 * A '#'-prefixed provenance header is emitted at boot and reprinted periodically.
 * Relays are defined and driven to their fail-safe OFF state at boot, with a task
 * watchdog that resets a hung loop (the #93 safety scaffold). Actuation is the manual,
 * bounded, single-channel `!water,<ch>[,<ms>]` pulse only (#215): default OFF, a hard
 * max-on ceiling, one pump at a time, and the probe sweep is suppressed while it runs.
 * NO autonomous dosing yet (that is epic #94). Inbound commands (all `!name[,args]*HH`,
 * checksum-gated): !cad (cadence), !water / !stop (manual pulse), !ping, !ver, !cfg,
 * !name.
 */

#include <Arduino.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <esp_task_wdt.h>
#include <Preferences.h>
#include <string.h>
#include "config.h"
#include "moisture_classifier.h"
#include "serial_cmd.h"
#include "pump_pulse.h"

#ifndef GIT_REV
#define GIT_REV "nogit"  // overridden by scripts/git_rev.py at build (commit hash + dirty)
#endif

// Per-boot identity (#188): a human-readable name, never a hardware fingerprint. No MAC,
// eFuse, or chip serial is ever read - privacy by construction (ADR-0015). device_id is
// the pretty chip-model default (set in configLoad) or an operator's custom name persisted
// in NVS (#90); session_id is a fresh per-boot RNG nonce (not a hardware id).
static char g_device_id[32]    = "Sprout ESP32";  // replaced in setup(): NVS custom or derived default
static bool g_device_id_custom = false;           // header provenance: custom name vs derived default
static char g_session_id[12]   = "000000";

// Sweep cadence (ms). Runtime-settable via !cad (ADR-0011 / #63) and now persisted to
// NVS (#90): a reboot restores the last set cadence (validated against the floor/ceil
// on load; an empty/corrupt store falls back to READ_INTERVAL_MS). The loop gate and
// the header read this, not the compile-time constant.
static unsigned long g_cadence_ms = READ_INTERVAL_MS;
static bool          g_cadence_from_nvs = false;  // header provenance: loaded from NVS?

// Persisted runtime config store (#90). Opened once for the session: read on boot,
// written on a successful !cad, cleared by !cfg,reset.
static Preferences g_prefs;
static const char *CFG_NS = "plants";

// Manual bounded pump-pulse actuator (#215): operator-commanded, single-channel,
// bounded !water pulses. NOT autonomous dosing - see pump_pulse.h / epic #94.
static pump_pulse_t g_pump;

// Shared classifier tuning - same boundaries for all channels for now. The module
// takes a cfg per call, so this becomes a per-channel array when per-probe
// calibration lands (BACKLOG C1).
static moisture_cfg_t cfg = {
  SAMPLES_PER_READ,                                  // sample_count
  SAMPLES_TRIM,                                      // trim_each_side
  60,                                                // deadband_raw
  3000,                                              // confirm_ms_soil (TESTING; prod 8000)
  3000,                                              // confirm_ms_dry  (TESTING; prod 8000)
  2000,                                              // confirm_ms_wet  (TESTING; prod 3500)
  READ_INTERVAL_MS,                                  // loop_period_ms
  250,                                               // spread_warn_raw (0 disables)
  // boundary (descending raw): 7-band scheme, reconciled 2026-06-25 (issue #3)
  // against the 2026-06-21 anchors (docs/SENSOR_CALIBRATION.md):
  //   [0] air-dry|DRY 3050 - air ~3180 vs bone-dry soil ~2440-2920, so a parched
  //       pot now WATERS instead of misreading "out of soil" (the fail-to-water fix).
  //   [4] ww|over 1150, [5] over|sub 1050 - field capacity ~1140-1435 reads
  //       well-watered; saturated soil / standing water (~970-1065) fire the
  //       "too wet / check probe" diagnostic. The wet split is below the ~60-count
  //       noise floor (saturated soil == standing water to a capacitive probe), so
  //       treat anything < ~1150 as ONE "too wet" condition. [1..3] interpolated.
  {3050, 2140, 1830, 1520, 1150, 1050},
};

static moisture_state_t state[NUM_SENSORS];

// NMEA-style XOR checksum over the row body (B6.4) so the host can
// deterministically detect and drop a byte-corrupted line - not just a
// prefix-garbled one - which matters when the data feeds calibration.
static uint8_t lineChecksum(const char *s) {
  uint8_t c = 0;
  while (*s) c ^= (uint8_t)*s++;
  return c;
}

// Map classifier health -> the shared quality_flag enum (docs/TELEMETRY_SCHEMA.md S4).
static const char *qualityFlag(const moisture_state_t *st) {
  uint16_t raw = st->last_raw;
  if (raw >= 4090 || raw <= 5) return "SATURATED";  // ADC railed
  if (st->last_spread >= 2000) return "NO_SIGNAL";  // floating / disconnected probe
  if (st->health_warn)         return "SUSPECT";    // noisy / poor contact
  return "OK";
}

// '#'-prefixed provenance block. The host folds this into the file header and
// shows a terse version on the console; a raw monitor reads it directly.
static void printHeader() {
  char buf[200];
  int n;
  Serial.println();
  Serial.println("# plants telemetry  schema_version=1  contract=docs/TELEMETRY_SCHEMA.md@v1");
  snprintf(buf, sizeof(buf), "# fw=%s  git=%s  built=%s  run=%s",
           PLANTS_FW_VERSION, GIT_REV, __DATE__ " " __TIME__, RUN_LABEL);
  Serial.println(buf);
  snprintf(buf, sizeof(buf), "# device_id=%s (%s)  chip=%s  adc=ADC1,12bit,11dB,eFuseCal=off",
           g_device_id, g_device_id_custom ? "custom" : "default", ESP.getChipModel());
  Serial.println(buf);
  snprintf(buf, sizeof(buf), "# session_id=%s  cadence_ms=%lu (%s)",
           g_session_id, g_cadence_ms, g_cadence_from_nvs ? "nvs" : "default");
  Serial.println(buf);
  n = snprintf(buf, sizeof(buf), "# sensors:");
  for (int i = 0; i < NUM_SENSORS && n < (int)sizeof(buf); i++)
    n += snprintf(buf + n, sizeof(buf) - n, " ch%d=GPIO%d/%s", i, SENSOR_PINS[i], SENSOR_NAMES[i]);
  if (n < (int)sizeof(buf))
    snprintf(buf + n, sizeof(buf) - n, "  (model=%s pos=%s)", SENSOR_MODEL, SENSOR_POSITION);
  Serial.println(buf);
  n = snprintf(buf, sizeof(buf), "# cal bounds(dry>wet):");
  for (int i = 0; i < MOISTURE_BOUNDARY_COUNT && n < (int)sizeof(buf); i++)
    n += snprintf(buf + n, sizeof(buf) - n, " %u", (unsigned)cfg.boundary[i]);
  Serial.println(buf);
  snprintf(buf, sizeof(buf),
           "# cfg: smp=%u trim=%u db=%u confirm_ms=%lu/%lu/%lu spr=%u discard=%u",
           (unsigned)cfg.sample_count, (unsigned)cfg.trim_each_side, (unsigned)cfg.deadband_raw,
           (unsigned long)cfg.confirm_ms_soil, (unsigned long)cfg.confirm_ms_dry,
           (unsigned long)cfg.confirm_ms_wet, (unsigned)cfg.spread_warn_raw, (unsigned)ADC_DISCARD);
  Serial.println(buf);
  snprintf(buf, sizeof(buf),
           "# safety: actuators fail-safe OFF (4ch CW-022 active-low, off=HIGH)  task-wdt=%lums  "
           "pump=manual(!water) bounded<=%lums",
           (unsigned long)WDT_TIMEOUT_MS, (unsigned long)PUMP_PULSE_MAX_MS);
  Serial.println(buf);
  Serial.println("# device_cols: record_type,session_id,device_id,fw,millis_ms,sensor_model,"
                 "sensor_id,sensor_position,channel,raw_value,value,unit,quality_flag,payload");
  Serial.println("# authoritative: raw_value (ADC counts) + band (payload 'level'); value/unit are "
                 "NULL - reserved for a future calibrated VWC, never an uncalibrated %.");
}

// Sample one channel into buf: select the pin, discard a few for the mux/S&H to
// settle, then fill the burst. (One channel at a time - never concurrent.)
static void sampleChannel(int ch, uint16_t *buf) {
  int pin = SENSOR_PINS[ch];
  for (int d = 0; d < ADC_DISCARD; d++) (void)analogRead(pin);
  for (int i = 0; i < SAMPLES_PER_READ; i++) buf[i] = (uint16_t)analogRead(pin);
}

// Fail-safe: drive every relay to its de-energized level. Called FIRST in setup() so
// any reset/boot lands actuators OFF before anything else runs, and reused by the
// irrigation supervisor on every fault/stop once pumps land. No pump exists yet -
// this just guarantees the safe state from the very first instruction (#93).
static void allRelaysOff() {
  for (int ch = 0; ch < NUM_SENSORS; ch++) {
    pinMode(RELAY_PINS[ch], OUTPUT);
    digitalWrite(RELAY_PINS[ch], RELAY_OFF_LEVEL);
  }
}

// Drive ONE channel's relay on/off, honoring the module's active-low polarity (#215).
// The single point that can energize a pump - the pulse path and any future engine
// both route through here.
static void pumpSet(int ch, bool on) {
  if (ch < 0 || ch >= NUM_SENSORS) return;
  digitalWrite(RELAY_PINS[ch], on ? RELAY_ON_LEVEL : RELAY_OFF_LEVEL);
}

// Derive the friendly default device name from the chip *model* only (#188) - e.g.
// "ESP32" from "ESP32-D0WD-V3" -> "Sprout ESP32". The model is a board *type* shared by
// millions of chips ("Honda Civic," not the VIN): no MAC, eFuse, or serial is read.
// Finer distinctions (S3 vs classic, or multiple identical boards) are the custom name's
// job, not this default's - keeping the zero-setup path clean.
static void deriveDefaultDeviceId(char *out, size_t outlen) {
  const char *model = ESP.getChipModel();  // e.g. "ESP32-D0WD-V3", "ESP32-S3"
  char family[16];
  size_t i = 0;
  for (; model[i] && model[i] != '-' && i < sizeof(family) - 1; i++) family[i] = model[i];
  family[i] = '\0';
  if (family[0] == '\0') snprintf(out, outlen, "Sprout MCU");        // defensive fallback
  else                   snprintf(out, outlen, "Sprout %s", family);  // "Sprout ESP32"
}

// Load the persisted runtime config from NVS (#90), validating each value against its
// bounds so a stale/corrupt store can never push the device out of safe range. Also
// resolves the device identity (#188): a persisted custom name wins, else the pretty
// default. Called in setup() before the header is printed.
static void configLoad() {
  g_prefs.begin(CFG_NS, false);                        // rw namespace, kept open for the session
  uint32_t saved = g_prefs.getULong("cadence_ms", 0);  // 0 = "unset" sentinel
  if (saved >= CADENCE_FLOOR_MS && saved <= CADENCE_CEIL_MS) {
    g_cadence_ms = saved;                              // valid persisted cadence
    g_cadence_from_nvs = true;
  }                                                    // else keep the READ_INTERVAL_MS default

  // Device identity (#188): an operator's custom name (persisted) wins; else derive the
  // pretty chip-model default. Never reads a hardware id either way.
  char name[sizeof(g_device_id)];
  size_t n = g_prefs.getString("device_name", name, sizeof(name));
  if (n > 0 && name[0] != '\0') {
    strncpy(g_device_id, name, sizeof(g_device_id) - 1);
    g_device_id[sizeof(g_device_id) - 1] = '\0';
    g_device_id_custom = true;
  } else {
    deriveDefaultDeviceId(g_device_id, sizeof(g_device_id));
  }
}

// Serial-command handlers (defined below, near pollSerialCommand) - forward-declared
// so setup() can register them with the serial_cmd registry (#92).
static void handleCad(const char *args, char *reply, size_t replen);
static void handlePing(const char *args, char *reply, size_t replen);
static void handleVer(const char *args, char *reply, size_t replen);
static void handleCfg(const char *args, char *reply, size_t replen);
static void handleName(const char *args, char *reply, size_t replen);
static void handleWater(const char *args, char *reply, size_t replen);
static void handleStop(const char *args, char *reply, size_t replen);

void setup() {
  allRelaysOff();  // FIRST: actuators de-energized before anything else can run (#93)

  Serial.begin(SERIAL_BAUD);
  delay(200);

  // Per-boot session nonce (#188): a fresh RNG value (not a hardware id) so a reboot is a
  // clean boundary in the data. device_id is resolved by configLoad() below (the persisted
  // custom name or the pretty chip-model default) - no MAC/eFuse/serial is read.
  snprintf(g_session_id, sizeof(g_session_id), "%06x", (unsigned)(esp_random() & 0xFFFFFF));

  Serial.println();
  Serial.print("# boot plants controller fw=");
  Serial.print(PLANTS_FW_VERSION);
  Serial.println(" - Rung 4 schema v1, four soil sensors (manual bounded pump pulse; fail-safe OFF)");

  pinMode(LED_PIN, OUTPUT);

  // Register the inbound serial commands (#92): one registration each; the registry
  // owns re-sync, the *HH checksum, and dispatch.
  serial_cmd_register("cad", handleCad);
  serial_cmd_register("ping", handlePing);
  serial_cmd_register("ver", handleVer);
  serial_cmd_register("cfg", handleCfg);
  serial_cmd_register("name", handleName);
  serial_cmd_register("water", handleWater);  // #215 manual bounded pump pulse
  serial_cmd_register("stop", handleStop);    // #215 abort

  // Prime the manual pump-pulse actuator (#215): bounded, default OFF. Relays are
  // already de-energized (allRelaysOff at the top of setup); this only inits FSM state.
  pump_pulse_init(&g_pump, NUM_SENSORS, PUMP_PULSE_DEFAULT_MS, PUMP_PULSE_MAX_MS);

  // Load any persisted runtime config (#90) so the header + first sweep reflect it.
  configLoad();

  // Seed every channel from one burst so each boots in the right band.
  uint16_t seed[SAMPLES_PER_READ];
  for (int ch = 0; ch < NUM_SENSORS; ch++) {
    sampleChannel(ch, seed);
    uint16_t s0 = moisture_trimmed_mean(seed, SAMPLES_PER_READ, SAMPLES_TRIM, NULL);
    moisture_init(&state[ch], &cfg, s0);
  }
  printHeader();

  // Task watchdog LAST, so setup()'s own work can't trip it; loop() feeds it every
  // iteration. A hung loop now resets the chip - and the reboot re-runs allRelaysOff()
  // - so a fault can never strand a pump on (#93). This platform's Arduino-ESP32 uses
  // the classic esp_task_wdt API (timeout in SECONDS, panic on stall); init is harmless
  // if the framework already started the TWDT, then we subscribe the loop task.
  esp_task_wdt_init(WDT_TIMEOUT_MS / 1000UL, true);
  esp_task_wdt_add(NULL);  // watch this (the Arduino loop) task
}

// --- inbound serial command handlers (#92 registry) -------------------------
// The device is otherwise write-only; this is its one inbound path. Each handler gets
// the comma-args and writes a single '#' reply line; the registry (lib/serial_cmd)
// owns the re-sync, the *HH checksum, and dispatch. No actuation, boundaries, or schema.

// !cad,<ms> - set the sweep cadence at runtime (ADR-0011 / #63). Applied at the next
// sweep boundary (g_cadence_ms is read there), never mid-row.
static void handleCad(const char *args, char *reply, size_t replen) {
  uint32_t ms;
  if (!serial_cmd_parse_u32(args, &ms)) {
    snprintf(reply, replen, "# nak err=parse floor=%lu", (unsigned long)CADENCE_FLOOR_MS);
    return;
  }
  if (ms < CADENCE_FLOOR_MS || ms > CADENCE_CEIL_MS) {
    snprintf(reply, replen, "# nak cad=%lu err=range floor=%lu",
             (unsigned long)ms, (unsigned long)CADENCE_FLOOR_MS);
    return;
  }
  unsigned long prev = g_cadence_ms;
  g_cadence_ms = ms;                     // next sweep uses the new period
  g_prefs.putULong("cadence_ms", ms);    // persist across reboots (#90)
  g_cadence_from_nvs = true;
  snprintf(reply, replen, "# ack cad=%lu prev=%lu floor=%lu",
           (unsigned long)ms, prev, (unsigned long)CADENCE_FLOOR_MS);
}

// !ping - liveness check.
static void handlePing(const char *args, char *reply, size_t replen) {
  (void)args;
  snprintf(reply, replen, "# ack pong");
}

// !ver - identity / provenance (fw + device_id + git rev).
static void handleVer(const char *args, char *reply, size_t replen) {
  (void)args;
  snprintf(reply, replen, "# ack ver fw=%s device_id=%s git=%s",
           PLANTS_FW_VERSION, g_device_id, GIT_REV);
}

// !cfg,reset - clear the persisted config so the next boot uses compile-time defaults,
// and apply the default cadence now (#90). Future !cfg subcommands register alongside.
static void handleCfg(const char *args, char *reply, size_t replen) {
  if (strcmp(args, "reset") == 0) {
    g_prefs.clear();                  // wipe the NVS namespace (cadence + custom name)
    g_cadence_ms = READ_INTERVAL_MS;  // apply the default immediately
    g_cadence_from_nvs = false;
    deriveDefaultDeviceId(g_device_id, sizeof(g_device_id));  // identity back to default (#188)
    g_device_id_custom = false;
    snprintf(reply, replen, "# ack cfg reset cad=%lu device_id=%s",
             (unsigned long)READ_INTERVAL_MS, g_device_id);
  } else {
    snprintf(reply, replen, "# nak err=cfg (use: !cfg,reset)");
  }
}

// !name,<string> - set a friendly custom device name (#188), persisted to NVS (#90) so it
// survives reboots; an empty arg clears it back to the pretty chip-model default. The name
// is sanitized for the CSV telemetry field (commas + control chars -> '_') so it can never
// break a row. Never reads or encodes a hardware id.
static void handleName(const char *args, char *reply, size_t replen) {
  if (args[0] == '\0') {
    g_prefs.remove("device_name");
    deriveDefaultDeviceId(g_device_id, sizeof(g_device_id));
    g_device_id_custom = false;
    snprintf(reply, replen, "# ack name device_id=%s (default)", g_device_id);
    return;
  }
  char   clean[sizeof(g_device_id)];
  size_t j = 0;
  for (size_t i = 0; args[i] && j < sizeof(clean) - 1; i++) {
    char c     = args[i];
    clean[j++] = (c == ',' || c < 0x20 || c == 0x7f) ? '_' : c;  // keep the CSV row intact
  }
  clean[j] = '\0';
  strncpy(g_device_id, clean, sizeof(g_device_id) - 1);
  g_device_id[sizeof(g_device_id) - 1] = '\0';
  g_prefs.putString("device_name", g_device_id);  // persist across reboots
  g_device_id_custom = true;
  snprintf(reply, replen, "# ack name device_id=%s (custom)", g_device_id);
}

// !water,<ch>[,<ms>] - arm ONE bounded manual pump pulse on channel <ch> (#215). With no
// <ms> it uses PUMP_PULSE_DEFAULT_MS; any value is clamped to PUMP_PULSE_MAX_MS (the hard
// ceiling). Rejected if a pulse is already running (one pump at a time) or <ch> is out of
// range. The loop turns the relay OFF when the pulse expires - default OFF, bounded, with
// the #93 watchdog as the independent backstop. NOT autonomous dosing (that is epic #94).
static void handleWater(const char *args, char *reply, size_t replen) {
  // args is "<ch>" or "<ch>,<ms>" - split at the first comma.
  char        chbuf[12];
  uint32_t    ms    = 0;  // 0 -> the pulse module substitutes PUMP_PULSE_DEFAULT_MS
  const char *comma = strchr(args, ',');
  size_t      chlen = comma ? (size_t)(comma - args) : strlen(args);
  if (chlen == 0 || chlen >= sizeof(chbuf)) {
    snprintf(reply, replen, "# nak err=parse (use: !water,<ch>[,<ms>])");
    return;
  }
  memcpy(chbuf, args, chlen);
  chbuf[chlen] = '\0';
  uint32_t ch;
  if (!serial_cmd_parse_u32(chbuf, &ch) ||
      (comma && comma[1] != '\0' && !serial_cmd_parse_u32(comma + 1, &ms))) {
    snprintf(reply, replen, "# nak err=parse (use: !water,<ch>[,<ms>])");
    return;
  }
  switch (pump_pulse_arm(&g_pump, (int)ch, ms, millis())) {
    case PUMP_PULSE_ARMED:
      pumpSet((int)ch, true);  // energize now; the loop turns it off at expiry
      snprintf(reply, replen, "# ack water ch=%lu ms=%lu max=%lu",
               (unsigned long)ch, (unsigned long)pump_pulse_armed_ms(&g_pump),
               (unsigned long)PUMP_PULSE_MAX_MS);
      break;
    case PUMP_PULSE_ERR_BUSY:
      snprintf(reply, replen, "# nak err=busy ch=%d", pump_pulse_channel(&g_pump));
      break;
    case PUMP_PULSE_ERR_CHANNEL:
      snprintf(reply, replen, "# nak err=channel ch=%lu n=%d", (unsigned long)ch, NUM_SENSORS);
      break;
    default:  // PUMP_PULSE_ERR_DURATION
      snprintf(reply, replen, "# nak err=duration");
      break;
  }
}

// !stop - force any active pump pulse OFF now (operator abort / safety, #215).
static void handleStop(const char *args, char *reply, size_t replen) {
  (void)args;
  int  ch  = pump_pulse_channel(&g_pump);
  bool was = pump_pulse_stop(&g_pump);
  if (was && ch >= 0) pumpSet(ch, false);
  allRelaysOff();  // belt-and-suspenders: every channel de-energized regardless
  if (was) snprintf(reply, replen, "# ack stop ch=%d", ch);
  else     snprintf(reply, replen, "# ack stop idle");
}

// Non-blocking host->device command RX: read whole lines and dispatch them through
// the registry, printing the handler's (or dispatch's nak) reply.
static void pollSerialCommand() {
  static char cmdbuf[48];
  static uint8_t cmdlen = 0;
  while (Serial.available() > 0) {
    int ci = Serial.read();
    if (ci < 0) break;
    char c = (char)ci;
    if (c == '\n' || c == '\r') {
      if (cmdlen == 0) continue;  // ignore blank lines
      cmdbuf[cmdlen] = '\0';
      char reply[96];
      if (serial_cmd_dispatch(cmdbuf, reply, sizeof(reply)) != SERIAL_CMD_IGNORED) {
        Serial.println(reply);
      }
      cmdlen = 0;
    } else if (cmdlen < sizeof(cmdbuf) - 1) {
      cmdbuf[cmdlen++] = c;
    } else {
      cmdlen = 0;  // oversized line: drop it
    }
  }
}

void loop() {
  esp_task_wdt_reset();  // feed the watchdog every iteration; a wedged loop -> reset (#93)

  // Process any inbound !cad command first, so cadence changes are responsive at
  // any cadence (this runs every loop iteration, not once per sweep).
  pollSerialCommand();

  // Service the manual pump pulse every iteration (#215): the instant the bounded
  // pulse expires, drive its relay OFF. Capture the channel before service() clears it.
  int pulse_ch = pump_pulse_channel(&g_pump);
  if (pump_pulse_service(&g_pump, millis())) pumpSet(pulse_ch, false);

  // HARD INVARIANT (irrigation.h): never sample a probe while a pump runs. While a
  // pulse is active, suppress the telemetry sweep - just feed the wdt + the pulse timer.
  // Keeps the pump's electrical noise off the ADC and bounds the pulse-off latency.
  if (pump_pulse_active(&g_pump)) return;

  // Non-blocking scheduler: one sweep of all channels every g_cadence_ms.
  static unsigned long lastRead = 0;
  unsigned long now = millis();
  if (now - lastRead < g_cadence_ms) return;
  lastRead = now;

  // Log uptime from the 64-bit esp_timer (us since boot), not millis(): millis()
  // is uint32 and wraps at ~49.7 days, but this counter stays monotonic for
  // ~292,000 years, so the millis_ms column survives an arbitrarily long run.
  unsigned long long up_ms = (unsigned long long)esp_timer_get_time() / 1000ULL;

  // B6.2 sacrificial sync: a leading newline absorbs the post-idle UART framing
  // glitch, so the first real data byte of the burst isn't the one that mangles.
  Serial.println();

  uint16_t samples[SAMPLES_PER_READ];
  for (int ch = 0; ch < NUM_SENSORS; ch++) {
    sampleChannel(ch, samples);
    moisture_level_t level = moisture_process(&state[ch], &cfg, samples, SAMPLES_PER_READ);
    uint16_t raw = state[ch].last_raw;

    // Type-specific fields live in the payload (k=v, ';'-sep, no commas).
    char payload[64];
    snprintf(payload, sizeof(payload), "level=%s;role=%s;spread=%u;gpio=%d",
             moisture_level_name(level),
             moisture_level_is_display(level) ? "disp" : "diag",
             (unsigned)state[ch].last_spread, SENSOR_PINS[ch]);

    // Compact device CSV row - host prepends time/sequence columns (B2).
    // value + unit are emitted NULL (empty fields): raw_value (ADC counts) and the
    // band (payload 'level') are authoritative; value/unit are reserved for a
    // future calibrated VWC, never an uncalibrated moisture % (issue #38).
    char line[200];
    snprintf(line, sizeof(line),
             "%s,%s,%s,%s,%llu,%s,%s,%s,%s,%u,,,%s,%s",
             RECORD_TYPE_SOIL, g_session_id, g_device_id, PLANTS_FW_VERSION,
             up_ms, SENSOR_MODEL, SENSOR_NAMES[ch], SENSOR_POSITION, SOIL_CHANNEL,
             (unsigned)raw, qualityFlag(&state[ch]), payload);
    char crc[6];
    snprintf(crc, sizeof(crc), "*%02X", lineChecksum(line));
    Serial.print(line);
    Serial.println(crc);
  }

  // Reprint the header every 20 sweeps so a long scroll stays self-describing.
  static unsigned int hdr = 0;
  if (++hdr % 20 == 0) printHeader();

  // Heartbeat blink - loop alive (does not affect the read cadence).
  digitalWrite(LED_PIN, HIGH);
  delay(20);
  digitalWrite(LED_PIN, LOW);
}
