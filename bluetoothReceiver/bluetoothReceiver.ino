#include <BluetoothSerial.h>

// ————— CONFIG —————
BluetoothSerial SerialBT;
static const size_t BUF_SIZE = 256;
char bufSerial2[BUF_SIZE];
size_t idxSerial2 = 0;
char bufBT[BUF_SIZE];
size_t idxBT = 0;

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, /*RX=*/16, /*TX=*/17);

  if (!SerialBT.begin("ESP32_Cinturon")) {
    Serial.println("¡Error iniciando Bluetooth!");
    while (true) delay(1000);
  }
  Serial.println("Bluetooth iniciado: empareja con \"ESP32_Cinturon\"");
}

void loop() {
  // 1) Leer de Arduino → Bluetooth
  while (Serial2.available()) {
    char c = Serial2.read();
    if (c == '\n' || idxSerial2 >= BUF_SIZE - 1) {
      bufSerial2[idxSerial2] = '\0';
      if (idxSerial2) {
        SerialBT.println(bufSerial2);
        Serial.printf("BT↑ %s\n", bufSerial2);
      }
      idxSerial2 = 0;
    } else if (c != '\r') {
      bufSerial2[idxSerial2++] = c;
    }
  }

  // 2) Leer de Bluetooth → Arduino
  while (SerialBT.available()) {
    char c = SerialBT.read();
    if (c == '\n' || idxBT >= BUF_SIZE - 1) {
      bufBT[idxBT] = '\0';
      if (idxBT) {
        Serial2.println(bufBT);
        Serial.printf("BT↓ %s\n", bufBT);
      }
      idxBT = 0;
    } else if (c != '\r') {
      bufBT[idxBT++] = c;
    }
  }

  delay(5);
}
