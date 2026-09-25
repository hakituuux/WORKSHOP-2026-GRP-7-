#include <Arduino.h>
#include <DHT.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "secrets.h"  // SSID, mdp, IP MQTT (ne pas committer)

// SDK bas niveau ESP8266 — utilisé pour le Wi‑Fi WPA2-Enterprise (réseau école)
extern "C" {
#include "user_interface.h"
#include "wpa2_enterprise.h"
}

// --- Capteur DHT11 (température + humidité air) ---
#define DHTPIN D1
#define DHTTYPE DHT11

// false = LED RGB cathode commune (HIGH = allumé). true si anode commune.
const bool COMMON_ANODE = false;

// --- Broches (noms NodeMCU D0–D7) ---
const int PIN_R = D5;      // LED rouge
const int PIN_G = D6;      // LED verte
const int PIN_B = D7;      // LED bleue
const int PIN_LUM = A0;    // LDR (pont diviseur) — seul ADC de l'ESP8266
const int PIN_SOL = D0;    // Module sol digital DO
const int PIN_POMPE = D2;  // Base du transistor PN2222 (via ~1 kΩ)

// --- Seuils pour la LED d'état (vert = OK, sinon rouge/bleu) ---
const float TEMP_MIN = 18.0;
const float TEMP_MAX = 32.0;
const float LUX_MIN = 400.0;
const float LUX_MAX = 25000.0;
// Module sol digital : 1 = humide (OK), 0 = sec → pompe auto ON
const int SOL_HUMIDE = 1;

// --- Calibration LDR (approximative) ---
const float R_DIVISEUR = 10000.0;  // 10 kΩ du pont avec la LDR
const float R10_LUX = 15000.0;     // résistance typique LDR à ~10 lux
const float GAMMA = 0.7;           // courbure ; plus petit = courbe plus douce

const unsigned long MQTT_INTERVAL_MS = 5000;   // publier toutes les 5 s
const unsigned long WIFI_RETRY_MS = 30000;     // ne pas spammer reconnect Wi‑Fi

DHT dht(DHTPIN, DHTTYPE);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

// Mode pompe : 0 = auto (ON si sol sec), 1 = forcé ON, 2 = forcé OFF
// Commandes Serial Monitor : '1' / '0' / 'a'
static int pompeMode = 0;
static unsigned long lastMqttMs = 0;
static unsigned long lastWifiTryMs = 0;

// Allume/éteint chaque couleur de la LED RGB
void setColor(bool rouge, bool vert, bool bleu) {
  if (COMMON_ANODE) {
    rouge = !rouge;
    vert = !vert;
    bleu = !bleu;
  }
  digitalWrite(PIN_R, rouge ? HIGH : LOW);
  digitalWrite(PIN_G, vert ? HIGH : LOW);
  digitalWrite(PIN_B, bleu ? HIGH : LOW);
}

// Lit A0 9 fois et renvoie la médiane (filtre le bruit)
int medianAnalog() {
  int v[9];
  for (int i = 0; i < 9; i++) {
    v[i] = analogRead(PIN_LUM);  // 0 = 0 V, 1023 ≈ 1 V (réf. ESP8266)
    delay(15);
  }
  // Tri croissant → v[4] = médiane
  for (int i = 0; i < 9; i++) {
    for (int j = i + 1; j < 9; j++) {
      if (v[j] < v[i]) {
        int tmp = v[i];
        v[i] = v[j];
        v[j] = tmp;
      }
    }
  }
  return v[4];
}

// Convertit la tension A0 (pont LDR + 10 kΩ) en lux approximatifs
float readLux() {
  float adc = medianAnalog();
  if (adc < 1.0) {
    return 0.0;  // évite division par 0
  }

  // Pont : R_ldr = 10k * (1023/adc - 1)
  float rLdr = R_DIVISEUR * ((1023.0 / adc) - 1.0);
  if (rLdr < 1.0) {
    return 100000.0;  // très lumineux
  }

  // Plus de lumière → R_ldr plus faible → lux plus élevé
  return 10.0 * pow(R10_LUX / rLdr, 1.0 / GAMMA);
}

// Lecture digital du module humidité sol (DO)
int readSol() {
  return digitalRead(PIN_SOL);
}

