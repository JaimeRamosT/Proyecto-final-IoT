#include "I2Cdev.h"
#include "MPU6050.h"
#include "Wire.h"

// Amarillo: Lumbar
// Naranja: Toráxico
// Morado: Axial

// --- CONSTANTES DE CONFIGURACIÓN ---
// Pines
const int MOTOR_PIN_LUMBAR = 3;
const int MOTOR_PIN_TORACICO = 4;
// const int MOTOR_PIN_HOMBRO = 5;   -- Morido

// Umbrales y Tiempos
const float UMBRAL_ANGULO_ALERTA_LUMBAR = 15.0; // Grados de desviación permitidos. Aumentado ligeramente para la espalda torácica.
const float UMBRAL_ANGULO_ALERTA_TORACICO = 10.0;
const float UMBRAL_ANGULO_ALERTA_HOMBRO = 12.0;
const unsigned long TIEMPO_CONFIRMACION_MALA_POSTURA = 1000; // 1 segundo en mala postura para activar el motor (evita falsos positivos).

// Sensor y Filtro
const float SENSITIVIDAD_GIROSCOPO = 131.0; // Para la configuración por defecto del MPU6050
const unsigned long INTERVALO_LECTURA = 50; // 50ms = 20Hz

// Parámetros del Filtro de Kalman (ajusta estos si es necesario)
const float Q_ANGLE = 0.001; // Ruido del proceso para el ángulo
const float Q_BIAS  = 0.003; // Ruido del proceso para la deriva del giroscopio
const float R_MEAS  = 0.03;  // Ruido de la medición del acelerómetro

// Calibración
const int MUESTRAS_CALIBRACION = 100; // Número de lecturas para promediar en la calibración

// --- PCA9548A ---
#define MUX_ADDR 0x70
#define NUM_SENSORES 2
#define CANAL_LUMBAR 0
#define CANAL_TORACICO 3
#define CANAL_HOMBRO 2

MPU6050 mpu;

// --- Estado de sensores ---
float anguloReferenciaLumbar = 0.0, anguloActualLumbar = 0.0;
float anguloReferenciaToracico = 0.0, anguloActualToracico = 0.0;
float anguloReferenciaHombro = 0.0, anguloActualHombro = 0.0;

bool malaPosturaLumbar = false, malaPosturaToracico = false, malaPosturaHombro = false;
unsigned long tiempoLumbar = 0, tiempoToracico = 0, tiempoHombro;

// Filtros Kalman independientes
float xhatLumbar[2] = {0, 0}, xhatToracico[2] = {0, 0}, xhatHombro[2] = {0, 0};
float PLumbar[2][2] = {{1, 0}, {0, 1}}, PToracico[2][2] = {{1, 0}, {0, 1}}, PHombro[2][2] = {{1, 0}, {0, 1}};

// Temporizador
unsigned long tiempoAnteriorLoop = 0;

// --- Funciones ---

void seleccionarCanalMux(uint8_t canal) {
  Wire.beginTransmission(MUX_ADDR);
  Wire.write(1 << canal);
  Wire.endTransmission();
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(115200);
  Wire.begin();

  pinMode(MOTOR_PIN_LUMBAR, OUTPUT);
  pinMode(MOTOR_PIN_TORACICO, OUTPUT);
  digitalWrite(MOTOR_PIN_LUMBAR, LOW);
  digitalWrite(MOTOR_PIN_TORACICO, LOW);

  // Inicialización de sensores
  seleccionarCanalMux(CANAL_LUMBAR);
  mpu.initialize();
  if (!mpu.testConnection()) {
    Serial.println("MPU LUMBAR no detectado");
    while (1);
  }
  Serial.println("MPU LUMBAR conectado.");

  seleccionarCanalMux(CANAL_TORACICO);
  mpu.initialize();
  if (!mpu.testConnection()) {
    Serial.println("MPU TORÁCICO no detectado");
    while (1);
  }
  Serial.println("MPU TORÁCICO conectado.");

  seleccionarCanalMux(CANAL_HOMBRO);
  mpu.initialize();
  if (!mpu.testConnection()) {
    Serial.println("MPU HOMBRO no detectado");
    while (1);
  }
  Serial.println("MPU HOMBRO conectado.");

  // Calibración
  calibrarSensor(CANAL_LUMBAR, anguloReferenciaLumbar, xhatLumbar);
  calibrarSensor(CANAL_TORACICO, anguloReferenciaToracico, xhatToracico);
  calibrarSensor(CANAL_HOMBRO, anguloReferenciaHombro, xhatHombro);


  tiempoAnteriorLoop = millis();
  Serial.println("\nSistema listo.");
}

