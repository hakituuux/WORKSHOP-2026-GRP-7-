/*
 * Premier essai ESP8266 (NodeMCU) : diode RGB 4 pattes.
 *
 * Branchement (cathode commune, patte la plus longue vers GND) :
 *   rouge  -> resistance 220 ohm -> D5 (GPIO 14)
 *   vert   -> resistance 220 ohm -> D6 (GPIO 12)
 *   bleu   -> resistance 220 ohm -> D7 (GPIO 13)
 *   commun -> GND
 *
 * Si la diode est a anode commune (patte longue vers 3V3),
 * passe COMMON_ANODE a true.
 */

const bool COMMON_ANODE = false;

const int PIN_R = 14;  // D5
const int PIN_G = 12;  // D6
const int PIN_B = 13;  // D7

// Sur ESP8266, analogWrite va de 0 (eteint) a 1023 (plein).
const int PWM_MAX = 1023;

void setColor(int r, int g, int b) {
  if (COMMON_ANODE) {
    r = PWM_MAX - r;
    g = PWM_MAX - g;
    b = PWM_MAX - b;
  }
  analogWrite(PIN_R, r);
  analogWrite(PIN_G, g);
  analogWrite(PIN_B, b);
}

void setup() {
  pinMode(PIN_R, OUTPUT);
  pinMode(PIN_G, OUTPUT);
  pinMode(PIN_B, OUTPUT);
  setColor(0, 0, 0);

  Serial.begin(115200);
  Serial.println("ESP8266 RGB pret");
}

void loop() {
  Serial.println("rouge");
  setColor(PWM_MAX, 0, 0);
  delay(800);

  Serial.println("vert");
  setColor(0, PWM_MAX, 0);
  delay(800);

  Serial.println("bleu");
  setColor(0, 0, PWM_MAX);
  delay(800);

  Serial.println("blanc");
  setColor(PWM_MAX, PWM_MAX, PWM_MAX);
  delay(800);

  Serial.println("eteint");
  setColor(0, 0, 0);
  delay(400);
}
