# config lue depuis le .env (copier .env.example si besoin)
# rien de magique, juste des constantes pour le reste du backend

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # charge le .env local si y'en a un

# broker mqtt (en atelier souvent localhost sans auth)
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "BiOrbit")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# prefixe commun a tous les topics du module
TOPIC_BASE = "ship/food/biorbit"

DB_PATH = BASE_DIR / os.getenv("DB_FILE", "BiOrbit.db")

# 127.0.0.1 = que ce pc ; 0.0.0.0 = accessible sur le reseau local (attention cmds pompe)
HTTP_HOST = os.getenv("HTTP_HOST", "127.0.0.1")
HTTP_PORT = int(os.getenv("HTTP_PORT", "5000"))

# nb de points d'humidite pour la prevision (~360 x 10s = 1h)
FORECAST_WINDOW = int(os.getenv("FORECAST_WINDOW", "360"))

# urls d'embed grafana (share > embed). vide = mode chart.js local
GRAFANA_SOIL_URL = os.getenv("GRAFANA_SOIL_URL", "")
GRAFANA_AIR_URL = os.getenv("GRAFANA_AIR_URL", "")
GRAFANA_TEMP_URL = os.getenv("GRAFANA_TEMP_URL", "")
GRAFANA_LIGHT_URL = os.getenv("GRAFANA_LIGHT_URL", "")
GRAFANA_POMPE_URL = os.getenv("GRAFANA_POMPE_URL", "")
GRAFANA_OVERVIEW_URL = os.getenv("GRAFANA_OVERVIEW_URL", "")
