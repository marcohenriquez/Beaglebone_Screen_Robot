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
  Serial.begin(38400);
  while(!Serial);  // Espera a que el USB-Serial esté listo

  // Configuración de pines motores
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

  // Inicializa bomba y solenoide
  bomba.attach(pinBomba);
  solenoide.attach(pinSolenoide);
  bomba.write(0);
  solenoide.write(0);

  // ACK de que el sistema está listo
  Serial.println("ACK:ready");
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    // Envío de ACK de recepción
    Serial.print("ACK:");
    Serial.println(command);

    // Procesar comando
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
          Serial.println("ERROR:InvalidMotor");
      }
    }
    else if (command == "bomba on") {
      bomba.write(180);
    }
    else if (command == "bomba off") {
      bomba.write(0);
    }
    else if (command == "solenoide on") {
      solenoide.write(180);
    }
    else if (command == "solenoide off") {
      solenoide.write(0);
    }
    else {
      Serial.println("ERROR:UnknownCommand");
    }

    // Envío de DONE al terminar
    Serial.print("DONE:");
    Serial.println(command);
  }
}

void moveMotor(int stepPin, int dirPin, int enablePin, char dir, int steps) {
  digitalWrite(enablePin, ENABLE_ACTIVE);

  // Definición de dirección
  if (dir == 'f') {
    digitalWrite(dirPin, HIGH);
  } else {
    digitalWrite(dirPin, LOW);
  }

  // Generar pulsos
  for (int i = 0; i < steps; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(800);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(800);
  }

  // El motor queda bloqueado (ENABLE activo)
}
