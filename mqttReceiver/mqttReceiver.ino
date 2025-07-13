/*
 * ESP32 - Cinturon Postura MQTT (Solo MQTT)
 * CONEXIONES: Arduino TX1->ESP32 RX2(16), Arduino RX1->ESP32 TX2(17), GND común
 * MQTT: mosquitto_sub -h localhost -t "cinturon/sensores" -v
 */

#include <WiFi.h>
#include <PubSubClient.h>

// --- CONFIGURACIÓN ---
const char* ssid = "ZTE_2.4G_exCHWZ";
const char* password = "KzDaF27N";
const char* mqtt_server = "192.168.1.40";

// --- OBJETOS ---
WiFiClient espClient;
PubSubClient mqtt_client(espClient);

// --- VARIABLES ---
String buffer_serial = "";
unsigned long ultimo_heartbeat = 0;

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, 16, 17); // RX=16, TX=17
  
  Serial.println("ESP32 Cinturon MQTT iniciando...");
  
  // WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectado: " + WiFi.localIP().toString());
  
  // MQTT
  mqtt_client.setServer(mqtt_server, 1883);
  
  Serial.println("Sistema listo");
}

void loop() {
  // Mantener MQTT
  if (!mqtt_client.connected()) {
    reconectar_mqtt();
  }
  mqtt_client.loop();
  
  // Leer Arduino
  while (Serial2.available()) {
    char c = Serial2.read();
    if (c == '\n') {
      if (buffer_serial.length() > 0) {
        procesar_datos(buffer_serial);
        buffer_serial = "";
      }
    } else if (c != '\r') {
      buffer_serial += c;
    }
  }
  
  // Heartbeat cada 30 segundos
  if (millis() - ultimo_heartbeat > 30000) {
    ultimo_heartbeat = millis();
    String estado = "ESP32_OK|" + WiFi.localIP().toString();
    
    if (mqtt_client.connected()) {
      mqtt_client.publish("cinturon/heartbeat", estado.c_str());
    }
    
    Serial.println("💓 " + estado);
  }
  
  delay(10);
}

void reconectar_mqtt() {
  while (!mqtt_client.connected()) {
    Serial.print("Conectando MQTT...");
    if (mqtt_client.connect("ESP32_Cinturon")) {
      Serial.println(" OK");
    } else {
      Serial.print(" Error: ");
      Serial.println(mqtt_client.state());
      delay(5000);
    }
  }
}

void procesar_datos(String json_data) {
  Serial.println("RX: " + json_data);
  
  // Enviar por MQTT (datos completos)
  if (mqtt_client.connected()) {
    if (mqtt_client.publish("cinturon/sensores", json_data.c_str())) {
      Serial.println("✓ MQTT enviado");
    }
  }
}