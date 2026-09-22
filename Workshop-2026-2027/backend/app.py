"""Backend BiOrbite : pont MQTT -> SQLite + API web + dashboard.

Lancement (depuis backend/, environnement virtuel active) :
    python app.py
puis ouvrir http://127.0.0.1:5000
"""

import csv
import io
import logging

from flask import Flask, Response, jsonify, request

import db
from config import (
    GRAFANA_AIR_URL,
    GRAFANA_LIGHT_URL,
    GRAFANA_OVERVIEW_URL,
    GRAFANA_SOIL_URL,
    HTTP_HOST,
    HTTP_PORT,
)
from mqtt_bridge import Bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

app = Flask(__name__, static_folder="static", static_url_path="")
bridge = Bridge()

METRICS = {"soil", "soil_raw", "temp", "humidity", "lux"}


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/status")
def status():
    """Derniere valeur de chaque topic + etat de la connexion au broker."""
    return jsonify(bridge.snapshot())


@app.get("/api/history")
def history():
    metric = request.args.get("metric", "soil")
    if metric not in METRICS:
        return jsonify(error=f"metric doit etre parmi {sorted(METRICS)}"), 400
    hours = min(max(request.args.get("hours", 6, type=float), 0.1), 168)
    return jsonify(metric=metric, hours=hours, points=db.history(metric, hours))


@app.get("/api/grafana")
def grafana():
    """URLs d'embed Grafana pour le dashboard de controle."""
    panels = {
        "soil": GRAFANA_SOIL_URL,
        "air": GRAFANA_AIR_URL,
        "light": GRAFANA_LIGHT_URL,
        "overview": GRAFANA_OVERVIEW_URL,
    }
    return jsonify(
        enabled=any(panels.values()),
        panels={key: url for key, url in panels.items() if url},
    )


@app.get("/api/events")
def events():
    limit = min(max(request.args.get("limit", 30, type=int), 1), 500)
    return jsonify(db.events(limit))


@app.post("/api/cmd")
def command():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(ok=False, message="corps JSON attendu"), 400
    ok, message = bridge.send_command(body)
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@app.get("/api/export.csv")
def export_csv():
    """Toutes les mesures en CSV (pour les courbes du dossier technique)."""

    def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["ts", "metric", "value"])
        for row in db.all_readings():
            writer.writerow(row)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()
        yield buffer.getvalue()

    return Response(
        rows(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=biorbite.csv"},
    )


if __name__ == "__main__":
    db.init()
    bridge.start()
    try:
        # use_reloader=False : sinon Flask lance deux processus, donc deux clients MQTT.
        app.run(host=HTTP_HOST, port=HTTP_PORT, debug=False, use_reloader=False)
    finally:
        bridge.stop()
