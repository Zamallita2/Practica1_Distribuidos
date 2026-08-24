# 🟣 Módulo Dashboard & Guía de Integración — Lucas

Este archivo explica a **Lucas** cómo integrar la interfaz del Dashboard Web con los métodos y datos en memoria RAM desarrollados por **Mateo**.

---

## 🔌 1. ¿De dónde obtener las Métricas y KPIs de la RAM?

En lugar de hacer consultas pesadas a la base de datos para refrescar la pantalla en tiempo real, puedes consumir directamente las métricas guardadas en memoria RAM por Mateo:

### Obtener KPIs del Cluster desde la RAM:
```python
from server.cluster_metrics import calculate_cluster_metrics_from_ram

# 'server' es la instancia activa de MonitoringServer
active_clients_ram = server.get_active_clients_in_memory()
kpis = calculate_cluster_metrics_from_ram(active_clients_ram)

print(kpis)
# Resultado:
# {
#   "total_cluster_gb": 466.36,
#   "used_cluster_gb": 396.34,
#   "free_cluster_gb": 46.2,
#   "pct_utilization": 84.99,
#   "avg_latency_ms": 312.4,
#   "active_nodes": 2
# }
```

---

## 🕹️ 2. ¿Cómo conectar Botones del Dashboard para Enviar Comandos?

Para la interfaz del Dashboard, puedes crear rutas HTTP POST (ej: `/api/send-command`) y llamar a los métodos preparados por Mateo:

### Ejemplo: Enviar comando a un cliente específico
```python
# Invocación directa:
exito, mensaje = server.send_command_to_client("REGIONAL_LA_PAZ", "Reinicie servicio")
```

### Ejemplo: Enviar comando a TODOS los nodos activos
```python
# Invocación directa:
nodos_notificados, mensaje = server.broadcast_command_to_all("Verifique espacio en disco")
```

---

## 🔄 3. Estructura de Respuesta ACK

Cuando el cliente recibe y procesa el comando, el Servidor Central guarda la confirmación ACK en la RAM del cliente:
`server.clients[client_id]["last_ack"]`

Retorna:
```json
{
  "command_id": "cmd-1724514000",
  "status": "OK",
  "message": "Ejecutado: 'Reinicie servicio'",
  "timestamp": "11:54:10"
}
```
Puedes usar este campo para mostrar un mensaje verde de confirmación en la tarjeta del servidor dentro del Dashboard.
