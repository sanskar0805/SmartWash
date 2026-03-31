# SmartWash 🧺

> AI-Enabled Smart Laundromat Management System for Campus Hostels

**Status:** Pre-build · Club lead-endorsed · Seeking active members to begin  
**Club:** [AccelAIrate](https://github.com/AccelAIrate) — AI & Hardware Co-design, IIIT Dharwad  
**Category:** IoT · Embedded Systems · Applied AI

---

## The Problem

Campus laundromats are one of the worst-managed shared facilities in any hostel. Students walk to the laundry room not knowing if a machine is free. Machines break and sit occupied for days. There's no queue, no schedule, no notifications — just wasted trips and informal disputes over machines.

Six specific problems, all solvable with one system:

| # | Problem | Impact |
|---|---|---|
| 1 | No machine status visibility | Students must physically walk to check |
| 2 | No scheduling system | Everyone arrives at the same time → queues |
| 3 | Broken machines still occupy space | Effective capacity is reduced |
| 4 | Clothes left piled outside machines | Clutter, hygiene issues, informal disputes |
| 5 | No fault reporting channel | Repairs get delayed |
| 6 | Dependency on caretaker | System fails when caretaker is absent |

---

## Proposed Solution

SmartWash is a three-layer system that transforms existing washing machines into smart, connected devices — **without modifying the machines themselves.**

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Machine 1   │   │  Machine 2   │   │  Machine N   │
│  [IoT Node]  │   │  [IoT Node]  │   │  [IoT Node]  │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       └──────────────────┴──────────────────┘
                          │ WiFi / MQTT
                          ▼
              ┌───────────────────────┐
              │   CLOUD BACKEND       │
              │  Firebase + AI Model  │
              └───────────┬───────────┘
                          │ REST API
              ┌───────────┴───────────┐
              │                       │
     ┌────────▼────────┐    ┌─────────▼───────┐
     │   Student App   │    │ Admin Dashboard │
     │  (Flutter)      │    │   (Web)         │
     └─────────────────┘    └─────────────────┘
```

**Layer 1 — Hardware (IoT Node per machine)**  
A small electronics module clipped externally to each machine. No machine modification needed.

| Component | Purpose | Module | Cost (INR) |
|---|---|---|---|
| ESP32 DevKit | Microcontroller + WiFi | ESP32 | ₹400–600 |
| Current Sensor | Detects if machine is drawing power | ACS712 30A | ₹80–130 |
| Vibration Sensor | Confirms drum is spinning | SW-420 | ₹40–80 |
| LED Status Ring | Visual status at the machine | WS2812B | ₹60–100 |
| Power Supply | Powers ESP32 | 5V USB adapter | ₹80–120 |

**Estimated cost per machine: ₹710–₹1,130 · 10-machine deployment: ~₹7,000–₹11,000**

**Layer 2 — Cloud Backend**  
Firebase Realtime Database + Python Flask API. Machine states pushed every 30 seconds or on state change. Free-tier sufficient for campus scale.

**Layer 3 — Student App (Flutter)**  
Live machine grid (🟢 Free · 🔵 Running · 🔴 Faulty · 🟡 Done), slot booking, push notifications when cycle ends.

---

## Machine State Detection

The ESP32 samples current and vibration 10× per second and classifies each machine:

| State | Current Draw | Vibration | Meaning |
|---|---|---|---|
| Available | ~0 A | None | Idle, ready to use |
| Running | > 2 A | Present | Wash cycle in progress |
| Cycle Done | ~0.5 A | None | Finished, clothes inside |
| Fault | Abnormal | Abnormal | Flag for maintenance |

---

## AI Features

Both models run on a free-tier cloud server — no GPU required.

**Demand Prediction** — After 2–3 weeks of usage logs, a lightweight time-series model (Facebook Prophet) learns peak hours and suggests quiet times to students in-app.

**Anomaly Detection** — Isolation Forest trained on normal current + vibration signatures. Flags machines showing unusual readings before they fully break down.

---

## Implementation Roadmap

| Phase | Activities | Timeline |
|---|---|---|
| Research | Component list, datasheets, team roles | Weeks 1–2 |
| Prototype | IoT node on breadboard, sensor testing | Weeks 3–5 |
| Backend | Firebase setup, REST API, cloud connection | Weeks 5–7 |
| App | Flutter app with status + notifications | Weeks 6–9 |
| Pilot | 2-machine deployment, 10-student test | Weeks 9–11 |
| AI + Scale | Demand prediction, anomaly detection, full rollout | Weeks 11–14 |

Basic deployment (status + notifications, no AI): **~7 weeks**  
Full feature completion: **~14 weeks**

---

## Future Scope

- FPGA-based edge inference to replace ESP32 (lower power, faster AI)
- Computer vision to visually confirm drum state
- UPI/QR payment integration for paid laundry facilities
- Neuromorphic sensing for ultra-low-power anomaly detection
- Campus app integration

---

## Stack

`Python` · `Flutter` · `Firebase` · `ESP32` · `MQTT` · `Flask` · `Facebook Prophet` · `Isolation Forest`

---

## Contributing

This project is in pre-build phase under AccelAIrate Club at IIIT Dharwad.  
If you're a club member interested in joining — IoT, embedded, backend, or app — open an issue or reach out directly.

---

*Proposed and authored by Sanskar Suman (CSE, 2025–2029) · AccelAIrate Club · IIIT Dharwad*
