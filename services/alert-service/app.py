"""Alert service: stateless. Calls temperature-service and food-service and turns their data into alerts."""
import os
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, jsonify

app = Flask(__name__)

TEMP_URL = os.getenv("TEMPERATURE_SERVICE_URL", "http://temperature-service:5001")
FOOD_URL = os.getenv("FOOD_SERVICE_URL", "http://food-service:5002")
STALE_HOURS = float(os.getenv("STALE_READING_HOURS", "24"))
TIMEOUT = 3
RANK = {"danger": 0, "warning": 1}


def fetch(url):
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def temperature_alerts(units):
    out = []
    now = datetime.now(timezone.utc)
    for u in units:
        r = u["latest"]
        if r is None:
            out.append({"type": "temperature", "level": "warning", "source": u["name"],
                        "title": "NO TEMPERATURE DATA",
                        "message": f"{u['name']} has no readings yet. Record a temperature."})
            continue
        if r["status"] in RANK:
            word = "HIGH TEMPERATURE" if u["kind"] != "hot" else "FOOD TOO COOL"
            out.append({"type": "temperature", "level": r["status"], "source": u["name"],
                        "title": word if r["status"] == "danger" else "TEMPERATURE WARNING",
                        "message": f"{u['name']} is at {r['value']:.1f}°C, outside the safe range."})
        if now - parse_ts(r["recorded_at"]).astimezone(timezone.utc) > timedelta(hours=STALE_HOURS):
            out.append({"type": "temperature", "level": "warning", "source": u["name"],
                        "title": "STALE READING",
                        "message": f"{u['name']} has not been checked for over {STALE_HOURS:g} hours."})
    return out


def food_alerts(items):
    out = []
    for i in items:
        d = i["days_left"]
        if i["status"] == "expired":
            when = "yesterday" if d == -1 else f"{-d} days ago"
            out.append({"type": "expiry", "level": "danger", "source": i["name"],
                        "title": "FOOD EXPIRED", "message": f"{i['name']} expired {when}. Remove it from storage."})
        elif i["status"] == "expiring_soon":
            when = "today" if d == 0 else "tomorrow" if d == 1 else f"in {d} days"
            out.append({"type": "expiry", "level": "warning", "source": i["name"],
                        "title": "EXPIRY WARNING", "message": f"{i['name']} expires {when}."})
    return out


@app.get("/health")
def health():
    return jsonify(status="ok", service="alert-service")


@app.get("/alerts")
def alerts():
    alerts, degraded = [], []
    for label, url, builder in (("temperature-service", f"{TEMP_URL}/units", temperature_alerts),
                                ("food-service", f"{FOOD_URL}/items", food_alerts)):
        try:
            alerts += builder(fetch(url))
        except Exception as exc:  # one broken dependency must not break the whole endpoint
            print(f"[alert-service] {label} unavailable: {exc}", flush=True)
            degraded.append(label)
    alerts.sort(key=lambda a: RANK[a["level"]])
    if len(degraded) == 2:
        overall = "UNKNOWN"
    elif any(a["level"] == "danger" for a in alerts):
        overall = "DANGER"
    elif alerts:
        overall = "WARNING"
    else:
        overall = "SAFE"
    return jsonify(overall=overall, alerts=alerts, degraded=degraded)
