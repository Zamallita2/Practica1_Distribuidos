# Storage Cluster - Sistema de Monitoreo Distribuido (Práctica 1)

Este proyecto implementa un **Storage Cluster Lógico Monitoreado** con arquitectura **Cliente-Servidor (TCP Sockets)** para la Caja Nacional de Salud (CNS), que abarca 9 nodos regionales (clientes), un servidor central de monitoreo, persistencia de datos (SQLite/PostgreSQL/MySQL) y un dashboard web de visualización en tiempo real.

---

## 📁 Estructura del Proyecto y Distribución por Módulos

```text
Practica1_Distribuidos/
├── client/                     # 🟠 Módulo Cliente (Tanina)
│   ├── main.py                 # Punto de entrada del nodo cliente
│   ├── disk_metrics.py         # Extracción de métricas de disco (SSD/HDD, IOPS, etc.)
│   ├── socket_client.py        # Cliente Socket TCP, reconexión y comunicación bidireccional
│   └── logger.py               # Gestión de logs locales (.log) y envío de ACK
│
├── server/                     # 🔵 Módulo Servidor Central (Mateo)
│   ├── main.py                 # Punto de entrada del servidor central
│   ├── socket_server.py        # Servidor TCP concurrente (Threads/Async)
│   ├── cluster_metrics.py      # Cálculo de KPIs globales, latencia y agregación del cluster
│   ├── client_manager.py       # Detección automática de nodos y control de timeout ("No Reporta")
│   └── command_handler.py      # Envío de comandos remotos a los clientes
│
├── database/                   # 🟢 Módulo Persistencia y Configuración (Kevin)
│   ├── db_manager.py           # Conexión, inicialización y operaciones CRUD (SQLite/PostgreSQL/etc.)
│   ├── models.py               # Esquema de base de datos (Clientes, Métricas, Historial, Estados)
│   └── config.py               # Parametrización global y frecuencia de actualización
│
├── dashboard/                  # 🟣 Módulo Dashboard Web y API (Lucas)
│   ├── app.py                  # API HTTP / Web Server (Flask/FastAPI) para el Dashboard
│   ├── static/                 # CSS (estilos visuales modernos, dark mode) y JS (Auto-Refresh)
│   └── templates/              # Interfaz HTML para monitoreo de los 9 servidores y KPIs globales
│
├── docs/                       # 📄 Documentación y Microinforme Técnico (Lucas & Equipo)
│   └── microinforme_tecnico.md # Roles, Cronograma, CutOff, Reglamento y Mandamientos
│
├── config.json                 # Archivo de configuración global parametrizable
├── requirements.txt            # Dependencias de Python necesarias
└── README.md                   # Instrucciones generales del repositorio
```

---

## 👥 Asignación de Roles y Responsabilidades

| Integrante | Rol / Módulo | Tareas Principales |
| :--- | :--- | :--- |
| 🟠 **Tanina** | **Nodo Cliente** | - Extracción de métricas de disco (Multiplataforma: Windows/Linux).<br>- Socket TCP cliente, envío periódico y manejo de desconexiones.<br>- Escucha bidireccional, registro de logs `.log` y respuestas `ACK`. |
| 🔵 **Mateo** | **Servidor Central** | - Socket TCP Servidor concurrente para soportar hasta 9 nodos.<br>- Recepción, agregación y cálculo de KPIs globales (capacidad, latencia).<br>- Detección automática de nuevos nodos y marcado de estado `"No Reporta"`.<br>- Envío de comandos remotos a nodos específicos. |
| 🟢 **Kevin** | **Persistencia y Parametrización** | - Diseño e implementación de la Base de Datos (Tablas: Clientes, Métricas, Estados).<br>- Integración Servidor-BD para guardar métricas e historial.<br>- Parametrización de frecuencia de envío (configurable cliente/servidor). |
| 🟣 **Lucas** | **Dashboard + Gestión** | - Interfaz gráfica web moderna con auto-refresh para monitorear los 9 servidores.<br>- Integración con la API/BD para métricas individuales y globales.<br>- Redacción del Microinforme Técnico (Roles, Cronograma, Reglamento/Mandamientos). |

---

## 🚀 Requisitos Previos e Instalación

### Requisitos
- **Python 3.8+**
- `pip` para la gestión de paquetes

### Instalación de dependencias
```bash
pip install -r requirements.txt
```

---

## 🛠️ Guía de Ejecución Local

### 1. Iniciar el Servidor Central (Mateo)
```bash
python server/main.py
```

### 2. Iniciar el Dashboard Web (Lucas)
```bash
python dashboard/app.py
```
Acceder en el navegador a `http://localhost:5000` (o el puerto configurado).

### 3. Iniciar un Nodo Cliente (Tanina)
```bash
python client/main.py --id REGIONAL_01
```

---

## 📌 Protocolo de Mensajes Socket (JSON)

Para asegurar interoperabilidad entre los desarrolladores, los mensajes TCP se enviarán como cadenas **JSON delimitas por salto de línea (`\n`)**:

### Reporte de Métricas (Cliente ➔ Servidor)
```json
{
  "type": "METRICS",
  "client_id": "REGIONAL_SANTA_CRUZ",
  "timestamp": "2026-08-20T03:30:00Z",
  "disk": {
    "name": "/dev/sda1",
    "type": "SSD",
    "total_gb": 500.0,
    "used_gb": 220.5,
    "free_gb": 279.5,
    "iops": 1500
  }
}
```

### Comando Remoto (Servidor ➔ Cliente)
```json
{
  "type": "COMMAND",
  "command_id": "cmd-101",
  "action": "Verifique espacio en disco"
}
```

### Respuesta ACK (Cliente ➔ Servidor)
```json
{
  "type": "ACK",
  "command_id": "cmd-101",
  "client_id": "REGIONAL_SANTA_CRUZ",
  "status": "OK",
  "message": "Comando recibido y ejecutado correctamente"
}
```
