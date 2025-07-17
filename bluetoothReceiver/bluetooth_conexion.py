import serial
import time
import paho.mqtt.client as mqtt

# ————— CONFIGURACIÓN —————
BT_PORT   = 'COM8'           # o '/dev/tty.SLAB_USBtoUART' según tu SO
BAUD_RATE = 115200
MQTT_BROKER = 'localhost'
MQTT_PORT   = 1883

# Cliente MQTT
client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# Conexión serial Bluetooth
ser = serial.Serial(BT_PORT, BAUD_RATE, timeout=1)
time.sleep(2)  # dejar que se inicie

print("Conectado a Bluetooth en", BT_PORT)
try:
    while True:
        line = ser.readline().decode('utf-8').strip()
        if not line:
            continue
        print("Recibido BT:", line)

        # Publicar en MQTT
        client.publish("cinturon/sensores", line)

        # (Opcional) Leer comandos desde MQTT 
        # y reenviarlos por serial BT:
        # def on_message(client, userdata, msg):
        #     ser.write(msg.payload + b'\n')
        # client.subscribe("cinturon/comandos")
        # client.on_message = on_message

except KeyboardInterrupt:
    pass
finally:
    client.loop_stop()
    ser.close()
    client.disconnect()
