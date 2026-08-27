import sqlite3
import os
import threading
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cluster_monitoring.db")

_write_lock = threading.Lock()


def get_connection():
    """Obtiene una conexión SQLite con soporte para dict de filas."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
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
            all_disks_json TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(client_id)
        )
        """)

        # Migración suave para BDs existentes
        try:
            cursor.execute("ALTER TABLE metrics ADD COLUMN all_disks_json TEXT;")
        except Exception:
            pass


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
            command_id TEXT,
            message TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            acknowledged INTEGER DEFAULT 0,
            FOREIGN KEY (client_id) REFERENCES clients(client_id)
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_client_ts ON metrics(client_id, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_client_ack ON messages(client_id, acknowledged)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_command_id ON messages(command_id)")

        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('REPORT_INTERVAL', '30')")
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('TIMEOUT', '60')")

        # Sembrado obligatorio de los 9 nodos del cluster de la CNS si la tabla está vacía
        cursor.execute("SELECT COUNT(*) as count FROM clients;")
        cnt = cursor.fetchone()["count"]
        if cnt == 0:
            regionales = [
                'REGIONAL_LA_PAZ',
                'REGIONAL_SANTA_CRUZ',
                'REGIONAL_COCHABAMBA',
                'REGIONAL_ORURO',
                'REGIONAL_POTOSI',
                'REGIONAL_CHUQUISACA',
                'REGIONAL_TARIJA',
                'REGIONAL_BENI',
                'REGIONAL_PANDO'
            ]
            for reg in regionales:
                cursor.execute(
                    "INSERT INTO clients (client_id, status, first_connected, last_seen) VALUES (?, 'No Reporta', datetime('now'), datetime('now'))",
                    (reg,)
                )

    print(f"[DATABASE] Base de datos inicializada en: {os.path.abspath(DB_PATH)}")


def is_client_authorized(client_id):
    """Verifica si un cliente está registrado en el CRUD (tabla clients)."""
    with _tx() as conn:
        row = conn.execute("SELECT client_id FROM clients WHERE client_id = ?", (client_id,)).fetchone()
        return row is not None


def add_client_crud(client_id):
    """Añade un nuevo cliente autorizado desde el CRUD del Dashboard."""
    with _write_lock, _tx() as conn:
        conn.execute("""
            INSERT INTO clients (client_id, status, first_connected, last_seen)
            VALUES (?, 'No Reporta', datetime('now'), datetime('now'))
            ON CONFLICT(client_id) DO NOTHING
        """, (client_id,))


def delete_client_crud(client_id):
    """Elimina un cliente autorizado desde el CRUD del Dashboard."""
    with _write_lock, _tx() as conn:
        conn.execute("DELETE FROM metrics WHERE client_id = ?", (client_id,))
        conn.execute("DELETE FROM messages WHERE client_id = ?", (client_id,))
        conn.execute("DELETE FROM clients WHERE client_id = ?", (client_id,))


def get_all_registered_clients():
    """Retorna la lista de todos los clientes autorizados en el CRUD."""
    with _tx() as conn:
        rows = conn.execute("SELECT client_id, status, first_connected, last_seen FROM clients ORDER BY client_id").fetchall()
        return [dict(r) for r in rows]


def save_metric(client_id, disk_data, timestamp):
    """Guarda métrica SOLO si el cliente está registrado previamente en el CRUD (Operación Autorizada)."""
    if not is_client_authorized(client_id):
        print(f"🛑 [DATABASE] Métrica RECHAZADA. Cliente '{client_id}' no está registrado en el CRUD.")
        return False

    import json
    all_disks_json = json.dumps(disk_data.get("all_disks", []))

    with _write_lock, _tx() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE clients SET status = 'Activo', last_seen = ? WHERE client_id = ?
        """, (timestamp, client_id))

        cursor.execute("""
        INSERT INTO metrics (client_id, disk_name, disk_type, total_gb, used_gb, free_gb, iops, timestamp, all_disks_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            disk_data.get("name"),
            disk_data.get("type"),
            disk_data.get("total_gb"),
            disk_data.get("used_gb"),
            disk_data.get("free_gb"),
            disk_data.get("iops"),
            timestamp,
            all_disks_json
        ))
    return True


def update_client_status(client_id, status):
    """Actualiza el estado de un nodo (ej. 'Activo' o 'No Reporta')."""
    with _write_lock, _tx() as conn:
        conn.execute("UPDATE clients SET status = ? WHERE client_id = ?", (status, client_id))


def get_latest_metrics_all_clients():
    """Retorna la última métrica reportada por cada cliente registrado."""
    import json
    with _tx() as conn:
        cursor = conn.execute("""
        SELECT c.client_id, c.status, c.last_seen, m.disk_name, m.disk_type, m.total_gb, m.used_gb, m.free_gb, m.iops, m.timestamp, m.all_disks_json
        FROM clients c
        LEFT JOIN metrics m ON m.id = (
            SELECT MAX(id) FROM metrics WHERE client_id = c.client_id
        )
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        for r in rows:
            raw = r.get("all_disks_json")
            if raw:
                try:
                    r["all_disks"] = json.loads(raw)
                except Exception:
                    r["all_disks"] = []
            else:
                r["all_disks"] = []
        return rows



def get_iops_history(client_id=None, limit=20):
    """
    Obtiene el historial de IOPS guardado en la BD para la gráfica de tiempo.
    Si client_id es None, retorna el promedio o serie de los clientes activos.
    """
    with _tx() as conn:
        if client_id:
            rows = conn.execute("""
                SELECT timestamp, iops, used_gb, free_gb
                FROM metrics
                WHERE client_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (client_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT timestamp, AVG(iops) as iops, SUM(used_gb) as used_gb, SUM(free_gb) as free_gb
                FROM metrics
                GROUP BY timestamp
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
        result = [dict(r) for r in rows]
        result.reverse()  # Orden cronológico ascendente para gráficos de línea
        return result


def get_config(key):
    """Obtiene un valor de configuración desde la tabla config."""
    with _tx() as conn:
        row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        return dict(row)["value"] if row else None


def set_config(key, value):
    """Guarda o actualiza un valor de configuración."""
    with _write_lock, _tx() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )


def save_message(client_id, command_id, message, sent_at):
    """Guarda un mensaje enviado a un cliente."""
    with _write_lock, _tx() as conn:
        cursor = conn.execute(
            "INSERT INTO messages (client_id, command_id, message, sent_at, acknowledged) VALUES (?, ?, ?, ?, 0)",
            (client_id, command_id, message, sent_at)
        )
        return cursor.lastrowid


def mark_message_acknowledged(message_id):
    """Marca un mensaje como confirmado por el cliente."""
    with _write_lock, _tx() as conn:
        conn.execute("UPDATE messages SET acknowledged = 1 WHERE id = ?", (message_id,))


def get_message_id_by_command_id(command_id):
    """Obtiene id del mensaje por command_id."""
    with _tx() as conn:
        row = conn.execute("SELECT id FROM messages WHERE command_id = ?", (command_id,)).fetchone()
        return row["id"] if row else None


def check_inactive_clients(timeout_seconds=60):
    """Marca como 'No Reporta' a clientes inactivos."""
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


if __name__ == "__main__":
    init_db()
    print("[DATABASE] Inicialización completada con soporte CRUD.")