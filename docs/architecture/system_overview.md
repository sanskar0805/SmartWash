# Architecture — SmartWash System Overview

## Three-Layer Architecture

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Machine 1   │   │  Machine 2   │   │  Machine N   │
│  [IoT Node]  │   │  [IoT Node]  │   │  [IoT Node]  │
│              │   │              │   │              │
│  ESP32       │   │  ESP32       │   │  ESP32       │
│  ACS712      │   │  ACS712      │   │  ACS712      │
│  SW-420      │   │  SW-420      │   │  SW-420      │
│  WS2812B     │   │  WS2812B     │   │  WS2812B     │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       └──────────────────┴──────────────────┘
                          │ WiFi / MQTT
                          ▼
              ┌───────────────────────────┐
              │      CLOUD BACKEND        │
              │                           │
              │  Firebase Realtime DB     │
              │  Python Flask API         │
              │  Firebase Cloud Messaging │
              │                           │
              │  AI Engine:               │
              │  - Demand Forecast        │
              │  - Anomaly Detection      │
              └───────────┬───────────────┘
                          │ REST API / FCM Push
              ┌───────────┴───────────┐
              │                       │
     ┌────────▼────────┐    ┌─────────▼────────┐
     │   Student App   │    │  Admin Dashboard │
     │   (Flutter)     │    │  (Web Browser)   │
     └─────────────────┘    └──────────────────┘
```

## Data Flow

```
Sensor Readings (10x/sec)
        │
        ▼
ESP32 classifies state
        │
        ▼ MQTT (every 30s or on change)
        │
        ▼
Firebase Realtime Database
        │
        ├──► Flask API ──► Student App (REST polling)
        │
        ├──► AI Engine ──► Demand forecast / Anomaly flag
        │
        └──► FCM ──► Push notification to student phone
```

## Deployment Phases

| Phase | What gets deployed |
|---|---|
| Phase 2 | IoT node on breadboard (2 machines) |
| Phase 3 | Firebase + Flask API live |
| Phase 4 | Flutter app (basic status screen) |
| Phase 5 | Pilot: 2 machines, 10 students |
| Phase 6 | AI features + full machine rollout |
