import argparse
import json
import os
from socket_client import MonitoringClient

def main():
    parser = argparse.ArgumentParser(description="Nodo Cliente de Monitoreo - Practica 1")
    parser.add_argument("--id", type=str, default="REGIONAL_01", help="Identificador único del cliente")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="IP del servidor central")
    parser.add_argument("--port", type=int, default=9000, help="Puerto del servidor central")
    parser.add_argument("--interval", type=int, default=5, help="Frecuencia de envío en segundos")
    args = parser.parse_args()

    # Cargar config global si existe
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f).get("client", {})
                args.host = cfg.get("server_host", args.host)
                args.port = cfg.get("server_port", args.port)
                args.interval = cfg.get("send_interval_seconds", args.interval)
        except Exception:
            pass

    client = MonitoringClient(
        client_id=args.id,
        server_host=args.host,
        server_port=args.port,
        send_interval=args.interval
    )
    
    try:
        client.start()
    except KeyboardInterrupt:
        print("\n[CLIENTE] Apagando cliente...")
        client.stop()

if __name__ == "__main__":
    main()
