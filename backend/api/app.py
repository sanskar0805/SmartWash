"""
SmartWash — Cloud Backend API
Flask REST API + Firebase Realtime Database integration
Handles: machine status, slot booking, notifications, admin dashboard
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db, messaging
from datetime import datetime, timedelta
import os
import logging

# ─────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smartwash")

# Firebase init — download serviceAccountKey.json from:
# Firebase Console → Project Settings → Service Accounts → Generate New Private Key
cred = credentials.Certificate(
    os.path.join(os.path.dirname(__file__), "..", "..", "serviceAccountKey.json")
)
firebase_admin.initialize_app(cred, {
    "databaseURL": os.environ.get(
        "FIREBASE_DB_URL", "https://smartwash-default-rtdb.firebaseio.com"
    )
})

machines_ref = db.reference("machines")
bookings_ref  = db.reference("bookings")
users_ref     = db.reference("users")
logs_ref      = db.reference("usage_logs")

# ─────────────────────────────────────────────
# Machine State Constants
# ─────────────────────────────────────────────
VALID_STATES = {"available", "running", "cycle_done", "fault"}
AVG_CYCLE_MINUTES = 45


# ═══════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "SmartWash API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    })


# ═══════════════════════════════════════════════
# MACHINE ENDPOINTS
# ═══════════════════════════════════════════════

@app.route("/machines", methods=["GET"])
def get_all_machines():
    """Return live status of all machines. Used by the student app home screen."""
    data = machines_ref.get() or {}
    machines = []
    for machine_id, info in data.items():
        machines.append({
            "machine_id":    machine_id,
            "state":         info.get("state", "unknown"),
            "current_user":  info.get("current_user"),
            "cycle_start":   info.get("cycle_start"),
            "estimated_end": info.get("estimated_end"),
            "fault_code":    info.get("fault_code"),
            "last_updated":  info.get("last_updated"),
        })
    return jsonify({"machines": machines, "count": len(machines)})


@app.route("/machines/<machine_id>", methods=["GET"])
def get_machine(machine_id):
    """Return status of a single machine."""
    data = machines_ref.child(machine_id).get()
    if not data:
        return jsonify({"error": "Machine not found"}), 404
    return jsonify({"machine_id": machine_id, **data})


@app.route("/machines/<machine_id>/status", methods=["POST"])
def update_machine_status(machine_id):
    """
    Called by IoT node (ESP32) every 30 seconds or immediately on state change.

    Request body:
    {
        "state":      "running",    # available | running | cycle_done | fault
        "current_a":  3.2,          # current draw in amperes
        "vibration":  true,         # boolean — is drum spinning?
        "fault_code": null          # fault code string, or null
    }
    """
    body = request.get_json()
    if not body:
        return jsonify({"error": "No JSON body provided"}), 400

    state = body.get("state", "").lower()
    if state not in VALID_STATES:
        return jsonify({"error": f"Invalid state '{state}'. Must be one of: {VALID_STATES}"}), 400

    now = datetime.utcnow().isoformat()
    update = {
        "state":        state,
        "current_a":    body.get("current_a"),
        "vibration":    body.get("vibration"),
        "fault_code":   body.get("fault_code"),
        "last_updated": now,
    }

    # If cycle just started → compute estimated end time
    if state == "running":
        cycle_start = now
        update["cycle_start"]   = cycle_start
        update["estimated_end"] = (
            datetime.fromisoformat(cycle_start) + timedelta(minutes=AVG_CYCLE_MINUTES)
        ).isoformat()
        update["fault_code"] = None  # clear any previous fault

    # If cycle done → push notification to student, free the slot
    if state == "cycle_done":
        _notify_cycle_done(machine_id)
        update["cycle_start"]   = None
        update["estimated_end"] = None

    # If fault → alert admin
    if state == "fault":
        _notify_admin_fault(machine_id, body.get("fault_code", "SENSOR_ANOMALY"))

    # If now available → clear user
    if state == "available":
        update["current_user"]  = None
        update["cycle_start"]   = None
        update["estimated_end"] = None
        update["fault_code"]    = None

    machines_ref.child(machine_id).update(update)

    # Log every state transition for AI model training
    logs_ref.push({
        "machine_id": machine_id,
        "state":      state,
        "current_a":  body.get("current_a"),
        "timestamp":  now,
    })

    logger.info(f"[{machine_id}] State → {state}")
    return jsonify({"success": True, "machine_id": machine_id, "state": state})


# ═══════════════════════════════════════════════
# BOOKING ENDPOINTS
# ═══════════════════════════════════════════════

@app.route("/bookings", methods=["POST"])
def create_booking():
    """
    Student books a machine slot.

    Request body:
    {
        "machine_id":   "M1",
        "student_id":   "stu_001",
        "student_name": "Rahul",
        "fcm_token":    "<Firebase Cloud Messaging token>",
        "slot_time":    "2026-03-15T10:00:00"   # ISO 8601
    }
    """
    body = request.get_json()
    if not body:
        return jsonify({"error": "No JSON body"}), 400

    required = ["machine_id", "student_id", "slot_time", "fcm_token"]
    for field in required:
        if field not in body:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    machine_id  = body["machine_id"]
    student_id  = body["student_id"]
    slot_time   = body["slot_time"]
    fcm_token   = body["fcm_token"]

    # Validate machine exists and isn't faulty
    machine = machines_ref.child(machine_id).get()
    if not machine:
        return jsonify({"error": f"Machine '{machine_id}' not found"}), 404
    if machine.get("state") == "fault":
        return jsonify({"error": "Cannot book a faulty machine. Try another."}), 400

    # Check for slot conflict
    existing = bookings_ref.order_by_child("machine_id").equal_to(machine_id).get() or {}
    for _, booking in existing.items():
        if booking.get("slot_time") == slot_time and booking.get("status") == "active":
            return jsonify({"error": "This slot is already taken. Choose a different time."}), 409

    # Create booking
    booking_data = {
        "machine_id":   machine_id,
        "student_id":   student_id,
        "student_name": body.get("student_name", "Student"),
        "fcm_token":    fcm_token,
        "slot_time":    slot_time,
        "status":       "active",
        "created_at":   datetime.utcnow().isoformat(),
    }
    new_booking = bookings_ref.push(booking_data)

    # Store FCM token for future notifications
    users_ref.child(student_id).update({
        "fcm_token":    fcm_token,
        "student_id":   student_id,
        "student_name": body.get("student_name", "Student"),
    })

    logger.info(f"Booking created: {new_booking.key} | {student_id} → {machine_id} @ {slot_time}")
    return jsonify({
        "success":    True,
        "booking_id": new_booking.key,
        **booking_data
    }), 201


@app.route("/bookings/<machine_id>", methods=["GET"])
def get_machine_queue(machine_id):
    """
    Get the queue (active bookings) for a machine.
    Used in the Machine Detail screen.
    """
    all_bookings = bookings_ref.order_by_child("machine_id").equal_to(machine_id).get() or {}
    queue = [
        {"booking_id": k, **v}
        for k, v in all_bookings.items()
        if v.get("status") == "active"
    ]
    queue.sort(key=lambda x: x.get("slot_time", ""))
    return jsonify({
        "machine_id":   machine_id,
        "queue":        queue,
        "queue_length": len(queue),
    })


@app.route("/bookings/<booking_id>/cancel", methods=["POST"])
def cancel_booking(booking_id):
    """Cancel a specific booking."""
    booking = bookings_ref.child(booking_id).get()
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
    bookings_ref.child(booking_id).update({
        "status":       "cancelled",
        "cancelled_at": datetime.utcnow().isoformat(),
    })
    return jsonify({"success": True, "booking_id": booking_id})


# ═══════════════════════════════════════════════
# FAULT REPORTING (Student → Admin)
# ═══════════════════════════════════════════════

@app.route("/machines/<machine_id>/report_fault", methods=["POST"])
def report_fault(machine_id):
    """
    One-tap fault report from student app.

    Request body:
    {
        "student_id":  "stu_001",
        "description": "Machine shaking loudly and not stopping"
    }
    """
    body = request.get_json() or {}

    fault_data = {
        "machine_id":  machine_id,
        "reported_by": body.get("student_id", "anonymous"),
        "description": body.get("description", "Fault reported via app (no description)"),
        "reported_at": datetime.utcnow().isoformat(),
        "resolved":    False,
    }
    db.reference("fault_reports").push(fault_data)
    machines_ref.child(machine_id).update({
        "state":      "fault",
        "fault_code": "USER_REPORT",
    })
    _notify_admin_fault(machine_id, "USER_REPORT")

    return jsonify({
        "success": True,
        "message": "Fault reported. The hostel admin has been notified.",
    })


# ═══════════════════════════════════════════════
# ANALYTICS (Admin Dashboard)
# ═══════════════════════════════════════════════

@app.route("/analytics/usage", methods=["GET"])
def usage_analytics():
    """
    Summary stats for admin dashboard.
    The AI demand model reads /usage_logs directly from Firebase.
    """
    all_bookings = bookings_ref.get() or {}
    total     = len(all_bookings)
    active    = sum(1 for b in all_bookings.values() if b.get("status") == "active")
    completed = sum(1 for b in all_bookings.values() if b.get("status") == "completed")
    cancelled = sum(1 for b in all_bookings.values() if b.get("status") == "cancelled")

    all_machines = machines_ref.get() or {}
    fault_count  = sum(1 for m in all_machines.values() if m.get("state") == "fault")

    return jsonify({
        "total_bookings":    total,
        "active_bookings":   active,
        "completed_bookings": completed,
        "cancelled_bookings": cancelled,
        "machines_in_fault": fault_count,
        "generated_at":      datetime.utcnow().isoformat(),
    })


@app.route("/analytics/logs", methods=["GET"])
def get_usage_logs():
    """
    Returns raw usage logs for the AI demand prediction model.
    Optional query param: ?limit=500
    """
    limit = int(request.args.get("limit", 500))
    all_logs = logs_ref.order_by_child("timestamp").limit_to_last(limit).get() or {}
    logs = [{"log_id": k, **v} for k, v in all_logs.items()]
    return jsonify({"logs": logs, "count": len(logs)})


# ═══════════════════════════════════════════════
# NOTIFICATION HELPERS (Internal)
# ═══════════════════════════════════════════════

def _notify_cycle_done(machine_id: str):
    """
    Send FCM push notification to the student whose cycle just finished.
    Marks their booking as 'completed'.
    """
    try:
        all_bookings = bookings_ref.order_by_child("machine_id").equal_to(machine_id).get() or {}
        for booking_id, booking in all_bookings.items():
            if booking.get("status") != "active":
                continue
            token = booking.get("fcm_token")
            if not token:
                continue

            message = messaging.Message(
                notification=messaging.Notification(
                    title="✅ Laundry Done!",
                    body=f"Your wash in {machine_id} is complete. Collect within 10 minutes!",
                ),
                data={"machine_id": machine_id, "action": "collect"},
                token=token,
            )
            messaging.send(message)
            bookings_ref.child(booking_id).update({
                "status":       "completed",
                "completed_at": datetime.utcnow().isoformat(),
            })
            logger.info(f"Cycle done notification sent for {machine_id} → {booking_id}")
    except Exception as e:
        logger.error(f"Notification error (cycle_done {machine_id}): {e}")


def _notify_admin_fault(machine_id: str, fault_code: str):
    """
    Broadcast fault alert to the 'smartwash_admin' FCM topic.
    All admin devices subscribed to this topic will receive the alert.
    """
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title="⚠️ Machine Fault — SmartWash",
                body=f"{machine_id} is flagged faulty (Code: {fault_code}). Please inspect.",
            ),
            data={"machine_id": machine_id, "fault_code": fault_code},
            topic="smartwash_admin",
        )
        messaging.send(message)
        logger.info(f"Admin fault alert sent: {machine_id} [{fault_code}]")
    except Exception as e:
        logger.error(f"Notification error (fault {machine_id}): {e}")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
