#include <Arduino.h>
#include <DHT.h>

#define DHTPIN D1
#define DHTTYPE DHT11

const bool COMMON_ANODE = false;

const int PIN_R = D5;
const int PIN_G = D6;
const int PIN_B = D7;
const int PIN_LUM = A0;
const int PIN_SOL = D0;
const int PIN_POMPE = D2;

const float TEMP_MIN = 18.0;
const float TEMP_MAX = 32.0;
const float LUX_MIN = 400.0;
const float LUX_MAX = 15000.0;
// Module sol digital : 1 = humide (OK), 0 = sec
const int SOL_HUMIDE = 1;

// 10 kΩ du pont avec la LDR
const float R_DIVISEUR = 10000.0;
// Résistance typique de la LDR à 10 lux (calib. approximative)
const float R10_LUX = 15000.0;
// Courbure de la LDR (plus c'est petit, plus la courbe est douce)
const float GAMMA = 0.7;

DHT dht(DHTPIN, DHTTYPE);

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

// Lit A0 9 fois et renvoie la valeur du milieu (moins de bruit que 1 seule lecture)
int medianAnalog() {
  int v[9];
  for (int i = 0; i < 9; i++) {
    v[i] = analogRead(PIN_LUM);  // 0 = 0 V, 1023 = max ADC
    delay(15);
  }
  // Tri croissant, puis on prend v[4] = médiane
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
    return 0.0;  // A0 à 0 V : on évite une division par 0
  }

  // Formule du pont : R_ldr = 10k * (1023/adc - 1)
  float rLdr = R_DIVISEUR * ((1023.0 / adc) - 1.0);
  if (rLdr < 1.0) {
    return 100000.0;  // LDR presque en court-circuit = très lumineux
  }

  // LDR : plus de lumière → résistance plus faible → lux plus élevé
  return 10.0 * pow(R10_LUX / rLdr, 1.0 / GAMMA);
}

int readSol() {
  return digitalRead(PIN_SOL);
}

void setup() {
  pinMode(PIN_POMPE, OUTPUT);
  digitalWrite(PIN_POMPE, LOW);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);

  pinMode(PIN_R, OUTPUT);
  pinMode(PIN_G, OUTPUT);
  pinMode(PIN_B, OUTPUT);
  setColor(false, true, false);
  pinMode(PIN_SOL, INPUT);

  Serial.begin(115200);
  dht.begin();
  delay(2000);
}

void loop() {
  static float lastT = NAN;
  static int badStreak = 0;

  float t = dht.readTemperature();
  if (!isnan(t)) {
    lastT = t;
  }

  float lux = readLux();
  int sol = readSol();

  bool tempOk = !isnan(lastT) && lastT >= TEMP_MIN && lastT <= TEMP_MAX;
  bool lightOk = lux >= LUX_MIN && lux <= LUX_MAX;
  bool solOk = (sol == SOL_HUMIDE);
  // Plus tard : pompe si sol == 0 (sec). Pour l'instant : lumière trop basse.
  bool pompeOn = (lux < LUX_MIN);
  digitalWrite(PIN_POMPE, pompeOn ? HIGH : LOW);

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

  Serial.print("temperature ");
  Serial.print(lastT);
  Serial.print(" C, luminosite ");
  Serial.print(lux);
  Serial.print(" lux, sol ");
  Serial.print(sol);
  Serial.println(solOk ? " humide" : " sec");
  Serial.println(pompeOn ? "pompe ON" : "pompe OFF");

  delay(500);
}