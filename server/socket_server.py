import socket
import json
import threading
import time
import os
from database.db_manager import init_db, save_metric, update_client_status
from server.cluster_metrics import calculate_cluster_metrics_from_ram

class MonitoringServer:
    def __init__(self, host="0.0.0.0", port=9000, timeout_seconds=15):
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds  # Límite configurable de inactividad
        
        # Diccionario en RAM para mantener TODOS los clientes (Activos y No Reporta)
        # Estructura: 
        # { client_id: { "status": "Activo"/"No Reporta", "socket": sock, "addr": addr, "last_seen": timestamp, "metrics": {...} } }
        self.clients = {}
        self.lock = threading.Lock()
        self.running = False
        
        # Inicializar la base de datos (Persistencia de Kevin)
        init_db()

    def set_timeout_seconds(self, new_timeout):
        """Permite modificar dinámicamente el límite de inactividad (Parametrización)."""
        with self.lock:
            self.timeout_seconds = max(3, int(new_timeout))
            print(f"\n⚙️ [CONFIGURACIÓN] Nuevo límite de timeout fijado a: {self.timeout_seconds} segundos.")

    def start(self):
        """Inicia el socket servidor TCP y la escucha concurrente de clientes."""
        self.running = True
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(9)  # Preparado para soportar los 9 clientes de la práctica
        
        # Hilo background para detección automática de fallos ("No Reporta")
        timeout_thread = threading.Thread(target=self._check_client_timeouts, daemon=True)
        timeout_thread.start()

        # Hilo background para el PANEL DE INSPECCIÓN Y GESTIÓN EN TIEMPO REAL
        monitor_ram_thread = threading.Thread(target=self._render_ram_inspector_panel, daemon=True)
        monitor_ram_thread.start()

        # Hilo background para permitir parametrización interactiva desde consola
        interactive_thread = threading.Thread(target=self._interactive_menu, daemon=True)
        interactive_thread.start()

        while self.running:
            try:
                client_sock, addr = server_sock.accept()
                client_thread = threading.Thread(
                    target=self._handle_client, 
                    args=(client_sock, addr), 
                    daemon=True
                )
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"❌ [SERVIDOR CENTRAL] Error aceptando cliente: {e}")
                break

    def _handle_client(self, sock, addr):
        """Atiende a un cliente individual en un hilo secundario (Manejo Concurrente)."""
        buffer = ""
        client_id = None
        
        while self.running:
            try:
                data = sock.recv(1024).decode('utf-8')
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        client_id = self._process_message(sock, addr, line.strip(), client_id)
            except Exception:
                break

        # Al desconectarse el socket TCP, NO eliminamos al cliente de la RAM.
        # En su lugar, lo conservamos y lo marcamos explícitamente como 'No Reporta' (Tarea 5).
        if client_id:
            with self.lock:
                if client_id in self.clients:
                    self.clients[client_id]["status"] = "No Reporta"
                    self.clients[client_id]["socket"] = None
            update_client_status(client_id, "No Reporta")
        
        sock.close()

    def _process_message(self, sock, addr, message_str, current_client_id):
        """Procesa mensajes JSON: adición automática, asignación de ID, estado 'Activo' y actualización."""
        try:
            msg = json.loads(message_str)
            msg_type = msg.get("type")
            client_id = msg.get("client_id", current_client_id)

            if not client_id:
                client_id = f"CLIENT_{addr[0]}:{addr[1]}"

            if msg_type == "METRICS":
                disk = msg.get("disk", {})
                timestamp = msg.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                
                # 1. Guardar en BD (Adición automática + Persistencia)
                save_metric(client_id, disk, timestamp)
                
                # 2. Adición/Actualización Automática en RAM: asociar ID y marcar como 'Activo'
                with self.lock:
                    self.clients[client_id] = {
                        "status": "Activo",  # Marcar explícitamente como 'Activo'
                        "socket": sock,
                        "addr": addr,
                        "last_seen": time.time(),
                        "last_timestamp": timestamp,
                        "metrics": disk
                    }

            elif msg_type == "ACK":
                cmd_id = msg.get("command_id")
                status = msg.get("status")
                print(f"\n✅ [SERVIDOR CENTRAL] ACK Confirmado por [{client_id}] para comando '{cmd_id}' (Estado: {status})")

            return client_id

        except Exception:
            return current_client_id

    def _check_client_timeouts(self):
        """Detección automática de clientes inactivos o caídos ('No Reporta') cuando superan timeout_seconds."""
        while self.running:
            time.sleep(2)
            now = time.time()
            with self.lock:
                for cid, info in list(self.clients.items()):
                    if info["status"] == "Activo":
                        elapsed = now - info["last_seen"]
                        if elapsed > self.timeout_seconds:
                            info["status"] = "No Reporta"
                            info["socket"] = None
                            update_client_status(cid, "No Reporta")

    def _render_ram_inspector_panel(self):
        """Panel visual que muestra Nodos Activos vs No Reporta y el timeout configurado."""
        while self.running:
            time.sleep(2)
            os.system('clear' if os.name == 'posix' else 'cls')
            
            print("==========================================================================================")
            print("🧠 [SERVIDOR CENTRAL (MATEO) — DETECCIÓN DE CLIENTES & CONTROL DE FALLOS (TAREA 5)]")
            print("==========================================================================================")
            
            with self.lock:
                # Filtrar activos para KPIs
                active_ram = {k: v for k, v in self.clients.items() if v["status"] == "Activo"}
                kpis = calculate_cluster_metrics_from_ram(active_ram)
                total_registrados = len(self.clients)
                
                print(f" ⚙️ CONFIGURACIÓN TIMEOUT: {self.timeout_seconds}s sin reportar -> pasa a 'No Reporta'")
                print(f" 📊 NODOS REGISTRADOS: {total_registrados} / 9 | ACTIVOS: {kpis['active_nodes']} | NO REPORTA: {total_registrados - kpis['active_nodes']}")
                print(f" 📈 KPIS CLUSTER ACTIVO: Usado {kpis['used_cluster_gb']}GB / {kpis['total_cluster_gb']}GB ({kpis['pct_utilization']}%)")
                print("------------------------------------------------------------------------------------------")
                
                if total_registrados == 0:
                    print(" 💤 Esperando conexiones de nodos clientes... (Adición automática al conectarse)")
                else:
                    print(f"{'CLIENT ID':<22} | {'ESTADO':<11} | {'DISCO':<10} | {'USADO / TOTAL':<18} | {'ÚLTIMO REPORTE'}")
                    print("------------------------------------------------------------------------------------------")
                    now = time.time()
                    for cid, data in self.clients.items():
                        status = data.get("status", "Desconocido")
                        status_str = "🟢 Activo" if status == "Activo" else "🔴 No Reporta"
                        disk = data.get("metrics", {})
                        used_total = f"{disk.get('used_gb', 0)}GB / {disk.get('total_gb', 0)}GB"
                        hace_seg = round(now - data.get("last_seen", now), 1)
                        disk_name = disk.get('name', 'N/A')
                        if len(disk_name) > 10: disk_name = disk_name[:7] + "..."
                        
                        tiempo_str = f"Hace {hace_seg}s" if status == "Activo" else f"Timeout ({hace_seg}s)"
                        
                        print(f"{cid:<22} | {status_str:<11} | {disk_name:<10} | {used_total:<18} | {tiempo_str}")
            
            print("==========================================================================================")
            print(" 💡 Para cambiar el límite de Timeout en caliente, escribe un número (ej: 10) y presiona Enter:")

    def _interactive_menu(self):
        """Permite al usuario/evaluador cambiar la variable de timeout en tiempo real desde la consola."""
        while self.running:
            try:
                user_input = input()
                if user_input.strip().isdigit():
                    new_val = int(user_input.strip())
                    self.set_timeout_seconds(new_val)
                    time.sleep(1)
            except Exception:
                pass

if __name__ == "__main__":
    server = MonitoringServer()
    server.start()
