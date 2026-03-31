# AI — Models & Inference

Two lightweight AI features that run on a free-tier cloud server. No GPU required.

## Folder Structure

```
ai/
├── demand_prediction/    ← Time-series demand forecasting model
├── anomaly_detection/    ← Fault detection model
└── datasets/             ← Usage logs and training data (generated after pilot)
```

## Feature 1 — Demand Prediction

**Goal:** Tell students the best time to do laundry today.

**How it works:**
- System logs machine usage timestamps continuously from day one
- After 2–3 weeks of data, a time-series model learns daily and weekly usage patterns
- Students see: *"Laundry is usually quiet between 10 AM–12 PM today"*

**Model:** Facebook Prophet (lightweight, runs on free-tier server, no GPU)  
**Input:** Timestamped usage logs from Firebase  
**Output:** Hourly demand forecast for the next 24 hours  
**Status:** Pending — requires pilot deployment data (Phase 6)

---

## Feature 2 — Anomaly Detection

**Goal:** Flag machines showing unusual behaviour before they fully break down.

**How it works:**
- System learns the normal current draw and vibration pattern of a healthy machine
- If readings deviate significantly → machine flagged as potentially faulty
- Admin notified automatically; machine marked in app

**Model:** Isolation Forest (scikit-learn) or statistical z-score threshold  
**Input:** Real-time current + vibration readings from ESP32  
**Output:** Binary flag — Normal / Anomalous  
**Status:** Pending — requires sensor data from hardware prototype (Phase 6)

---

## Dependencies (Planned)

```
pandas
numpy
prophet
scikit-learn
firebase-admin
```
