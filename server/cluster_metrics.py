import time
from database.db_manager import get_latest_metrics_all_clients

def calculate_cluster_metrics():
    """
    Calcula los KPIs globales del cluster a partir de los datos más recientes en BD:
    - Capacidad total (Σ total)
    - Espacio utilizado total (Σ used)
    - Espacio libre total (Σ free)
    - Porcentaje de utilización global
    - Cantidad de nodos activos vs inactivos
    """
    latest_data = get_latest_metrics_all_clients()
    
    total_cluster_gb = 0.0
    used_cluster_gb = 0.0
    free_cluster_gb = 0.0
    active_nodes = 0
    total_nodes = len(latest_data)

    for item in latest_data:
        if item.get("status") == "Activo":
            active_nodes += 1
        total_cluster_gb += item.get("total_gb") or 0.0
        used_cluster_gb += item.get("used_gb") or 0.0
        free_cluster_gb += item.get("free_gb") or 0.0

    pct_utilization = round((used_cluster_gb / total_cluster_gb * 100), 2) if total_cluster_gb > 0 else 0.0

    return {
        "total_cluster_gb": round(total_cluster_gb, 2),
        "used_cluster_gb": round(used_cluster_gb, 2),
        "free_cluster_gb": round(free_cluster_gb, 2),
        "pct_utilization": pct_utilization,
        "active_nodes": active_nodes,
        "total_nodes": total_nodes,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
