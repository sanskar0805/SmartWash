"""
===========================================================
SmartWash Backend API
AccelAIrate Club - AI Enabled Smart Laundromat System

Author: Sanskar Suman
Project: SmartWash
Module: Backend API (FastAPI)

Description:
This is the main backend server for SmartWash.

It handles:

1. Machine status management
2. Student booking system
3. IoT device data updates
4. AI demand prediction
5. Anomaly detection
6. Notifications and monitoring
7. Database communication

-----------------------------------------------------------
System Architecture

IoT ESP32 Devices ---> FastAPI Backend ---> Database
                                 |
                                 |
                                 ---> Student Web App
                                 ---> Admin Dashboard
                                 ---> AI Models

-----------------------------------------------------------

This file is designed to be:

- clean
- readable
- modular
- contributor-friendly
- scalable

Every section is clearly defined.
===========================================================
"""

# =========================================================
# Imports
# =========================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import datetime
import logging

# =========================================================
# AI Model Imports (future integration)
# =========================================================

# Demand Prediction
# from ai.demand_prediction.demand_model import predict_demand

# Anomaly Detection
# from ai.anomaly_detection.anomaly_detection import detect_anomaly

# =========================================================
# Database (temporary in-memory for development)
# =========================================================

machines_db = {}
bookings_db = {}

# =========================================================
# FastAPI App Initialization
# =========================================================

app = FastAPI(
    title="SmartWash Backend API",
    description="AI Enabled Smart Laundromat System",
    version="1.0.0"
)

# =========================================================
# CORS Middleware
# Allows Web App and Mobile App to connect
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# Logging Configuration
# =========================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smartwash")

# =========================================================
# Data Models
# =========================================================

class Machine(BaseModel):
    machine_id: int
    status: str
    current: float
    vibration: float
    last_updated: str


class Booking(BaseModel):
    booking_id: int
    student_name: str
    machine_id: int
    start_time: str
    end_time: str


class IoTUpdate(BaseModel):
    machine_id: int
    current: float
    vibration: float


# =========================================================
# Root Route
# =========================================================

@app.get("/")
def home():
    return {
        "message": "SmartWash Backend Running",
        "status": "active",
        "timestamp": datetime.datetime.now()
    }


# =========================================================
# Machine Routes
# =========================================================

@app.post("/machines/add")
def add_machine(machine: Machine):
    """
    Add a new washing machine to the system
    """

    machines_db[machine.machine_id] = machine
    logger.info(f"Machine {machine.machine_id} added")

    return {
        "message": "Machine added successfully",
        "machine": machine
    }


@app.get("/machines")
def get_all_machines():
    """
    Get all machines
    """

    return list(machines_db.values())


@app.get("/machines/{machine_id}")
def get_machine(machine_id: int):
    """
    Get single machine
    """

    if machine_id not in machines_db:
        raise HTTPException(status_code=404, detail="Machine not found")

    return machines_db[machine_id]


# =========================================================
# Booking Routes
# =========================================================

@app.post("/book")
def book_machine(booking: Booking):
    """
    Book a washing machine
    """

    if booking.machine_id not in machines_db:
        raise HTTPException(status_code=404, detail="Machine not found")

    bookings_db[booking.booking_id] = booking

    logger.info(f"Machine {booking.machine_id} booked by {booking.student_name}")

    return {
        "message": "Booking successful",
        "booking": booking
    }


@app.get("/bookings")
def get_bookings():
    """
    Get all bookings
    """

    return list(bookings_db.values())


# =========================================================
# IoT Update Route
# ESP32 will send sensor data here
# =========================================================

@app.post("/iot/update")
def iot_update(data: IoTUpdate):
    """
    ESP32 sends current and vibration data
    Backend classifies machine state
    """

    if data.machine_id not in machines_db:
        raise HTTPException(status_code=404, detail="Machine not found")

    # Machine state classification

    if data.current < 0.2:
        status = "available"

    elif data.current > 2 and data.vibration > 1:
        status = "running"

    elif data.current < 1:
        status = "cycle_done"

    else:
        status = "fault"

    machines_db[data.machine_id].status = status
    machines_db[data.machine_id].current = data.current
    machines_db[data.machine_id].vibration = data.vibration
    machines_db[data.machine_id].last_updated = str(datetime.datetime.now())

    logger.info(f"Machine {data.machine_id} updated: {status}")

    return {
        "machine_id": data.machine_id,
        "status": status
    }


# =========================================================
# AI Demand Prediction
# =========================================================

@app.get("/predict/demand")
def demand_prediction():
    """
    Predict best time to use laundry
    """

    # prediction = predict_demand()

    prediction = "Laundry is less busy between 10 AM and 12 PM"

    return {
        "prediction": prediction
    }


# =========================================================
# AI Anomaly Detection
# =========================================================

@app.get("/predict/anomaly/{machine_id}")
def anomaly_detection(machine_id: int):
    """
    Detect machine anomaly
    """

    if machine_id not in machines_db:
        raise HTTPException(status_code=404, detail="Machine not found")

    # result = detect_anomaly()

    result = "No anomaly detected"

    return {
        "machine_id": machine_id,
        "anomaly_status": result
    }


# =========================================================
# Health Check
# =========================================================

@app.get("/health")
def health():
    return {
        "server": "running",
        "time": datetime.datetime.now()
    }


# =========================================================
# Run Server
# =========================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )