# SmartWash — Bill of Materials (BOM)
Hardware Components for One IoT Node (one per washing machine)

---

## Component List

| # | Component                     | Model / Spec       | Purpose                                      | Qty | Unit Cost (INR) | Total (INR) |
|---|-------------------------------|--------------------|----------------------------------------------|-----|-----------------|-------------|
| 1 | Microcontroller               | ESP32 DevKit v1    | Brain — reads sensors, sends data over WiFi  |  1  |   400 – 600     |  400 – 600  |
| 2 | Current Sensor                | ACS712-30A         | Measures power draw to detect machine state  |  1  |    80 – 130     |   80 – 130  |
| 3 | Vibration Sensor              | SW-420 Module      | Detects drum spinning (confirms active cycle)|  1  |    40 – 80      |   40 – 80   |
| 4 | LED Status Ring               | WS2812B 8-LED ring | Visual status indicator at the machine       |  1  |    60 – 100     |   60 – 100  |
| 5 | USB Power Adapter             | 5V 2A USB          | Powers ESP32 from wall socket near machine   |  1  |    80 – 120     |   80 – 120  |
| 6 | Project Enclosure             | ABS 100×60×25mm    | Weatherproof box to protect electronics      |  1  |    50 – 100     |   50 – 100  |
| 7 | USB Micro-B Cable             | 30cm               | Connect USB adapter to ESP32                 |  1  |    20 – 40      |   20 – 40   |
| 8 | Jumper Wires                  | Female–Female 20cm | Connect sensors to ESP32 GPIO pins           | 10  |    10 – 20      |   10 – 20   |
| 9 | Breadboard (prototyping only) | 400-point          | Phase 2 prototyping                          |  1  |    40 – 70      |   40 – 70   |

---

## Cost Summary

| Scope                  | Low Estimate | High Estimate |
|------------------------|-------------|----------------|
| Per machine (IoT node) | ₹ 740       | ₹ 1,160        |
| 5-machine pilot        | ₹ 3,700     | ₹ 5,800        |
| 10-machine full deploy | ₹ 7,400     | ₹ 11,600       |

---

## Where to Buy

| Platform         | Best For                          | Notes                          |
|------------------|-----------------------------------|--------------------------------|
| Robocraze        | ESP32, sensors, LED modules       | Fast shipping, student pricing |
| Robu.in          | ACS712, SW-420, WS2812B           | Good stock of sensor modules   |
| Amazon India     | USB adapters, enclosures, cables  | Easiest for non-tech parts     |
| EasyEDA / JLCPCB | Custom PCB (Phase 3+)             | For permanent board if needed  |

---

## ESP32 GPIO Pin Assignments

| Pin     | GPIO | Component               | Signal Type             |
|---------|------|-------------------------|-------------------------|
| GPIO 34 | 34   | ACS712 VOUT             | Analog input (ADC1_CH6) |
| GPIO 27 | 27   | SW-420 DOUT             | Digital input           |
| GPIO 14 | 14   | WS2812B DIN             | Digital output (PWM)    |
| GND     | —    | All sensor GNDs         | Common ground           |
| 3.3V    | —    | SW-420 VCC              | 3.3V power              |
| 5V (VIN)| —    | ACS712 VCC, WS2812B VCC | 5V power (from USB)     |

> **Note:** The ACS712 runs on 5V. The ESP32 runs on 3.3V logic.
> The ACS712 VOUT output (max 5V) must be voltage-divided before connecting
> to the ESP32 GPIO or use a 5V-tolerant ADC input. GPIO 34 is input-only
> and ADC1 is preferred (ADC2 conflicts with WiFi).

---

## Future Hardware (Phase 3+)

| Component                  | Purpose                             | Cost           |
|----------------------------|-------------------------------------|----------------|
| Custom PCB (JLCPCB)        | Replace breadboard, permanent mount | ₹200–400/board |
| OLED 0.96" Display         | Show status at machine without phone| ₹80–150        |
| Buzzer                     | Audible alert at machine            | ₹20–40         |
| OV2640 Camera Module       | Computer vision (Phase 3 future)    | ₹500–800       |
| Ethernet Module (W5500)    | Backup to WiFi for reliability      | ₹300–500       |
