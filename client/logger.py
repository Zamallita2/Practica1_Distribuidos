import os
import datetime

LOG_FILE = "client_commands.log"

def log_command(command_data):
    """
    Registra el comando recibido en el archivo client_commands.log.
    Requisito explícito 4 del Cliente.
    """
    timestamp = datetime.datetime.now().isoformat()
    log_entry = f"[{timestamp}] COMANDO RECIBIDO: {command_data}\n"
    
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
        
    print(f"[LOGGER] Registrado en {LOG_FILE}: {command_data}")

def create_ack_response(command_id, client_id, status="OK", message="Comando procesado correctamente"):
    """
    Genera la estructura de respuesta ACK para enviar al servidor central.
    """
    return {
        "type": "ACK",
        "command_id": command_id,
        "client_id": client_id,
        "status": status,
        "message": message,
        "timestamp": datetime.datetime.now().isoformat()
    }
