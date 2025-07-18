from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import serial
import json
from datetime import datetime
from collections import deque
import uvicorn
import threading
import time

# 🔧 CONFIGURACIÓN SIMPLE
BT_PORT = 'COM9'           # Puerto Bluetooth
BAUD_RATE = 115200
WEB_PORT = 8000

# 📊 Variables globales para datos
current_data = None
eventos_malas_posturas = deque(maxlen=100)  # Últimos 100 eventos
historial_posturas = deque(maxlen=200)  # Historial para gráfica tiempo vs postura
estadisticas = {
    "total_malas": 0,
    "malas_hoy": 0,
    "porcentaje_buena": 100
}

# Estado de conexión
conexion_bt_activa = False
bt_serial = None

# Estado de postura para evitar registros duplicados
mala_postura_registrada = False  # Flag para saber si ya registramos esta sesión de mala postura

app = FastAPI(title="Monitor Postura Bluetooth")

# 🔌 Conexión Bluetooth
def init_bluetooth():
    global bt_serial, conexion_bt_activa
    
    while True:
        try:
            print(f"🔄 Conectando a Bluetooth: {BT_PORT}")
            bt_serial = serial.Serial(BT_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)  # Esperar inicialización
            conexion_bt_activa = True
            print(f"✅ Bluetooth conectado: {BT_PORT}")
            
            # Leer datos continuamente
            while conexion_bt_activa:
                try:
                    line = bt_serial.readline().decode('utf-8').strip()
                    if line:
                        print(f"📱 BT recibido: {line}")
                        procesar_datos_bluetooth(line)
                        
                except serial.SerialException as e:
                    print(f"❌ Error serial: {e}")
                    break
                except Exception as e:
                    print(f"❌ Error leyendo BT: {e}")
                    
        except serial.SerialException as e:
            print(f"❌ Error conectando Bluetooth: {e}")
            conexion_bt_activa = False
            
        except Exception as e:
            print(f"❌ Error Bluetooth: {e}")
            conexion_bt_activa = False
            
        # Si se desconecta, cerrar puerto y reintentar
        if bt_serial:
            bt_serial.close()
            bt_serial = None
        print("🔄 Reintentando Bluetooth en 5 segundos...")
        time.sleep(5)

