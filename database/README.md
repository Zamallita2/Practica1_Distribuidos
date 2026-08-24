# 🟢 Módulo Persistencia y Base de Datos — Kevin

Este archivo explica a **Kevin** cómo está estructurada la capa de datos y cómo se conecta con el Servidor Central de Mateo.

---

## 🗄️ 1. Estructura de la Base de Datos SQLite

La base de datos principal es un archivo SQLite ubicado en la raíz del proyecto: `cluster_monitoring.db`.

### Tabla `clients` (Estado de los Nodos):
- `client_id` (TEXT PRIMARY KEY): Identificador del nodo regional (ej: `REGIONAL_LA_PAZ`).
- `status` (TEXT): Estado del nodo (`Activo` / `No Reporta`).
- `first_connected` (TEXT): Fecha y hora de primera conexión.
- `last_seen` (TEXT): Fecha y hora del último reporte recibido.

### Tabla `metrics` (Historial de Métricas):
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT): ID correlativo.
- `client_id` (TEXT): Clave foránea al cliente.
- `disk_name` (TEXT): Nombre de la partición/disco.
- `disk_type` (TEXT): `SSD` o `HDD`.
- `total_gb` (REAL): Capacidad total en Gigabytes.
- `used_gb` (REAL): Espacio utilizado en Gigabytes.
- `free_gb` (REAL): Espacio libre en Gigabytes.
- `iops` (INTEGER): Rendimiento en Operaciones E/S por segundo.
- `timestamp` (TEXT): Fecha y hora del reporte.

---

## 🔌 2. Integración con el Servidor Central (Mateo)

Cada vez que el Servidor Central recibe un paquete TCP de métricas, invoca automáticamente la función:
`save_metric(client_id, disk_data, timestamp)` en `database/db_manager.py`.

### Consultas Históricas para Kevin:
Puedes usar `get_latest_metrics_all_clients()` para obtener la métrica más reciente de cada uno de los 9 servidores registrados.
