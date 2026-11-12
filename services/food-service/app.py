"""Food service: owns food inventory items and their expiry dates."""
import os
from datetime import date, datetime, timedelta, timezone

from flask import Flask, jsonify, request

import db

app = Flask(__name__)

EXPIRING_SOON_DAYS = int(os.getenv("EXPIRING_SOON_DAYS", "2"))


def to_date(v):
    return v if isinstance(v, date) and not isinstance(v, datetime) else date.fromisoformat(str(v)[:10])


def item_out(row):
    expiry = to_date(row["expiry_date"])
    days_left = (expiry - date.today()).days
    status = "expired" if days_left < 0 else "expiring_soon" if days_left <= EXPIRING_SOON_DAYS else "safe"
    return {"id": row["id"], "name": row["name"], "unit_id": row["unit_id"],
            "expiry_date": expiry.isoformat(), "days_left": days_left, "status": status}


def init_db():
    db.init([
        """CREATE TABLE IF NOT EXISTS items (
               id SERIAL PRIMARY KEY,
               name TEXT NOT NULL,
               unit_id TEXT NOT NULL,
               expiry_date DATE NOT NULL,
               created_at TIMESTAMPTZ NOT NULL
           )""",
    ])
    if os.getenv("SEED_DEMO_DATA", "true").lower() == "true":
        seed_demo_data()


def seed_demo_data():
    if db.run("SELECT COUNT(*) AS n FROM items", fetch="one")["n"]:
        return
    today = date.today()
    demo = [("Chicken", "fridge-1", 3), ("Beef", "fridge-1", 5),
            ("Fish", "fridge-2", 1), ("Ice Cream", "freezer-1", 30)]
    now = datetime.now(timezone.utc).isoformat()
    for name, unit_id, days in demo:
        db.run("INSERT INTO items (name, unit_id, expiry_date, created_at) VALUES (%s, %s, %s, %s)",
               (name, unit_id, (today + timedelta(days=days)).isoformat(), now), fetch=None)
    print("[food-service] demo items seeded", flush=True)


@app.get("/health")
def health():
    db.run("SELECT 1", fetch="one")
    return jsonify(status="ok", service="food-service")


@app.get("/items")
def list_items():
    rows = db.run("SELECT * FROM items ORDER BY expiry_date ASC, id ASC")
    return jsonify([item_out(r) for r in rows])


@app.post("/items")
def add_item():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    unit_id = str(data.get("unit_id", "")).strip()
    if not name or len(name) > 100:
        return jsonify(error="name is required (max 100 characters)"), 400
    if not unit_id or len(unit_id) > 50:
        return jsonify(error="unit_id is required"), 400
    try:
        expiry = date.fromisoformat(str(data.get("expiry_date", "")))
    except ValueError:
        return jsonify(error="expiry_date must be YYYY-MM-DD"), 400
    row = db.run("INSERT INTO items (name, unit_id, expiry_date, created_at) "
                 "VALUES (%s, %s, %s, %s) RETURNING *",
                 (name, unit_id, expiry.isoformat(), datetime.now(timezone.utc).isoformat()), fetch="one")
    return jsonify(item_out(row)), 201


@app.delete("/items/<int:item_id>")
def delete_item(item_id):
    row = db.run("DELETE FROM items WHERE id = %s RETURNING id", (item_id,), fetch="one")
    if not row:
        return jsonify(error="item not found"), 404
    return jsonify(deleted=item_id)


init_db()
