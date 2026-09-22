# Dossier technique — BiOrbit

> Rédigé au fil de l'eau, exporté en PDF le jeudi.

## 1. Contexte et objectif

<!-- Le besoin (module « food » du vaisseau), ce que fait BiOrbit en une phrase. -->

## 2. Architecture générale

<!-- Schéma : capteurs → ESP32 → MQTT (Mosquitto) → dashboard / prévision. -->

## 3. Matériel et câblage

Voir [cablage.md](cablage.md). Ajouter ici le schéma exporté.

## 4. Firmware

### 4.1 Découpage en modules
<!-- SoilSensor, TempSensor, WaterLevel, Pump, GrowLight, Scheduler, Controller, Network, Logger -->

### 4.2 Machine à états

| État | Condition | Comportement |
|---|---|---|
| ERREUR | capteur d'humidité hors plage | pompe bloquée, LED rouge clignotante |
| PÉNURIE | réservoir vide | pompe bloquée, LED orange clignotante |
| AUTONOME | broker injoignable | régulation locale inchangée |
| NORMAL | tout fonctionne | régulation + télémétrie |

### 4.3 Tâches FreeRTOS
<!-- Pourquoi deux tâches : le réseau ne bloque jamais l'arrosage. -->

### 4.4 Sécurités
<!-- Impulsion max 10 s, temps de repos, blocage si réservoir vide, niveau de relais fixé avant pinMode. -->

## 5. Communication MQTT

<!-- Tableau des topics et format des commandes (voir README). -->

## 5 bis. Backend Python

<!-- mqtt_bridge.py (MQTT -> SQLite), app.py (API Flask + dashboard), choix de SQLite, captures du dashboard. -->

## 6. Calibration et essais

<!-- Valeurs sec / humide mesurées, courbe de séchage, résultats des tests. -->

## 7. Prévision

<!-- Régression linéaire sur la courbe de séchage depuis le dernier arrosage. -->

## 8. Limites et améliorations
