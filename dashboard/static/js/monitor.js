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

        // 3. Actualizar Gráfica de IOPS en el tiempo (promediado por minuto desde BD)
        if (data.iops_history && data.iops_history.length > 0) {
            const labels = data.iops_history.map(item => {
                if (!item.timestamp) return 'Min';
                const parts = item.timestamp.split(' ');
                return parts.length > 1 ? parts[1].substring(0, 5) : item.timestamp;
            });
            const values = data.iops_history.map(item => Math.round(item.iops));

            iopsChartInstance.data.labels = labels;
            iopsChartInstance.data.datasets[0].data = values;
            iopsChartInstance.update();
        }

        // 4. Renderizar tarjetas de servidores autorizados
        window.latestServersData = data.servers;
        renderServerCards(data.servers);

        // 5. Si hay un modal individual abierto, refrescarlo activamente en tiempo real
        if (window.activeModalServerId) {
            updateNodeModalContent(window.activeModalServerId);
        }

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

// Variables globales de las dos gráficas separadas del modal
let nodeStorageChartInstance = null;
let nodeIopsChartInstance = null;

// Palette de colores vibrantes para la barra apilada por disco
const DISK_COLORS = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'];

// --- 4. Modal Individual de Nodo (Evolución Temporal de Capacidad e IOPS en Tiempo Real) ---
async function openNodeModal(serverId) {
    window.activeModalServerId = serverId;
    document.getElementById('node-modal').style.display = 'flex';
    await updateNodeModalContent(serverId);
}

