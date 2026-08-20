import os
import sys
from flask import Flask, render_template, jsonify, request

# Importar BD y servidor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.db_manager import get_latest_metrics_all_clients
from server.cluster_metrics import calculate_cluster_metrics

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/dashboard')
def get_dashboard_data():
    """Endpoint API para auto-refresh del dashboard."""
    servers = get_latest_metrics_all_clients()
    cluster = calculate_cluster_metrics()
    return jsonify({
        "servers": servers,
        "cluster": cluster
    })

if __name__ == "__main__":
    print("[DASHBOARD] Iniciando servidor Web en http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
