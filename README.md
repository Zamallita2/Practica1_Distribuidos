# Storage Cluster - Sistema de Monitoreo Distribuido (Práctica 1)

Este repositorio contiene la solución completa para el **Storage Cluster Lógico Monitoreado** de la Caja Nacional de Salud (CNS), que soporta 9 nodos regionales de almacenamiento, un servidor central de monitoreo en tiempo real con Sockets TCP, persistencia en base de datos SQLite y una interfaz web (Dashboard).

---

## 👥 Roles del Equipo y Asignación de Módulos

| Integrante | Rol | Módulo Asignado |
| :--- | :--- | :--- |
| 🟠 **Tanina** | Nodo Cliente Multiplataforma | `client/` |
| 🔵 **Mateo** | Servidor Central TCP & Lógica Cluster | `server/` |
| 🟢 **Kevin** | Persistencia & BD | `database/` |
| 🟣 **Lucas** | Dashboard Web & Documentación | `dashboard/` y `docs/` |

---

## 🚀 Guía de Inicio Rápido (Prueba Local)

### 1. Iniciar el Servidor Central (Mateo)
```bash
python server/main.py
```

### 2. Iniciar Nodos Clientes Simulados (Tanina / Pruebas)
En terminales separadas:
```bash
python client/main.py --id REGIONAL_LA_PAZ --interval 3
python client/main.py --id REGIONAL_SANTA_CRUZ --interval 5
```

### 3. Iniciar el Dashboard Web (Lucas)
```bash
python dashboard/app.py
```
Acceder en el navegador a: `http://localhost:5000`

---

## 📘 Guía de Integración para Kevin (🟢 Persistencia & BD)

### ¿De dónde y cómo consultar / guardar los datos?
Toda la lógica de persistencia está centralizada en `database/db_manager.py`.

1. **Ubicación de la Base de Datos:**
   - Archivo SQLite: `cluster_monitoring.db` en la raíz del proyecto.
2. **Tablas Creadas:**
   - `clients`: Almacena `client_id`, `status` (`Activo` / `No Reporta`), `first_connected`, `last_seen`.
   - `metrics`: Historial de métricas con `client_id`, `disk_name`, `disk_type`, `total_gb`, `used_gb`, `free_gb`, `iops`, `timestamp`.
   - `config`: Almacena la parametrización de frecuencia y configuración.
3. **Funciones Clave para Kevin:**
   - `save_metric(client_id, disk_data, timestamp)`: Invocada automáticamente por el servidor al recibir un paquete de métricas.
   - `get_latest_metrics_all_clients()`: Retorna el último estado de los 9 servidores para reportes o consultas avanzadas de BD.

---

## 🟣 Guía de Integración para Lucas (Dashboard Web & API)

### 1. ¿Cómo obtener los datos en tiempo real de la RAM?
Para lograr un Dashboard fluido y de rápida respuesta, **Lucas debe consumir los datos directamente desde la memoria RAM del Servidor Central o a través de los helpers**:

- **Métricas de Nodos en RAM:**
  Consumir `server.get_active_clients_in_memory()` o llamar a la función helper:
  ```python
  from server.cluster_metrics import calculate_cluster_metrics_from_ram
  # Pasa el diccionario de la RAM para obtener KPIs consolidados al instante:
  kpis = calculate_cluster_metrics_from_ram(server.clients)
  ```
- **Datos expuestos en la API REST (`dashboard/app.py`):**
  Actualmente, el endpoint `/api/dashboard` retorna un JSON listo con la lista de servidores y KPIs globales:
  ```json
  {
    "cluster": {
      "total_cluster_gb": 466.36,
      "used_cluster_gb": 396.34,
      "free_cluster_gb": 46.2,
      "pct_utilization": 84.99,
      "avg_latency_ms": 312.4,
      "active_nodes": 2
    },
    "servers": [ ... ]
  }
  ```

### 2. ¿Cómo enviar Comandos Remotos desde el Dashboard?
Mateo ha preparado e integrado métodos directos en la clase `MonitoringServer` para que Lucas pueda enviar comandos mediante botones en el Dashboard:

- **Enviar comando a un cliente específico:**
  ```python
  # Retorna (True/False, "Mensaje de estado")
  ok, msg = server_instance.send_command_to_client("REGIONAL_LA_PAZ", "Reinicie servicio")
  ```
- **Enviar comando masivo a todos los nodos activos (Broadcast):**
  ```python
  # Retorna (cantidad_enviados, "Mensaje de estado")
  count, msg = server_instance.broadcast_command_to_all("Verifique espacio en disco")
  ```
- **Comandos Soportados por Estándar:**
  - `"Reinicie servicio"`
  - `"Verifique espacio en disco"`
  - `"Actualización de configuración"`

---

## 📡 Especificación del Protocolo TCP (JSON)

Toda comunicación a través de los Sockets TCP se realiza con objetos JSON terminados en `\n`:

- **Métricas (Cliente ➔ Servidor):**
  `{"type": "METRICS", "client_id": "REGIONAL_01", "timestamp": "...", "disk": {...}}`
- **Comando Remoto (Servidor ➔ Cliente):**
  `{"type": "COMMAND", "command_id": "cmd-123", "action": "Reinicie servicio"}`
- **Confirmación ACK (Cliente ➔ Servidor):**
  `{"type": "ACK", "command_id": "cmd-123", "client_id": "REGIONAL_01", "status": "OK", "message": "Ejecutado: 'Reinicie servicio'"}`
