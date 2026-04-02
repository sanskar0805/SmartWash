# SmartWash — Firebase Realtime Database Schema

Firebase Realtime Database stores data as a JSON tree.
Below is the complete schema with field descriptions and example values.

---

## Root Structure

```
smartwash-default-rtdb/
├── machines/
├── bookings/
├── users/
├── usage_logs/
└── fault_reports/
```

---

## /machines/{machine_id}

Live state of each washing machine. Written by the IoT node (ESP32) via the backend API.

| Field          | Type            | Description                                                   | Example                    |
|----------------|-----------------|---------------------------------------------------------------|----------------------------|
| state          | string          | One of: available, running, cycle_done, fault                 | "running"                  |
| current_a      | float           | Current draw in amperes (from ACS712 sensor)                  | 3.2                        |
| vibration      | boolean         | Whether drum vibration is detected (SW-420 sensor)            | true                       |
| fault_code     | string or null  | Fault type if state == fault; null otherwise                  | "SENSOR_ANOMALY"           |
| current_user   | string or null  | student_id of the student currently using the machine         | "stu_001"                  |
| cycle_start    | ISO 8601 string | UTC timestamp when current cycle started                      | "2026-03-15T10:05:00"      |
| estimated_end  | ISO 8601 string | Computed end time (cycle_start + 45 min default)              | "2026-03-15T10:50:00"      |
| last_updated   | ISO 8601 string | UTC timestamp of last update from IoT node                    | "2026-03-15T10:06:30"      |

### Fault Codes

| Code            | Source         | Meaning                                              |
|-----------------|----------------|------------------------------------------------------|
| SENSOR_ANOMALY  | AI model       | Isolation Forest flagged abnormal sensor readings    |
| USER_REPORT     | Student app    | Student manually reported a fault                    |
| HIGH_CURRENT    | Firmware       | Current draw exceeded safe threshold (>15 A)         |
| NO_VIBRATION    | Firmware       | Machine running but no vibration detected            |

### Example

```json
"machines": {
  "M1": {
    "state": "running",
    "current_a": 3.2,
    "vibration": true,
    "fault_code": null,
    "current_user": "stu_001",
    "cycle_start": "2026-03-15T10:05:00",
    "estimated_end": "2026-03-15T10:50:00",
    "last_updated": "2026-03-15T10:06:30"
  },
  "M2": {
    "state": "available",
    "current_a": 0.0,
    "vibration": false,
    "fault_code": null,
    "current_user": null,
    "cycle_start": null,
    "estimated_end": null,
    "last_updated": "2026-03-15T09:55:10"
  },
  "M3": {
    "state": "fault",
    "current_a": 0.1,
    "vibration": false,
    "fault_code": "USER_REPORT",
    "current_user": null,
    "cycle_start": null,
    "estimated_end": null,
    "last_updated": "2026-03-15T08:30:00"
  }
}
```

---

## /bookings/{booking_id}

Each entry is a student's slot reservation. Firebase auto-generates the booking_id key via `.push()`.

| Field         | Type            | Description                                          | Example                    |
|---------------|-----------------|------------------------------------------------------|----------------------------|
| machine_id    | string          | Which machine was booked                             | "M1"                       |
| student_id    | string          | Unique student identifier                            | "stu_001"                  |
| student_name  | string          | Display name                                         | "Rahul"                    |
| fcm_token     | string          | Firebase Cloud Messaging token for push notifications| "dQw4w9WgXcQ..."           |
| slot_time     | ISO 8601 string | Requested start time of the slot                     | "2026-03-15T10:00:00"      |
| status        | string          | One of: active, completed, cancelled                 | "active"                   |
| created_at    | ISO 8601 string | When booking was made                                | "2026-03-14T22:10:05"      |
| completed_at  | ISO 8601 string | When booking was marked completed (nullable)         | "2026-03-15T10:52:00"      |
| cancelled_at  | ISO 8601 string | When booking was cancelled (nullable)                | null                       |

### Example

```json
"bookings": {
  "-NaB3xKf7rTm0pqYwZ": {
    "machine_id": "M1",
    "student_id": "stu_001",
    "student_name": "Rahul",
    "fcm_token": "dQw4w9WgXcQ...",
    "slot_time": "2026-03-15T10:00:00",
    "status": "active",
    "created_at": "2026-03-14T22:10:05",
    "completed_at": null,
    "cancelled_at": null
  }
}
```

---

## /users/{student_id}

Stores student FCM tokens for push notifications. Updated on each booking.

| Field         | Type   | Description                                 | Example         |
|---------------|--------|---------------------------------------------|-----------------|
| student_id    | string | Unique student identifier                   | "stu_001"       |
| student_name  | string | Display name                                | "Rahul"         |
| fcm_token     | string | Latest Firebase Cloud Messaging token       | "dQw4w9WgXcQ…"  |

---

## /usage_logs/{log_id}

Append-only log of every machine state transition. The AI demand prediction model reads this table.
Firebase auto-generates the log_id key via `.push()`.

| Field      | Type            | Description                                   | Example               |
|------------|-----------------|-----------------------------------------------|-----------------------|
| machine_id | string          | Which machine                                 | "M1"                  |
| state      | string          | New state after transition                    | "running"             |
| current_a  | float           | Current draw at time of log                   | 3.2                   |
| timestamp  | ISO 8601 string | UTC time of the transition                    | "2026-03-15T10:05:00" |

> **Note:** After 2–3 weeks of logs, the `/ai/demand_prediction/demand_model.py` Prophet model
> can be trained on this data. The model reads logs via `GET /analytics/logs`.

---

## /fault_reports/{report_id}

Records all fault reports (both AI-detected and student-reported).

| Field       | Type            | Description                                   | Example                      |
|-------------|-----------------|-----------------------------------------------|------------------------------|
| machine_id  | string          | Machine that was reported faulty              | "M3"                         |
| reported_by | string          | student_id or "ai_model"                      | "stu_042"                    |
| description | string          | Free-text description from student            | "Machine shaking loudly"     |
| reported_at | ISO 8601 string | When the fault was reported                   | "2026-03-15T08:29:55"        |
| resolved    | boolean         | Whether admin has resolved the fault          | false                        |

---

## Firebase Security Rules

Add these rules in Firebase Console → Realtime Database → Rules:

```json
{
  "rules": {
    "machines": {
      ".read": true,
      ".write": false
    },
    "bookings": {
      ".read": "auth != null",
      ".write": "auth != null"
    },
    "users": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": "$uid === auth.uid"
      }
    },
    "usage_logs": {
      ".read": "auth != null",
      ".write": false
    },
    "fault_reports": {
      ".read": "auth != null",
      ".write": "auth != null"
    }
  }
}
```

> **For prototyping**, use permissive rules temporarily:
> `{ "rules": { ".read": true, ".write": true } }`
> Switch to secure rules before any real deployment.

---

## Firebase Indexes (for efficient queries)

Add to `firebase.json` or Firebase Console for the queries used in the API:

```json
{
  "rules": {
    "bookings": {
      ".indexOn": ["machine_id", "student_id", "status", "slot_time"]
    },
    "usage_logs": {
      ".indexOn": ["timestamp", "machine_id"]
    },
    "fault_reports": {
      ".indexOn": ["machine_id", "resolved"]
    }
  }
}
```
