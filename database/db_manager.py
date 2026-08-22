import sqlite3
import os
import threading
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cluster_monitoring.db")

# Lock global: SQLite serializa escrituras de todas formas; esto evita
# "database is locked" bajo alta concurrencia con 9 clientes reportando
# simultáneamente, y hace explícita la sección crítica.
_write_lock = threading.Lock()


def get_connection():
    """Obtiene una conexión SQLite con soporte para dict de filas."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL permite lecturas concurrentes mientras hay una escritura en curso
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _tx():
    """Context manager que abre conexión, hace commit/rollback y cierra siempre."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    with _tx() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            client_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'Activo',
            first_connected TEXT,
            last_seen TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            disk_name TEXT,
            disk_type TEXT,
            total_gb REAL,
            used_gb REAL,
            free_gb REAL,
            iops INTEGER,
            timestamp TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(client_id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            acknowledged INTEGER DEFAULT 0,
            FOREIGN KEY (client_id) REFERENCES clients(client_id)
        )
        """)

        # Índices para las consultas más frecuentes del dashboard
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_client_ts ON metrics(client_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_client_ack ON messages(client_id, acknowledged)")

        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('REPORT_INTERVAL', '30')")
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('TIMEOUT', '60')")

    print(f"[DATABASE] Base de datos inicializada en: {os.path.abspath(DB_PATH)}")


def save_metric(client_id, disk_data, timestamp):
    """Guarda una métrica recibida y actualiza o registra al cliente (operación atómica)."""
    with _write_lock, _tx() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO clients (client_id, status, first_connected, last_seen)
        VALUES (?, 'Activo', ?, ?)
        ON CONFLICT(client_id) DO UPDATE SET
            status = 'Activo',
            last_seen = excluded.last_seen
        """, (client_id, timestamp, timestamp))

        cursor.execute("""
        INSERT INTO metrics (client_id, disk_name, disk_type, total_gb, used_gb, free_gb, iops, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            disk_data.get("name"),
            disk_data.get("type"),
            disk_data.get("total_gb"),
            disk_data.get("used_gb"),
            disk_data.get("free_gb"),
            disk_data.get("iops"),
            timestamp
        ))


def update_client_status(client_id, status):
    """Actualiza el estado de un nodo (ej. 'Activo' o 'No Reporta')."""
    with _write_lock, _tx() as conn:
        conn.execute("UPDATE clients SET status = ? WHERE client_id = ?", (status, client_id))


def get_latest_metrics_all_clients():
    """Retorna la última métrica reportada por cada cliente."""
    with _tx() as conn:
        cursor = conn.execute("""
        SELECT c.client_id, c.status, c.last_seen, m.disk_name, m.disk_type, m.total_gb, m.used_gb, m.free_gb, m.iops, m.timestamp
        FROM clients c
        LEFT JOIN metrics m ON m.id = (
            SELECT MAX(id) FROM metrics WHERE client_id = c.client_id
        )
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_config(key):
    """Obtiene un valor de configuración desde la tabla config."""
    with _tx() as conn:
        row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        return dict(row)["value"] if row else None


def get_all_config():
    """Obtiene toda la configuración como diccionario {key: value}."""
    with _tx() as conn:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        return {row["key"]: row["value"] for row in rows}


def set_config(key, value):
    """Guarda o actualiza un valor de configuración."""
    with _write_lock, _tx() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )


def save_message(client_id, message, sent_at):
    """Guarda un mensaje enviado a un cliente."""
    with _write_lock, _tx() as conn:
        cursor = conn.execute(
            "INSERT INTO messages (client_id, message, sent_at, acknowledged) VALUES (?, ?, ?, 0)",
            (client_id, message, sent_at)
        )
        return cursor.lastrowid


def mark_message_acknowledged(message_id):
    """Marca un mensaje como confirmado por el cliente."""
    with _write_lock, _tx() as conn:
        conn.execute("UPDATE messages SET acknowledged = 1 WHERE id = ?", (message_id,))


