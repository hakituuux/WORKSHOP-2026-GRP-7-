"""Pont MQTT : ecoute tous les topics BiOrbit, enregistre en base, publie la prevision.

Tourne dans un thread de fond (loop_start) a cote du serveur Flask.
"""

import json
import logging
import threading
import time

import paho.mqtt.client as mqtt

import db
from config import FORECAST_WINDOW, MQTT_HOST, MQTT_PASSWORD, MQTT_PORT, MQTT_USER, TOPIC_BASE
from forecast import Forecaster

log = logging.getLogger("mqtt")

ALLOWED_ACTIONS = {"pump", "light", "light_auto", "set", "calibrate"}


class Bridge:
    def __init__(self):
        self.latest: dict[str, dict] = {}  # derniere valeur recue par sous-topic
        self.lock = threading.Lock()
        self.broker_connected = False
        self.forecaster = Forecaster(FORECAST_WINDOW)

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="growcore-backend")
        if MQTT_USER or MQTT_PASSWORD:
            self.client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self) -> None:
        # connect_async + loop_start : reconnexion automatique si le broker redemarre.
        self.client.connect_async(MQTT_HOST, MQTT_PORT)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    # ---------- Lecture depuis Flask ----------

    def snapshot(self) -> dict:
        with self.lock:
            latest = {topic: dict(entry) for topic, entry in self.latest.items()}
        return {"broker_connected": self.broker_connected, "now": time.time(), "topics": latest}

    def send_command(self, command: dict) -> tuple[bool, str]:
        action = command.get("action")
        if action not in ALLOWED_ACTIONS:
            return False, f"action inconnue : {action!r}"
        if not self.broker_connected:
            return False, "broker MQTT injoignable"

        payload = json.dumps(command)
        info = self.client.publish(f"{TOPIC_BASE}/cmd", payload, qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            return False, f"echec de publication (rc={info.rc})"
        db.add_event("command", payload)
        return True, "commande envoyee"

    # ---------- Callbacks MQTT ----------

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("Connexion au broker refusee : %s", reason_code)
            return
        self.broker_connected = True
        log.info("Connecte au broker %s:%s", MQTT_HOST, MQTT_PORT)
        client.subscribe(f"{TOPIC_BASE}/#", qos=1)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.broker_connected = False
        log.warning("Deconnecte du broker (%s), nouvelle tentative automatique", reason_code)

    def _on_message(self, client, userdata, msg):
        subtopic = msg.topic.removeprefix(TOPIC_BASE + "/")
        if subtopic == "cmd":
            return  # nos propres commandes

        text = msg.payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = text  # ex. status : "online" / "offline"

        now = time.time()
        with self.lock:
            previous = self.latest.get(subtopic, {}).get("value")
            self.latest[subtopic] = {"value": data, "ts": now}

        try:
            self._store(subtopic, data, previous, now)
        except Exception:
            log.exception("Erreur de traitement du message %s", msg.topic)

    def _store(self, subtopic: str, data, previous, now: float) -> None:
        if subtopic == "soil" and isinstance(data, dict):
            if not data.get("valid", True):
                return
            db.add_reading("soil", data["moisture"], now)
            db.add_reading("soil_raw", data["raw"], now)
            forecast = self.forecaster.add(now, float(data["moisture"]))
            if forecast:
                self.client.publish(f"{TOPIC_BASE}/forecast", json.dumps(forecast), retain=True)

        elif subtopic == "temp" and isinstance(data, dict):
            if data.get("celsius") is not None:
                db.add_reading("temp", data["celsius"], now)

        elif subtopic == "humidity" and isinstance(data, dict):
            if data.get("percent") is not None:
                db.add_reading("humidity", data["percent"], now)

        elif subtopic == "light" and isinstance(data, dict):
            # Capteur de luminosite (lux) — distinct de light/state (eclairage / actionneur).
            if data.get("lux") is not None:
                db.add_reading("lux", data["lux"], now)

        elif subtopic == "pump/state" and isinstance(data, dict):

            # L'ESP32 republie l'etat toutes les 10 s : on n'enregistre que les changements.
            if previous is not None and data.get("on") != previous.get("on"):
                db.add_event("pump", "ON" if data.get("on") else "OFF", now)
            if data.get("on"):
                self.forecaster.reset()

        elif subtopic == "light/state" and isinstance(data, dict):
            if previous is not None and data.get("on") != previous.get("on"):
                db.add_event("light", "ON" if data.get("on") else "OFF", now)

        elif subtopic == "state" and isinstance(data, dict):
            if "soil_min" in data:
                self.forecaster.threshold = float(data["soil_min"])
            if previous is not None and data.get("state") != previous.get("state"):
                db.add_event("state", f"{previous.get('state')} -> {data.get('state')}", now)

        elif subtopic == "status":
            if previous is not None and data != previous:
                db.add_event("status", str(data), now)
