/*
 * SmartWash — ESP32 IoT Node Firmware
 * ─────────────────────────────────────
 * Hardware:
 *   - ESP32 DevKit v1
 *   - ACS712 30A current sensor  → GPIO 34 (ADC)
 *   - SW-420 vibration sensor    → GPIO 27 (digital)
 *   - WS2812B LED ring (8 LEDs)  → GPIO 14
 *
 * Communication: WiFi → MQTT → Cloud Backend REST API
 *
 * Machine States:
 *   AVAILABLE  — idle, ready to use
 *   RUNNING    — wash cycle in progress
 *   CYCLE_DONE — cycle finished, clothes inside
 *   FAULT      — abnormal readings, flag for maintenance
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>

// ─────────────────────────────────────────────
// CONFIGURATION — Edit these before flashing
// ─────────────────────────────────────────────
const char* WIFI_SSID      = "YourHostelWiFi";
const char* WIFI_PASSWORD  = "YourPassword";

// Backend API — use Render/Railway URL in production
const char* API_BASE_URL   = "http://smartwash-api.onrender.com";
const char* MACHINE_ID     = "M1";   // Change per machine: M1, M2, M3...

// ─────────────────────────────────────────────
// PIN DEFINITIONS
// ─────────────────────────────────────────────
#define CURRENT_SENSOR_PIN   34   // ACS712 analog output
#define VIBRATION_SENSOR_PIN 27   // SW-420 digital output
#define LED_PIN              14   // WS2812B data pin
#define LED_COUNT             8   // Number of LEDs in ring

// ─────────────────────────────────────────────
// THRESHOLDS — Tune after calibration
// ─────────────────────────────────────────────
#define CURRENT_RUNNING_THRESHOLD  2.0f   // A — machine is drawing power
#define CURRENT_CYCLE_DONE_THRESHOLD 0.3f // A — standby / cycle done
#define CURRENT_FAULT_HIGH         15.0f  // A — overcurrent fault
#define ADC_VREF                   3.3f   // ESP32 ADC reference voltage
#define ACS712_SENSITIVITY         0.066f // V/A for ACS712-30A
#define ACS712_OFFSET_V            1.65f  // Midpoint voltage (VCC/2)

// ─────────────────────────────────────────────
// TIMING
// ─────────────────────────────────────────────
#define SAMPLE_INTERVAL_MS    100    // Sample sensors every 100ms
#define REPORT_INTERVAL_MS    30000  // Push to server every 30 seconds
#define SAMPLES_PER_READING   10     // Average 10 samples for stability
#define CYCLE_DONE_TIMEOUT_MS 120000 // 2 min of low current = cycle done

// ─────────────────────────────────────────────
// LED COLOURS (GRB format for WS2812B)
// ─────────────────────────────────────────────
#define COLOR_AVAILABLE  0x00FF00  // Green
#define COLOR_RUNNING    0x0000FF  // Blue
#define COLOR_CYCLE_DONE 0xFFAA00  // Amber
#define COLOR_FAULT      0xFF0000  // Red
#define COLOR_CONNECTING 0x222222  // Dim white (connecting)

// ─────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────
enum MachineState { AVAILABLE, RUNNING, CYCLE_DONE, FAULT };

MachineState currentState    = AVAILABLE;
MachineState previousState   = AVAILABLE;
unsigned long lastReportTime = 0;
unsigned long lastSampleTime = 0;
unsigned long lowCurrentSince = 0;  // Timestamp when current dropped low (cycle done detection)

Adafruit_NeoPixel ledRing(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);


// ═══════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════

void setup() {
  Serial.begin(115200);
  Serial.println("\n[SmartWash] Booting...");
  Serial.print("[SmartWash] Machine ID: ");
  Serial.println(MACHINE_ID);

  // Init LED ring
  ledRing.begin();
  ledRing.setBrightness(80);
  setLED(COLOR_CONNECTING);

  // Init sensor pins
  pinMode(CURRENT_SENSOR_PIN, INPUT);
  pinMode(VIBRATION_SENSOR_PIN, INPUT);

  // Connect WiFi
  connectWiFi();

  setLED(COLOR_AVAILABLE);
  Serial.println("[SmartWash] Ready.");
}


// ═══════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════

void loop() {
  unsigned long now = millis();

  // Reconnect WiFi if dropped
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Disconnected. Reconnecting...");
    connectWiFi();
  }

  // Sample sensors at SAMPLE_INTERVAL_MS
  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;

    float currentA  = readCurrent();
    bool  vibration = readVibration();
    MachineState newState = classifyState(currentA, vibration, now);

    if (newState != currentState) {
      previousState = currentState;
      currentState  = newState;
      updateLED(currentState);
      Serial.printf("[State Change] %s → %s | %.2fA | vib=%d\n",
        stateToString(previousState), stateToString(currentState), currentA, vibration);
      // Report immediately on state change
      reportToServer(currentA, vibration);
      lastReportTime = now;
    }
  }

  // Periodic report (heartbeat every 30 seconds)
  if (now - lastReportTime >= REPORT_INTERVAL_MS) {
    float currentA  = readCurrent();
    bool  vibration = readVibration();
    reportToServer(currentA, vibration);
    lastReportTime = now;
  }
}


// ═══════════════════════════════════════════════
// SENSOR READING
// ═══════════════════════════════════════════════

float readCurrent() {
  long   adcSum = 0;
  for (int i = 0; i < SAMPLES_PER_READING; i++) {
    adcSum += analogRead(CURRENT_SENSOR_PIN);
    delay(2);
  }
  float adcAvg = (float)adcSum / SAMPLES_PER_READING;
  float voltage = (adcAvg / 4095.0f) * ADC_VREF;    // 12-bit ADC
  float current = (voltage - ACS712_OFFSET_V) / ACS712_SENSITIVITY;
  return abs(current);  // Return absolute value (AC current)
}

bool readVibration() {
  // SW-420 is HIGH when no vibration, LOW when vibration detected
  return digitalRead(VIBRATION_SENSOR_PIN) == LOW;
}


// ═══════════════════════════════════════════════
// STATE CLASSIFICATION
// ═══════════════════════════════════════════════

MachineState classifyState(float currentA, bool vibration, unsigned long now) {

  // Fault: overcurrent
  if (currentA > CURRENT_FAULT_HIGH) {
    return FAULT;
  }

  // Fault: machine running (high current) but no vibration — motor issue
  if (currentA > CURRENT_RUNNING_THRESHOLD && !vibration) {
    return FAULT;
  }

  // Running: significant current AND vibration
  if (currentA > CURRENT_RUNNING_THRESHOLD && vibration) {
    lowCurrentSince = 0;  // reset cycle-done timer
    return RUNNING;
  }

  // Cycle Done detection: came from RUNNING, now low current + no vibration
  // Wait CYCLE_DONE_TIMEOUT_MS before confirming (avoid false triggers)
  if (currentState == RUNNING && currentA <= CURRENT_RUNNING_THRESHOLD && !vibration) {
    if (lowCurrentSince == 0) {
      lowCurrentSince = now;
    }
    if (now - lowCurrentSince >= CYCLE_DONE_TIMEOUT_MS) {
      return CYCLE_DONE;
    }
    return RUNNING;  // Still counting down timeout
  }

  // Cycle Done → Available (student collected clothes)
  // After CYCLE_DONE, if it stays idle it goes back to AVAILABLE
  if (currentState == CYCLE_DONE && currentA < CURRENT_CYCLE_DONE_THRESHOLD) {
    return AVAILABLE;
  }

  return AVAILABLE;
}


// ═══════════════════════════════════════════════
// REPORTING TO BACKEND
// ═══════════════════════════════════════════════

void reportToServer(float currentA, bool vibration) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Report] Skipped — no WiFi");
    return;
  }

  HTTPClient http;
  String url = String(API_BASE_URL) + "/machines/" + MACHINE_ID + "/status";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  // Build JSON payload
  StaticJsonDocument<256> doc;
  doc["state"]     = stateToString(currentState);
  doc["current_a"] = currentA;
  doc["vibration"] = vibration;

  // Include fault code if applicable
  if (currentState == FAULT) {
    if (currentA > CURRENT_FAULT_HIGH) {
      doc["fault_code"] = "HIGH_CURRENT";
    } else {
      doc["fault_code"] = "NO_VIBRATION";
    }
  } else {
    doc["fault_code"] = nullptr;
  }

  String body;
  serializeJson(doc, body);

  int httpCode = http.POST(body);

  if (httpCode == 200 || httpCode == 201) {
    Serial.printf("[Report] OK → %s | %.2fA | vib=%d\n",
      stateToString(currentState), currentA, vibration);
  } else {
    Serial.printf("[Report] FAILED — HTTP %d\n", httpCode);
  }

  http.end();
}


// ═══════════════════════════════════════════════
// LED CONTROL
// ═══════════════════════════════════════════════

void setLED(uint32_t color) {
  for (int i = 0; i < LED_COUNT; i++) {
    ledRing.setPixelColor(i, color);
  }
  ledRing.show();
}

void updateLED(MachineState state) {
  switch (state) {
    case AVAILABLE:  setLED(COLOR_AVAILABLE);  break;
    case RUNNING:    setLED(COLOR_RUNNING);    break;
    case CYCLE_DONE: setLED(COLOR_CYCLE_DONE); break;
    case FAULT:      setLED(COLOR_FAULT);      break;
  }
}


// ═══════════════════════════════════════════════
// WIFI CONNECTION
// ═══════════════════════════════════════════════

void connectWiFi() {
  Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    retries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WiFi] FAILED — will retry in next loop.");
  }
}


// ═══════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════

const char* stateToString(MachineState state) {
  switch (state) {
    case AVAILABLE:  return "available";
    case RUNNING:    return "running";
    case CYCLE_DONE: return "cycle_done";
    case FAULT:      return "fault";
    default:         return "unknown";
  }
}

/*
 * ─────────────────────────────────────────────
 * CALIBRATION NOTES
 * ─────────────────────────────────────────────
 * 1. ACS712-30A: Zero-current output = VCC/2 = 1.65V
 *    Sensitivity = 66mV/A. Adjust ACS712_OFFSET_V if your
 *    ESP32's 3.3V supply is slightly off — measure with multimeter.
 *
 * 2. SW-420: Adjust the onboard potentiometer until the sensor
 *    reads LOW only during active drum spin, HIGH when idle.
 *
 * 3. CURRENT_RUNNING_THRESHOLD: Measure the actual standby and
 *    running current of your washing machine model and set accordingly.
 *    Common ranges: standby ~0.1A, running ~2–8A.
 *
 * 4. CYCLE_DONE_TIMEOUT_MS: 2 minutes is conservative. Reduce to 60s
 *    if your machine cuts power more cleanly at cycle end.
 *
 * ─────────────────────────────────────────────
 * REQUIRED ARDUINO LIBRARIES
 * ─────────────────────────────────────────────
 * Install via Arduino IDE → Tools → Manage Libraries:
 *   - ArduinoJson       (Benoit Blanchon)
 *   - Adafruit NeoPixel (Adafruit)
 *   - ESP32 board package: https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
 */
