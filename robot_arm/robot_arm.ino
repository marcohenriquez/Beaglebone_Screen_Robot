#include <Arduino.h>pbd play_all
#include <limits.h>          // Para LONG_MIN como indicador de error
#include <Servo.h>
#include <Adafruit_NeoPixel.h>
#include "MKS_SERVO42.h"

// ——— UARTs ———
// UART0 (Serial):   Host ↔ BeagleBone
// UART1 (Serial1):  Motor 1 encoder
// UART2 (Serial2):  Motor 2 encoder
// UART4 (Serial4):  Motor 3 encoder
// UART3 (Serial3):  Debug USB

// ——— Pines de los drivers paso a paso ———
const int stepPin1   = 3,  dirPin1    = 4,  enablePin1 = A3;
const int stepPin2   = 6,  dirPin2    = 7,  enablePin2 = A1;
const int stepPin3   = 9,  dirPin3    = 8,  enablePin3 = A2;
const int enableActive   = LOW;
const int enableInactive = HIGH;

// ——— Objetos MKS SERVO42 ———
MKS_SERVO42 servo1, servo2, servo3;
const byte ID1 = 1, ID2 = 2, ID3 = 3;

// ——— Servos auxiliares ———
Servo bomba, solenoide, endEffectorServo, rotateEffector, screenServo, segmentServo;
const int pinBomba        = 46;
const int pinSolenoide    = 44;
const int pinEndEffector  = 13;
const int pinRotateEff    = 10;
const int pinScreenServo  = 11;
const int pinSegmentServo = 12;
const int restAngle       = 80;
const int angleOffset     = 4;

// ——— NeoPixel ———
#define PIXEL_PIN  2
#define NUM_PIXELS 8
Adafruit_NeoPixel pixels(NUM_PIXELS, PIXEL_PIN, NEO_GRB + NEO_KHZ800);

// ——— Grabación de encoders ———
bool recording = false;
byte recordAxis = 0;                   // 1 o 2
unsigned long lastSample = 0;
const unsigned long sampleInterval = 1000; // ms entre muestras

// ——— Modo PBD ———
bool pbdMode = false;  // Programación por demostración activa?

// Prototipos\ void processCommand(const String &cmd);
void moveMotor(int, int, int, char, int);
void startAxis(int);
void endAxis(int);
void moveScreen(int, char);
void disableAxis(int);
void enableAxis(int);

void setup() {

  // — Host ↔ BeagleBone en UART0 —
  Serial.begin(38400);
  while (!Serial);

  // — Motor 1 en UART1 —
  Serial1.begin(38400);
  servo1.initialize(&Serial1, 38400, 100);

  // — Motor 2 en UART2 —
  Serial2.begin(38400);
  servo2.initialize(&Serial2, 38400, 100);

  // — Motor 3 en UART4 —
  Serial3.begin(38400);
  servo3.initialize(&Serial3, 38400, 100);

  // — Pines de drivers como salida —
  pinMode(stepPin1, OUTPUT); pinMode(dirPin1, OUTPUT); pinMode(enablePin1, OUTPUT);
  digitalWrite(enablePin1, enableInactive);
  pinMode(stepPin2, OUTPUT); pinMode(dirPin2, OUTPUT); pinMode(enablePin2, OUTPUT);
  digitalWrite(enablePin2, enableInactive);
  pinMode(stepPin3, OUTPUT); pinMode(dirPin3, OUTPUT); pinMode(enablePin3, OUTPUT);
  digitalWrite(enablePin3, enableInactive);

  // — Servos auxiliares —
  bomba.attach(pinBomba);
  solenoide.attach(pinSolenoide);
  endEffectorServo.attach(pinEndEffector);
  rotateEffector.attach(pinRotateEff);
  screenServo.attach(pinScreenServo);
  segmentServo.attach(pinSegmentServo);
  bomba.write(0); solenoide.write(0);
  endEffectorServo.write(0); rotateEffector.write(0);
  screenServo.write(restAngle); segmentServo.write(restAngle);

  // — NeoPixel —
  pixels.begin();
  pixels.fill(0, 0, NUM_PIXELS);
  pixels.show();
}

