"""
SmartWash — AI Demand Prediction Model
───────────────────────────────────────
Uses Facebook Prophet to forecast when the laundromat is busiest.

Input:  Usage logs from Firebase (fetched via /analytics/logs API endpoint)
Output: Hourly demand forecasts → "Best time" suggestions shown in student app

Run manually:  python demand_model.py
Deploy:        Schedule with cron (runs nightly, writes forecast back to Firebase)
"""

import os
import json
import logging
import requests
import pandas as pd
from datetime import datetime, timezone
from prophet import Prophet
import firebase_admin
from firebase_admin import credentials, db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smartwash.demand")

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
API_BASE_URL     = os.environ.get("API_BASE_URL", "http://localhost:5000")
FIREBASE_DB_URL  = os.environ.get("FIREBASE_DB_URL", "https://smartwash-default-rtdb.firebaseio.com")
SERVICE_ACCOUNT  = os.path.join(os.path.dirname(__file__), "..", "..", "serviceAccountKey.json")

FORECAST_HOURS   = 48   # Predict next 48 hours
MIN_LOGS_NEEDED  = 100  # Don't train if data is too sparse


# ═══════════════════════════════════════════════
# STEP 1: Fetch Usage Logs
# ═══════════════════════════════════════════════

def fetch_usage_logs(limit: int = 2000) -> pd.DataFrame:
    """
    Pull usage logs from the backend API.
    Each log is a machine state transition with a timestamp.
    We count 'running' transitions per hour as the demand signal.
    """
    logger.info(f"Fetching up to {limit} usage logs from API...")
    try:
        response = requests.get(f"{API_BASE_URL}/analytics/logs", params={"limit": limit}, timeout=10)
        response.raise_for_status()
        logs = response.json().get("logs", [])
        logger.info(f"Fetched {len(logs)} logs.")
    except requests.RequestException as e:
        logger.error(f"Failed to fetch logs: {e}")
        return pd.DataFrame()

    if not logs:
        return pd.DataFrame()

    df = pd.DataFrame(logs)
    # Only count 'running' state (a student started a wash) as demand events
    df = df[df["state"] == "running"].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    logger.info(f"{len(df)} 'running' events to train on.")
    return df


# ═══════════════════════════════════════════════
# STEP 2: Prepare Training Data
# ═══════════════════════════════════════════════

