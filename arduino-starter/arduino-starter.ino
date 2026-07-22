/*
 * Sprout Starter — your first soil sensor sketch.
 *
 * Board: Arduino Uno R4 WiFi (Arduino IDE — no libraries, no PlatformIO).
 * Wiring: capacitive soil sensor signal wire -> A0, plus GND + power (3.3V/5V
 * per your sensor's spec). That's the whole circuit.
 *
 * This is a STARTER, not Sprout. It does NOT scale into the full Sprout
 * project (different board, one sensor, no pump, no logging) — it's a
 * friendly front porch, not a branch of the real thing. When you're ready to
 * go further: VS Code + PlatformIO, or GitHub Codespaces. Come meet Sprout
 * Full: you just hand-built its heart — read, calibrate, band, speak.
 *
 * Real numbers, from minute one: this prints the RAW sensor reading + a
 * plain-word band. A raw number, plus where it falls
 * between the two spots YOU measured, is all you need.
 */

// ===== TUNE ME — this is the whole control panel =====
const int SENSOR_PIN = A0;        // the analog pin your sensor's signal wire goes to (A0 on the Uno R4)
const long READ_EVERY_MS = 1000;  // how often I check the soil (try 200 — watch it speed up!)
const int SAMPLES = 8;            // readings I average each check (smooths the jitter)

// --- Calibrate these two to YOUR probe (the fun part — go measure!) ---
// ILLUSTRATIVE 10-bit Uno R4 numbers (0-1023) — yours WILL differ, that's the whole
// point: MEASURE + replace them. (Sprout Full's real, bench-measured per-board anchors
// now live in firmware/include/cal_class_defaults.h (#952) — but those are 12-bit ESP32
// values at a different ADC reference, so they do NOT transfer to the R4 as-is; your R4
// numbers are yours to measure. When you graduate to Sprout Full, that file is where a
// board's dry/wet anchors are sourced.)
const int DRY_READING = 600;  // what you saw with the probe in dry AIR
const int WET_READING = 260;  // what you saw with the probe in a CUP OF WATER

// --- Where the 3 bands split (between your two numbers above) ---
// These are three of Sprout's real mood words — the same ladder you'll meet in
// Sprout Full (Faint · Parched · Thirsty · Content · Thriving · Refreshed · Soaked).
const int THIRSTY_ABOVE = 500;  // drier (bigger) than this  -> "Thirsty"
const int SOAKED_BELOW = 340;   // wetter (smaller) than this -> "Soaked"
//                        (anything in between -> "Content")

const bool BLINK_WHEN_THIRSTY = true;  // light up the onboard LED (LED_BUILTIN) when it needs water
// ===== end of the control panel — everything below just runs it =====

unsigned long lastReadMs = 0;

void setup()
{
    Serial.begin(9600);
    if (BLINK_WHEN_THIRSTY) pinMode(LED_BUILTIN, OUTPUT);

    // Give the Serial Monitor / Plotter a moment to connect on first boot.
    delay(1500);
    Serial.println(F("Sprout Starter — reading A0. Open Tools > Serial Plotter to watch it live."));
}

// Average SAMPLES raw reads — a cheap way to smooth ADC jitter.
int readSensorRaw()
{
    long total = 0;
    for (int i = 0; i < SAMPLES; i++) {
        total += analogRead(SENSOR_PIN);
    }
    return (int)(total / SAMPLES);
}

// Turn a raw reading into one of Sprout's real mood words — the mood leads, then a
// friendly first-person line (the same shape Sprout Full speaks in).
const __FlashStringHelper *bandFor(int raw)
{
    if (raw > THIRSTY_ABOVE) return F("Thirsty - I could really use a drink. Grab the watering can.");
    if (raw < SOAKED_BELOW) return F("Soaked - ahh, just drank; let me soak it up. "
                                     "(If the outer pot's swimming, tip the extra out.)");
    return F("Content - comfy, nothing to do. I'm happy.");
}

void loop()
{
    unsigned long now = millis();
    if (now - lastReadMs < (unsigned long)READ_EVERY_MS) return;  // non-blocking: no delay() here
    lastReadMs = now;

    int raw = readSensorRaw();
    bool thirsty = raw > THIRSTY_ABOVE;

    Serial.print(F("raw="));
    Serial.print(raw);
    Serial.print(F("  "));
    Serial.println(bandFor(raw));

    if (BLINK_WHEN_THIRSTY) digitalWrite(LED_BUILTIN, thirsty ? HIGH : LOW);
}
