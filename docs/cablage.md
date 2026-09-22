# Câblage BiOrbit

| Élément | Broche ESP32 | Remarque |
|---|---|---|
| Capteur d'humidité capacitif (AOUT) | GPIO 34 | ADC1 : compatible avec le Wi-Fi (l'ADC2 ne l'est pas) |
| DS18B20 (DATA) | GPIO 4 | Résistance de rappel 4,7 kΩ entre DATA et 3V3 |
| Flotteur du réservoir | GPIO 27 | Contact vers GND, pull-up interne activé |
| Relais de la pompe (IN) | GPIO 26 | Module actif à l'état bas (`PUMP_ACTIVE_LOW`) |
| LED RGB rouge | GPIO 25 | Résistance ≈ 220 Ω |
| LED RGB verte | GPIO 33 | Résistance ≈ 220 Ω |
| LED RGB bleue | GPIO 32 | Résistance ≈ 220 Ω |

Toutes les broches se modifient dans `firmware/include/config.h`.

**Alimentation de la pompe :** la pompe est alimentée par une source séparée (5 V ou 12 V selon le modèle) et commutée par le relais. Ne jamais l'alimenter depuis la broche 3V3 ou 5V de l'ESP32. Les masses (GND) doivent être communes.

Le schéma Fritzing ou draw.io va dans `docs/cablage/`.