def prepare_prophet_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prophet expects a DataFrame with two columns:
      ds — datetime
      y  — value to forecast (number of wash starts per hour)
    """
    df["hour"] = df["timestamp"].dt.floor("h")
    hourly_counts = df.groupby("hour").size().reset_index(name="y")
    hourly_counts.rename(columns={"hour": "ds"}, inplace=True)

    # Fill in any missing hours with 0 (no usage = 0 demand)
    full_range = pd.date_range(
        start=hourly_counts["ds"].min(),
        end=hourly_counts["ds"].max(),
        freq="h", tz="UTC"
    )
    hourly_counts = hourly_counts.set_index("ds").reindex(full_range, fill_value=0)
    hourly_counts.index.name = "ds"
    hourly_counts = hourly_counts.reset_index()

    # Prophet requires timezone-naive datetimes
    hourly_counts["ds"] = hourly_counts["ds"].dt.tz_localize(None)

    logger.info(f"Training data: {len(hourly_counts)} hourly records from "
                f"{hourly_counts['ds'].min()} to {hourly_counts['ds'].max()}")
    return hourly_counts


# ═══════════════════════════════════════════════
# STEP 3: Train Prophet Model
# ═══════════════════════════════════════════════

def train_model(train_df: pd.DataFrame) -> Prophet:
    """
    Train a Prophet model with:
    - Daily seasonality (morning/evening peaks)
    - Weekly seasonality (weekends may differ)
    - Holidays disabled (hostel patterns don't follow public holidays)
    """
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,     # Not enough data yet
        holidays=None,
        changepoint_prior_scale=0.1,  # Moderate flexibility
        seasonality_prior_scale=10.0,
        interval_width=0.80,          # 80% confidence intervals
    )
    logger.info("Training Prophet model...")
    model.fit(train_df)
    logger.info("Training complete.")
    return model


# ═══════════════════════════════════════════════
# STEP 4: Generate Forecast
# ═══════════════════════════════════════════════

def generate_forecast(model: Prophet, hours: int = FORECAST_HOURS) -> pd.DataFrame:
    """
    Predict demand for the next `hours` hours.
    Returns a DataFrame with ds, yhat (predicted demand), and quiet/busy flags.
    """
    future = model.make_future_dataframe(periods=hours, freq="h")
    forecast = model.predict(future)

    # Only keep future predictions
    now = datetime.now()
    future_only = forecast[forecast["ds"] >= now][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    future_only["yhat"] = future_only["yhat"].clip(lower=0).round(2)

    # Classify each hour: "quiet", "moderate", "busy"
    q33 = future_only["yhat"].quantile(0.33)
    q66 = future_only["yhat"].quantile(0.66)

    def classify(y):
        if y <= q33:
            return "quiet"
        elif y <= q66:
            return "moderate"
        else:
            return "busy"

    future_only["demand_level"] = future_only["yhat"].apply(classify)
    future_only["ds"] = future_only["ds"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    logger.info(f"Generated {len(future_only)} hourly forecasts.")
    return future_only


# ═══════════════════════════════════════════════
# STEP 5: Best-Time Suggestion
# ═══════════════════════════════════════════════

def get_best_times(forecast_df: pd.DataFrame, top_n: int = 3) -> list:
    """
    Returns top N quiet windows in the next 24 hours.
    The student app shows these as "Best Time" suggestions.
    """
    next_24h = forecast_df.head(24)
    quiet = next_24h[next_24h["demand_level"] == "quiet"].head(top_n)

    suggestions = []
    for _, row in quiet.iterrows():
        dt = datetime.fromisoformat(row["ds"])
        suggestions.append({
            "time":         row["ds"],
            "display":      dt.strftime("%I:%M %p"),          # e.g., "10:00 AM"
            "day":          dt.strftime("%A"),                 # e.g., "Monday"
            "demand_level": row["demand_level"],
            "predicted_usage": float(row["yhat"]),
        })

    if not suggestions:
        # Fallback: just pick the lowest hour
        lowest = next_24h.nsmallest(1, "yhat").iloc[0]
        dt = datetime.fromisoformat(lowest["ds"])
        suggestions.append({
            "time":         lowest["ds"],
            "display":      dt.strftime("%I:%M %p"),
            "day":          dt.strftime("%A"),
            "demand_level": "moderate",
            "predicted_usage": float(lowest["yhat"]),
        })

    return suggestions


# ═══════════════════════════════════════════════
# STEP 6: Write Forecast to Firebase
# ═══════════════════════════════════════════════

def write_forecast_to_firebase(forecast_df: pd.DataFrame, suggestions: list):
    """
    Writes forecast results to Firebase so the student app can read them.
    Path: /ai_forecasts/demand/
    """
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})

    forecast_ref = db.reference("ai_forecasts/demand")
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "best_times":   suggestions,
        "hourly_forecast": forecast_df.to_dict(orient="records"),
    }
    forecast_ref.set(payload)
    logger.info("Forecast written to Firebase at /ai_forecasts/demand")


# ═══════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════

def run():
    logger.info("=== SmartWash Demand Prediction Pipeline ===")

    # 1. Fetch data
    raw_df = fetch_usage_logs(limit=2000)
    if raw_df.empty or len(raw_df) < MIN_LOGS_NEEDED:
        logger.warning(
            f"Not enough data to train ({len(raw_df)} events, need {MIN_LOGS_NEEDED}). "
            "Skipping. Re-run after more usage data accumulates (2–3 weeks)."
        )
        return

    # 2. Prepare
    train_df = prepare_prophet_df(raw_df)

    # 3. Train
    model = train_model(train_df)

    # 4. Forecast
    forecast_df = generate_forecast(model, hours=FORECAST_HOURS)

    # 5. Best times
    suggestions = get_best_times(forecast_df, top_n=3)
    logger.info("Best times to do laundry:")
    for s in suggestions:
        logger.info(f"  {s['day']} {s['display']} — {s['demand_level']} (predicted usage: {s['predicted_usage']:.1f})")

    # 6. Write to Firebase
    write_forecast_to_firebase(forecast_df, suggestions)

    logger.info("=== Pipeline complete ===")
    return {"forecast": forecast_df, "suggestions": suggestions}


if __name__ == "__main__":
    run()
