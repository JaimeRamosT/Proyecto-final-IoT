from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import paho.mqtt.client as mqtt
import json
from datetime import datetime
from collections import deque
import uvicorn
import threading

# 🔧 CONFIGURACIÓN SIMPLE
MQTT_BROKER = "192.168.1.40"  # Misma IP que usa el ESP32
MQTT_PORT = 1883
MQTT_TOPIC = "cinturon/sensores"  # CORREGIDO: mismo topic que usa el ESP32
WEB_PORT = 8000

# 📊 Variables globales para datos
current_data = None
eventos_malas_posturas = deque(maxlen=100)  # Últimos 100 eventos
estadisticas = {
    "total_malas": 0,
    "malas_hoy": 0,
    "porcentaje_buena": 100
}

app = FastAPI(title="Monitor Postura WiFi")

# 🔌 Cliente MQTT
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Conectado a MQTT broker: {MQTT_BROKER}")
        client.subscribe(MQTT_TOPIC)
        print(f"📡 Suscrito al topic: {MQTT_TOPIC}")
    else:
        print(f"❌ Error MQTT: {rc}")

def on_message(client, userdata, msg):
    global current_data, eventos_malas_posturas, estadisticas
    
    try:
        # Decodificar y parsear datos JSON
        payload = msg.payload.decode()
        print(f"📨 Mensaje recibido: {payload}")
        
        data = json.loads(payload)
        
        # Actualizar datos actuales
        current_data = {
            "lumbar": data["lumbar"],
            "toracico": data["toracico"], 
            "hombro": data["hombro"],
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "fecha": datetime.now().strftime("%Y-%m-%d")
        }
        
        # Verificar si hay mala postura
        mala_postura = (
            data["lumbar"]["malaPostura"] or 
            data["toracico"]["malaPostura"] or 
            data["hombro"]["malaPostura"]
        )
        
        # Agregar evento si hay mala postura
        if mala_postura:
            sensores_afectados = []
            if data["lumbar"]["malaPostura"]:
                sensores_afectados.append("Lumbar")
            if data["toracico"]["malaPostura"]:
                sensores_afectados.append("Torácico")
            if data["hombro"]["malaPostura"]:
                sensores_afectados.append("Hombro")
            
            evento = {
                "timestamp": current_data["timestamp"],
                "fecha": current_data["fecha"],
                "sensores": ", ".join(sensores_afectados)
            }
            eventos_malas_posturas.appendleft(evento)
            
            # Actualizar estadísticas
            estadisticas["total_malas"] += 1
            
            # Contar malas posturas de hoy
            hoy = datetime.now().strftime("%Y-%m-%d")
            estadisticas["malas_hoy"] = sum(1 for e in eventos_malas_posturas if e["fecha"] == hoy)
        
        print(f"📊 Datos procesados: {current_data['timestamp']} - Mala postura: {mala_postura}")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error JSON: {e}")
        print(f"📝 Payload recibido: {msg.payload.decode()}")
    except KeyError as e:
        print(f"❌ Error clave faltante: {e}")
        print(f"📝 Datos recibidos: {data}")
    except Exception as e:
        print(f"❌ Error procesando datos: {e}")

# Inicializar MQTT
def init_mqtt():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"🔄 Conectando a broker MQTT: {MQTT_BROKER}:{MQTT_PORT}")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"❌ Error MQTT: {e}")