const char *wifiStatusText(int status) {
  switch (status) {
    case WL_IDLE_STATUS: return "IDLE";
    case WL_NO_SSID_AVAIL: return "SSID introuvable";
    case WL_SCAN_COMPLETED: return "SCAN OK";
    case WL_CONNECTED: return "CONNECTED";
    case WL_CONNECT_FAILED: return "CONNECT_FAILED";
    case WL_CONNECTION_LOST: return "CONNECTION_LOST";
    case WL_WRONG_PASSWORD: return "WRONG_PASSWORD";
    case WL_DISCONNECTED: return "DISCONNECTED";
    default: return "UNKNOWN";
  }
}

// Liste les réseaux 2.4 GHz visibles (aide au debug SSID)
void scanWifi() {
  Serial.println("Scan WiFi (2.4 GHz)...");
  int n = WiFi.scanNetworks();
  if (n <= 0) {
    Serial.println("Aucun reseau trouve");
    return;
  }
  for (int i = 0; i < n; i++) {
    Serial.print("  ");
    Serial.print(i + 1);
    Serial.print(") ");
    Serial.print(WiFi.SSID(i));
    Serial.print("  RSSI=");
    Serial.println(WiFi.RSSI(i));
  }
}

// Connexion Wi‑Fi : PSK si WIFI_USER vide, sinon WPA2-Enterprise
void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  const bool enterprise = WIFI_USER != nullptr && WIFI_USER[0] != '\0';

  Serial.print(enterprise ? "WiFi Enterprise " : "WiFi PSK ");
  Serial.print(WIFI_SSID);
  if (enterprise) {
    Serial.print(" / ");
    Serial.print(WIFI_USER);
  }
  Serial.println();

  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setSleepMode(WIFI_NONE_SLEEP);  // plus stable pour MQTT
  wifi_station_disconnect();
  delay(200);

  if (enterprise) {
    // Réseau école (COMDEV-PEDAGO, etc.)
    struct station_config conf;
    memset(&conf, 0, sizeof(conf));
    strncpy(reinterpret_cast<char *>(conf.ssid), WIFI_SSID, sizeof(conf.ssid) - 1);
    wifi_station_set_config(&conf);

    wifi_station_clear_cert_key();
    wifi_station_clear_enterprise_ca_cert();
    wifi_station_set_wpa2_enterprise_auth(1);
    wifi_station_set_enterprise_identity((uint8 *)WIFI_USER, strlen(WIFI_USER));
    wifi_station_set_enterprise_username((uint8 *)WIFI_USER, strlen(WIFI_USER));
    wifi_station_set_enterprise_password((uint8 *)WIFI_PASS, strlen(WIFI_PASS));
    wifi_station_connect();
  } else {
    // Hotspot / Wi‑Fi classique (SSID + mdp)
    wifi_station_set_wpa2_enterprise_auth(0);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
  }

  // Attente max 45 s
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 45000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  int st = WiFi.status();
  if (st == WL_CONNECTED) {
    Serial.print("WiFi OK IP=");
    Serial.println(WiFi.localIP());
  } else {
    Serial.print("WiFi ECHEC status=");
    Serial.print(st);
    Serial.print(" (");
    Serial.print(wifiStatusText(st));
    Serial.println(")");
    scanWifi();
    Serial.println("Verifie: SSID exact (sensible a la casse), mdp.");
    if (enterprise) {
      Serial.println("Si l'ecole demande un domaine: user@domaine dans WIFI_USER.");
    }
  }
}

// Connexion au broker Mosquitto (IP = MQTT_HOST dans secrets.h)
bool connectMqtt() {
  if (mqtt.connected()) {
    return true;
  }
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  String clientId = "espacefarm-esp-" + String(ESP.getChipId(), HEX);
  Serial.print("MQTT ");
  Serial.print(MQTT_HOST);
  Serial.print(":");
  Serial.print(MQTT_PORT);
  Serial.print(" ...");

  // Sans user → connexion anonyme (config Mosquitto atelier)
  bool ok = false;
  if (MQTT_USER != nullptr && MQTT_USER[0] != '\0') {
    ok = mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASS);
  } else {
    ok = mqtt.connect(clientId.c_str());
  }
  if (!ok) {
    // state=-2 = TCP impossible (souvent mauvaise IP Mac)
    Serial.print(" ECHEC state=");
    Serial.println(mqtt.state());
  } else {
    Serial.println(" OK");
  }
  return ok;
}

