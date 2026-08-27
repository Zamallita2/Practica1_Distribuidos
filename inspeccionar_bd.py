"""
Inspector de la base de datos REAL del cluster (cluster_monitoring.db).
Úsalo mientras el servidor y los clientes están corriendo, para verificar
que los datos se están persistiendo correctamente.

Uso: python inspeccionar_bd.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database.db_manager import (
    get_latest_metrics_all_clients,
    get_client_history,
    get_cluster_summary,
    get_all_config,
    get_all_pending_messages,
)


def separador(titulo):
    print("\n" + "=" * 70)
    print(f" {titulo}")
    print("=" * 70)


def main():
    separador("1. CLIENTES Y SU ÚLTIMA MÉTRICA (get_latest_metrics_all_clients)")
    clientes = get_latest_metrics_all_clients()
    if not clientes:
        print("  (sin clientes registrados todavía)")
    for c in clientes:
        print(f"  {c['client_id']:<15} | {c['status']:<12} | "
              f"disco={c.get('disk_name')} | total={c.get('total_gb')}GB | "
              f"usado={c.get('used_gb')}GB | último_reporte={c.get('timestamp')}")

    separador("2. CONFIGURACIÓN ACTUAL (get_all_config)")
    print(f"  {get_all_config()}")

    separador("3. RESUMEN / KPIs DEL CLUSTER (get_cluster_summary)")
    print(f"  {get_cluster_summary()}")

    separador("4. MENSAJES PENDIENTES SIN ACK (get_all_pending_messages)")
    pendientes = get_all_pending_messages()
    if not pendientes:
        print("  (ninguno pendiente)")
    for m in pendientes:
        print(f"  id={m['id']} -> {m['client_id']}: '{m['message']}' (enviado {m['sent_at']})")

    if clientes:
        separador(f"5. HISTORIAL DE MÉTRICAS de '{clientes[0]['client_id']}' (últimas 10)")
        hist = get_client_history(clientes[0]['client_id'], limit=10)
        for h in hist:
            print(f"  {h['timestamp']} | total={h['total_gb']}GB usado={h['used_gb']}GB libre={h['free_gb']}GB iops={h['iops']}")


if __name__ == "__main__":
    main()