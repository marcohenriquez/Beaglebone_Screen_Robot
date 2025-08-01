// Arduino Mega – control por Serial (USB) y Serial1 (pines 18/19)
// Extendido: end effector, rotación, pantalla, LEDs NeoPixel

#include <Servo.h>
#include <Adafruit_NeoPixel.h>

// --- Pines de pasos y dirección ---
const int stepPin1   = 3;
const int dirPin1    = 4;
const int enablePin1 = A0;

const int stepPin2   = 6;
const int dirPin2    = 7;
const int enablePin2 = A1;

const int stepPin3   = 9;
const int dirPin3    = 8;       // Moved from 10 to avoid conflict
const int enablePin3 = A2;

// --- Bomba, Solenoide y End Effector Open/Close ---
Servo bomba;
Servo solenoide;
const int pinBomba        = 46;
const int pinSolenoide    = 44;
const int pinEndEffector  = 45;  // Digital output open/close

// --- Servo de rotación del End Effector ---
Servo rotateEffector;
const int pinRotateEff    = 10;  // Servo pin (D10)

// --- Servo para mover la pantalla (eje 1) ---
Servo screenServo;
const int pinScreenServo  = 11;  // Servo pin que gira la pantalla

// --- Nuevo: Servo para ejes 2 y 3 ---
Servo segmentServo;
const int pinSegmentServo = 12;   // ← Servo pin que inclina la pantalla

const int restAngle       = 90;   // Ángulo de reposo
const int angleOffset     = 10;   // Desplazamiento por movimiento

// --- NeoPixel LEDs ---
#define PIXEL_PIN    2
#define NUM_PIXELS   8
Adafruit_NeoPixel pixels(NUM_PIXELS, PIXEL_PIN, NEO_GRB + NEO_KHZ800);

#define ENABLE_ACTIVE   LOW
#define ENABLE_INACTIVE HIGH

void setup() {
  // Consola USB
  Serial.begin(38400);
  while (!Serial);
  // UART1 con BBB
  Serial1.begin(38400);

  // Pines motores
  pinMode(stepPin1,   OUTPUT);
  pinMode(dirPin1,    OUTPUT);
  pinMode(enablePin1, OUTPUT);
  digitalWrite(enablePin1, ENABLE_INACTIVE);

  pinMode(stepPin2,   OUTPUT);
  pinMode(dirPin2,    OUTPUT);
  pinMode(enablePin2, OUTPUT);
  digitalWrite(enablePin2, ENABLE_INACTIVE);

  pinMode(stepPin3,   OUTPUT);
  pinMode(dirPin3,    OUTPUT);
  pinMode(enablePin3, OUTPUT);
  digitalWrite(enablePin3, ENABLE_INACTIVE);

  // Inicializa servos bomba/solenoide
  bomba.attach(pinBomba);
  solenoide.attach(pinSolenoide);
  bomba.write(0);
  solenoide.write(0);

  // End effector open/close
  pinMode(pinEndEffector, OUTPUT);
  digitalWrite(pinEndEffector, LOW);

  // Servos adicionales
  rotateEffector.attach(pinRotateEff);
  rotateEffector.write(0);
  screenServo.attach(pinScreenServo);
  screenServo.write(restAngle);

  // ← NUEVO: inicializar segundo servo
  segmentServo.attach(pinSegmentServo);   // ← NUEVO
  segmentServo.write(restAngle);          // ← NUEVO

  // LEDs NeoPixel
  pixels.begin();
  pixels.fill(0, 0, NUM_PIXELS);
  pixels.show();
}

void loop() {
  // Comandos desde USB
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n'); cmd.trim();
    processCommand(cmd);
  }
  // Comandos desde BBB
  if (Serial1.available()) {
    String cmd = Serial1.readStringUntil('\n'); cmd.trim();
    processCommand(cmd);
  }
}

void processCommand(const String &cmd) {
  if (cmd.startsWith("move")) {
    int motor = cmd.substring(5,6).toInt();
    int space = cmd.indexOf(' ',7);
    int steps = (space > 0)
                ? cmd.substring(7, space).toInt()
                : cmd.substring(7).toInt();
    char dir = cmd.charAt(cmd.length()-1);

    // Enciende LEDs y mueve pantalla/segmento
    startAxis(motor);
    moveScreen(motor, dir);

    // Ejecuta movimiento paso a paso
    switch (motor) {
      case 1: moveMotor(stepPin1, dirPin1, enablePin1, dir, steps); break;
      case 2: moveMotor(stepPin2, dirPin2, enablePin2, dir, steps); break;
      case 3: moveMotor(stepPin3, dirPin3, enablePin3, dir, steps); break;
    }

    // Apaga LEDs y retorna servos a reposo
    endAxis(motor);
    if (motor == 1) {
      screenServo.write(restAngle);
    } else {
      segmentServo.write(restAngle);      // ← NUEVO
    }
  }
  else if (cmd == "bomba on")  {
      bomba.write(180);
      solenoide.write(0);
  }
  else if (cmd == "bomba off")  { 
    bomba.write(0);
    solenoide.write(180);
    delay(5000);
    solenoide.write(0);
  }
  else if (cmd == "efector open")  digitalWrite(pinEndEffector, HIGH);
  else if (cmd == "efector close") digitalWrite(pinEndEffector, LOW);
  else if (cmd.startsWith("rotarEfector")) {
    int angle = cmd.substring(cmd.indexOf(' ')+1).toInt();
    angle = constrain(angle, 0, 180);
    rotateEffector.write(angle);
  }
}

void moveMotor(int stepPin, int dirPin, int enablePin, char dir, int steps) {
  digitalWrite(enablePin, ENABLE_ACTIVE);
  
  bool forward = (dir == 'f');
  digitalWrite(dirPin, forward ? HIGH : LOW);

  // Debug: imprimimos lo que acabamos de forzar
  Serial.print(" → Motor en pin "); Serial.print(stepPin);
  Serial.print(" dirPin="); Serial.print(dirPin);
  Serial.print(" nivel escrito="); Serial.print(forward ? "HIGH" : "LOW");
  Serial.print(" / nivel leído="); 
  Serial.println(digitalRead(dirPin) ? "HIGH" : "LOW");

  for (int i = 0; i < steps; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(800);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(800);
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
  if (motor == 1) {
    angle = restAngle + ((dir=='f') ? -angleOffset : angleOffset);
  } 
  else if (motor == 2) {
    // mismo desplazamiento que eje 1, pero invertido o igual según necesites
    angle = restAngle + ((dir=='f') ? angleOffset : -angleOffset);
  } 
  else if (motor == 3) {
    // invertido
    angle = restAngle + ((dir=='b') ? -angleOffset : angleOffset);
  }
  angle = constrain(angle, 0, 180);

  // Aplicar al servo correspondiente
  if (motor == 1) {
    screenServo.write(angle);
  } else {
    segmentServo.write(angle);  // ← NUEVO
  }
}
