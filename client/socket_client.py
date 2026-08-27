import socket
import json
import time
import threading
import sys
import os

# Agregar la ruta raíz al path para importar correctamente
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.disk_metrics import get_first_disk_metrics
from client.logger import log_command, create_ack_response

class MonitoringClient:
    def __init__(self, client_id, server_host="127.0.0.1", server_port=9000, send_interval=5):
        self.client_id = client_id
        self.server_host = server_host
        self.server_port = server_port
        self.send_interval = send_interval
        self.sock = None
        self.running = False
        self.interval_lock = threading.Lock()  # Para cambiar el intervalo de forma segura

    def connect(self):
        """Conecta el socket TCP al servidor central."""
        while self.running:
            try:
                print(f"[CLIENTE {self.client_id}] Intentando conectar a {self.server_host}:{self.server_port}...")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.server_host, self.server_port))
                print(f"[CLIENTE {self.client_id}] ¡Conectado al Servidor Central!")
                
                # Hilo para escuchar mensajes bidireccionales del servidor
                listen_thread = threading.Thread(target=self._listen_server, daemon=True)
                listen_thread.start()
                
                # Bucle de envío periódico de métricas
                self._send_loop()
            except Exception as e:
                print(f"[CLIENTE {self.client_id}] Error de conexión: {e}. Reintentando en 5s...")
                time.sleep(5)

    def _send_loop(self):
        """Envía métricas de disco de forma periódica con intervalo dinámico."""
        while self.running:
            try:
                disk = get_first_disk_metrics()
                payload = {
                    "type": "METRICS",
                    "client_id": self.client_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "disk": disk
                }
                data_str = json.dumps(payload) + "\n"
                self.sock.sendall(data_str.encode('utf-8'))
                print(f"[CLIENTE {self.client_id}] Métricas enviadas correctamente.")
                
                # Usar el intervalo actual (puede cambiar dinámicamente)
                with self.interval_lock:
                    current_interval = self.send_interval
                time.sleep(current_interval)
            except Exception as e:
                print(f"[CLIENTE {self.client_id}] Error enviando métricas: {e}")
                break

    def _listen_server(self):
        """Escucha comandos bidireccionales provenientes del servidor."""
        buffer = ""
        while self.running and self.sock:
            try:
                data = self.sock.recv(1024).decode('utf-8')
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        self._handle_server_message(line.strip())
            except Exception:
                break

    def _handle_server_message(self, message_str):
        """Procesa comandos recibidos, registra logs y responde ACK."""
        try:
            msg = json.loads(message_str)
            print(f"[CLIENTE {self.client_id}] Mensaje recibido del servidor: {msg}")
            
            if msg.get("type") == "COMMAND":
                action = msg.get("action", "")
                
                print("\n==================================================================")
                print(f"🔔 [NOTIFICACIÓN DEL SERVIDOR CENTRAL CENTRAL] 🔔")
                print(f"👉 MENSAJE / ACCIÓN SOLICITADA: '{action}'")
                print("==================================================================\n")

                # Verificar si es una actualización de configuración
                if action.startswith("Actualización de configuración"):
                    parts = action.split("|")
                    if len(parts) > 1:
                        try:
                            new_interval = int(parts[1])
                            with self.interval_lock:
                                self.send_interval = new_interval
                            print(f"⚙️ [CLIENTE {self.client_id}] Nuevo intervalo aplicado: {new_interval} segundos.")
                        except ValueError:
                            print(f"⚠️ [CLIENTE {self.client_id}] Error procesando nuevo intervalo.")
                
                # Registrar en .log y responder ACK
                log_command(msg)
                cmd_id = msg.get("command_id", "unk")
                ack = create_ack_response(cmd_id, self.client_id, status="OK", message=f"Ejecutado: '{action}'")
                ack_str = json.dumps(ack) + "\n"
                self.sock.sendall(ack_str.encode('utf-8'))
                print(f"✅ [CLIENTE {self.client_id}] ACK enviado al Servidor Central y guardado en client_commands.log.")


        except Exception as e:
            print(f"[CLIENTE {self.client_id}] Error procesando mensaje: {e}")

    def start(self):
        self.running = True
        self.connect()

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()