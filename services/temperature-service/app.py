"""Temperature service: owns storage units and temperature readings."""
import math
import os
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request

import db

app = Flask(__name__)

# Storage units this service knows about. kind decides which safe range applies.
UNITS = {
    "fridge-1": {"name": "Refrigerator 1", "icon": "❄️", "kind": "cold", "base": 3.8},
    "fridge-2": {"name": "Refrigerator 2", "icon": "❄️", "kind": "cold", "base": 6.8},
    "freezer-1": {"name": "Freezer 1", "icon": "🧊", "kind": "freezer", "base": -18.0},
    "cold-storage": {"name": "Cold Storage", "icon": "🥶", "kind": "cold", "base": 4.1},
    "hot-food": {"name": "Hot Food", "icon": "🔥", "kind": "hot", "base": 63.0},
}
MIN_VALUE, MAX_VALUE = -50.0, 150.0


def classify(kind, value):
    """Return normal | warning | danger for a reading."""
    if kind == "cold":      # fridge: <=5 ok, >5 warning, >7 danger
        return "danger" if value > 7 else "warning" if value > 5 else "normal"
    if kind == "freezer":   # freezer: <=-15 ok, >-15 warning, >-12 danger
        return "danger" if value > -12 else "warning" if value > -15 else "normal"
    # hot holding: >=60 ok, <60 warning, <55 danger
    return "danger" if value < 55 else "warning" if value < 60 else "normal"


def iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def reading_out(row):
    unit = UNITS[row["unit_id"]]
    value = float(row["value"])
    return {
        "id": row["id"],
        "unit_id": row["unit_id"],
        "unit_name": unit["name"],
        "value": round(value, 1),
        "status": classify(unit["kind"], value),
        "recorded_at": iso(row["recorded_at"]),
    }


def init_db():
    db.init([
        """CREATE TABLE IF NOT EXISTS readings (
               id SERIAL PRIMARY KEY,
               unit_id TEXT NOT NULL,
               value DOUBLE PRECISION NOT NULL,
               recorded_at TIMESTAMPTZ NOT NULL
           )""",
        "CREATE INDEX IF NOT EXISTS idx_readings_unit_time ON readings (unit_id, recorded_at)",
    ])
    if os.getenv("SEED_DEMO_DATA", "true").lower() == "true":
        seed_demo_data()


def seed_demo_data():
    """Give a fresh install some history so the dashboard is not empty."""
    if db.run("SELECT COUNT(*) AS n FROM readings", fetch="one")["n"]:
        return
    wobble = [0.3, -0.2, 0.5, -0.4, 0.2, -0.1, 0.4, 0.0]  # last point = exact base value
    now = datetime.now(timezone.utc)
    for unit_id, unit in UNITS.items():
        for i, w in enumerate(wobble):
            ts = now - timedelta(hours=3 * (len(wobble) - 1 - i))
            db.run("INSERT INTO readings (unit_id, value, recorded_at) VALUES (%s, %s, %s)",
                   (unit_id, unit["base"] + w, ts.isoformat()), fetch=None)
    print("[temperature-service] demo readings seeded", flush=True)


@app.get("/health")
def health():
    db.run("SELECT 1", fetch="one")
    return jsonify(status="ok", service="temperature-service")


@app.get("/units")
def units():
    out = []
    for unit_id, unit in UNITS.items():
        row = db.run("SELECT * FROM readings WHERE unit_id = %s ORDER BY recorded_at DESC, id DESC LIMIT 1",
                     (unit_id,), fetch="one")
        out.append({"id": unit_id, "name": unit["name"], "icon": unit["icon"], "kind": unit["kind"],
                    "latest": reading_out(row) if row else None})
    return jsonify(out)


@app.get("/readings")
def list_readings():
    unit_id = request.args.get("unit_id")
    if unit_id and unit_id not in UNITS:
        return jsonify(error="unknown unit_id"), 404
    try:
        hours = min(max(float(request.args.get("hours", 24)), 0.1), 24 * 90)
        limit = min(max(int(request.args.get("limit", 500)), 1), 5000)
    except ValueError:
        return jsonify(error="hours and limit must be numbers"), 400
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    if unit_id:
        rows = db.run("SELECT * FROM readings WHERE unit_id = %s AND recorded_at >= %s "
                      "ORDER BY recorded_at DESC, id DESC LIMIT %s", (unit_id, since, limit))
    else:
        rows = db.run("SELECT * FROM readings WHERE recorded_at >= %s "
                      "ORDER BY recorded_at DESC, id DESC LIMIT %s", (since, limit))
    return jsonify([reading_out(r) for r in rows])


@app.post("/readings")
def add_reading():
    data = request.get_json(silent=True) or {}
    unit_id = data.get("unit_id")
    if unit_id not in UNITS:
        return jsonify(error="unknown unit_id"), 400
    try:
        value = float(data.get("value"))
    except (TypeError, ValueError):
        return jsonify(error="value must be a number"), 400
    if not math.isfinite(value) or not MIN_VALUE <= value <= MAX_VALUE:
        return jsonify(error=f"value must be between {MIN_VALUE:g} and {MAX_VALUE:g} °C"), 400
    row = db.run("INSERT INTO readings (unit_id, value, recorded_at) VALUES (%s, %s, %s) RETURNING *",
                 (unit_id, round(value, 1), datetime.now(timezone.utc).isoformat()), fetch="one")
    return jsonify(reading_out(row)), 201


init_db()