def procesar_datos_bluetooth(json_string):
    global current_data, eventos_malas_posturas, estadisticas, historial_posturas, mala_postura_registrada
    
    try:
        # Parsear datos JSON
        data = json.loads(json_string)
        
        # Actualizar datos actuales
        now = datetime.now()
        current_data = {
            "lumbar": data["lumbar"],
            "toracico": data["toracico"], 
            "hombro": data["hombro"],
            "timestamp": now.strftime("%H:%M:%S"),
            "fecha": now.strftime("%Y-%m-%d")
        }
        
        # Verificar si hay mala postura
        mala_postura = (
            data["lumbar"]["alerta"] or 
            data["toracico"]["alerta"] or 
            data["hombro"]["alerta"]
        )

        # Agregar al historial para gráfica (tiempo vs postura) - SIEMPRE
        historial_posturas.append({
            "timestamp": now.strftime("%H:%M:%S"),
            "datetime": now.isoformat(),
            "postura_mala": mala_postura,
            "lumbar_mala": data["lumbar"]["alerta"],
            "toracico_mala": data["toracico"]["alerta"],
            "hombro_mala": data["hombro"]["alerta"],
            "angulo_lumbar": data["lumbar"]["angulo"],
            "angulo_toracico": data["toracico"]["angulo"],
            "angulo_hombro": data["hombro"]["angulo"]
        })
        
        # NUEVA LÓGICA: Solo registrar evento si es una nueva sesión de mala postura
        if mala_postura and not mala_postura_registrada:
            # Primera detección de mala postura - REGISTRAR
            sensores_afectados = []
            if data["lumbar"]["alerta"]:
                sensores_afectados.append("Lumbar")
            if data["toracico"]["alerta"]:
                sensores_afectados.append("Torácico")
            if data["hombro"]["alerta"]:
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
            
            # Marcar que ya registramos esta sesión de mala postura
            mala_postura_registrada = True
            
            print(f"🚨 NUEVA mala postura registrada: {', '.join(sensores_afectados)} - {current_data['timestamp']}")
            
        elif not mala_postura and mala_postura_registrada:
            # La postura se corrigió - resetear flag para permitir futuras detecciones
            mala_postura_registrada = False
            print(f"✅ Postura corregida - Sistema listo para detectar nuevas malas posturas - {current_data['timestamp']}")
            
        elif mala_postura and mala_postura_registrada:
            # Sigue en mala postura - NO registrar
            print(f"⏳ Continúa en mala postura (no se registra) - {current_data['timestamp']}")
        else:
            # Postura buena - todo normal
            print(f"📊 Postura buena - {current_data['timestamp']}")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error JSON: {e}")
        print(f"📝 Datos recibidos: {json_string}")
    except KeyError as e:
        print(f"❌ Error clave faltante: {e}")
        print(f"📝 Datos recibidos: {data}")
    except Exception as e:
        print(f"❌ Error procesando datos: {e}")

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
    <title>Monitor de Postura</title>
    <style>
        :root {
            --color1: #12170c; --color2: #124645; --color3: #159a68;
            --color4: #ceda78; --color5: #f8efe1; --bluetooth: #0e7db8;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, var(--color4), var(--color5));
            min-height: 100vh; padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, var(--color1), var(--bluetooth));
            color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;
            text-align: center;
        }
        .status { 
            background: var(--bluetooth); color: white; padding: 8px 16px; 
            border-radius: 20px; display: inline-block; margin-top: 10px;
        }
        .status.desconectado { background: #ef4444; }
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
            background: rgba(14, 125, 184, 0.1); padding: 10px; border-radius: 5px;
            margin-top: 10px; font-size: 0.8rem; color: var(--bluetooth);
        }
        .status-deteccion {
            background: rgba(255,255,255,0.1); padding: 8px 12px; border-radius: 15px;
            margin-top: 5px; font-size: 0.7rem; display: inline-block;
        }
        @media (max-width: 768px) { 
            .grid { grid-template-columns: 1fr; } 
            .stats { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📱 Monitor de Postura</h1>
        <div class="status" id="status">Conectando...</div>
        <div class="status-deteccion" id="statusDeteccion">Sistema de detección: Listo</div>
        <div class="connection-info">
            Puerto Bluetooth: ''' + BT_PORT + ''' | Velocidad: ''' + str(BAUD_RATE) + ''' bps
        </div>
    </div>

    <div class="postura-general" id="posturaGeneral">⏳ Cargando...</div>

    <div class="grid">
        <div class="card">
            <h3>📊 Sensores</h3>
            <div id="sensores">
                <div class="loading">Esperando datos Bluetooth...</div>
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
            <h3>📈 Línea de Tiempo: Postura vs Tiempo</h3>
            <div style="position: relative; height: 300px; margin-bottom: 20px;">
                <canvas id="posturaChart"></canvas>
            </div>
        </div>

        <div class="card timeline-card">
            <h3>⚠️ Eventos Recientes</h3>
            <button class="btn" onclick="limpiarEventos()">🗑️ Limpiar Todo</button>
            <div class="timeline" id="timeline">
                <div class="loading">Sin eventos...</div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <script>
        let actualizando = true;
        let posturaChart = null;

        // Inicializar gráfica
        function initChart() {
            const ctx = document.getElementById('posturaChart').getContext('2d');
            posturaChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'Postura General',
                            data: [],
                            borderColor: '#ef4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.1,
                            pointBackgroundColor: '#ef4444',
                            pointBorderColor: '#ffffff',
                            pointBorderWidth: 2,
                            pointRadius: 4
                        },
                        {
                            label: 'Lumbar',
                            data: [],
                            borderColor: '#ff9500',
                            backgroundColor: 'rgba(255, 149, 0, 0.1)',
                            borderWidth: 1,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 2
                        },
                        {
                            label: 'Torácico',
                            data: [],
                            borderColor: '#007aff',
                            backgroundColor: 'rgba(0, 122, 255, 0.1)',
                            borderWidth: 1,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 2
                        },
                        {
                            label: 'Hombro',
                            data: [],
                            borderColor: '#5856d6',
                            backgroundColor: 'rgba(88, 86, 214, 0.1)',
                            borderWidth: 1,
                            fill: false,
                            tension: 0.1,
                            pointRadius: 2
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                label: function(context) {
                                    const label = context.dataset.label || '';
                                    const value = context.parsed.y;
                                    return label + ': ' + (value === 1 ? 'MALA' : 'BUENA');
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Tiempo'
                            },
                            grid: {
                                display: true,
                                color: 'rgba(0,0,0,0.1)'
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Estado Postura'
                            },
                            min: -0.1,
                            max: 1.1,
                            ticks: {
                                stepSize: 1,
                                callback: function(value) {
                                    return value === 1 ? 'MALA' : value === 0 ? 'BUENA' : '';
                                }
                            },
                            grid: {
                                display: true,
                                color: 'rgba(0,0,0,0.1)'
                            }
                        }
                    },
                    animation: {
                        duration: 0 // Desactivar animaciones para tiempo real
                    }
                }
            });
        }

        async function cargarDatos() {
            try {
                const resp = await fetch('/api/datos');
                const data = await resp.json();
                
                if (data.success) {
                    document.getElementById('status').textContent = 'Conectado Bluetooth 📱';
                    document.getElementById('status').className = 'status';
                    mostrarDatos(data.data);
                } else {
                    document.getElementById('status').textContent = 'Sin datos Bluetooth ❌';
                    document.getElementById('status').className = 'status desconectado';
                }
            } catch (error) {
                document.getElementById('status').textContent = 'Error conexión ❌';
                document.getElementById('status').className = 'status desconectado';
                console.error('Error:', error);
            }
        }

        async function cargarStatus() {
            try {
                const resp = await fetch('/api/status');
                const status = await resp.json();
                
                // Actualizar estado de detección
                const statusDeteccion = document.getElementById('statusDeteccion');
                if (status.mala_postura_activa) {
                    statusDeteccion.textContent = 'Sesión de mala postura activa - Esperando corrección';
                    statusDeteccion.style.background = 'rgba(239, 68, 68, 0.3)';
                } else {
                    statusDeteccion.textContent = 'Sistema de detección: Listo para detectar';
                    statusDeteccion.style.background = 'rgba(21, 154, 104, 0.3)';
                }
            } catch (error) {
                console.error('Error cargando status:', error);
            }
        }

        async function cargarHistorial() {
            try {
                const resp = await fetch('/api/historial');
                const data = await resp.json();
                
                if (posturaChart && data.historial) {
                    // Mantener solo los últimos 50 puntos para mejor rendimiento
                    const historial = data.historial.slice(-50);
                    
                    const labels = historial.map(item => item.timestamp);
                    const posturaGeneral = historial.map(item => item.postura_mala ? 1 : 0);
                    const lumbar = historial.map(item => item.lumbar_mala ? 1 : 0);
                    const toracico = historial.map(item => item.toracico_mala ? 1 : 0);
                    const hombro = historial.map(item => item.hombro_mala ? 1 : 0);

                    posturaChart.data.labels = labels;
                    posturaChart.data.datasets[0].data = posturaGeneral;
                    posturaChart.data.datasets[1].data = lumbar;
                    posturaChart.data.datasets[2].data = toracico;
                    posturaChart.data.datasets[3].data = hombro;
                    
                    posturaChart.update('none'); // Actualizar sin animación
                }
            } catch (error) {
                console.error('Error cargando historial:', error);
            }
        }

        function mostrarDatos(data) {
            // Actualizar sensores
            const sensores = document.getElementById('sensores');
            sensores.innerHTML = `
                <div class="sensor ${data.lumbar.alerta ? 'mala' : ''}">
                    <span><strong>Lumbar</strong></span>
                    <span>${data.lumbar.angulo.toFixed(1)}° 
                        <span class="badge ${data.lumbar.alerta ? 'mala' : ''}">${data.lumbar.alerta ? 'MALA' : 'BUENA'}</span>
                    </span>
                </div>
                <div class="sensor ${data.toracico.alerta ? 'mala' : ''}">
                    <span><strong>Torácico</strong></span>
                    <span>${data.toracico.angulo.toFixed(1)}° 
                        <span class="badge ${data.toracico.alerta ? 'mala' : ''}">${data.toracico.alerta ? 'MALA' : 'BUENA'}</span>
                    </span>
                </div>
                <div class="sensor ${data.hombro.alerta ? 'mala' : ''}">
                    <span><strong>Hombro</strong></span>
                    <span>${data.hombro.angulo.toFixed(1)}° 
                        <span class="badge ${data.hombro.alerta ? 'mala' : ''}">${data.hombro.alerta ? 'MALA' : 'BUENA'}</span>
                    </span>
                </div>
            `;

            // Actualizar postura general
            const malaPostura = data.lumbar.alerta || data.toracico.alerta || data.hombro.alerta;
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
                cargarHistorial(); // También actualizar gráfica
                alert('Todos los datos limpiados');
            } catch (error) {
                alert('Error al limpiar');
            }
        }

        function actualizar() {
            if (actualizando) {
                cargarDatos();
                cargarEstadisticas();
                cargarEventos();
                cargarHistorial(); // Actualizar gráfica
                cargarStatus(); // Actualizar estado de detección
            }
        }

        // Inicializar cuando se carga la página
        window.addEventListener('load', function() {
            initChart();
            actualizar(); // Cargar datos iniciales
        });

        // Iniciar actualizaciones
        setInterval(actualizar, 2000); // Cada 2 segundos
    </script>