void loop() {
  unsigned long ahora = millis();
  float dt = (ahora - tiempoAnteriorLoop) / 1000.0;

  if (ahora - tiempoAnteriorLoop >= INTERVALO_LECTURA) {
    tiempoAnteriorLoop = ahora;

    // LUMBAR
    seleccionarCanalMux(CANAL_LUMBAR);
    anguloActualLumbar = calcularAngulo(dt, xhatLumbar, PLumbar);
    verificarPostura(UMBRAL_ANGULO_ALERTA_LUMBAR, anguloActualLumbar, anguloReferenciaLumbar, malaPosturaLumbar, tiempoLumbar, MOTOR_PIN_LUMBAR);

    // TORÁCICO
    seleccionarCanalMux(CANAL_TORACICO);
    anguloActualToracico = calcularAngulo(dt, xhatToracico, PToracico);
    verificarPostura(UMBRAL_ANGULO_ALERTA_TORACICO, anguloActualToracico, anguloReferenciaToracico, malaPosturaToracico, tiempoToracico, MOTOR_PIN_TORACICO);

    // HOMBRO
    seleccionarCanalMux(CANAL_HOMBRO);
    anguloActualHombro = calcularAngulo(dt, xhatHombro, PHombro);
    verificarPostura(UMBRAL_ANGULO_ALERTA_HOMBRO, anguloActualHombro, anguloReferenciaHombro, malaPosturaHombro, tiempoHombro, MOTOR_PIN_LUMBAR);

    // Mostrar estado
    imprimirEstado("Lumbar", UMBRAL_ANGULO_ALERTA_LUMBAR, anguloActualLumbar, anguloReferenciaLumbar, MOTOR_PIN_LUMBAR);
    imprimirEstado("Toráxico", UMBRAL_ANGULO_ALERTA_TORACICO, anguloActualToracico, anguloReferenciaToracico, MOTOR_PIN_TORACICO);
    imprimirEstado("Hombro", UMBRAL_ANGULO_ALERTA_HOMBRO, anguloActualHombro, anguloReferenciaHombro, MOTOR_PIN_LUMBAR);
  }
  enviarDatosESP32();
}

void calibrarSensor(uint8_t canal, float &ref, float xhat[2]) {
  Serial.print("\nCalibrando canal ");
  Serial.print(canal);
  Serial.println("... Mantente quieto.");
  delay(3000);

  float suma = 0;
  for (int i = 0; i < MUESTRAS_CALIBRACION; i++) {
    seleccionarCanalMux(canal);
    suma += obtenerAnguloAcelerometro();
    delay(10);
  }
  ref = suma / MUESTRAS_CALIBRACION;
  xhat[0] = ref;

  Serial.print("Ángulo de referencia canal ");
  Serial.print(canal);
  Serial.print(": ");
  Serial.println(ref);
}

float calcularAngulo(float dt, float xhat[2], float P[2][2]) {
  int16_t ax, ay, az, gx, gy, gz;
  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
  float angAcc = atan2(ax, az) * 180.0 / PI;
  float velGyro = gy / SENSITIVIDAD_GIROSCOPO;
  return kalmanUpdate(angAcc, velGyro, dt, xhat, P);
}

