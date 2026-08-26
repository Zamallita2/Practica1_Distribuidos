# Evidencia — Pruebas de Persistencia y Sincronización

**Tarea 3 — Kevin | Storage Cluster CNS**
**Fecha de ejecución:** 26 de agosto de 2026

## Entorno de prueba

- Servidor: `python -m server.main` (host `0.0.0.0:9000`, timeout cargado desde BD: 60s)
- Clientes: `python -m client.main --id REGIONAL_01` y `REGIONAL_02`
- Inspección: script `inspeccionar_bd.py` sobre `cluster_monitoring.db` real

---

## Prueba 1 — Verificar que cada métrica recibida quede almacenada

Se conectó `REGIONAL_01` y se dejó reportando ~40 segundos. El servidor confirmó
recepción (`Métricas enviadas correctamente` x8 en consola del cliente) y las 8
métricas aparecieron persistidas en la tabla `metrics` sin pérdidas, cada una con
timestamp e IOPS distintos.

## Prueba 2 — Verificar historial

`get_client_history("REGIONAL_01", limit=10)` devolvió 10 filas con timestamps
consecutivos (22:04:44 a 22:05:52), confirmando que el historial completo se
conserva y no se sobrescribe entre reportes.

## Prueba 3 — Verificar estados

Se detuvo `REGIONAL_01` (Ctrl+C) y se esperó >60s (el `TIMEOUT` configurado). El
estado en `clients` pasó automáticamente de `Activo` a `No Reporta`, sin
intervención manual, vía `check_inactive_clients()`.

## Prueba 4 — Verificar nuevos clientes

Se conectaron dos clientes con IDs nunca antes vistos (`REGIONAL_01`,
`REGIONAL_02`). Ambos se dieron de alta automáticamente en la tabla `clients` al
llegar su primera métrica (`save_metric` hace upsert), sin necesidad de un
registro previo. Con ambos coexistiendo, el estado de cada uno se mantuvo
independiente (`REGIONAL_01: No Reporta`, `REGIONAL_02: Activo`).

## Prueba 5 — Comprobar que los datos coincidan con los recibidos

Se contrastó la métrica persistida contra una fuente independiente del sistema
operativo (`Get-PSDrive C` en PowerShell):

| Fuente                                  | Usado (GB) | Libre (GB) |
| --------------------------------------- | ---------- | ---------- |
| Base de datos (`cluster_monitoring.db`) | 330.27     | 6.01       |
| Windows (`Get-PSDrive C`)               | 330.27     | 6.01       |

**Coincidencia exacta.** Los datos que el cliente reporta y el servidor persiste
corresponden fielmente al estado real del disco monitoreado.

---

## KPIs consolidados verificados (`get_cluster_summary`)

Con 2 nodos (uno activo, uno caído), los KPIs sumaron correctamente:

```
total_nodes: 2  |  active_nodes: 1
total_capacity: 672.56 GB  (336.28 x 2, correcto)
total_used: 660.54 GB
utilization_percent: 98.21%
```

Un nodo caído se sigue contando en `total_nodes` (no desaparece del registro),
pero no en `active_nodes` — comportamiento correcto para un cluster real.

---

## Observaciones para seguimiento (no bloqueantes)

1. **Intervalo de envío real vs. configurado**: `config.json` define
   `send_interval_seconds: 5`, pero el espaciado real entre métricas fue de
   ~7-8 segundos (probablemente por el tiempo de lectura de disco + latencia de
   red sumado al `sleep`). No afecta la persistencia, pero conviene documentarlo
   si se pregunta en la defensa.
2. **`REPORT_INTERVAL` de la base de datos no se aplica al arranque del
   cliente**, solo se usa cuando se cambia en caliente vía el comando
   `i <segundos>` del servidor. El valor inicial siempre viene de
   `config.json` o del argumento `--interval`. Pendiente de confirmar con el
   equipo si esto cumple el requisito de "parametrización desde la BD" o si
   falta conectar esa lectura inicial también.

## Conclusión

Las 4 verificaciones exigidas por la práctica (almacenamiento, historial,
estados, nuevos clientes) y la comprobación de fidelidad de datos quedan
confirmadas con evidencia reproducible sobre el sistema real, no solo con
pruebas unitarias aisladas.

---

## Nota operativa: si el esquema de tu BD local está desactualizado

`cluster_monitoring.db` es un archivo generado localmente (está en `.gitignore`,
`*.db`, así que nunca se sube al repositorio). Si alguien del equipo corrió el
servidor o los tests antes de que se agregara la columna `command_id` a la
tabla `messages`, su archivo local quedará con el esquema viejo — y
`init_db()` no la va a corregir sola, porque usa `CREATE TABLE IF NOT EXISTS`
(no altera tablas que ya existen).

**Solución:** si te sale un error relacionado con `command_id` en la tabla
`messages`, simplemente borra el archivo local y regenera el esquema. Hay dos
formas de hacerlo, según lo que necesites en el momento:

**Opción A — levantando el servidor completo** (si de todas formas vas a
probar el sistema):

```
del cluster_monitoring.db          (Windows, cmd)
Remove-Item cluster_monitoring.db  (Windows, PowerShell)
rm cluster_monitoring.db           (Linux / macOS)

python -m server.main
```

El constructor de `MonitoringServer` llama a `init_db()` automáticamente al
arrancar, así que el archivo se regenera con el esquema completo (incluyendo
`command_id`) apenas se ejecuta este comando — no hace falta nada más.

**Opción B — regenerar solo la base de datos, sin levantar sockets** (más
rápido si solo quieres corregir el esquema, sin conectar clientes todavía):

```
del cluster_monitoring.db      (o rm / Remove-Item, según tu sistema)
python database/db_manager.py
```

Este segundo comando funciona porque `db_manager.py` tiene un bloque
`if __name__ == "__main__": init_db()` al final — al ejecutarlo directamente,
solo crea/actualiza el esquema de la BD y termina, sin abrir el puerto 9000 ni
entrar al menú interactivo del servidor.

Cualquiera de las dos opciones deja el archivo listo con las 4 tablas y sus
columnas actuales; ninguna requiere escribir `ALTER TABLE` a mano.