# 🌐 Rutas Web
@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Dashboard principal - Todo en un solo archivo"""
    return '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor de Postura WiFi</title>
    <style>
        :root {
            --color1: #12170c; --color2: #124645; --color3: #159a68;
            --color4: #ceda78; --color5: #f8efe1;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, var(--color4), var(--color5));
            min-height: 100vh; padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, var(--color1), var(--color2));
            color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;
            text-align: center;
        }
        .status { 
            background: var(--color3); color: white; padding: 8px 16px; 
            border-radius: 20px; display: inline-block; margin-top: 10px;
        }
        .postura-general {
            padding: 15px; border-radius: 10px; margin-bottom: 20px;
            text-align: center; font-weight: bold; font-size: 1.1rem;
            background: #ef4444; color: white;
        }
        .postura-general.buena { background: var(--color3); }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .card {
            background: rgba(248, 239, 225, 0.9); border-radius: 15px; padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .card h3 { color: var(--color1); margin-bottom: 15px; }
        .sensor {
            display: flex; justify-content: space-between; align-items: center;
            padding: 12px; margin-bottom: 10px; border-radius: 8px;
            border-left: 4px solid var(--color3);
        }
        .sensor.mala { border-left-color: #ef4444; background: rgba(239, 68, 68, 0.1); }
        .badge { 
            background: var(--color3); color: white; padding: 4px 12px; 
            border-radius: 15px; font-size: 0.8rem; font-weight: bold;
        }
        .badge.mala { background: #ef4444; }
        .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .stat {
            background: rgba(206, 218, 120, 0.2); padding: 15px; 
            border-radius: 10px; text-align: center;
        }
        .stat-number { font-size: 2rem; font-weight: bold; color: var(--color1); }
        .stat-label { color: var(--color2); font-size: 0.9rem; margin-top: 5px; }
        .timeline-card { grid-column: 1 / -1; }
        .timeline { max-height: 300px; overflow-y: auto; padding: 10px; }
        .evento {
            display: flex; align-items: center; padding: 10px; margin-bottom: 10px;
            border-radius: 8px; background: rgba(239, 68, 68, 0.1);
            border-left: 4px solid #ef4444;
        }
        .evento-icon {
            width: 30px; height: 30px; border-radius: 50%; background: #ef4444;
            display: flex; align-items: center; justify-content: center;
            color: white; margin-right: 15px; font-size: 0.8rem;
        }
        .btn {
            background: #ef4444; color: white; border: none; padding: 10px 20px;
            border-radius: 5px; cursor: pointer; font-weight: bold; margin-bottom: 15px;
        }
        .loading { text-align: center; color: var(--color2); padding: 20px; }
        .connection-info {
            background: rgba(18, 70, 69, 0.1); padding: 10px; border-radius: 5px;
            margin-top: 10px; font-size: 0.8rem; color: var(--color2);
        }
        @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } .stats { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏃 Monitor de Postura WiFi</h1>
        <div class="status" id="status">Conectando...</div>
        <div class="connection-info">
            MQTT: ''' + MQTT_BROKER + ''' | Topic: ''' + MQTT_TOPIC + '''
        </div>
    </div>

    <div class="postura-general" id="posturaGeneral">⏳ Cargando...</div>

    <div class="grid">
        <div class="card">
            <h3>📊 Sensores</h3>
            <div id="sensores">
                <div class="loading">Esperando datos MQTT...</div>
            </div>
        </div>

        <div class="card">
            <h3>📈 Estadísticas</h3>
            <div class="stats">
                <div class="stat">
                    <div class="stat-number" id="totalMalas">0</div>
                    <div class="stat-label">Total Malas</div>
                </div>
                <div class="stat">
                    <div class="stat-number" id="malasHoy">0</div>
                    <div class="stat-label">Malas Hoy</div>
                </div>
            </div>
        </div>

        <div class="card timeline-card">
            <h3>⚠️ Eventos Recientes</h3>
            <button class="btn" onclick="limpiarEventos()">🗑️ Limpiar</button>
            <div class="timeline" id="timeline">
                <div class="loading">Sin eventos...</div>
            </div>
        </div>
    </div>

    <script>
        let actualizando = true;

        async function cargarDatos() {
            try {
                const resp = await fetch('/api/datos');
                const data = await resp.json();
                
                if (data.success) {
                    document.getElementById('status').textContent = 'Conectado MQTT ✓';
                    mostrarDatos(data.data);
                } else {
                    document.getElementById('status').textContent = 'Sin datos MQTT';
                }
            } catch (error) {
                document.getElementById('status').textContent = 'Error conexión ❌';
                console.error('Error:', error);
            }
        }

        function mostrarDatos(data) {
            // Actualizar sensores
            const sensores = document.getElementById('sensores');
            sensores.innerHTML = `
                <div class="sensor ${data.lumbar.malaPostura ? 'mala' : ''}">
                    <span><strong>Lumbar</strong></span>
                    <span>${data.lumbar.angulo.toFixed(1)}° 
                        <span class="badge ${data.lumbar.malaPostura ? 'mala' : ''}">${data.lumbar.malaPostura ? 'MALA' : 'BUENA'}</span>
                    </span>
                </div>
                <div class="sensor ${data.toracico.malaPostura ? 'mala' : ''}">
                    <span><strong>Torácico</strong></span>
                    <span>${data.toracico.angulo.toFixed(1)}° 
                        <span class="badge ${data.toracico.malaPostura ? 'mala' : ''}">${data.toracico.malaPostura ? 'MALA' : 'BUENA'}</span>
                    </span>
                </div>
                <div class="sensor ${data.hombro.malaPostura ? 'mala' : ''}">
                    <span><strong>Hombro</strong></span>
                    <span>${data.hombro.angulo.toFixed(1)}° 
                        <span class="badge ${data.hombro.malaPostura ? 'mala' : ''}">${data.hombro.malaPostura ? 'MALA' : 'BUENA'}</span>
                    </span>
                </div>
            `;

            // Actualizar postura general
            const malaPostura = data.lumbar.malaPostura || data.toracico.malaPostura || data.hombro.malaPostura;
            const posturaElement = document.getElementById('posturaGeneral');
            if (malaPostura) {
                posturaElement.textContent = '❌ POSTURA GENERAL: MALA';
                posturaElement.className = 'postura-general';
            } else {
                posturaElement.textContent = '✅ POSTURA GENERAL: BUENA';
                posturaElement.className = 'postura-general buena';
            }
        }

        async function cargarEstadisticas() {
            try {
                const resp = await fetch('/api/estadisticas');
                const data = await resp.json();
                
                document.getElementById('totalMalas').textContent = data.total_malas;
                document.getElementById('malasHoy').textContent = data.malas_hoy;
            } catch (error) {
                console.log('Error cargando estadísticas');
            }
        }

        async function cargarEventos() {
            try {
                const resp = await fetch('/api/eventos');
                const data = await resp.json();
                
                const timeline = document.getElementById('timeline');
                if (data.eventos.length === 0) {
                    timeline.innerHTML = '<div class="loading">Sin eventos recientes</div>';
                } else {
                    timeline.innerHTML = data.eventos.map(evento => `
                        <div class="evento">
                            <div class="evento-icon">⚠️</div>
                            <div>
                                <div style="font-size: 0.8rem; color: var(--color2);">${evento.timestamp}</div>
                                <div style="color: var(--color1); font-weight: 500;">Mala postura: ${evento.sensores}</div>
                            </div>
                        </div>
                    `).join('');
                }
            } catch (error) {
                console.log('Error cargando eventos');
            }
        }

        async function limpiarEventos() {
            try {
                await fetch('/api/limpiar', { method: 'POST' });
                cargarEventos();
                cargarEstadisticas();
                alert('Eventos limpiados');
            } catch (error) {
                alert('Error al limpiar');
            }
        }

        function actualizar() {
            if (actualizando) {
                cargarDatos();
                cargarEstadisticas();
                cargarEventos();
            }
        }

        // Iniciar actualizaciones
        setInterval(actualizar, 2000); // Cada 2 segundos
        actualizar(); // Cargar inmediatamente
    </script>
</body>
</html>
    '''

@app.get("/api/datos")
def obtener_datos():
    """API para obtener datos actuales"""
    if current_data:
        return {"success": True, "data": current_data}
    return {"success": False, "data": None}

@app.get("/api/estadisticas")  
def obtener_estadisticas():
    """API para estadísticas"""
    return estadisticas

@app.get("/api/eventos")
def obtener_eventos():
    """API para eventos de mala postura"""
    return {"eventos": list(eventos_malas_posturas)[:20]}  # Últimos 20

@app.post("/api/limpiar")
def limpiar_eventos():
    """Limpiar historial de eventos"""
    global eventos_malas_posturas, estadisticas
    eventos_malas_posturas.clear()
    estadisticas = {"total_malas": 0, "malas_hoy": 0, "porcentaje_buena": 100}
    return {"success": True}

if __name__ == "__main__":
    print("🏃 Monitor de Postura WiFi")
    print("=" * 60)
    print(f"📡 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📋 Topic MQTT: {MQTT_TOPIC}")
    print(f"🌐 Dashboard: http://localhost:{WEB_PORT}")
    print("=" * 60)
    
    # Iniciar MQTT en hilo separado
    mqtt_thread = threading.Thread(target=init_mqtt, daemon=True)
    mqtt_thread.start()
    
    print("⏳ Esperando datos del ESP32...")
    
    # Iniciar servidor web
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)
