import os
import json
import threading
from server.socket_server import MonitoringServer

# Instancia global del servidor TCP para que Flask la comparta
server_instance = None

def get_server_instance(host="0.0.0.0", port=9000, timeout=15, timeout_seconds=None):
    global server_instance
    if server_instance is None:
        actual_timeout = timeout_seconds if timeout_seconds is not None else timeout
        server_instance = MonitoringServer(host=host, port=port, timeout_seconds=actual_timeout)
    return server_instance

def start_server_in_background(host="0.0.0.0", port=9000, timeout=15, timeout_seconds=None):
    """Inicia el Servidor Central TCP en un hilo daemon secundario."""
    actual_timeout = timeout_seconds if timeout_seconds is not None else timeout
    srv = get_server_instance(host=host, port=port, timeout=actual_timeout)
    server_thread = threading.Thread(target=srv.start, daemon=True)
    server_thread.start()
    return srv


def main():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    host = "0.0.0.0"
    port = 9000
    timeout = 15

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f).get("server", {})
                host = cfg.get("host", host)
                port = cfg.get("port", port)
                timeout = cfg.get("timeout_seconds", timeout)
        except Exception:
            pass

    server = get_server_instance(host=host, port=port, timeout_seconds=timeout)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[SERVIDOR CENTRAL] Deteniendo servidor...")

if __name__ == "__main__":
    main()
