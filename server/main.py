import os
import json
from server.socket_server import MonitoringServer

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

    server = MonitoringServer(host=host, port=port, timeout_seconds=timeout)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[SERVIDOR CENTRAL] Deteniendo servidor...")

if __name__ == "__main__":
    main()
