# Hardware — IoT Node

Each washing machine gets one IoT node attached externally. No modification to the machine itself is required.

## Folder Structure

```
hardware/
├── firmware/        ← ESP32 Arduino/MicroPython code (coming soon)
├── schematics/      ← Wiring diagrams and circuit schematics (coming soon)
└── components/      ← Bill of materials and sourcing notes
```

## Bill of Materials (Per Machine)

| Component | Module | Approx. Cost (INR) |
|---|---|---|
| Microcontroller + WiFi | ESP32 DevKit | ₹400–600 |
| Current Sensor | ACS712 30A | ₹80–130 |
| Vibration Sensor | SW-420 | ₹40–80 |
| LED Status Ring | WS2812B (8 LED) | ₹60–100 |
| Power Supply | 5V USB Adapter | ₹80–120 |
| Enclosure | Project Box | ₹50–100 |

**Per machine: ₹710–₹1,130 · 10-machine deployment: ~₹7,000–₹11,000**

## Machine State Logic

The ESP32 samples sensors 10× per second and classifies each machine:

| State | Current | Vibration | Meaning |
|---|---|---|---|
| Available | ~0 A | None | Idle, ready to use |
| Running | > 2 A | Present | Wash cycle active |
| Cycle Done | ~0.5 A | None | Done, clothes inside |
| Fault | Abnormal | Abnormal | Flag for maintenance |

State is pushed to cloud every 30 seconds, or immediately on state change.

## Status: Pending procurement
