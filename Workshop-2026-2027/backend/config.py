"""Configuration du backend, lue depuis backend/.env (voir .env.example)."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "BiOrbit")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

TOPIC_BASE = "ship/food/biorbit"

DB_PATH = BASE_DIR / os.getenv("DB_FILE", "BiOrbit.db")

# 127.0.0.1 : dashboard accessible uniquement depuis ce PC.
# 0.0.0.0 : accessible depuis le reseau local (n'importe qui sur le reseau peut alors arroser).
HTTP_HOST = os.getenv("HTTP_HOST", "127.0.0.1")
HTTP_PORT = int(os.getenv("HTTP_PORT", "5000"))

# Nombre de mesures d'humidite utilisees pour la prevision (360 x 10 s = 1 h).
FORECAST_WINDOW = int(os.getenv("FORECAST_WINDOW", "360"))

# URLs d'embed Grafana (Share > Embed sur chaque panel).
# Exemple : http://localhost:3000/d-solo/<uid>/biorbite?orgId=1&panelId=1&theme=light
GRAFANA_SOIL_URL = os.getenv("GRAFANA_SOIL_URL", "")
GRAFANA_AIR_URL = os.getenv("GRAFANA_AIR_URL", "")
GRAFANA_LIGHT_URL = os.getenv("GRAFANA_LIGHT_URL", "")
GRAFANA_OVERVIEW_URL = os.getenv("GRAFANA_OVERVIEW_URL", "")
