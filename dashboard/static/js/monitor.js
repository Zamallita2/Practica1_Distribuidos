// --- 1. Inicialización de Gráficas Chart.js Globales ---
let iopsChartInstance = null;
let globalPieChartInstance = null;
let individualChartInstance = null;

function initCharts() {
    // Gráfica de Líneas de IOPS (Histórico BD)
    const ctxIops = document.getElementById('iopsChart').getContext('2d');
    iopsChartInstance = new Chart(ctxIops, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'IOPS Promedio Cluster',
                data: [],
                borderColor: '#38bdf8',
                backgroundColor: 'rgba(56, 189, 248, 0.1)',
                tension: 0.3,
                fill: true,
                pointRadius: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#94a3b8', font: { size: 9 } } },
                y: { ticks: { color: '#94a3b8' } }
            }
        }
    });

    // Gráfica Pie Global de Almacenamiento
    const ctxPie = document.getElementById('globalPieChart').getContext('2d');
    globalPieChartInstance = new Chart(ctxPie, {
        type: 'doughnut',
        data: {
            labels: ['Usado (GB)', 'Libre (GB)'],
            datasets: [{
                data: [0, 100],
                backgroundColor: ['#ef4444', '#22c55e'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', boxWidth: 12 } } }
        }
    });
}

// --- 2. Función Principal de Carga de Datos (Auto-Refresh) ---
async function fetchDashboardData() {
    try {
        const res = await fetch('/api/dashboard');
        const data = await res.json();

        // 1. Actualizar KPIs del Header
        document.getElementById('kpi-total').innerText = data.cluster.total_str;
        document.getElementById('kpi-used').innerText = data.cluster.used_str;
        document.getElementById('kpi-free').innerText = data.cluster.free_str;
        document.getElementById('kpi-pct').innerText = `${data.cluster.utilization_pct} %`;
        document.getElementById('kpi-nodes').innerText = `${data.cluster.active_nodes} / ${data.cluster.total_registered}`;

        // 2. Actualizar Pie Chart
        const usedNum = parseFloat(data.cluster.used_str) || 0;
        const freeNum = parseFloat(data.cluster.free_str) || 0;
        globalPieChartInstance.data.datasets[0].data = [usedNum, freeNum];
        globalPieChartInstance.update();

        // 3. Actualizar Gráfica de IOPS en el tiempo (desde BD)
        if (data.iops_history && data.iops_history.length > 0) {
            const labels = data.iops_history.map(item => {
                const d = new Date(item.timestamp);
                return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            });
            const values = data.iops_history.map(item => Math.round(item.iops));

            iopsChartInstance.data.labels = labels;
            iopsChartInstance.data.datasets[0].data = values;
            iopsChartInstance.update();
        }

        // 4. Renderizar tarjetas de servidores autorizados
        window.latestServersData = data.servers;
        renderServerCards(data.servers);

    } catch (err) {
        console.error("Error cargando dashboard:", err);
    }
}

// --- 3. Renderizado de Tarjetas de Servidores ---
function renderServerCards(servers) {
    const container = document.getElementById('servers-container');
    container.innerHTML = '';

    servers.forEach(srv => {
        const isActive = srv.status === 'Activo';
        const disks = srv.disks || [];

        let disksBarsHtml = '';
        if (!isActive || disks.length === 0) {
            disksBarsHtml = `
                <div class="disk-bar-container">
                    <div class="disk-bar-info">
                        <span>Sin señal / No reporta</span>
                        <span>0%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill fill-empty" style="width: 0%;"></div>
                    </div>
                </div>
            `;
        } else {
            disks.forEach(d => {
                let colorClass = 'fill-green';
                if (d.pct >= 85) colorClass = 'fill-red';
                else if (d.pct >= 55) colorClass = 'fill-orange';

                disksBarsHtml += `
                    <div class="disk-bar-container" style="margin-bottom: 8px;">
                        <div class="disk-bar-info">
                            <span><i class="fa-solid fa-hard-drive"></i> ${d.name} (${d.type})</span>
                            <span>${d.used} / ${d.total} (${d.pct}%)</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill ${colorClass}" style="width: ${d.pct}%;"></div>
                        </div>
                    </div>
                `;
            });
        }

        const card = `
            <div class="server-card ${!isActive ? 'inactive' : ''}" onclick="openNodeModal('${srv.id}')">
                <div class="card-header">
                    <span class="card-title"><i class="fa-solid fa-server"></i> ${srv.id}</span>
                    <span class="status-tag ${isActive ? 'tag-active' : 'tag-inactive'}">
                        ${isActive ? '🟢 Activo' : '🔴 No Reporta'}
                    </span>
                </div>
                
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 8px;">
                    Rendimiento: <strong>${srv.iops} IOPS</strong>
                </div>

                ${disksBarsHtml}
            </div>
        `;
        container.innerHTML += card;
    });
}

// --- 4. Modal Individual de Nodo ---
function openNodeModal(serverId) {
    const srv = (window.latestServersData || []).find(s => s.id === serverId);
    if (!srv) return;

    document.getElementById('node-modal-title').innerHTML = `<i class="fa-solid fa-server"></i> Análisis de Nodo: ${srv.id}`;
    
    const disks = srv.disks || [];
    let disksListText = disks.map(d => `<li><strong>${d.name} (${d.type}):</strong> ${d.used} ocupados de ${d.total} (${d.pct}%) - ${d.iops} IOPS</li>`).join('');

    document.getElementById('node-modal-info').innerHTML = `
        <h4 style="margin-bottom: 8px;">Estado del Nodo: <span style="color: ${srv.status === 'Activo' ? 'var(--accent-green)' : 'var(--accent-red)'}">${srv.status}</span></h4>
        <p style="margin-bottom: 6px;"><strong>Almacenamiento Consolidado:</strong> ${srv.used} / ${srv.total}</p>
        <p style="margin-bottom: 6px;"><strong>IOPS Medidos:</strong> ${srv.iops} IOPS</p>
        <p style="margin-bottom: 12px;"><strong>Respuesta ACK:</strong> ${srv.last_ack || 'Ninguna'}</p>
        
        <h4 style="margin-bottom: 6px;">Discos Físicos Conectados (${disks.length}):</h4>
        <ul style="font-size: 0.85rem; color: var(--text-secondary); padding-left: 18px;">
            ${disksListText || '<li>Sin información de discos</li>'}
        </ul>
        
        <div style="margin-top: 16px;">
            <button class="btn btn-sm btn-secondary" onclick="sendDirectCommand('${srv.id}', 'Reinicie servicio')">
                <i class="fa-solid fa-rotate-right"></i> Reiniciar Servicio
            </button>
        </div>
    `;

    document.getElementById('node-modal').style.display = 'flex';

    // Renderizar gráfico de barras por disco
    const ctx = document.getElementById('individualChart').getContext('2d');
    if (individualChartInstance) individualChartInstance.destroy();

    const labels = disks.map(d => `${d.name} (${d.type})`);
    const usedVals = disks.map(d => parseFloat(d.used) || 0);
    const freeVals = disks.map(d => parseFloat(d.free) || 0);

    individualChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.length > 0 ? labels : ['Total Nodo'],
            datasets: [
                { label: 'Usado (GB)', data: usedVals.length > 0 ? usedVals : [parseFloat(srv.used) || 0], backgroundColor: '#ef4444' },
                { label: 'Libre (GB)', data: freeVals.length > 0 ? freeVals : [parseFloat(srv.free) || 0], backgroundColor: '#22c55e' }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { stacked: true }, y: { stacked: true } }
        }
    });
}

