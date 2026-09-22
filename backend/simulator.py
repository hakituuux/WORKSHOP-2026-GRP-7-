# faux module : publie les memes topics qu'un vrai esp, pour tester sans matos
# le sol "seche", et si ca passe sous le seuil la "pompe" remonte l'humidite
# les cmd du dash (arroser, lumiere, seuils) sont prises en compte

import json
import random
import time

import paho.mqtt.client as mqtt

from config import MQTT_HOST, MQTT_PASSWORD, MQTT_PORT, MQTT_USER, TOPIC_BASE

PERIOD_S = 10  # tick toutes les 10s comme un vrai firmware chill
DRYING_PER_TICK = 0.4  # sechage accelere, sinon on attend trop pour la demo

# etat interne du faux esp (pas super propre mais ca fait le job)
sim = {"moisture": 60.0, "soil_min": 35, "pulse_s": 3, "pump_until": 0.0, "light": True, "manual": False}
started = time.time()


def on_message(client, userdata, msg):
    # recoit les cmd du dashboard (meme format que le vrai firmware)
    try:
        cmd = json.loads(msg.payload)
    except json.JSONDecodeError:
        return  # payload pourri, on drop
    action = cmd.get("action")
    if action == "pump":
        # duree bornee 1..10s, on joue pas a arroser 3h
        sim["pump_until"] = time.time() + min(max(int(cmd.get("duration_s", 3)), 1), 10)
    elif action == "light":
        sim["light"], sim["manual"] = bool(cmd.get("on")), True
    elif action == "light_auto":
        sim["light"], sim["manual"] = True, False
    elif action == "set":
        # seuils / timing : on update ce qui est fourni
        sim["soil_min"] = cmd.get("soil_min", sim["soil_min"])
        sim["pulse_s"] = cmd.get("pump_pulse_s", sim["pulse_s"])
    print("commande :", cmd)


def publish(client, subtopic, data, retain=False):
    # ptite helper pour pas repeter le prefixe a chaque fois
    client.publish(f"{TOPIC_BASE}/{subtopic}", json.dumps(data), retain=retain)


def main():
    # branchement mqtt + boucle de pub des fausses mesures
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="biorbit-simulator")
    if MQTT_USER or MQTT_PASSWORD:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    # last will : si on crash, le broker dit "offline" tout seul
    client.will_set(f"{TOPIC_BASE}/status", "offline", qos=1, retain=True)
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT)
    client.subscribe(f"{TOPIC_BASE}/cmd", qos=1)
    client.loop_start()
    client.publish(f"{TOPIC_BASE}/status", "online", qos=1, retain=True)
    print(f"Simulateur connecte a {MQTT_HOST}:{MQTT_PORT}")

    try:
        while True:
            now = time.time()
            # auto-arrosage simplifie : trop sec + cooldown passe => pulse pompe
            if sim["moisture"] < sim["soil_min"] and now > sim["pump_until"] + 60:
                sim["pump_until"] = now + sim["pulse_s"]
            pump_on = now < sim["pump_until"]
            sim["moisture"] += 8 if pump_on else -DRYING_PER_TICK
            sim["moisture"] = min(max(sim["moisture"], 0), 100)

            # un peu de bruit pour que les courbes aient l'air "vivantes"
            moisture = round(sim["moisture"] + random.uniform(-0.5, 0.5))
            publish(client, "soil", {"moisture": moisture, "raw": int(3000 - moisture * 18), "valid": True})
            publish(client, "temp", {"celsius": round(22 + random.uniform(-0.3, 0.3), 1)})
            publish(client, "humidity", {"percent": round(55 + random.uniform(-2, 2), 1)})
            publish(client, "light", {"lux": round(420 + random.uniform(-40, 40), 0)})
            publish(client, "pump/state", {"on": pump_on}, retain=True)
            publish(client, "light/state", {"on": sim["light"], "mode": "manual" if sim["manual"] else "auto"}, retain=True)
            publish(client, "state", {"state": "NORMAL", "tank_ok": True, "soil_min": sim["soil_min"],
                                      "uptime_s": int(now - started)}, retain=True)
            time.sleep(PERIOD_S)
    except KeyboardInterrupt:
        # ctrl+c : on dit offline avant de partir
        client.publish(f"{TOPIC_BASE}/status", "offline", qos=1, retain=True).wait_for_publish(2)
        client.loop_stop()


if __name__ == "__main__":
    main()