void loop() {
  // — Procesar comandos —
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    processCommand(cmd);
  }

  // — Muestreo en grabación dentro de PBD —
  if (pbdMode && recording && (millis() - lastSample >= sampleInterval)) {
    lastSample = millis();
    long pos = LONG_MIN;
    if (recordAxis == 1) pos = servo1.getCurrentPosition(ID1);
    else if (recordAxis == 2) pos = servo2.getCurrentPosition(ID2);
    else if (recordAxis == 3) pos = servo3.getCurrentPosition(ID3);
    if (pos != LONG_MIN) {
      // Enviar al BeagleBone y debug JSON
      String js = String("{\"axis\":") + recordAxis
                  + ",\"pos\":" + pos + "}";
      Serial.println(js);
    }
  }
}

void processCommand(const String &cmd) {

  if (cmd == "pbd start") {
    pbdMode = true;
    return;
  }
  if (cmd == "pbd stop") {
    pbdMode = false;
    recording = false;
    endAxis(recordAxis);
    return;
  }

  if (cmd.startsWith("move")) {
    int motor = cmd.substring(5,6).toInt();
    int space = cmd.indexOf(' ',7);
    int steps = (space > 0)
                ? cmd.substring(7, space).toInt()
                : cmd.substring(7).toInt();
    char dir = cmd.charAt(cmd.length()-1);
    startAxis(motor);
    moveScreen(motor, dir);
    switch (motor) {
      case 1: moveMotor(stepPin1, dirPin1, enablePin1, dir, steps); break;
      case 2: moveMotor(stepPin2, dirPin2, enablePin2, dir, steps); break;
      case 3: moveMotor(stepPin3, dirPin3, enablePin3, dir, steps); break;
    }
    delay(100);
    endAxis(motor);
    if (motor==1) screenServo.write(restAngle);
    if (motor==2) segmentServo.write(restAngle);
    if (motor==3) segmentServo.write(restAngle);
  }
  else if (cmd.startsWith("record start")) {
    byte m = cmd.substring(cmd.lastIndexOf(' ') + 1).toInt();
    if ((m==1||m==2||m==3) && pbdMode) {
      recordAxis = m;
      recording = true;
      lastSample = millis();
      disableAxis(m);
      startAxis(m);
      Serial.println(F("{\"record\":\"start\"}"));
    }
  }
  else if (cmd == "record stop") {
    if (recording && pbdMode) {
      recording = false;
      enableAxis(recordAxis);
      endAxis(recordAxis);
      Serial.println(F("{\"record\":\"stop\"}"));
    }
  }
}

void moveMotor(int stepPin, int dirPin, int enablePin, char dir, int steps) {
  digitalWrite(enablePin, enableActive);
  digitalWrite(dirPin, dir=='f' ? HIGH : LOW);
  for (int i = 0; i < steps; i++) {
    digitalWrite(stepPin, HIGH); delayMicroseconds(600);
    digitalWrite(stepPin, LOW);  delayMicroseconds(600);
  }
}

void startAxis(int m) {
  int i0 = (m-1)*2;
  pixels.setPixelColor(i0,   pixels.Color(255,255,255));
  pixels.setPixelColor(i0+1, pixels.Color(255,255,255));
  pixels.show();
}

void endAxis(int m) {
  int i0 = (m-1)*2;
  pixels.setPixelColor(i0,   0);
  pixels.setPixelColor(i0+1, 0);
  pixels.show();
}

void moveScreen(int motor, char dir) {
  int angle = restAngle;
  if (motor==1) {
    angle += dir=='f'?angleOffset:-angleOffset;
    screenServo.write(constrain(angle,0,180));
  }
  else if(motor==2) {
    angle += dir=='f'?-angleOffset:angleOffset;
    segmentServo.write(constrain(angle,0,180));
  }
  else if(motor==3) {
    angle += dir=='b'?angleOffset:-angleOffset;
    segmentServo.write(constrain(angle,0,180));
  }
}

void disableAxis(int m) {
  digitalWrite(m==1?enablePin1:(m==2?enablePin2:enablePin3), enableInactive);
}

void enableAxis(int m) {
  digitalWrite(m==1?enablePin1:(m==2?enablePin2:enablePin3), enableActive);
}


