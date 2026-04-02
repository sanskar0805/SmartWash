"""
SmartWash — AI Anomaly Detection Model
────────────────────────────────────────
Uses scikit-learn's Isolation Forest to detect faulty machines
before they fully break down — by learning what "normal" looks like.

Input:  Streaming sensor readings (current_a, vibration) per machine
Output: Anomaly flag + fault confidence score → triggers admin alert via backend API

Two modes:
  1. TRAINING  — Learn normal behaviour from historical logs (run after 2+ weeks of data)
  2. INFERENCE — Score new readings in real-time (run continuously / called by backend)
"""

import os
import json
import pickle
import logging
import requests
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smartwash.anomaly")

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
API_BASE_URL     = os.environ.get("API_BASE_URL", "http://localhost:5000")
MODEL_DIR        = os.path.join(os.path.dirname(__file__), "models")
CONTAMINATION    = 0.05   # Assume ~5% of historical readings were anomalous
RANDOM_STATE     = 42
N_ESTIMATORS     = 100    # IsolationForest trees

os.makedirs(MODEL_DIR, exist_ok=True)


# ═══════════════════════════════════════════════
# FEATURE ENGINEERING
# ═══════════════════════════════════════════════

def extract_features(logs: list[dict]) -> pd.DataFrame:
    """
    Convert raw sensor logs into features for the model.

    Features per reading:
      - current_a           : raw current draw in amperes
      - vibration_int       : 1 = vibrating, 0 = idle
      - hour_of_day         : 0–23 (captures time-of-day patterns)
      - current_rolling_std : stddev of last 5 readings (detect instability)
    """
    df = pd.DataFrame(logs)
    df["timestamp"]    = pd.to_datetime(df["timestamp"])
    df["vibration_int"] = df["vibration"].astype(int)
    df["hour_of_day"]  = df["timestamp"].dt.hour
    df["current_a"]    = pd.to_numeric(df["current_a"], errors="coerce").fillna(0.0)

    # Rolling standard deviation (instability signal)
    df = df.sort_values("timestamp")
    df["current_rolling_std"] = df["current_a"].rolling(window=5, min_periods=1).std().fillna(0.0)

    features = ["current_a", "vibration_int", "hour_of_day", "current_rolling_std"]
    return df[features].dropna()


# ═══════════════════════════════════════════════
# TRAINING
# ═══════════════════════════════════════════════

def fetch_training_logs(machine_id: str, limit: int = 3000) -> list:
    """Fetch historical sensor logs for a specific machine from the backend."""
    logger.info(f"Fetching training logs for machine {machine_id}...")
    try:
        response = requests.get(
            f"{API_BASE_URL}/analytics/logs",
            params={"limit": limit},
            timeout=10
        )
        response.raise_for_status()
        all_logs = response.json().get("logs", [])
        machine_logs = [l for l in all_logs if l.get("machine_id") == machine_id]
        logger.info(f"Got {len(machine_logs)} logs for {machine_id}.")
        return machine_logs
    except requests.RequestException as e:
        logger.error(f"Failed to fetch logs: {e}")
        return []


