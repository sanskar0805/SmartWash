# SmartWash — System Architecture Overview

**Version:** 1.0  
**Author:** Sanskar Suman · AccelAIrate Club · IIIT Dharwad  
**Last updated:** March 2026

---

## 1. System Overview

SmartWash is a three-layer IoT system that transforms existing washing machines into smart, connected devices without any hardware modification to the machines themselves.

```
┌────────────────────────────────────────────────────────────────────┐
│                    SMARTWASH — SYSTEM OVERVIEW                     │
└────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │  Machine 1   │   │  Machine 2   │   │  Machine N   │
  │  [IoT Node]  │   │  [IoT Node]  │   │  [IoT Node]  │
  │  ESP32       │   │  ESP32       │   │  ESP32       │
  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
         └──────────────────┴──────────────────┘
                            │
                     WiFi / HTTPS REST
                            │
                            ▼
              ┌─────────────────────────┐
              │     CLOUD BACKEND       │
              │  Flask API (Python)     │
              │  Firebase Realtime DB   │
              │  FCM Push Notifications │
              │  AI Engine (Python)     │
              └────────────┬────────────┘
                           │
                    REST API + FCM
                           │
              ┌────────────┴────────────┐
              │                         │
   ┌──────────▼──────────┐   ┌──────────▼──────────┐
   │    Student App      │   │   Admin Dashboard   │
   │  (Flutter/Web)      │   │   (Web Browser)     │
   └─────────────────────┘   └─────────────────────┘
```

---

## 2. Layer 1 — IoT Hardware Node

**One node per washing machine. Requires no modification to the machine.**

### Components
- ESP32 DevKit v1 — microcontroller + WiFi
- ACS712-30A — current sensor (reads power draw)
- SW-420 — vibration sensor (detects drum spin)
- WS2812B LED ring — visual status indicator at machine

### Firmware Logic (`hardware/firmware/main.ino`)
The ESP32 samples sensors 10× per second and classifies the machine into one of four states:

| State       | Current Draw| Vibration | Meaning                           |
|-------------|-------------|-----------|-----------------------------------|
| available   | ~0 A        | No        | Idle, ready to use                |
| running     | > 2 A       | Yes       | Wash cycle in progress            |
| cycle_done  | ~0.5 A      | No        | Cycle finished, clothes inside    |
| fault       | Abnormal    | Abnormal  | Malfunction — flag for maintenance|

State transitions are sent to the backend:
- **Immediately** on state change (real-time updates)
- **Every 30 seconds** as a heartbeat (keeps Firebase fresh)

### Communication Protocol
- Transport: WiFi → HTTPS
- Direction: ESP32 → Backend REST API (POST `/machines/{id}/status`)
- No inbound connections needed from the internet to the ESP32

---

## 3. Layer 2 — Cloud Backend

**Central server: receives IoT data, stores state, runs AI, sends notifications.**

### Components
- `backend/api/app.py` — Flask REST API
- Firebase Realtime Database — live machine state + bookings + logs
- Firebase Cloud Messaging (FCM) — push notifications
- `ai/demand_prediction/demand_model.py` — Prophet forecasting (cron job)
- `ai/anomaly_detection/anomaly_detection.py` — Isolation Forest (per machine)

### REST API Endpoints

| Method | Path                                    | Description                          |
|--------|-----------------------------------------|--------------------------------------|
| GET    | `/machines`                             | All machine states (student home)    |
| GET    | `/machines/{id}`                        | Single machine detail                |
| POST   | `/machines/{id}/status`                 | IoT node updates machine state       |
| POST   | `/bookings`                             | Student creates a booking            |
| GET    | `/bookings/{machine_id}`                | Queue for a machine                  |
| POST   | `/bookings/{booking_id}/cancel`         | Cancel a booking                     |
| POST   | `/machines/{id}/report_fault`           | Student reports a fault              |
| GET    | `/analytics/usage`                      | Summary stats (admin dashboard)      |
| GET    | `/analytics/logs`                       | Raw usage logs (AI model input)      |

### Firebase Data Paths
```
smartwash-default-rtdb/
├── machines/{machine_id}       ← Live state (written by IoT + backend)
├── bookings/{booking_id}       ← Student reservations
├── users/{student_id}          ← FCM tokens for notifications
├── usage_logs/{log_id}         ← Append-only log for AI training
└── fault_reports/{report_id}   ← All fault events
```

See `backend/database/schema.md` for full field documentation.

### Hosting
- **Prototype:** Render.com or Railway.app (both have free tiers)
- **Production:** Any cloud VM (DigitalOcean, AWS EC2, etc.)

---

## 4. Layer 3 — Student App & Admin Dashboard

### Student App (`app/index.html` or Flutter)
Built as a web-first app (HTML/CSS/JS) for prototyping, with Flutter for native mobile later.

Key screens:
- **Home:** Machine grid with colour-coded live status
- **Machine Detail:** Estimated time, queue, booking button
- **Book a Slot:** Pick machine + time
- **Notifications:** Push alerts via FCM
- **Report Fault:** One-tap fault report

### Admin Dashboard
Web browser interface (can reuse same app with admin auth). Shows:
- All machine states + fault list
- Usage analytics from `/analytics/usage`
- Fault reports + resolution status
- AI demand forecast chart

---

## 5. AI Engine

### 5.1 Demand Prediction (`ai/demand_prediction/demand_model.py`)

**When to run:** Nightly cron job (after 2–3 weeks of data)

**How it works:**
1. Fetches usage logs from `/analytics/logs`
2. Aggregates into hourly demand counts
3. Trains a Facebook Prophet model (daily + weekly seasonality)
4. Generates 48-hour hourly forecast
5. Classifies hours as "quiet / moderate / busy"
6. Writes forecast + best-time suggestions to Firebase at `/ai_forecasts/demand`
7. Student app reads this path to show the AI suggestion banner

**Resource requirements:** CPU only, ~30 seconds to train, runs on free-tier server

### 5.2 Anomaly Detection (`ai/anomaly_detection/anomaly_detection.py`)

**When to run:** Training phase after data collection; inference continuously

**How it works:**
1. Training: learns normal current + vibration patterns per machine using Isolation Forest
2. Inference: each new sensor reading is scored
3. If anomaly confidence > 70%, backend is called to set machine state to `fault`
4. Admin is notified via FCM

**Resource requirements:** CPU only, model <1MB per machine, inference <10ms

---

## 6. Data Flow — Student Journey

```
Student opens app
      │
      ▼
GET /machines → Firebase → App shows live grid
      │
  Machine free?
 ┌────┴────┐
Yes       No
 │         │
POST       AI forecast shows
/bookings  quiet time suggestion
 │
Machine reserved
      │
Student starts machine physically
      │
ESP32 detects cycle start → POST /machines/{id}/status (state: running)
      │
Firebase updated → App shows "Running" + timer
      │
~45 minutes later
      │
ESP32 detects cycle end → POST /machines/{id}/status (state: cycle_done)
      │
Backend calls _notify_cycle_done() → FCM push to student
      │
Student collects clothes
      │
ESP32 detects idle → POST (state: available)
      │
Firebase updated → machine shown as free to next student
```

---

## 7. Deployment Checklist

### Phase 1 — Local Dev
- [ ] Clone repo, install Python deps: `pip install -r requirements.txt`
- [ ] Download `serviceAccountKey.json` from Firebase Console
- [ ] Set `FIREBASE_DB_URL` in `.env`
- [ ] Run Flask API: `python backend/api/app.py`
- [ ] Open `app/index.html` in browser (prototype UI)

### Phase 2 — Hardware Prototype
- [ ] Wire IoT node on breadboard (see `hardware/components/bom.md`)
- [ ] Set `WIFI_SSID`, `WIFI_PASSWORD`, `API_BASE_URL`, `MACHINE_ID` in `main.ino`
- [ ] Flash firmware via Arduino IDE
- [ ] Monitor Serial output at 115200 baud
- [ ] Verify machine states appear in Firebase Console

### Phase 3 — Pilot Deployment
- [ ] Deploy Flask API to Render.com
- [ ] Update `API_BASE_URL` in firmware and reflash
- [ ] Deploy on 2 machines, test with 10 students
- [ ] Collect 2–3 weeks of usage logs
- [ ] Train AI models: `python ai/demand_prediction/demand_model.py`
- [ ] Train anomaly models: `python ai/anomaly_detection/anomaly_detection.py train M1 M2`

---

## 8. Design Decisions & Trade-offs

| Decision                        | Chosen Approach              | Alternative Considered          | Reason                                         |
|---------------------------------|-----------------------------|---------------------------------|------------------------------------------------|
| Communication protocol          | HTTPS REST                  | MQTT broker                     | Simpler setup, Firebase handles pub/sub natively|
| Database                        | Firebase Realtime DB        | PostgreSQL on server            | Free tier, built-in real-time sync to app      |
| AI demand model                 | Facebook Prophet            | LSTM neural network             | No GPU needed, interpretable, runs on free tier|
| AI anomaly model                | Isolation Forest            | Autoencoder                     | No labeled fault data needed, fast inference   |
| App framework                   | Web HTML (prototype)        | Flutter native                  | Fastest to prototype; migrate to Flutter later |
| Machine modification            | None (external sensors only)| Internal wiring                 | Zero risk, no warranty voiding, portable       |
