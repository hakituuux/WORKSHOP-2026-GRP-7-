# Grafana — embed dans le dashboard BiOrbite

## Principe

Le dashboard Flask (`http://127.0.0.1:5000`) peut afficher des panels Grafana via `<iframe>`.
Les URLs viennent de Grafana → panel → **Share** → **Embed**.

## Configuration Grafana (atelier)

Dans `grafana.ini` (ou variables d’environnement Docker) :

```ini
[security]
allow_embedding = true

[auth.anonymous]
enabled = true
org_role = Viewer
```

Sans auth anonyme, l’iframe exige une session Grafana (cookie) : possible en local, fragile en démo.

## Brancher les URLs

Dans `backend/.env` (voir `.env.example`) :

- `GRAFANA_SOIL_URL` — humidité sol
- `GRAFANA_AIR_URL` — température + humidité air
- `GRAFANA_LIGHT_URL` — luminosité
- `GRAFANA_OVERVIEW_URL` — vue d’ensemble

Puis redémarrer le backend. `GET /api/grafana` indique si le mode Grafana est actif.

## Chaîne cible BiOrbite

```
ESP ──MQTT──> Mosquitto ──> Node-RED ──> PostgreSQL ──> Grafana
                                  └── (option) commandes MQTT
Dashboard Flask/HTML  <── iframes ──  Grafana
```

Tant que PostgreSQL/Grafana ne sont pas en place, le dashboard utilise le **mode local** (SQLite + Chart.js) alimenté par le même pont MQTT.
