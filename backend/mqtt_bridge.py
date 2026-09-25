# pont mqtt <-> sqlite
# ecoute les topics, stocke, et balance la prevision d'arrosage
# tourne en thread a cote de flask (loop_start)

import json
import logging
import threading
import time

import paho.mqtt.client as mqtt

import db
from config import FORECAST_WINDOW, MQTT_HOST, MQTT_PASSWORD, MQTT_PORT, MQTT_USER, TOPIC_BASE
from forecast import Forecaster

log = logging.getLogger("mqtt")

# Topic unique publié par l'ESP atelier (JSON flat)
ESP_TOPIC = "espacefarm/capteurs"

# actions qu'on laisse passer vers le module (le reste = nope)
ALLOWED_ACTIONS = {"pump", "light", "light_auto", "set", "calibrate"}


class Bridge:
    def __init__(self):
        self.latest: dict[str, dict] = {}  # cache memoire : derniere valeur par sous-topic
        self.lock = threading.Lock()  # flask + mqtt touchent latest en parallele
        self.broker_connected = False
        self.forecaster = Forecaster(FORECAST_WINDOW)

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="growcore-backend")
        # auth optionnelle : en atelier on laisse souvent vide
        if MQTT_USER or MQTT_PASSWORD:
            self.client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self) -> None:
        # async + loop_start = il se reconnecte tout seul si le broker reboot
        self.client.connect_async(MQTT_HOST, MQTT_PORT)
        self.client.loop_start()

    def stop(self) -> None:
        # a appeler a l'arret du serveur
        self.client.loop_stop()
        self.client.disconnect()

    def snapshot(self) -> dict:
        # copie rapide pour /api/status (le front poll ca ttes les 2s)
        with self.lock:
            latest = {topic: dict(entry) for topic, entry in self.latest.items()}
        return {"broker_connected": self.broker_connected, "now": time.time(), "topics": latest}

    def send_command(self, command: dict) -> tuple[bool, str]:
        # envoie une cmd depuis le dashboard vers le topic .../cmd
        action = command.get("action")
        if action not in ALLOWED_ACTIONS:
            return False, f"action inconnue : {action!r}"
        if not self.broker_connected:
            return False, "broker MQTT injoignable"

        payload = json.dumps(command)
        info = self.client.publish(f"{TOPIC_BASE}/cmd", payload, qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            return False, f"echec de publication (rc={info.rc})"
        db.add_event("command", payload)  # on log aussi en db pour l'historique
        return True, "commande envoyee"

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        # callback paho : si ok on s'abonne a tout le prefixe + topic ESP
        if reason_code.is_failure:
            log.error("Connexion au broker refusee : %s", reason_code)
            return
        self.broker_connected = True
        log.info("Connecte au broker %s:%s", MQTT_HOST, MQTT_PORT)
        client.subscribe(f"{TOPIC_BASE}/#", qos=1)
        client.subscribe(ESP_TOPIC, qos=1)
        log.info("Abonne a %s/# et %s", TOPIC_BASE, ESP_TOPIC)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        # paho retentera, on met juste le flag a false pour le bandeau ui
        self.broker_connected = False
        log.warning("Deconnecte du broker (%s), nouvelle tentative automatique", reason_code)

    def _ingest(self, subtopic: str, data, now: float) -> None:
        """Met a jour le cache + stockage pour un sous-topic biorbit."""
        with self.lock:
            previous = self.latest.get(subtopic, {}).get("value")
            self.latest[subtopic] = {"value": data, "ts": now}
        try:
            self._store(subtopic, data, previous, now)
        except Exception:
            log.exception("Erreur de traitement du sous-topic %s", subtopic)

    def _handle_espacefarm(self, data: dict, now: float) -> None:
        """Convertit le JSON ESP atelier vers les topics attendus par le dashboard."""
        # temperature
        if data.get("temperature") is not None:
            self._ingest("temp", {"celsius": float(data["temperature"])}, now)

        # humidite air (DHT)
        if data.get("humidite_air") is not None:
            self._ingest("humidity", {"percent": float(data["humidite_air"])}, now)

        # luminosite
        if data.get("luminosite") is not None:
            self._ingest("light", {"lux": float(data["luminosite"])}, now)

        # humidite terre : soit humidite_terre (0-100), soit sol digital 0/1
        moisture = data.get("humidite_terre")
        if moisture is None and data.get("sol") is not None:
            moisture = 100.0 if int(data["sol"]) == 1 else 0.0
        if moisture is not None:
            m = float(moisture)
            self._ingest(
                "soil",
                {"moisture": m, "raw": int(m * 10), "valid": True},
                now,
            )

        # pompe (optionnel)
        if data.get("pompe") is not None:
            self._ingest("pump/state", {"on": bool(int(data["pompe"]))}, now)

        # etat module resume
        self._ingest(
            "status",
            "online",
            now,
        )
        self._ingest(
            "state",
            {
                "state": "NORMAL",
                "tank_ok": True,
                "soil_min": 35,
                "source": "espacefarm/capteurs",
            },
            now,
        )

    def _on_message(self, client, userdata, msg):
        # un msg arrive -> on parse, on met a jour le cache, on stocke
        text = msg.payload.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = text  # ex: status = "online" / "offline" (pas du json)

        now = time.time()

        # Topic plat de l'ESP atelier
        if msg.topic == ESP_TOPIC:
            if isinstance(data, dict):
                self._handle_espacefarm(data, now)
            else:
                log.warning("Payload ESP invalide: %s", text[:120])
            return

        subtopic = msg.topic.removeprefix(TOPIC_BASE + "/")
        if subtopic == "cmd":
            return  # c'est nous qui les envoyons, pas la peine de se reboucler

        self._ingest(subtopic, data, now)

    def _store(self, subtopic: str, data, previous, now: float) -> None:
        # dispatch selon le topic : mesures en readings, changements en events
        if subtopic == "soil" and isinstance(data, dict):
            if not data.get("valid", True):
                return  # capteur foireux, on ignore
            db.add_reading("soil", data["moisture"], now)
            db.add_reading("soil_raw", data["raw"], now)
            forecast = self.forecaster.add(now, float(data["moisture"]))
            if forecast:
                # retain=true pour que le dash ait la prev meme apres un refresh
                self.client.publish(f"{TOPIC_BASE}/forecast", json.dumps(forecast), retain=True)

        elif subtopic == "temp" and isinstance(data, dict):
            if data.get("celsius") is not None:
                db.add_reading("temp", data["celsius"], now)

        elif subtopic == "humidity" and isinstance(data, dict):
            if data.get("percent") is not None:
                db.add_reading("humidity", data["percent"], now)

        elif subtopic == "light" and isinstance(data, dict):
            # attention : "light" = capteur lux, "light/state" = la led/actionneur
            if data.get("lux") is not None:
                db.add_reading("lux", data["lux"], now)

        elif subtopic == "pump/state" and isinstance(data, dict):
            # le module republie souvent : on log que les vrais changements
            if previous is not None and data.get("on") != previous.get("on"):
                db.add_event("pump", "ON" if data.get("on") else "OFF", now)
            if data.get("on"):
                self.forecaster.reset()  # nouvel arrosage = on recommence la courbe

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
