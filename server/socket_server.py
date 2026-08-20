import socket
import json
import threading
import time
from database.db_manager import init_db, save_metric, update_client_status

class MonitoringServer:
    def __init__(self, host="0.0.0.0", port=9000, timeout_seconds=15):
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        
        # Almacenamiento en memoria de clientes conectados e información actual
        # Estructura: { client_id: { "socket": sock, "addr": addr, "last_seen": timestamp, "metrics": {...} } }
        self.clients = {}
        self.lock = threading.Lock()
        self.running = False
        
        # Inicializar la base de datos (Persistencia de Kevin)
        init_db()

    def start(self):
        """Inicia el socket servidor TCP y la escucha concurrente de clientes."""
        self.running = True
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(9)  # Preparado para soportar los 9 clientes de la práctica
        
        print("=========================================================")
        print(f"🚀 [SERVIDOR CENTRAL] Servidor TCP iniciado en {self.host}:{self.port}")
        print(f"⏱️  [SERVIDOR CENTRAL] Timeout de inactividad: {self.timeout_seconds} segundos")
        print("=========================================================")

        # Hilo background para detección de fallos / nodos inactivos ("No Reporta")
        timeout_thread = threading.Thread(target=self._check_client_timeouts, daemon=True)
        timeout_thread.start()

        while self.running:
            try:
                client_sock, addr = server_sock.accept()
                print(f"\n🔌 [SERVIDOR CENTRAL] Nueva conexión entrante desde: {addr}")
                # Creación de Thread dedicado por cliente para garantizar concurrencia sin bloqueos
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
            except Exception as e:
                print(f"⚠️ [SERVIDOR CENTRAL] Conexión interrumpida con {client_id or addr}: {e}")
                break

        # Limpieza y actualización de estado si se desconecta el socket
        if client_id:
            with self.lock:
                if client_id in self.clients:
                    del self.clients[client_id]
            update_client_status(client_id, "No Reporta")
            print(f"🔴 [SERVIDOR CENTRAL] Cliente [{client_id}] desconectado -> Estado actualizado a: 'No Reporta'")
        
        sock.close()

    def _process_message(self, sock, addr, message_str, current_client_id):
        """Procesa el mensaje JSON recibido del cliente y actualiza estado en Memoria y BD."""
        try:
            msg = json.loads(message_str)
            msg_type = msg.get("type")
            client_id = msg.get("client_id", current_client_id)

            if not client_id:
                client_id = f"CLIENT_{addr[0]}:{addr[1]}"

            if msg_type == "METRICS":
                disk = msg.get("disk", {})
                timestamp = msg.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                
                # 1. Guardar en Base de Datos (Persistencia)
                save_metric(client_id, disk, timestamp)
                
                # 2. Mantener estado actual en Memoria (Servidor Central)
                with self.lock:
                    self.clients[client_id] = {
                        "socket": sock,
                        "addr": addr,
                        "last_seen": time.time(),
                        "last_timestamp": timestamp,
                        "metrics": disk
                    }
                print(f"📥 [SERVIDOR CENTRAL] Métricas recibidas de [{client_id}] | Uso: {disk.get('used_gb')}GB / {disk.get('total_gb')}GB")

            elif msg_type == "ACK":
                cmd_id = msg.get("command_id")
                status = msg.get("status")
                print(f"✅ [SERVIDOR CENTRAL] ACK Confirmado por [{client_id}] para comando '{cmd_id}' (Estado: {status})")

            return client_id

        except json.JSONDecodeError:
            print(f"❌ [SERVIDOR CENTRAL] Error: JSON malformado recibido de {addr}: {message_str}")
            return current_client_id
        except Exception as e:
            print(f"❌ [SERVIDOR CENTRAL] Error procesando mensaje de {addr}: {e}")
            return current_client_id

    def get_active_clients_in_memory(self):
        """Retorna copia segura de los clientes actualmente registrados en memoria."""
        with self.lock:
            return dict(self.clients)

    def send_command(self, client_id, action):
        """Envía un comando remoto bidireccional a un cliente específico (Tarea 6 de Mateo)."""
        with self.lock:
            client_info = self.clients.get(client_id)
            if not client_info or not client_info.get("socket"):
                return False, f"El cliente [{client_id}] no está conectado actualmente."

            cmd_payload = {
                "type": "COMMAND",
                "command_id": f"cmd-{int(time.time())}",
                "action": action
            }
            try:
                cmd_str = json.dumps(cmd_payload) + "\n"
                client_info["socket"].sendall(cmd_str.encode('utf-8'))
                print(f"📤 [SERVIDOR CENTRAL] Comando enviado a [{client_id}]: '{action}'")
                return True, "Comando transmitido correctamente"
            except Exception as e:
                return False, f"Error enviando comando a [{client_id}]: {e}"

    def _check_client_timeouts(self):
        """Detección automática de clientes inactivos o caídos ('No Reporta') (Tarea 5 de Mateo)."""
        while self.running:
            time.sleep(4)
            now = time.time()
            with self.lock:
                for cid, info in list(self.clients.items()):
                    elapsed = now - info["last_seen"]
                    if elapsed > self.timeout_seconds:
                        print(f"⏳ [SERVIDOR CENTRAL] Timeout alcanzado para [{cid}] ({int(elapsed)}s sin reportar) -> Marcado como 'No Reporta'")
                        update_client_status(cid, "No Reporta")

if __name__ == "__main__":
    server = MonitoringServer()
    server.start()
