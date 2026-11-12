"""Report service: stateless. Builds summaries and CSV exports from the other services."""
import csv
import io
import os
from datetime import datetime

import requests
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

TEMP_URL = os.getenv("TEMPERATURE_SERVICE_URL", "http://temperature-service:5001")
FOOD_URL = os.getenv("FOOD_SERVICE_URL", "http://food-service:5002")
TIMEOUT = 5


def fetch(url, **params):
    r = requests.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def days_arg():
    try:
        return min(max(int(request.args.get("days", 7)), 1), 90)
    except ValueError:
        return 7


@app.errorhandler(requests.RequestException)
def upstream_down(exc):
    print(f"[report-service] upstream error: {exc}", flush=True)
    return jsonify(error="a required service is unavailable, try again shortly"), 502


@app.get("/health")
def health():
    return jsonify(status="ok", service="report-service")


@app.get("/summary")
def summary():
    days = days_arg()
    units = fetch(f"{TEMP_URL}/units")
    readings = fetch(f"{TEMP_URL}/readings", hours=days * 24, limit=5000)
    items = fetch(f"{FOOD_URL}/items")

    per_unit = []
    for u in units:
        rs = [r for r in readings if r["unit_id"] == u["id"]]
        vals = [r["value"] for r in rs]
        per_unit.append({
            "unit_id": u["id"], "name": u["name"], "readings": len(rs),
            "min": min(vals) if vals else None, "max": max(vals) if vals else None,
            "avg": round(sum(vals) / len(vals), 1) if vals else None,
            "warnings": sum(r["status"] == "warning" for r in rs),
            "critical": sum(r["status"] == "danger" for r in rs),
        })
    total = len(readings)
    normal = sum(r["status"] == "normal" for r in readings)
    return jsonify({
        "period_days": days,
        "monitored_units": len(units),
        "total_readings": total,
        "normal_percent": round(100 * normal / total, 1) if total else None,
        "warning_events": sum(r["status"] == "warning" for r in readings),
        "critical_events": sum(r["status"] == "danger" for r in readings),
        "food": {"total": len(items),
                 "expired": sum(i["status"] == "expired" for i in items),
                 "expiring_soon": sum(i["status"] == "expiring_soon" for i in items)},
        "units": per_unit,
    })


@app.get("/export.csv")
def export_csv():
    days = days_arg()
    readings = fetch(f"{TEMP_URL}/readings", hours=days * 24, limit=5000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["recorded_at", "unit", "temperature_c", "status"])
    for r in reversed(readings):
        w.writerow([r["recorded_at"], r["unit_name"], r["value"], r["status"]])
    name = f"foodsafe-readings-{datetime.now():%Y%m%d}.csv"
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}"})
