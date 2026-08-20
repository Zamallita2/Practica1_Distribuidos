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
        self.clients = {}  # {client_id: {"socket": sock, "last_seen": timestamp}}
        self.lock = threading.Lock()
        self.running = False
        init_db()

    def start(self):
        """Inicia el servidor TCP concurrente."""
        self.running = True
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(9)  # Soporta los 9 clientes exigidos
        print(f"[SERVIDOR CENTRAL] Escuchando en {self.host}:{self.port}...")

        # Hilo background para monitorear timeouts ("No Reporta")
        timeout_thread = threading.Thread(target=self._check_client_timeouts, daemon=True)
        timeout_thread.start()

        while self.running:
            try:
                client_sock, addr = server_sock.accept()
                print(f"[SERVIDOR CENTRAL] Nueva conexión recibida de {addr}")
                client_thread = threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True)
                client_thread.start()
            except Exception as e:
                print(f"[SERVIDOR CENTRAL] Error en accept: {e}")
                break

    def _handle_client(self, sock, addr):
        """Maneja la recepción de mensajes de un cliente individual."""
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
                        client_id = self._process_message(sock, line.strip(), client_id)
            except Exception as e:
                print(f"[SERVIDOR CENTRAL] Error en comunicación con {client_id or addr}: {e}")
                break

        # Limpieza al desconectarse
        if client_id:
            with self.lock:
                if client_id in self.clients:
                    del self.clients[client_id]
            update_client_status(client_id, "No Reporta")
            print(f"[SERVIDOR CENTRAL] Cliente {client_id} desconectado -> Estado: No Reporta")
        sock.close()

    def _process_message(self, sock, message_str, current_client_id):
        """Procesa cada mensaje JSON recibido del cliente."""
        try:
            msg = json.loads(message_str)
            msg_type = msg.get("type")
            client_id = msg.get("client_id", current_client_id)

            if msg_type == "METRICS":
                disk = msg.get("disk", {})
                timestamp = msg.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                
                # Guardar en BD (Adición automática + persistencia)
                save_metric(client_id, disk, timestamp)
                
                with self.lock:
                    self.clients[client_id] = {
                        "socket": sock,
                        "last_seen": time.time()
                    }
                print(f"[SERVIDOR CENTRAL] Métricas guardadas para [{client_id}]")

            elif msg_type == "ACK":
                cmd_id = msg.get("command_id")
                print(f"[SERVIDOR CENTRAL] ACK RECIBIDO de [{client_id}] para comando {cmd_id}: {msg.get('message')}")

            return client_id
        except Exception as e:
            print(f"[SERVIDOR CENTRAL] Error procesando JSON: {e}")
            return current_client_id

    def send_command(self, client_id, action):
        """Envía un comando remoto personalizado a un cliente específico (Requisito 6)."""
        with self.lock:
            client_info = self.clients.get(client_id)
            if not client_info or not client_info.get("socket"):
                return False, f"Cliente {client_id} no está conectado."

            cmd_payload = {
                "type": "COMMAND",
                "command_id": f"cmd-{int(time.time())}",
                "action": action
            }
            try:
                cmd_str = json.dumps(cmd_payload) + "\n"
                client_info["socket"].sendall(cmd_str.encode('utf-8'))
                print(f"[SERVIDOR CENTRAL] Comando '{action}' enviado a [{client_id}]")
                return True, "Comando enviado correctamente"
            except Exception as e:
                return False, f"Error enviando comando: {e}"

    def _check_client_timeouts(self):
        """Verifica periódicamente si algún cliente ha dejado de reportar (Requisito 5)."""
        while self.running:
            time.sleep(5)
            now = time.time()
            with self.lock:
                for cid, info in list(self.clients.items()):
                    if now - info["last_seen"] > self.timeout_seconds:
                        print(f"[SERVIDOR CENTRAL] Cliente [{cid}] superó el timeout de {self.timeout_seconds}s -> No Reporta")
                        update_client_status(cid, "No Reporta")

if __name__ == "__main__":
    server = MonitoringServer()
    server.start()