float kalmanUpdate(float medidaAcc, float velGyro, float dt, float xhat[2], float P[2][2]) {
  // Predicción
  xhat[0] += dt * (velGyro - xhat[1]);
  P[0][0] += dt * (dt * P[1][1] - P[0][1] - P[1][0] + Q_ANGLE);
  P[0][1] -= dt * P[1][1];
  P[1][0] -= dt * P[1][1];
  P[1][1] += Q_BIAS * dt;

  // Actualización
  float S = P[0][0] + R_MEAS;
  float K[2] = {P[0][0] / S, P[1][0] / S};
  float y = medidaAcc - xhat[0];

  xhat[0] += K[0] * y;
  xhat[1] += K[1] * y;

  float P00_temp = P[0][0], P01_temp = P[0][1];
  P[0][0] -= K[0] * P00_temp;
  P[0][1] -= K[0] * P01_temp;
  P[1][0] -= K[1] * P00_temp;
  P[1][1] -= K[1] * P01_temp;

  return xhat[0];
}

float obtenerAnguloAcelerometro() {
  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);
  return atan2(ax, az) * 180.0 / PI;
}

void verificarPostura(float anguloAlerta, float anguloActual, float anguloRef, bool &malaPostura, unsigned long &tInicio, int pin) {
  float dif = anguloActual - anguloRef;
  if (abs(dif) > anguloAlerta) {
    if (!malaPostura) {
      malaPostura = true;
      tInicio = millis();
    }
  } else {
    malaPostura = false;
    digitalWrite(pin, LOW);
  }

  if (malaPostura && (millis() - tInicio > TIEMPO_CONFIRMACION_MALA_POSTURA)) {
    digitalWrite(pin, HIGH);
  }
}

void imprimirEstado(const char* nombre, float anguloAlerta, float angulo, float ref, int pin) {
  Serial.print(nombre);
  Serial.print(" | Ángulo: ");
  Serial.print(angulo, 1);
  Serial.print(" | Ref: ");
  Serial.print(ref, 1);
  Serial.print(" | Estado: ");
  if (abs(angulo - ref) > anguloAlerta) {
    if (digitalRead(pin) == HIGH)
      Serial.println("ALERTA (Motor ON)");
    else
      Serial.println("Mala postura (Confirmando...)");
  } else {
    Serial.println("Postura OK");
  }
}

void enviarDatosESP32() {
  // Crear mensaje JSON con los datos de los sensores
  Serial1.print("{");
  Serial1.print("\"lumbar\":{\"angulo\":");
  Serial1.print(anguloActualLumbar, 2);
  Serial1.print(",\"referencia\":");
  Serial1.print(anguloReferenciaLumbar, 2);
  Serial1.print(",\"alerta\":");
  Serial1.print((abs(anguloActualLumbar - anguloReferenciaLumbar) > UMBRAL_ANGULO_ALERTA_LUMBAR) ? "true" : "false");
  Serial1.print(",\"motor\":");
  Serial1.print((digitalRead(MOTOR_PIN_LUMBAR) == HIGH) ? "true" : "false");
  Serial1.print("},");
  
  Serial1.print("\"toracico\":{\"angulo\":");
  Serial1.print(anguloActualToracico, 2);
  Serial1.print(",\"referencia\":");
  Serial1.print(anguloReferenciaToracico, 2);
  Serial1.print(",\"alerta\":");
  Serial1.print((abs(anguloActualToracico - anguloReferenciaToracico) > UMBRAL_ANGULO_ALERTA_TORACICO) ? "true" : "false");
  Serial1.print(",\"motor\":");
  Serial1.print((digitalRead(MOTOR_PIN_TORACICO) == HIGH) ? "true" : "false");
  Serial1.print("},");
  
  Serial1.print("\"hombro\":{\"angulo\":");
  Serial1.print(anguloActualHombro, 2);
  Serial1.print(",\"referencia\":");
  Serial1.print(anguloReferenciaHombro, 2);
  Serial1.print(",\"alerta\":");
  Serial1.print((abs(anguloActualHombro - anguloReferenciaHombro) > UMBRAL_ANGULO_ALERTA_HOMBRO) ? "true" : "false");
  Serial1.print(",\"motor\":");
  Serial1.print((digitalRead(MOTOR_PIN_LUMBAR) == HIGH) ? "true" : "false");
  Serial1.print("},");
  
  Serial1.print("\"timestamp\":");
  Serial1.print(millis());
  Serial1.println("}");
}