</body>
</html>
    '''

@app.get("/api/datos")
def obtener_datos():
    """API para obtener datos actuales"""
    if current_data and conexion_bt_activa:
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

@app.get("/api/historial")
def obtener_historial():
    """API para historial de posturas (gráfica tiempo vs postura)"""
    return {"historial": list(historial_posturas)}

@app.get("/api/status")
def obtener_status():
    """API para estado de conexión"""
    return {
        "bluetooth_conectado": conexion_bt_activa,
        "puerto": BT_PORT,
        "mala_postura_activa": mala_postura_registrada  # Nuevo campo para mostrar si hay una mala postura activa
    }

@app.post("/api/limpiar")
def limpiar_eventos():
    """Limpiar historial de eventos y gráfica"""
    global eventos_malas_posturas, estadisticas, historial_posturas, mala_postura_registrada
    eventos_malas_posturas.clear()
    historial_posturas.clear()
    estadisticas = {"total_malas": 0, "malas_hoy": 0, "porcentaje_buena": 100}
    mala_postura_registrada = False  # Resetear flag de postura registrada
    print("🗑️ Datos limpiados - Sistema reseteado")
    return {"success": True}

if __name__ == "__main__":
    print("📱 Monitor de Postura Bluetooth - Versión Inteligente")
    print("=" * 60)
    print(f"📱 Puerto Bluetooth: {BT_PORT} @ {BAUD_RATE} bps")
    print(f"🌐 Dashboard: http://localhost:{WEB_PORT}")
    print("=" * 60)
    print("🔄 Flujo: Arduino → Bluetooth → Dashboard")
    print("🧠 Detección inteligente: Una alerta por sesión de mala postura")
    print("=" * 60)
    
    # Iniciar Bluetooth en hilo separado
    bt_thread = threading.Thread(target=init_bluetooth, daemon=True)
    bt_thread.start()
    
    print("⏳ Esperando datos del dispositivo Bluetooth...")
    
    # Iniciar servidor web
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)
