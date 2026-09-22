# BiOrbite (héritage BiOrbit)

Solution de supervision pour cultures autonomes (module « food »).
Les capteurs publient via MQTT ; un backend Flask enregistre les mesures et sert un **dashboard de contrôle** qui peut embarquer des graphiques Grafana.

```
 capteurs ──> ESP8266 / ESP32 ──MQTT──> Mosquitto ──> backend Python ──> dashboard
                                              │         (Flask + SQLite)
                                              └── (cible) Node-RED → PostgreSQL → Grafana
                                                                      └── iframes dans le dashboard
```

## Ce que contient ce dépôt (travail collègue)

| Présent | Absent / à prévoir |
|---|---|
| Broker Mosquitto | Dossier `firmware/` (annoncé dans le README d’origine, **pas dans le dépôt**) |
| Backend Flask + SQLite + prévision arrosage | Node-RED, PostgreSQL, Grafana (stack cible BiOrbite) |
| Dashboard web + simulateur MQTT | Capteurs air humidité / luminosité côté firmware réel |
| Docs câblage ESP32 (sol, DS18B20, réservoir, pompe, LED) | Câblage ESP8266 + DHT/BH1750 |

**Compatible en l’état ?** Oui sur le socle MQTT + dashboard + commandes. À adapter pour coller à BiOrbite : microcontrôleur (ESP8266), capteurs (humidité air + luminosité), et chaîne Node-RED / PostgreSQL / Grafana si vous l’adoptez pleinement.

## Lancement rapide

### 1. Broker

```powershell
& "C:\Program Files\mosquitto\mosquitto_passwd.exe" -c broker\passwd BiOrbit
& "C:\Program Files\mosquitto\mosquitto.exe" -c broker\mosquitto.conf -v
```

### 2. Backend + dashboard

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Dashboard : <http://127.0.0.1:5000>

Sans module : `python simulator.py` (publie sol, temp air, humidité air, lux, pompe, lumière).

## Embarquer Grafana dans le dashboard

Oui, c’est prévu. Grafana expose chaque panel en iframe (`Share` → `Embed`).

1. Dans `grafana.ini` : `allow_embedding = true` (et auth adaptée : anonyme en atelier, ou cookie SameSite).
2. Copier les URLs `d-solo/...` dans `backend/.env` :

```env
GRAFANA_SOIL_URL=http://localhost:3000/d-solo/...
GRAFANA_AIR_URL=http://localhost:3000/d-solo/...
GRAFANA_LIGHT_URL=http://localhost:3000/d-solo/...
GRAFANA_OVERVIEW_URL=http://localhost:3000/d-solo/...
```

3. Relancer `python app.py`. Le dashboard affiche les iframes ; sans URL, il reste en **mode local** (Chart.js).

Endpoint : `GET /api/grafana`.

## Topics MQTT

Préfixe : `ship/food/biorbit`

| Topic | Contenu |
|---|---|
| `status` | `online` / `offline` |
| `state` | `{"state":"NORMAL","tank_ok":true,"soil_min":35,"uptime_s":120}` |
| `soil` | `{"moisture":42,"raw":2210,"valid":true}` |
| `temp` | `{"celsius":21.5}` |
| `humidity` | `{"percent":55.2}` |
| `light` | `{"lux":420}` (capteur) |
| `pump/state` | `{"on":false}` |
| `light/state` | `{"on":true,"mode":"auto"}` (actionneur) |
| `forecast` | prévision de séchage (backend) |
| `cmd` | commandes (pompe, lumière, seuils, calibration) |

## API

| Route | Rôle |
|---|---|
| `GET /api/status` | Dernières valeurs MQTT |
| `GET /api/history?metric=…&hours=6` | `soil`, `soil_raw`, `temp`, `humidity`, `lux` |
| `GET /api/grafana` | URLs d’embed configurées |
| `GET /api/events` | Journal |
| `POST /api/cmd` | Commande vers le module |
| `GET /api/export.csv` | Export mesures |