def get_pending_messages(client_id):
    """Obtiene mensajes no confirmados para un cliente."""
    with _tx() as conn:
        rows = conn.execute(
            "SELECT id, message, sent_at FROM messages WHERE client_id = ? AND acknowledged = 0",
            (client_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_all_pending_messages():
    """Obtiene todos los mensajes no confirmados."""
    with _tx() as conn:
        rows = conn.execute("""
            SELECT id, client_id, message, sent_at
            FROM messages
            WHERE acknowledged = 0
            ORDER BY sent_at ASC
        """).fetchall()
        return [dict(row) for row in rows]


def get_cluster_summary():
    """Calcula KPIs globales del cluster."""
    with _tx() as conn:
        row = conn.execute("""
            SELECT
                COUNT(DISTINCT c.client_id) as total_nodes,
                SUM(CASE WHEN c.status = 'Activo' THEN 1 ELSE 0 END) as active_nodes,
                SUM(m.total_gb) as total_capacity,
                SUM(m.used_gb) as total_used,
                SUM(m.free_gb) as total_free
            FROM clients c
            LEFT JOIN metrics m ON m.id = (
                SELECT MAX(id) FROM metrics WHERE client_id = c.client_id
            )
        """).fetchone()

    if row:
        result = dict(row)
        total = result.get("total_capacity") or 0
        used = result.get("total_used") or 0
        result["utilization_percent"] = (used / total * 100) if total > 0 else 0
        result["total_nodes"] = result.get("total_nodes") or 0
        result["active_nodes"] = result.get("active_nodes") or 0
        return result
    return {
        "total_nodes": 0,
        "active_nodes": 0,
        "total_capacity": 0,
        "total_used": 0,
        "total_free": 0,
        "utilization_percent": 0
    }


def check_inactive_clients(timeout_seconds=60):
    """Marca como 'No Reporta' a clientes inactivos y retorna sus IDs (útil para logging/alertas)."""
    with _write_lock, _tx() as conn:
        cursor = conn.execute("""
            SELECT client_id FROM clients
            WHERE last_seen IS NOT NULL
            AND (julianday('now') - julianday(last_seen)) * 86400 > ?
            AND status = 'Activo'
        """, (timeout_seconds,))
        affected_ids = [row["client_id"] for row in cursor.fetchall()]

        if affected_ids:
            conn.execute(f"""
                UPDATE clients SET status = 'No Reporta'
                WHERE client_id IN ({",".join("?" * len(affected_ids))})
            """, affected_ids)

        return affected_ids


def get_client_history(client_id, limit=10):
    """Obtiene el historial de métricas de un cliente específico."""
    with _tx() as conn:
        rows = conn.execute("""
            SELECT disk_name, disk_type, total_gb, used_gb, free_gb, iops, timestamp
            FROM metrics
            WHERE client_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (client_id, limit)).fetchall()
        return [dict(row) for row in rows]


def get_client_details(client_id):
    """Obtiene la ficha completa de un nodo: estado + última métrica + mensajes pendientes."""
    with _tx() as conn:
        client_row = conn.execute(
            "SELECT * FROM clients WHERE client_id = ?", (client_id,)
        ).fetchone()
        if not client_row:
            return None
        client = dict(client_row)

        last_metric = conn.execute("""
            SELECT disk_name, disk_type, total_gb, used_gb, free_gb, iops, timestamp
            FROM metrics WHERE client_id = ? ORDER BY id DESC LIMIT 1
        """, (client_id,)).fetchone()
        client["last_metric"] = dict(last_metric) if last_metric else None

        pending = conn.execute(
            "SELECT id, message, sent_at FROM messages WHERE client_id = ? AND acknowledged = 0",
            (client_id,)
        ).fetchall()
        client["pending_messages"] = [dict(r) for r in pending]

        return client


def delete_old_metrics(days=30):
    """Elimina métricas más antiguas que 'days' días."""
    with _write_lock, _tx() as conn:
        cursor = conn.execute("""
            DELETE FROM metrics
            WHERE julianday('now') - julianday(timestamp) > ?
        """, (days,))
        return cursor.rowcount


if __name__ == "__main__":
    init_db()
    print("[DATABASE] Inicialización completada.")