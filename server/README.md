# 🔵 Módulo Servidor Central — Mateo

Este módulo contiene el núcleo del **Servidor Central de Monitoreo TCP** desarrollado por **Mateo**. Es el responsable de recibir las métricas de los 9 nodos cliente, gestionar la concurrencia multihilo, mantener el estado en memoria, invocar la persistencia en base de datos y enviar comandos remotos bidireccionales.

---

## 🛠️ Explicación Técnica: ¿Qué hace esta parte?

1. **Socket TCP Concurrente (`socket_server.py`)**:
   - Escucha en la IP `0.0.0.0` y Puerto `9000`.
   - **Manejo de Concurrencia**: Por cada cliente que se conecta, crea un **hilo secundario (`threading.Thread`) dedicado**. Esto evita que si un cliente (ej. `REGIONAL_SANTA_CRUZ`) experimenta lag o se desconecta, afecte o bloquee la recepción del resto de los nodos.
2. **Recepción e Interpretación de Datos**:
   - Lee paquetes de texto JSON terminados en salto de línea (`\n`).
   - Mantiene en **memoria ram (Thread-Safe con Lock)** las métricas más recientes y la fecha/hora de comunicación de cada cliente conectado.
3. **Integración con Persistencia (Kevin)**:
   - Al recibir métricas, llama automáticamente a `save_metric(...)` en la Base de Datos. Si el cliente no existía, lo añade automáticamente (Adición Automática de Clientes).
4. **Detección de Fallos / Inactividad ("No Reporta")**:
   - Ejecuta un hilo en segundo plano que revisa si un nodo lleva más del tiempo configurado (`timeout_seconds`, por defecto 15s) sin enviar métricas. En caso de superar ese límite, actualiza su estado automáticamente a `"No Reporta"`.
5. **Comandos Bidireccionales**:
   - Permite enviar órdenes directas a un nodo conectado (ej. *"Reinicie servicio"*, *"Verifique espacio en disco"*) y recibir su confirmación `ACK`.

---

## 🤝 ¿Cómo les sirve esta parte a tus compañeros de equipo?

- 🟠 **A Tanina (Nodo Cliente)**: Le provee el socket TCP servidor listo al cual conectarse (`127.0.0.1:9000`). Ella puede enviar sus métricas en JSON y verificar que tu servidor las recibe y procesa correctamente.
- 🟢 **A Kevin (Persistencia)**: Le garantiza que cada dato recibido por el socket servidor activa automáticamente la inserción en la base de datos (`cluster_monitoring.db`).
- 🟣 **A Lucas (Dashboard)**: Le expone las métricas actuales consolidadas y listas para ser consultadas por la API REST y mostradas visualmente en la interfaz web.

---

## 🧪 Guía de Prueba Local (Paso a Paso)

Puedes probar el funcionamiento del Servidor Central abriendo **múltiples terminales** para validar la concurrencia y detección de clientes:

### Paso 1: Iniciar el Servidor Central (Mateo)
En la primera terminal, ejecuta:
```bash
python server/main.py
```
*(Verás un mensaje indicando que el servidor está escuchando en el puerto 9000).*

### Paso 2: Conectar Simuladores de Clientes Concurrentes (Tanina / Pruebas)
Abre **2 o más terminales adicionales** y ejecuta clientes simulados con diferentes identificadores:

- **Terminal 2 (Cliente 1)**:
  ```bash
  python client/main.py --id REGIONAL_LA_PAZ --interval 3
  ```
- **Terminal 3 (Cliente 2)**:
  ```bash
  python client/main.py --id REGIONAL_SANTA_CRUZ --interval 5
  ```
- **Terminal 4 (Cliente 3)**:
  ```bash
  python client/main.py --id REGIONAL_COCHABAMBA --interval 4
  ```

### Paso 3: ¿Qué debes observar en la consola del Servidor Central?
1. Verás aparecer las conexiones de los 3 nodos concurrentemente.
2. Cada pocos segundos verás los mensajes:
   `📥 [SERVIDOR CENTRAL] Métricas recibidas de [REGIONAL_LA_PAZ] ...`
3. Si en una terminal presionas `Ctrl + C` para desconectar un cliente, a los 15 segundos tu servidor mostrará:
   `⏳ [SERVIDOR CENTRAL] Timeout alcanzado para [REGIONAL_LA_PAZ] -> Marcado como 'No Reporta'`.