def train(machine_id: str) -> Pipeline:
    """
    Train an Isolation Forest model on the normal behaviour of machine_id.
    Saves the trained model to disk (models/{machine_id}_anomaly_model.pkl).
    """
    logs = fetch_training_logs(machine_id)
    if len(logs) < 50:
        raise ValueError(
            f"Not enough data to train anomaly model for {machine_id} "
            f"({len(logs)} logs, need at least 50). "
            "Run again after more data is collected."
        )

    # Only train on 'available' and 'running' states — the healthy baseline
    normal_logs = [l for l in logs if l.get("state") in ("available", "running")]
    logger.info(f"Training on {len(normal_logs)} normal readings.")

    features_df = extract_features(normal_logs)

    # Pipeline: standardise → IsolationForest
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("iforest", IsolationForest(
            n_estimators=N_ESTIMATORS,
            contamination=CONTAMINATION,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )),
    ])
    model.fit(features_df)

    # Save model
    model_path = os.path.join(MODEL_DIR, f"{machine_id}_anomaly_model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    logger.info(f"Model trained and saved: {model_path}")
    return model


def load_model(machine_id: str) -> Pipeline | None:
    """Load a saved anomaly model for the given machine_id."""
    model_path = os.path.join(MODEL_DIR, f"{machine_id}_anomaly_model.pkl")
    if not os.path.exists(model_path):
        logger.warning(f"No model found for {machine_id} at {model_path}. Train first.")
        return None
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    logger.info(f"Loaded anomaly model for {machine_id}.")
    return model


# ═══════════════════════════════════════════════
# INFERENCE
# ═══════════════════════════════════════════════

def score_reading(
    machine_id: str,
    current_a: float,
    vibration: bool,
    recent_readings: list[dict] | None = None,
) -> dict:
    """
    Score a single new sensor reading for anomaly.

    Args:
        machine_id:       Which machine (e.g., "M1")
        current_a:        Current draw in amperes
        vibration:        Whether drum vibration detected
        recent_readings:  Last 5 readings for rolling std computation (optional)

    Returns:
        {
            "machine_id":        "M1",
            "is_anomaly":        True/False,
            "anomaly_score":     float (-1.0 to 0.0; more negative = more anomalous),
            "fault_confidence":  float (0.0 to 1.0),
            "timestamp":         ISO 8601,
        }
    """
    model = load_model(machine_id)
    if model is None:
        return {
            "machine_id":       machine_id,
            "is_anomaly":       False,
            "anomaly_score":    0.0,
            "fault_confidence": 0.0,
            "error":            "Model not trained yet",
            "timestamp":        datetime.utcnow().isoformat(),
        }

    # Build feature vector
    now = datetime.utcnow()
    # Rolling std from recent readings (or 0 if not provided)
    rolling_std = 0.0
    if recent_readings and len(recent_readings) >= 2:
        currents = [r.get("current_a", 0.0) for r in recent_readings[-5:]] + [current_a]
        rolling_std = float(np.std(currents))

    features = pd.DataFrame([{
        "current_a":            current_a,
        "vibration_int":        int(vibration),
        "hour_of_day":          now.hour,
        "current_rolling_std":  rolling_std,
    }])

    # IsolationForest: predict returns 1 (normal) or -1 (anomaly)
    prediction    = model.predict(features)[0]
    raw_score     = model.decision_function(features)[0]  # More negative = more anomalous

    is_anomaly = prediction == -1
    # Normalize score to 0–1 confidence (heuristic: clamp raw_score to [-0.5, 0.5])
    fault_confidence = float(np.clip((-raw_score + 0.5) / 1.0, 0.0, 1.0))

    result = {
        "machine_id":       machine_id,
        "is_anomaly":       bool(is_anomaly),
        "anomaly_score":    float(raw_score),
        "fault_confidence": round(fault_confidence, 3),
        "timestamp":        now.isoformat(),
    }

    if is_anomaly:
        logger.warning(
            f"[{machine_id}] ANOMALY DETECTED | current={current_a:.2f}A | "
            f"vib={vibration} | confidence={fault_confidence:.0%}"
        )

    return result


def report_fault_if_anomaly(score_result: dict, confidence_threshold: float = 0.7):
    """
    If anomaly confidence exceeds threshold, report fault to backend.
    The backend will then update Firebase and notify admin.
    """
    if not score_result.get("is_anomaly"):
        return
    if score_result.get("fault_confidence", 0) < confidence_threshold:
        return

    machine_id = score_result["machine_id"]
    logger.info(f"[{machine_id}] Reporting fault to backend (AI-detected)...")

    try:
        response = requests.post(
            f"{API_BASE_URL}/machines/{machine_id}/status",
            json={
                "state":      "fault",
                "fault_code": "SENSOR_ANOMALY",
                "current_a":  None,
                "vibration":  None,
            },
            timeout=5,
        )
        response.raise_for_status()
        logger.info(f"[{machine_id}] Fault reported successfully.")
    except requests.RequestException as e:
        logger.error(f"[{machine_id}] Failed to report fault: {e}")


# ═══════════════════════════════════════════════
# BATCH SCORING (for streaming use)
# ═══════════════════════════════════════════════

def score_batch(machine_id: str, readings: list[dict]) -> list[dict]:
    """
    Score a batch of readings at once.
    readings: list of {"current_a": float, "vibration": bool, "timestamp": str}
    """
    results = []
    window = []
    for reading in readings:
        result = score_reading(
            machine_id=machine_id,
            current_a=reading.get("current_a", 0.0),
            vibration=bool(reading.get("vibration", False)),
            recent_readings=window,
        )
        results.append(result)
        window.append(reading)
        if len(window) > 10:
            window.pop(0)
    return results


# ═══════════════════════════════════════════════
# MAIN — Training Mode
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    # Usage: python anomaly_detection.py train M1 M2 M3
    #        python anomaly_detection.py score M1 3.2 true

    args = sys.argv[1:]
    mode = args[0] if args else "train"

    if mode == "train":
        machines = args[1:] if len(args) > 1 else ["M1", "M2", "M3"]
        for mid in machines:
            logger.info(f"=== Training anomaly model for {mid} ===")
            try:
                train(mid)
            except ValueError as e:
                logger.warning(str(e))

    elif mode == "score":
        if len(args) < 4:
            print("Usage: python anomaly_detection.py score <machine_id> <current_a> <vibration>")
            sys.exit(1)
        mid       = args[1]
        current   = float(args[2])
        vibration = args[3].lower() in ("true", "1", "yes")
        result    = score_reading(mid, current, vibration)
        print(json.dumps(result, indent=2))
        report_fault_if_anomaly(result)

    else:
        print(f"Unknown mode: {mode}. Use 'train' or 'score'.")
        sys.exit(1)
