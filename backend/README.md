# Backend — Cloud Server

Lightweight cloud backend that receives data from all IoT nodes and serves it to the student app.

## Folder Structure

```
backend/
├── api/          ← Python Flask REST API (coming soon)
├── database/     ← Firebase schema and rules
└── config/       ← Environment config templates
```

## Stack

| Layer | Tool | Why |
|---|---|---|
| Database | Firebase Realtime Database | Free tier sufficient for campus scale; real-time sync |
| Push Notifications | Firebase Cloud Messaging | Free, reliable push to student phones |
| REST API | Python Flask | Lightweight, easy to host |
| Hosting | Render.com / Railway.app | Free tier for prototyping |

## API Endpoints (Planned)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/machines` | Get status of all machines |
| GET | `/machines/<id>` | Get status of a single machine |
| POST | `/machines/<id>/report` | Student reports a fault |
| POST | `/machines/<id>/book` | Book a slot |
| GET | `/ai/demand` | Get AI demand forecast for today |

## Data Flow

```
ESP32 Node → MQTT → Firebase → Flask API → Student App
                                    ↓
                               AI Model
                                    ↓
                          Push Notification (FCM)
```

## Status: Pending — API and Firebase schema to be built during Phase 3
