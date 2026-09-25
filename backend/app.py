# backend flask du dashboard biorbite
# en gros : api + fichiers static, et le pont mqtt qui tourne a cote

import csv
import io
import logging

from flask import Flask, Response, jsonify, request

import db
from config import (
    GRAFANA_AIR_URL,
    GRAFANA_LIGHT_URL,
    GRAFANA_OVERVIEW_URL,
    GRAFANA_POMPE_URL,
    GRAFANA_SOIL_URL,
    GRAFANA_TEMP_URL,
    HTTP_HOST,
    HTTP_PORT,
)
from mqtt_bridge import Bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

app = Flask(__name__, static_folder="static", static_url_path="")
bridge = Bridge()  # ptit pont mqtt partagé entre les routes

# les metriques qu'on accepte cote historique (sinon 400)
METRICS = {"soil", "soil_raw", "temp", "humidity", "lux"}


@app.get("/")
def index():
    # page d'accueil = le dashboard html, rien de fancy
    return app.send_static_file("index.html")


@app.get("/api/status")
def status():
    # snapshot live : dernieres valeurs mqtt + si le broker est up
    return jsonify(bridge.snapshot())


@app.get("/api/history")
def history():
    # pour les courbes : on prend une metrique + une fenetre en heures
    metric = request.args.get("metric", "soil")
    if metric not in METRICS:
        return jsonify(error=f"metric doit etre parmi {sorted(METRICS)}"), 400
    # on clamp un peu pour pas se faire spammer avec 10 ans de data
    hours = min(max(request.args.get("hours", 6, type=float), 0.1), 168)
    return jsonify(metric=metric, hours=hours, points=db.history(metric, hours))


@app.get("/api/grafana")
def grafana():
    # si y'a des urls d'embed dans le .env on les renvoie, sinon mode local chart.js
    panels = {
        "soil": GRAFANA_SOIL_URL,
        "air": GRAFANA_AIR_URL,
        "temp": GRAFANA_TEMP_URL,
        "light": GRAFANA_LIGHT_URL,
        "pompe": GRAFANA_POMPE_URL,
        "overview": GRAFANA_OVERVIEW_URL,
    }
    return jsonify(
        enabled=any(panels.values()),
        panels={key: url for key, url in panels.items() if url},
    )


@app.get("/api/events")
def events():
    # journal pompe / lumiere / etats / cmd, pour le bas du dashboard
    limit = min(max(request.args.get("limit", 30, type=int), 1), 500)
    return jsonify(db.events(limit))


@app.post("/api/cmd")
def command():
    # le front envoie une cmd json, on la forward en mqtt vers le module
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(ok=False, message="corps JSON attendu"), 400
    ok, message = bridge.send_command(body)
    return jsonify(ok=ok, message=message), (200 if ok else 400)


@app.get("/api/export.csv")
def export_csv():
    # export pour le dossier tech / excel, on stream pour pas tout charger en ram

    def rows():
        # generateur line par line, ca passe mieux si la db grossit
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
    db.init()  # cree les tables si elles existent pas encore
    bridge.start()
    try:
        # use_reloader=false sinon flask fork x2 et on se retrouve avec 2 clients mqtt
        app.run(host=HTTP_HOST, port=HTTP_PORT, debug=False, use_reloader=False)
    finally:
        bridge.stop()  # clean exit, on coupe mqtt proprement
