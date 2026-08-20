# Microinforme Técnico - Storage Cluster CNS

## 1. Integrantes y Roles

| Integrante | Rol en el Proyecto | Módulo Asignado |
| :--- | :--- | :--- |
| **Tanina** | Desarrollador de Nodo Cliente / QA | 🟠 `client/` - Cliente Socket & Métricas Multiplataforma |
| **Mateo** | Arquitecto de Software / Servidor Central | 🔵 `server/` - Servidor TCP Concurrente & Lógica de Cluster |
| **Kevin** | DB Engineer / Lead de Persistencia | 🟢 `database/` - Modelo de Datos, Persistencia y Configuración |
| **Lucas** | Project Manager / Frontend Developer | 🟣 `dashboard/` & `docs/` - Dashboard Web & Microinforme |

---

## 2. Cronograma de Trabajo y Fechas Críticas (CutOff)

- **19/08 - 22/08**: Inicio de Diseño (Sockets Servidor, Extracción Métricas Disco, Esquema BD, Mock Dashboard).
- **21/08 - 24/08**: Desarrollo de Concurrencia (Threads/Async), Multiplataforma Cliente y Tablas de BD.
- **23/08 - 26/08**: Comunicación Bidireccional, Persistencia de Métricas, Detección de Timeout y Auto-Refresh.
- **25/08 - 27/08**: Integración General, Pruebas con Múltiples Nodos y CutOff Final (Preparación para Defensa).

---

## 3. Reglamento y "Mandamientos" del Equipo

1. **Trabajar en su respectiva carpeta modular**: Cada integrante desarrollará su código en el módulo asignado (`client/`, `server/`, `database/`, `dashboard/`) para evitar conflictos en Git.
2. **Respetar la especificación de mensajes (JSON sobre Sockets)**: Toda comunicación TCP debe cumplir estrictamente la estructura delimitada por `\n` acordada en el `README.md`.
3. **Manejar excepciones y pérdidas de conexión**: El cliente debe intentar reconectarse automáticamente y el servidor no debe caerse si un cliente se desconecta abruptamente.
4. **Registrar todo comando recibido en `.log` y responder ACK**: Requisito obligatorio de la práctica para auditoría de comandos bidireccionales.
5. **No romper la rama principal (`main`)**: Toda función debe probarse localmente antes de ser commiteada.