async function updateNodeModalContent(serverId) {
    const srv = (window.latestServersData || []).find(s => s.id === serverId);
    if (!srv) return;

    document.getElementById('node-modal-title').innerHTML = `<i class="fa-solid fa-server"></i> Análisis de Nodo: ${srv.id}`;
    
    const disks = srv.disks || [];

    // 1. Rendimiento textual del nodo
    document.getElementById('node-modal-info').innerHTML = `
        <h4 style="margin-bottom: 8px;">Estado del Nodo: <span style="color: ${srv.status === 'Activo' ? 'var(--accent-green)' : 'var(--accent-red)'}">${srv.status}</span></h4>
        <p style="margin-bottom: 6px;"><strong>Capacidad Consolidada:</strong> ${srv.used} / ${srv.total}</p>
        <p style="margin-bottom: 6px;"><strong>Rendimiento Actual:</strong> ${srv.iops} IOPS</p>
        <p style="margin-bottom: 12px;"><strong>Confirmación ACK:</strong> ${srv.last_ack || 'Ninguna'}</p>
        
        <h4 style="margin-bottom: 6px;">Unidades de Almacenamiento (${disks.length}):</h4>
        <ul style="font-size: 0.85rem; color: var(--text-secondary); padding-left: 18px;">
            ${disks.map(d => `<li><strong>${d.name} (${d.type}):</strong> ${d.used} / ${d.total} (${d.pct}%) - ${d.iops} IOPS</li>`).join('') || '<li>Sin información de discos</li>'}
        </ul>
        
        <div style="margin-top: 14px;">
            <button class="btn btn-sm btn-secondary" onclick="sendDirectCommand('${srv.id}', 'Reinicie servicio')">
                <i class="fa-solid fa-rotate-right"></i> Reiniciar Servicio
            </button>
        </div>
    `;

    // 2. Construir la Barra Apilada por Colores (Discos ordenados de mayor a menor uso)
    const sortedDisks = [...disks].sort((a, b) => {
        const uA = parseFloat(a.used) || 0;
        const uB = parseFloat(b.used) || 0;
        return uB - uA; // Orden descendente por espacio usado
    });

    const totalClusterGB = parseFloat(srv.total) || 1.0;
    const stackedContainer = document.getElementById('stacked-disk-container');

    let segmentsHtml = '';
    let legendHtml = '';

    sortedDisks.forEach((d, idx) => {
        const usedVal = parseFloat(d.used) || 0;
        const widthPct = Math.min(100, Math.max(2, (usedVal / totalClusterGB) * 100));
        const color = DISK_COLORS[idx % DISK_COLORS.length];

        segmentsHtml += `
            <div style="width: ${widthPct}%; background-color: ${color}; height: 100%; transition: width 0.3s;" 
                 title="${d.name} (${d.type}): ${d.used} ocupados"></div>
        `;

        legendHtml += `
            <div style="display: flex; align-items: center; gap: 6px; font-size: 0.78rem; color: #cbd5e1;">
                <span style="width: 10px; height: 10px; background-color: ${color}; border-radius: 2px; display: inline-block;"></span>
                <span><strong>${d.name}</strong> (${d.type}): ${d.used}</span>
            </div>
        `;
    });

    stackedContainer.innerHTML = `
        <div style="background: #1e293b; border-radius: 6px; height: 22px; display: flex; overflow: hidden; width: 100%; border: 1px solid var(--border-color);">
            ${segmentsHtml || '<div style="width: 100%; background: #334155;"></div>'}
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px;">
            ${legendHtml || '<span style="font-size:0.75rem; color:#64748b;">No hay discos activos</span>'}
        </div>
    `;

    // 3. Obtener historial del cliente desde la API /api/history/<client_id>
    try {
        const res = await fetch(`/api/history/${serverId}`);
        const historyData = await res.json();

        let labels = [];
        let usedSeries = [];
        let iopsSeries = [];

        if (historyData && historyData.length > 0) {
            labels = historyData.map(h => {
                if (!h.timestamp) return 'Min';
                const parts = h.timestamp.split(' ');
                return parts.length > 1 ? parts[1].substring(0, 5) : h.timestamp;
            });
            usedSeries = historyData.map(h => h.used_gb);
            iopsSeries = historyData.map(h => h.iops);
        } else {
            labels = ['Actual'];
            usedSeries = [parseFloat(srv.used) || 0];
            iopsSeries = [srv.iops || 0];
        }

        // Gráfica 1: Tendencia de Almacenamiento (GB)
        const ctxStorage = document.getElementById('nodeStorageChart').getContext('2d');
        if (nodeStorageChartInstance) nodeStorageChartInstance.destroy();

        nodeStorageChartInstance = new Chart(ctxStorage, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Capacidad Usada Total (GB)',
                    data: usedSeries,
                    borderColor: '#f97316',
                    backgroundColor: 'rgba(249, 115, 22, 0.15)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#94a3b8', font: { size: 9 } } },
                    y: { ticks: { color: '#f97316', font: { size: 9 } } }
                }
            }
        });

        // Gráfica 2: Rendimiento Media IOPS (por minuto)
        const ctxIops = document.getElementById('nodeIopsChart').getContext('2d');
        if (nodeIopsChartInstance) nodeIopsChartInstance.destroy();

        nodeIopsChartInstance = new Chart(ctxIops, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Media IOPS (por minuto)',
                    data: iopsSeries,
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.15)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#94a3b8', font: { size: 9 } } },
                    y: { ticks: { color: '#38bdf8', font: { size: 9 } } }
                }
            }
        });

    } catch (err) {
        console.error("Error cargando historial de cliente:", err);
    }
}

function closeNodeModal() {
    window.activeModalServerId = null;
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

// --- 7. Modal y Gestión de Parámetros Globales ---
async function openConfigModal() {
    try {
        const res = await fetch('/api/config');
        const cfg = await res.json();

        document.getElementById('cfg-report-interval').value = cfg.report_interval || 5;
        document.getElementById('cfg-timeout').value = cfg.timeout_seconds || 60;
        document.getElementById('config-modal').style.display = 'flex';
    } catch (e) {
        alert("Error cargando configuración: " + e);
    }
}

function closeConfigModal() {
    document.getElementById('config-modal').style.display = 'none';
}

async function handleSaveConfig(event) {
    event.preventDefault();
    const intervalVal = parseInt(document.getElementById('cfg-report-interval').value);
    const timeoutVal = parseInt(document.getElementById('cfg-timeout').value);

    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                report_interval: intervalVal,
                timeout_seconds: timeoutVal
            })
        });
        const data = await res.json();
        alert(data.message);
        closeConfigModal();
        fetchDashboardData();
    } catch (e) {
        alert("Error guardando configuración: " + e);
    }
}

// Inicializar
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    fetchDashboardData();
    setInterval(fetchDashboardData, 3000);
});