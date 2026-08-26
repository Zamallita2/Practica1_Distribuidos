"""
Pruebas de persistencia y sincronización para database/db_manager.py

Cómo correrlas:
    pip install pytest
    pytest tests/test_db_manager.py -v

Cada test usa un archivo SQLite temporal aislado (nunca la BD real del cluster).
"""

import os
import sys
import tempfile
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

# Ajusta el path para importar database/db_manager.py desde tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import db_manager  # noqa: E402


@pytest.fixture(autouse=True)
def bd_temporal(monkeypatch):
    """Redirige DB_PATH a un archivo temporal antes de cada test y lo borra después."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # que init_db lo cree desde cero

    monkeypatch.setattr(db_manager, "DB_PATH", path)
    db_manager.init_db()

    yield path

    for ext in ("", "-wal", "-shm"):
        p = path + ext
        if os.path.exists(p):
            os.remove(p)


def ahora():
    # UTC, para que sea comparable con julianday('now') de SQLite (siempre UTC)
    return dt.datetime.utcnow().isoformat()


def hace_segundos(segundos):
    return (dt.datetime.utcnow() - dt.timedelta(seconds=segundos)).isoformat()


# ---------------------------------------------------------------------
# 1. Concurrencia: 9 clientes reportando simultáneamente
# ---------------------------------------------------------------------
def test_save_metric_concurrente_no_pierde_filas():
    disk_data = {"name": "sda1", "type": "SSD", "total_gb": 500, "used_gb": 100, "free_gb": 400, "iops": 1200}
    n_clientes = 9
    reportes_por_cliente = 5

    def reportar(client_id):
        for _ in range(reportes_por_cliente):
            db_manager.save_metric(client_id, disk_data, ahora())

    with ThreadPoolExecutor(max_workers=n_clientes) as executor:
        futuros = [executor.submit(reportar, f"nodo-{i}") for i in range(n_clientes)]
        for f in as_completed(futuros):
            f.result()  # relanza cualquier excepción del hilo

    clientes = db_manager.get_latest_metrics_all_clients()
    assert len(clientes) == n_clientes

    # Verifica que no se perdió ninguna fila de métricas
    with db_manager._tx() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM metrics").fetchone()["c"]
    assert total == n_clientes * reportes_por_cliente


# ---------------------------------------------------------------------
# 2. Detección de nodos inactivos
# ---------------------------------------------------------------------
def test_check_inactive_clients_marca_nodos_caidos():
    db_manager.save_metric("nodo-viejo", {"name": "sda1"}, hace_segundos(300))
    db_manager.save_metric("nodo-activo", {"name": "sda1"}, ahora())

    afectados = db_manager.check_inactive_clients(timeout_seconds=60)

    assert "nodo-viejo" in afectados
    assert "nodo-activo" not in afectados

    clientes = {c["client_id"]: c["status"] for c in db_manager.get_latest_metrics_all_clients()}
    assert clientes["nodo-viejo"] == "No Reporta"
    assert clientes["nodo-activo"] == "Activo"


# ---------------------------------------------------------------------
# 3. Idempotencia de init_db()
# ---------------------------------------------------------------------
def test_init_db_es_idempotente():
    db_manager.set_config("REPORT_INTERVAL", "45")  # cambia el valor por defecto

    db_manager.init_db()  # segunda llamada, no debe fallar ni resetear config

    config = db_manager.get_all_config()
    assert config["REPORT_INTERVAL"] == "45"  # no se sobrescribió (usa INSERT OR IGNORE)
    assert config["TIMEOUT"] == "60"


# ---------------------------------------------------------------------
# 4. Ciclo de vida de mensajes bidireccionales
# ---------------------------------------------------------------------
def test_ciclo_mensajes_ack():
    # El cliente debe existir antes de poder enviarle un mensaje (FK constraint)
    db_manager.save_metric("nodo-1", {"name": "sda1"}, ahora())

    msg_id = db_manager.save_message("nodo-1", "cmd-test-1", "Ajustar intervalo a 45s", ahora())

    pendientes = db_manager.get_pending_messages("nodo-1")
    assert len(pendientes) == 1
    assert pendientes[0]["id"] == msg_id

    db_manager.mark_message_acknowledged(msg_id)

    pendientes = db_manager.get_pending_messages("nodo-1")
    assert len(pendientes) == 0


# ---------------------------------------------------------------------
# 5. KPIs del cluster
# ---------------------------------------------------------------------
def test_get_cluster_summary_calcula_bien():
    db_manager.save_metric("nodo-1", {"name": "sda1", "total_gb": 100, "used_gb": 40, "free_gb": 60}, ahora())
    db_manager.save_metric("nodo-2", {"name": "sda1", "total_gb": 200, "used_gb": 60, "free_gb": 140}, ahora())

    resumen = db_manager.get_cluster_summary()

    assert resumen["total_nodes"] == 2
    assert resumen["active_nodes"] == 2
    assert resumen["total_capacity"] == 300
    assert resumen["total_used"] == 100
    assert round(resumen["utilization_percent"], 2) == pytest.approx(33.33, rel=0.01)


def test_get_cluster_summary_sin_datos_no_divide_por_cero():
    resumen = db_manager.get_cluster_summary()
    assert resumen["total_nodes"] == 0
    assert resumen["utilization_percent"] == 0