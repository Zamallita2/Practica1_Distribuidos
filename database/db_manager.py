import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cluster_monitoring.db")

def get_connection():
    """Obtiene una conexión SQLite con soporte para dict de filas."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de Nodos / Clientes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        client_id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'Activo',
        first_connected TEXT,
        last_seen TEXT
    )
    """)

    # Tabla de Métricas de Disco (Historial)
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

    # Tabla de Configuración (Parametrización)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()
    conn.close()
    print(f"[DATABASE] Base de datos inicializada en: {os.path.abspath(DB_PATH)}")

def save_metric(client_id, disk_data, timestamp):
    """Guarda una métrica recibida y actualiza o registra al cliente."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Adición/actualización automática de cliente
    cursor.execute("""
    INSERT INTO clients (client_id, status, first_connected, last_seen)
    VALUES (?, 'Activo', ?, ?)
    ON CONFLICT(client_id) DO UPDATE SET
        status = 'Activo',
        last_seen = excluded.last_seen
    """, (client_id, timestamp, timestamp))
    
    # Insertar historial de métrica
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

    conn.commit()
    conn.close()

def update_client_status(client_id, status):
    """Actualiza el estado de un nodo (ej. 'Activo' o 'No Reporta')."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE clients SET status = ? WHERE client_id = ?", (status, client_id))
    conn.commit()
    conn.close()

def get_latest_metrics_all_clients():
    """Retorna la última métrica reportada por cada cliente."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.client_id, c.status, c.last_seen, m.disk_name, m.disk_type, m.total_gb, m.used_gb, m.free_gb, m.iops, m.timestamp
    FROM clients c
    LEFT JOIN metrics m ON m.id = (
        SELECT MAX(id) FROM metrics WHERE client_id = c.client_id
    )
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