// Construit le JSON capteurs et publie sur espacefarm/capteurs
void publishMesures(float temperature, float humiditeAir, float lux, int sol, bool pompeOn) {
  // Reconnect Wi‑Fi si besoin (espacé dans le temps)
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWifiTryMs < WIFI_RETRY_MS) {
      return;
    }
    lastWifiTryMs = millis();
    connectWifi();
  }
  if (!connectMqtt()) {
    return;
  }

  // Champs attendus par Node-RED → Postgres → Grafana / dashboard
  JsonDocument doc;
  if (!isnan(temperature)) {
    doc["temperature"] = temperature;
  }
  if (!isnan(humiditeAir)) {
    doc["humidite_air"] = humiditeAir;
  }
  doc["luminosite"] = lux;
  // Sol digital mappé en % pour la colonne humidite_terre
  doc["humidite_terre"] = (sol == SOL_HUMIDE) ? 100 : 0;
  doc["sol"] = sol;
  doc["pompe"] = pompeOn ? 1 : 0;

  // Sérialise le JSON dans un buffer texte, puis publie sur le topic MQTT
  char payload[256];
  size_t n = serializeJson(doc, payload, sizeof(payload));
  if (mqtt.publish(MQTT_TOPIC, payload, n)) {
    Serial.print("MQTT -> ");
    Serial.println(payload);
  } else {
    Serial.println("MQTT publish ECHEC");
  }
}

void setup() {
  // Pompe OFF au boot (évite démarrage parasite si GPIO flottant)
  pinMode(PIN_POMPE, OUTPUT);
  digitalWrite(PIN_POMPE, LOW);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);  // LED carte éteinte (active LOW)

  pinMode(PIN_R, OUTPUT);
  pinMode(PIN_G, OUTPUT);
  pinMode(PIN_B, OUTPUT);
  setColor(false, true, false);  // vert au démarrage
  pinMode(PIN_SOL, INPUT);

  Serial.begin(115200);
  Serial.println();
  Serial.println("Pompe: tape 1=ON  0=OFF  a=auto (sol sec)");
  dht.begin();
  delay(2000);  // stabilisation DHT11

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  lastWifiTryMs = millis();
  WiFi.mode(WIFI_STA);
  scanWifi();
  connectWifi();
  connectMqtt();
}

void loop() {
  static float lastT = NAN;  // dernière temp valide (DHT peut renvoyer NaN)
  static int badStreak = 0;  // compteur mesures hors seuils (anti-clignotement LED)

  // --- Commandes manuelles pompe via Serial ---
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '1') {
      pompeMode = 1;
      Serial.println("mode manuel: pompe ON");
    } else if (c == '0') {
      pompeMode = 2;
      Serial.println("mode manuel: pompe OFF");
    } else if (c == 'a' || c == 'A') {
      pompeMode = 0;
      Serial.println("mode auto (sol sec)");
    }
  }

  // --- Capteurs ---
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (!isnan(t)) {
    lastT = t;
  }

  float lux = readLux();
  int sol = readSol();

  bool tempOk = !isnan(lastT) && lastT >= TEMP_MIN && lastT <= TEMP_MAX;
  bool lightOk = lux >= LUX_MIN && lux <= LUX_MAX;
  bool solOk = (sol == SOL_HUMIDE);

  // Auto : pompe ON si sol sec ; manuel via Serial
  bool pompeOn = false;
  if (pompeMode == 1) {
    pompeOn = true;
  } else if (pompeMode == 2) {
    pompeOn = false;
  } else {
    pompeOn = !solOk;
  }
  digitalWrite(PIN_POMPE, pompeOn ? HIGH : LOW);

  // --- LED d'état : vert = tout OK, bleu = sol sec seul, rouge = temp/lux hors plage ---
  if (tempOk && lightOk && solOk) {
    badStreak = 0;
    setColor(false, true, false);
  } else {
    badStreak++;
    if (badStreak >= 8) {
      if (tempOk && lightOk) {
        setColor(false, false, true);
      } else {
        setColor(true, false, false);
      }
    }
  }

  // Trace Serial pour debug atelier
  Serial.print("temperature ");
  Serial.print(lastT);
  Serial.print(" C, humidite_air ");
  Serial.print(h);
  Serial.print(" %, luminosite ");
  Serial.print(lux);
  Serial.print(" lux, sol ");
  Serial.print(sol);
  Serial.println(solOk ? " humide" : " sec");
  Serial.println(pompeOn ? "pompe ON" : "pompe OFF");

  // Keepalive MQTT + publish périodique
  mqtt.loop();
  if (millis() - lastMqttMs >= MQTT_INTERVAL_MS) {
    lastMqttMs = millis();
    publishMesures(lastT, h, lux, sol, pompeOn);
  }

  delay(500);
}
