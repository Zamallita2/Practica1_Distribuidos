import os
import sys
import time
import json
from flask import Flask, render_template, jsonify, request

# Importar Servidor Central y Persistencia
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server.main import get_server_instance, start_server_in_background
from server.cluster_metrics import calculate_cluster_metrics_from_ram
from database.db_manager import (
    get_latest_metrics_all_clients,
    get_all_registered_clients,
    add_client_crud,
    delete_client_crud,
    get_iops_history
)

app = Flask(__name__, template_folder='templates', static_folder='static')

# Inicializar o recuperar la instancia global del Servidor Central TCP
server = get_server_instance()



@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/dashboard')
def get_dashboard_data():
    """
    Endpoint principal del Dashboard:
    - Retorna KPIs del cluster
    - Retorna el listado de nodos registrados
    - Retorna el historial de IOPS desde la BD para la gráfica de tiempo
    """
    with server.lock:
        clients_ram = dict(server.clients)
        timeout_sec = server.timeout_seconds

    now = time.time()
    
    # 1. Obtener todos los clientes autorizados en el CRUD
    registered_clients = get_all_registered_clients()
    registered_ids = [c["client_id"] for c in registered_clients]

    # 2. Métricas de la BD para respaldo
    db_metrics = get_latest_metrics_all_clients()
    db_dict = {item["client_id"]: item for item in db_metrics}

    # KPIs de nodos activos en RAM
    active_ram = {k: v for k, v in clients_ram.items() if k in registered_ids and v.get("status") == "Activo"}
    kpis_ram = calculate_cluster_metrics_from_ram(active_ram)

    servers_list = []

    for cid in registered_ids:
        ram_data = clients_ram.get(cid)
        db_data = db_dict.get(cid, {})

        if ram_data and ram_data.get("status") == "Activo":
            status = "Activo"
            disk = ram_data.get("metrics", {})
            last_seen = ram_data.get("last_seen")
            if last_seen is None:
                last_seen = now
            elapsed_sec = round(now - last_seen, 1)

            ack_info = ram_data.get("last_ack")
            ack_str = f"[{ack_info['timestamp']}] {ack_info['status']}" if ack_info else None
        else:
            status = db_data.get("status", "No Reporta")
            disk = {
                "name": db_data.get("disk_name", "N/A"),
                "type": db_data.get("disk_type", "SSD/HDD"),
                "total_gb": db_data.get("total_gb", 0.0),
                "used_gb": db_data.get("used_gb", 0.0),
                "free_gb": db_data.get("free_gb", 0.0),
                "iops": db_data.get("iops", 0),
                "all_disks": db_data.get("all_disks", [])
            }
            elapsed_sec = 999.0
            ack_str = None



        total_gb = float(disk.get("total_gb") or 0.0)
        used_gb = float(disk.get("used_gb") or 0.0)
        free_gb = float(disk.get("free_gb") or 0.0)
        iops = int(disk.get("iops") or 0)

        all_disks_raw = disk.get("all_disks", [])
        disks_formatted = []

        if all_disks_raw and len(all_disks_raw) > 0:
            sum_total = 0.0
            sum_used = 0.0
            sum_free = 0.0
            sum_iops = 0

            for d in all_disks_raw:
                d_total = float(d.get("total_gb") or 0.0)
                d_used = float(d.get("used_gb") or 0.0)
                d_free = float(d.get("free_gb") or 0.0)
                d_pct = round((d_used / d_total * 100), 1) if d_total > 0 else 0.0
                
                sum_total += d_total
                sum_used += d_used
                sum_free += d_free
                sum_iops += int(d.get("iops") or 0)

                disks_formatted.append({
                    "name": d.get("name", "N/A"),
                    "type": d.get("type", "SSD/HDD"),
                    "total": f"{d_total} GB",
                    "used": f"{d_used} GB",
                    "free": f"{d_free} GB",
                    "pct": d_pct,
                    "iops": int(d.get("iops") or 0)
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

    # Filtrar únicamente los servidores cuyo estado sea 'Activo'
    active_servers = [s for s in servers_list if s.get("status") == "Activo"]
    active_count = len(active_servers)
    
    total_disks_count = sum(len(s.get("disks", [])) for s in active_servers)
    
    if active_count > 0:
        sum_tot = sum(float(s["total"].replace(" GB", "")) for s in active_servers)
        sum_usd = sum(float(s["used"].replace(" GB", "")) for s in active_servers)
        sum_fre = sum(float(s["free"].replace(" GB", "")) for s in active_servers)
        
        total_cluster = round(sum_tot, 2)
        used_cluster = round(sum_usd, 2)
        free_cluster = round(sum_fre, 2)
        util_pct = round((used_cluster / total_cluster * 100), 1) if total_cluster > 0 else 0.0
    else:
        total_cluster = 0.0
        used_cluster = 0.0
        free_cluster = 0.0
        util_pct = 0.0
        total_disks_count = 0

    cluster_data = {
        "total_str": f"{round(total_cluster / 1024, 2)} TB" if total_cluster >= 1024 else f"{total_cluster} GB",
        "used_str": f"{used_cluster} GB",
        "free_str": f"{free_cluster} GB",
        "total_disks": total_disks_count,
        "utilization_pct": util_pct,
        "active_nodes": active_count,
        "total_registered": len(registered_ids),
        "avg_latency_ms": kpis_ram["avg_latency_ms"],
        "timeout_seconds": timeout_sec
    }


    # Historial de IOPS desde la BD para la gráfica de tiempo en el Dashboard
    iops_history = get_iops_history(limit=15)

    return jsonify({
        "cluster": cluster_data,
        "servers": servers_list,
        "iops_history": iops_history
    })


@app.route('/api/history/<client_id>')
def get_client_history_api(client_id):
    """Retorna la serie temporal histórica (IOPS y Espacio Ocupado total) para un nodo específico."""
    history = get_iops_history(client_id=client_id, limit=20)
    return jsonify(history)




@app.route('/api/nodes', methods=['GET', 'POST', 'DELETE'])
def manage_nodes_crud():
    """
    CRUD completo para los servidores registrados.
    GET: Lista de nodos
    POST: Agregar nuevo nodo autorizado
    DELETE: Eliminar nodo
    """
    if request.method == 'GET':
        return jsonify(get_all_registered_clients())

    elif request.method == 'POST':
        req = request.json or {}
        cid = req.get("client_id", "").strip()
        if not cid:
            return jsonify({"success": False, "message": "Identificador de cliente inválido"}), 400
        
        add_client_crud(cid)
        return jsonify({"success": True, "message": f"Servidor '{cid}' registrado exitosamente."})

    elif request.method == 'DELETE':
        req = request.json or {}
        cid = req.get("client_id", "").strip()
        if not cid:
            return jsonify({"success": False, "message": "Identificador no especificado"}), 400
        
        delete_client_crud(cid)
        # Si estaba conectado en la RAM, desconectarlo
        with server.lock:
            if cid in server.clients:
                del server.clients[cid]
        return jsonify({"success": True, "message": f"Servidor '{cid}' eliminado del CRUD."})


@app.route('/api/config', methods=['GET', 'POST'])
def manage_config_api():
    """GET/POST de parámetros globales (REPORT_INTERVAL y TIMEOUT)."""
    srv = get_server_instance()
    from database.db_manager import get_config, set_config

    if request.method == 'GET':
        report_interval = get_config("REPORT_INTERVAL") or "5"
        timeout = srv.timeout_seconds
        return jsonify({
            "report_interval": int(report_interval),
            "timeout_seconds": int(timeout)
        })

    elif request.method == 'POST':
        req = request.json or {}
        new_interval = req.get("report_interval")
        new_timeout = req.get("timeout_seconds")

        if new_timeout is not None:
            srv.set_timeout_seconds(int(new_timeout))

        if new_interval is not None and int(new_interval) >= 1:
            set_config("REPORT_INTERVAL", str(new_interval))
            srv._broadcast_config_update(int(new_interval))

        return jsonify({"success": True, "message": "Parámetros globales actualizados correctamente."})


@app.route('/api/command', methods=['POST'])
def send_command_api():
    """Endpoint para enviar comandos bidireccionales."""
    srv = get_server_instance()
    req_data = request.json or {}
    target_id = req_data.get("client_id")
    action = req_data.get("action")

    if not action:
        return jsonify({"success": False, "message": "Acción no especificada"}), 400

    if target_id:
        ok, msg = srv.send_command_to_client(target_id, action)
    else:
        sent_count, msg = srv.broadcast_command_to_all(action)
        ok = sent_count > 0

    return jsonify({"success": ok, "message": msg})




if __name__ == "__main__":
    start_server_in_background()
    print("[DASHBOARD PREMIUM] Servidor Web corriendo en http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
