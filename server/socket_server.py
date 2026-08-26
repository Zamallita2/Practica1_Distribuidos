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
        self.timeout_seconds = timeout_seconds
        
        # Diccionario en RAM para mantener TODOS los clientes (Activos y No Reporta)
        # Estructura: 
        # { client_id: { "status": "Activo"/"No Reporta", "socket": sock, "addr": addr, "last_seen": timestamp, "metrics": {...}, "last_ack": {...} } }
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
        server_sock.listen(9)
        
        # Hilo background para detección automática de fallos ("No Reporta")
        timeout_thread = threading.Thread(target=self._check_client_timeouts, daemon=True)
        timeout_thread.start()

        # Hilo background para el PANEL VISUAL Y GESTIÓN EN TIEMPO REAL
        monitor_ram_thread = threading.Thread(target=self._render_ram_inspector_panel, daemon=True)
        monitor_ram_thread.start()

        # Hilo background para el Menú Interactivo de Comandos y Teclas Rápidas
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

        if client_id:
            with self.lock:
                if client_id in self.clients:
                    self.clients[client_id]["status"] = "No Reporta"
                    self.clients[client_id]["socket"] = None
            update_client_status(client_id, "No Reporta")
        
        sock.close()

    def _process_message(self, sock, addr, message_str, current_client_id):
        """Procesa mensajes JSON: adición automática, métricas y confirmaciones ACK."""
        try:
            msg = json.loads(message_str)
            msg_type = msg.get("type")
            client_id = msg.get("client_id", current_client_id)

            if not client_id:
                client_id = f"CLIENT_{addr[0]}:{addr[1]}"

            if msg_type == "METRICS":
                disk = msg.get("disk", {})
                timestamp = msg.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                
                save_metric(client_id, disk, timestamp)
                
                with self.lock:
                    existing_ack = self.clients.get(client_id, {}).get("last_ack")
                    self.clients[client_id] = {
                        "status": "Activo",
                        "socket": sock,
                        "addr": addr,
                        "last_seen": time.time(),
                        "last_timestamp": timestamp,
                        "metrics": disk,
                        "last_ack": existing_ack
                    }

            elif msg_type == "ACK":
                cmd_id = msg.get("command_id")
                status = msg.get("status")
                action_text = msg.get("message", "Comando ejecutado")
                
                with self.lock:
                    if client_id in self.clients:
                        self.clients[client_id]["last_ack"] = {
                            "command_id": cmd_id,
                            "status": status,
                            "message": action_text,
                            "timestamp": time.strftime("%H:%M:%S", time.localtime())
                        }
                print(f"\n✅ [SERVIDOR CENTRAL] ACK RECIBIDO de [{client_id}] para '{cmd_id}': {action_text}")

            return client_id

        except Exception:
            return current_client_id

    def send_command_to_client(self, client_id, action):
        """Envía un comando bidireccional a un cliente específico (Tarea 6 de Mateo)."""
        with self.lock:
            client_info = self.clients.get(client_id)
            if not client_info or client_info.get("status") != "Activo" or not client_info.get("socket"):
                return False, f"El cliente [{client_id}] no está activo o conectado."

            cmd_payload = {
                "type": "COMMAND",
                "command_id": f"cmd-{int(time.time())}",
                "action": action
            }
            try:
                cmd_str = json.dumps(cmd_payload) + "\n"
                client_info["socket"].sendall(cmd_str.encode('utf-8'))
                return True, f"Comando '{action}' transmitido a [{client_id}]."
            except Exception as e:
                # Manejar errores de comunicación (desconexión súbita)
                client_info["status"] = "No Reporta"
                client_info["socket"] = None
                return False, f"Error enviando comando a [{client_id}]: {e}"

    def broadcast_command_to_all(self, action):
        """Envía un comando a TODOS los nodos activos."""
        with self.lock:
            active_ids = [cid for cid, data in self.clients.items() if data["status"] == "Activo"]
        
        if not active_ids:
            return 0, "No hay clientes activos conectados."
        
        sent_count = 0
        for cid in active_ids:
            ok, _ = self.send_command_to_client(cid, action)
            if ok: sent_count += 1
        return sent_count, f"Comando '{action}' enviado a {sent_count} clientes."

    def _check_client_timeouts(self):
        """Detección automática de inactividad."""
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
        """Panel visual que incluye KPIs, clientes, comandos y confirmaciones ACK."""
        while self.running:
            time.sleep(2)
            os.system('clear' if os.name == 'posix' else 'cls')
            
            print("==========================================================================================")
            print("🧠 [SERVIDOR CENTRAL (MATEO) — COMANDOS BIDIRECCIONALES & RECEPCIÓN ACK (TAREA 6)]")
            print("==========================================================================================")
            
            with self.lock:
                active_ram = {k: v for k, v in self.clients.items() if v["status"] == "Activo"}
                kpis = calculate_cluster_metrics_from_ram(active_ram)
                total_registrados = len(self.clients)
                
                print(f" ⚙️ TIMEOUT: {self.timeout_seconds}s | NODOS: {total_registrados}/9 | ACTIVOS: {kpis['active_nodes']} | NO REPORTA: {total_registrados - kpis['active_nodes']}")
                print("------------------------------------------------------------------------------------------")
                
                if total_registrados == 0:
                    print(" 💤 Esperando conexiones de nodos clientes... (Ejecuta: python3 client/main.py --id REGIONAL_LA_PAZ)")
                else:
                    print(f"{'CLIENT ID':<18} | {'ESTADO':<10} | {'DISCO (TIPO)':<16} | {'USADO / TOTAL':<16} | {'LIBRE':<9} | {'IOPS':<6} | {'REPORTE'}")
                    print("----------------------------------------------------------------------------------------------------")
                    now = time.time()
                    for cid, data in self.clients.items():
                        status = data.get("status", "Desconocido")
                        status_str = "🟢 Activo" if status == "Activo" else "🔴 No Reporta"
                        disk = data.get("metrics", {})
                        hace_seg = round(now - data.get("last_seen", now), 1)
                        
                        disk_name = f"{disk.get('name', 'N/A')} ({disk.get('type', 'SSD')})"
                        if len(disk_name) > 16: disk_name = disk_name[:14] + ".."
                        
                        used_total = f"{disk.get('used_gb', 0)}G/{disk.get('total_gb', 0)}G"
                        free_str = f"{disk.get('free_gb', 0)} GB"
                        iops_str = str(disk.get('iops', 0))
                        tiempo_str = f"Hace {hace_seg}s" if status == "Activo" else f"Timeout ({hace_seg}s)"
                        
                        print(f"{cid:<18} | {status_str:<10} | {disk_name:<16} | {used_total:<16} | {free_str:<9} | {iops_str:<6} | {tiempo_str}")

            
            print("==========================================================================================")
            print(" 🕹️ MENÚ DE COMANDOS RÁPIDOS EN CONSOLA (Escribe una opción + Enter):")
            print("    [1] Reiniciar Servicio (A todos los nodos activos)")
            print("    [2] Verificar Espacio en Disco (A todos los nodos activos)")
            print("    [3] Actualización de Configuración (A todos los nodos activos)")
            print("    [4 <CLIENT_ID> <COMANDO>] Enviar comando a un cliente específico")
            print("    [t <SEGUNDOS>] Cambiar timeout (Ejemplo: 't 10')")

    def _interactive_menu(self):
        """Menú interactivo por teclado para probar el envío de comandos y recepción de ACK."""
        while self.running:
            try:
                user_input = input().strip()
                if not user_input:
                    continue
                
                parts = user_input.split(" ", 2)
                option = parts[0].lower()
                
                if option == "1":
                    count, msg = self.broadcast_command_to_all("Reinicie servicio")
                    print(f"\n📤 {msg}")
                elif option == "2":
                    count, msg = self.broadcast_command_to_all("Verifique espacio en disco")
                    print(f"\n📤 {msg}")
                elif option == "3":
                    count, msg = self.broadcast_command_to_all("Actualización de configuración")
                    print(f"\n📤 {msg}")
                elif option == "4" and len(parts) >= 3:
                    target_id = parts[1]
                    action_cmd = parts[2]
                    ok, msg = self.send_command_to_client(target_id, action_cmd)
                    print(f"\n📤 {msg}")
                elif option == "t" and len(parts) >= 2 and parts[1].isdigit():
                    self.set_timeout_seconds(int(parts[1]))
                time.sleep(1)
            except Exception:
                pass

if __name__ == "__main__":
    server = MonitoringServer()
    server.start()
