#include <Servo.h>

// Pines de pasos y dirección
const int stepPin1 = 3;
const int dirPin1 = 4;
const int enablePin1 = A0;

const int stepPin2 = 6;
const int dirPin2 = 7;
const int enablePin2 = A1;

const int stepPin3 = 9;
const int dirPin3 = 10;
const int enablePin3 = A2;

// Bomba y solenoide
Servo bomba;
Servo solenoide;

const int pinBomba = 44;
const int pinSolenoide = 46;

// Define nivel activo del ENABLE
#define ENABLE_ACTIVE LOW
#define ENABLE_INACTIVE HIGH

void setup() {
  Serial.begin(115200);

  // Pines motores
  pinMode(stepPin1, OUTPUT);
  pinMode(dirPin1, OUTPUT);
  pinMode(enablePin1, OUTPUT);
  digitalWrite(enablePin1, ENABLE_INACTIVE);

  pinMode(stepPin2, OUTPUT);
  pinMode(dirPin2, OUTPUT);
  pinMode(enablePin2, OUTPUT);
  digitalWrite(enablePin2, ENABLE_INACTIVE);

  pinMode(stepPin3, OUTPUT);
  pinMode(dirPin3, OUTPUT);
  pinMode(enablePin3, OUTPUT);
  digitalWrite(enablePin3, ENABLE_INACTIVE);

  // Bomba y solenoide
  bomba.attach(pinBomba);
  solenoide.attach(pinSolenoide);
  bomba.write(0);
  solenoide.write(0);

  Serial.println("🔧 Sistema listo. Enviar comandos.");
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    processCommand(command);
  }
}

void processCommand(String command) {
  if (command.startsWith("move")) {
    int motor = command.substring(5, 6).toInt();
    int steps = command.substring(7, command.indexOf(' ', 7)).toInt();
    char dir = command.charAt(command.length() - 1);

    switch (motor) {
      case 1:
        moveMotor(stepPin1, dirPin1, enablePin1, dir, steps);
        break;
      case 2:
        moveMotor(stepPin2, dirPin2, enablePin2, dir, steps);
        break;
      case 3:
        moveMotor(stepPin3, dirPin3, enablePin3, dir, steps);
        break;
      default:
        Serial.println("⚠️ Motor inválido. Usa 1, 2 o 3.");
    }
  }
  else if (command == "bomba on") {
    bomba.write(180);
    Serial.println("🟢 Bomba activada.");
  }
  else if (command == "bomba off") {
    bomba.write(0);
    Serial.println("🔴 Bomba desactivada.");
  }
  else if (command == "solenoide on") {
    solenoide.write(180);
    Serial.println("🟢 Solenoide activado.");
  }
  else if (command == "solenoide off") {
    solenoide.write(0);
    Serial.println("🔴 Solenoide desactivado.");
  }
  else {
    Serial.println("⚠️ Comando no reconocido.");
  }
}

void moveMotor(int stepPin, int dirPin, int enablePin, char dir, int steps) {
  digitalWrite(enablePin, ENABLE_ACTIVE);  // Activar

  if (dir == 'f') {
    digitalWrite(dirPin, HIGH);
  } else if (dir == 'b') {
    digitalWrite(dirPin, LOW);
  } else {
    Serial.println("⚠️ Dirección inválida. Usa 'f' o 'b'.");
    return;
  }

  for (int i = 0; i < steps; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(800);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(800);
  }

  // No se libera el motor
  Serial.println("✅ Movimiento completado.");
}
