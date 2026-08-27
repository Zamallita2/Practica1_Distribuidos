import os
import sys
import time
import json
from flask import Flask, render_template, jsonify, request

# Importar Servidor Central y Métricas RAM
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server.main import get_server_instance, start_server_in_background
from server.cluster_metrics import calculate_cluster_metrics_from_ram

app = Flask(__name__, template_folder='templates', static_folder='static')

# Inicializar o recuperar la instancia del Servidor Central TCP
server = get_server_instance()

@app.route('/')
def index():
    # Leer la frecuencia de actualización desde el config.json
    try:
        with open('../config.json', 'r') as f:
            config = json.load(f)
            # Extraer los segundos y convertirlos a milisegundos para JS
            refresh_rate = config['dashboard']['refresh_interval_seconds'] * 1000
    except Exception as e:
        print(f"Error leyendo config.json: {e}")
        refresh_rate = 3000 # Valor por defecto si falla
        
    # Pasar la variable refresh_rate a la plantilla HTML
    return render_template('index.html', refresh_rate=refresh_rate)

@app.route('/api/dashboard')
def get_dashboard_data():
    """
    Endpoint API REST que une la memoria RAM en tiempo real del Servidor Central
    con el historial guardado en la Base de Datos para mostrar siempre los 9 nodos.
    """
    from database.db_manager import get_latest_metrics_all_clients
    
    # 1. Obtener la RAM en tiempo real
    with server.lock:
        clients_ram = dict(server.clients)
        timeout_sec = server.timeout_seconds

    now = time.time()
    
    # 2. Obtener datos persistidos de la BD para respaldar nodos
    db_metrics = get_latest_metrics_all_clients()
    db_dict = {item["client_id"]: item for item in db_metrics}

    # Unificar nodos conocidos de RAM y BD
    all_client_ids = list(set(list(clients_ram.keys()) + list(db_dict.keys())))

    active_ram = {k: v for k, v in clients_ram.items() if v.get("status") == "Activo"}
    kpis_ram = calculate_cluster_metrics_from_ram(active_ram)

    servers_list = []
    
    for cid in all_client_ids:
        ram_data = clients_ram.get(cid)
        db_data = db_dict.get(cid, {})

        if ram_data:
            status = ram_data.get("status", "No reporta")
            disk = ram_data.get("metrics", {})
            last_seen = ram_data.get("last_seen", now)
            elapsed_sec = round(now - last_seen, 1)
            ack_info = ram_data.get("last_ack")
            ack_str = f"[{ack_info['timestamp']}] {ack_info['status']}" if ack_info else None
        else:
            status = db_data.get("status", "No reporta")
            disk = {
                "name": db_data.get("disk_name", "N/A"),
                "type": db_data.get("disk_type", "SSD/HDD"),
                "total_gb": db_data.get("total_gb", 0.0),
                "used_gb": db_data.get("used_gb", 0.0),
                "free_gb": db_data.get("free_gb", 0.0),
                "iops": db_data.get("iops", 0)
            }
            elapsed_sec = 999.0
            ack_str = None

        total_gb = disk.get("total_gb", 0.0)
        used_gb = disk.get("used_gb", 0.0)
        free_gb = disk.get("free_gb", 0.0)
        iops = disk.get("iops", 0)

        all_disks_raw = disk.get("all_disks", [])
        disks_formatted = []

        if all_disks_raw and len(all_disks_raw) > 0:
            sum_total = 0.0
            sum_used = 0.0
            sum_free = 0.0
            sum_iops = 0

            for d in all_disks_raw:
                d_total = d.get("total_gb", 0.0)
                d_used = d.get("used_gb", 0.0)
                d_free = d.get("free_gb", 0.0)
                d_pct = round((d_used / d_total * 100), 1) if d_total > 0 else 0.0
                
                sum_total += d_total
                sum_used += d_used
                sum_free += d_free
                sum_iops += d.get("iops", 0)

                disks_formatted.append({
                    "name": d.get("name", "N/A"),
                    "type": d.get("type", "SSD/HDD"),
                    "total": f"{d_total} GB",
                    "used": f"{d_used} GB",
                    "free": f"{d_free} GB",
                    "pct": d_pct,
                    "iops": d.get("iops", 0)
                })

            total_gb = round(sum_total, 2)
            used_gb = round(sum_used, 2)
            free_gb = round(sum_free, 2)
            iops = sum_iops
        else:
            pct = round((used_gb / total_gb * 100), 1) if total_gb > 0 else 0.0
            disks_formatted.append({
                "name": disk.get("name", "N/A"),
                "type": disk.get("type", "SSD/HDD"),
                "total": f"{total_gb} GB",
                "used": f"{used_gb} GB",
                "free": f"{free_gb} GB",
                "pct": pct,
                "iops": iops
            })

        pct_overall = round((used_gb / total_gb * 100), 1) if total_gb > 0 else 0.0

        servers_list.append({
            "id": cid,
            "status": status,
            "disk_name": disk.get("name", "N/A"),
            "disk_type": disk.get("type", "SSD/HDD"),
            "total": f"{total_gb} GB",
            "used": f"{used_gb} GB",
            "free": f"{free_gb} GB",
            "pct": pct_overall,
            "iops": iops,
            "elapsed_sec": elapsed_sec,
            "last_ack": ack_str,
            "disks": disks_formatted
        })


    # Formatear KPIs del cluster para la cabecera del Dashboard
    total_cluster = kpis_ram["total_cluster_gb"]
    used_cluster = kpis_ram["used_cluster_gb"]
    free_cluster = kpis_ram["free_cluster_gb"]

    cluster_data = {
        "total_str": f"{round(total_cluster / 1024, 2)} TB" if total_cluster >= 1024 else f"{total_cluster} GB",
        "used_str": f"{used_cluster} GB",
        "free_str": f"{free_cluster} GB",
        "utilization_pct": kpis_ram["pct_utilization"],
        "active_nodes": kpis_ram["active_nodes"],
        "avg_latency_ms": kpis_ram["avg_latency_ms"],
        "timeout_seconds": timeout_sec
    }

    return jsonify({
        "cluster": cluster_data,
        "servers": servers_list
    })


@app.route('/api/command', methods=['POST'])
def send_command_api():
    """Endpoint para enviar comandos bidireccionales desde el Dashboard Web."""
    req_data = request.json or {}
    target_id = req_data.get("client_id")
    action = req_data.get("action")

    if not action:
        return jsonify({"success": False, "message": "Acción no especificada"}), 400

    if target_id:
        ok, msg = server.send_command_to_client(target_id, action)
    else:
        sent_count, msg = server.broadcast_command_to_all(action)
        ok = sent_count > 0

    return jsonify({"success": ok, "message": msg})

if __name__ == "__main__":
    # Iniciar también el servidor TCP en segundo plano si se ejecuta app.py directamente
    start_server_in_background()
    print("[DASHBOARD] Servidor Web corriendo en http://localhost:5000 (Leyendo datos en tiempo real de la RAM)")
    app.run(host="0.0.0.0", port=5000, debug=False)
