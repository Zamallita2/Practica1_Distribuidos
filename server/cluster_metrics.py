import time

def calculate_cluster_metrics_from_ram(clients_ram_dict):
    """
    Calcula los KPIs globales del cluster directamente desde la memoria RAM (self.clients):
    - Capacidad total del cluster (Σ total_gb)
    - Espacio utilizado global (Σ used_gb)
    - Espacio libre global (Σ free_gb)
    - Porcentaje de utilización global (% Utilización)
    - Latencia promedio estimada/registrada en ms
    - Cantidad de nodos activos
    """
    total_cluster_gb = 0.0
    used_cluster_gb = 0.0
    free_cluster_gb = 0.0
    active_nodes = len(clients_ram_dict)
    total_latency_ms = 0.0

    now = time.time()

    for cid, data in clients_ram_dict.items():
        disk = data.get("metrics", {})
        total_cluster_gb += disk.get("total_gb", 0.0)
        used_cluster_gb += disk.get("used_gb", 0.0)
        free_cluster_gb += disk.get("free_gb", 0.0)
        
        # Calcular latencia (tiempo transcurrido desde el último reporte en ms)
        last_seen = data.get("last_seen", now)
        latency = (now - last_seen) * 1000  # Convertir a milisegundos
        total_latency_ms += latency

    pct_utilization = round((used_cluster_gb / total_cluster_gb * 100), 2) if total_cluster_gb > 0 else 0.0
    avg_latency_ms = round(total_latency_ms / active_nodes, 1) if active_nodes > 0 else 0.0

    return {
        "total_cluster_gb": round(total_cluster_gb, 2),
        "used_cluster_gb": round(used_cluster_gb, 2),
        "free_cluster_gb": round(free_cluster_gb, 2),
        "pct_utilization": pct_utilization,
        "avg_latency_ms": avg_latency_ms,
        "active_nodes": active_nodes,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


def calculate_cluster_metrics():
    """
    Función puente para el dashboard.
    Calcula métricas del cluster usando los datos de la base de datos (persistencia).
    Esta función es llamada por dashboard/app.py para obtener KPIs globales.
    """
    from database.db_manager import get_cluster_summary
    return get_cluster_summary()