function closeNodeModal() {
    document.getElementById('node-modal').style.display = 'none';
}

// --- 5. Modal y Operaciones CRUD ---
async function openCrudModal() {
    try {
        const res = await fetch('/api/nodes');
        const nodes = await res.json();
        
        const tbody = document.getElementById('crud-table-body');
        tbody.innerHTML = '';

        nodes.forEach(n => {
            tbody.innerHTML += `
                <tr>
                    <td><strong>${n.client_id}</strong></td>
                    <td>${n.status === 'Activo' ? '🟢 Activo' : '🔴 No Reporta'}</td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="deleteNodeCrud('${n.client_id}')">
                            <i class="fa-solid fa-trash"></i> Eliminar
                        </button>
                    </td>
                </tr>
            `;
        });

        document.getElementById('crud-modal').style.display = 'flex';
    } catch (e) {
        alert("Error al abrir CRUD: " + e);
    }
}

function closeCrudModal() {
    document.getElementById('crud-modal').style.display = 'none';
}

async function handleAddNode(event) {
    event.preventDefault();
    const input = document.getElementById('new-node-id');
    const val = input.value.strip ? input.value.strip() : input.value.trim();
    if (!val) return;

    try {
        const res = await fetch('/api/nodes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: val })
        });
        const data = await res.json();
        if (data.success) {
            input.value = '';
            openCrudModal();
            fetchDashboardData();
        } else {
            alert(data.message);
        }
    } catch (e) {
        alert("Error agregando nodo: " + e);
    }
}

async function deleteNodeCrud(clientId) {
    if (!confirm(`¿Estás seguro de eliminar al servidor '${clientId}' del CRUD? Nodos no autorizados serán rechazados por el servidor.`)) return;

    try {
        const res = await fetch('/api/nodes', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: clientId })
        });
        const data = await res.json();
        if (data.success) {
            openCrudModal();
            fetchDashboardData();
        } else {
            alert(data.message);
        }
    } catch (e) {
        alert("Error eliminando nodo: " + e);
    }
}

// --- 6. Enviar Comandos Directos ---
async function sendDirectCommand(clientId, action) {
    try {
        const res = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: clientId, action: action })
        });
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("Error enviando comando: " + e);
    }
}

async function sendBroadcastCommand(action) {
    try {
        const res = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action })
        });
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("Error enviando comando masivo: " + e);
    }
}

// Inicializar
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    fetchDashboardData();
    setInterval(fetchDashboardData, 3000);
});