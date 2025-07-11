# 🌍 OrbitaLink_GroundStation

OrbitaLink GroundStation is a real-time Raspberry Pi–powered satellite ground control platform designed for field deployment. It features automated antenna pointing using sensor data, satellite tracking via live TLEs, and a web-based dashboard for monitoring and control.

## 📡 Key Features

- 🛰️ **Live Satellite Tracking**: Uses Celestrak or Space-Track API to fetch TLEs and compute Azimuth/Elevation in real-time.
- 🌐 **FastAPI + Socket.IO Server**: Scalable server backend for real-time bi-directional communication with field units (clients).
- 🖥️ **Raspberry Pi-Based UI Display**: Server hosted on a Pi that auto-launches a fullscreen dashboard on HDMI-connected display.
- 🧭 **Antenna Auto-pointing**: Stepper motor + AS5600 encoder–based az/el motor control with fallback manual override.
- 🌡️ **Sensor Integration**: DHT11 and GPS module for telemetry, displayed on dashboard.
- 📶 **Field Unit Client**: A Python-based Raspberry Pi script that connects to the server, sends sensor data, receives pointing commands, and controls motors.
- 🔄 **State Persistence**: All unit data is saved to `fu_data.json` for resilience and auto-recovery.

---

## 🗂️ Repository Structure

```bash
OrbitaLink_GroundStation/
│
├── Server/                      # FastAPI + Socket.IO server
│   ├── server.py                # Main backend server script
│   ├── fu_data.json             # Persistent state store
│   └── static/                  # Dashboard HTML/CSS/JS files
│
├── Client/                      # Field Unit (FU) Raspberry Pi client
│   ├── client.py                # Main FU script
│   └── utils/                   # Helper scripts for GPS, TLE, etc.
│
├── Arduino/                     # Arduino firmware for low-level motor control
│   └── antenna_motor.ino
│
├── systemd/                     # Autostart service config
│   └── dashboard-server.service
│
├── kiosk/                       # Kiosk startup config for RPi GUI
│   └── autostart                # LXDE autostart file for Chromium
│
└── README.md
