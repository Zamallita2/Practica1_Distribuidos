// 1. Inicialización del gráfico circular (Pie Chart) global
const ctx = document.getElementById('globalChart').getContext('2d');
let globalPieChart = new Chart(ctx, {
    type: 'pie',
    data: {
        datasets: [{
            data: [0, 100], // Se inicializa en 0 usado, 100 libre
            backgroundColor: ['#00ff00', '#d1d5db'],
            borderWidth: 1,
            borderColor: '#6b7280'
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { tooltip: { enabled: false }, legend: { display: false } }
    }
});

// 2. Función principal para obtener y renderizar datos
async function fetchDashboardData() {
    try {
        // NOTA PARA EL EQUIPO: Descomentar esto cuando la API esté lista
        const res = await fetch('/api/dashboard');
        const data = await res.json();

        // 3. Actualizar la información del Header
        document.getElementById('hdr-total').innerText = data.cluster.total_str;
        document.getElementById('hdr-used').innerText = data.cluster.used_str;
        document.getElementById('hdr-free').innerText = data.cluster.free_str;
        document.getElementById('hdr-reporting').innerText = `${data.cluster.active_nodes} de 9`;
        document.getElementById('hdr-pct').innerText = `${data.cluster.utilization_pct} %`;

        // 4. Actualizar el Gráfico
        globalPieChart.data.datasets[0].data = [data.cluster.utilization_pct, 100 - data.cluster.utilization_pct];
        globalPieChart.update();

        // 5. Renderizado de las 9 tarjetas del clúster
        const container = document.getElementById('servers-container');
        container.innerHTML = ''; // Limpiar grid anterior

        data.servers.forEach(srv => {
            const isInactive = srv.status.toLowerCase().includes('no reporta');
            
            // Generar bloque de métricas y barras de progreso por cada disco
            let disksHtml = '';
            
            if (isInactive) {
                disksHtml = `<div class="status-text">No reporta</div>
                             <div class="progress-bar">
                                 <div class="progress-fill fill-empty" style="width: 0%;"></div>
                             </div>`;
            } else {
                const diskList = srv.disks || [];
                diskList.forEach(d => {
                    let barColorClass = 'fill-green';
                    if (d.pct >= 80) barColorClass = 'fill-red';
                    else if (d.pct >= 50) barColorClass = 'fill-orange';

                    disksHtml += `
                        <div class="disk-item" style="margin-bottom: 8px; width: 100%;">
                            <div class="metrics-text" style="margin-bottom: 4px; font-size: 0.75rem;">
                                <strong>${d.name} (${d.type})</strong>: ${d.used} / ${d.total} (${d.pct}%)
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill ${barColorClass}" style="width: ${d.pct}%;"></div>
                            </div>
                        </div>
                    `;
                });
            }

            // Construcción del HTML de la tarjeta
            const card = `
                <div class="server-card ${isInactive ? 'inactive' : ''}">
                    <!-- SVG Icono Disco Duro -->
                    <svg class="disk-icon" viewBox="0 0 24 24">
                        <path d="M4 7C4 5.89543 5.34315 5 7 5H17C18.6569 5 20 5.89543 20 7V17C20 18.1046 18.6569 19 17 19H7C5.34315 19 4 18.1046 4 17V7Z" stroke-width="2"/>
                        <path d="M4 11H20" stroke-width="2"/>
                        <circle cx="8" cy="15" r="1" fill="currentColor" stroke="none"/>
                        <circle cx="12" cy="15" r="1" fill="currentColor" stroke="none"/>
                    </svg>
                    
                    <div class="server-title">${srv.id}</div>
                    <div style="font-size: 0.75rem; color: #6b7280; margin-bottom: 8px;">
                        Total Nodo: ${srv.used} / ${srv.total} (${srv.iops} IOPS)
                    </div>
                    
                    ${disksHtml}
                </div>
            `;

            container.innerHTML += card;
        });

    } catch (err) {
        console.error("Error obteniendo métricas del cluster:", err);
    }
}
function updateGlobalPieChart(usedPct) {
    if (window.globalPieChart) {
        window.globalPieChart.data.datasets[0].data = [usedPct, 100 - usedPct];
        window.globalPieChart.update();
    }
}

// Añadido: Inyección de analíticas y renderizado del dashboard individual
let individualChartInstance = null;

function openServerDashboard(serverData) {
    document.getElementById('server-modal').style.display = 'flex';
    
    // Desplegar datos analíticos precisos del servidor
    document.getElementById('modal-metrics').innerHTML = `
        <h2 style="color: #38bdf8; margin-bottom: 12px;">Servidor: ${serverData.client_id || serverData.id}</h2>
        <p style="margin-bottom: 8px;"><strong>Capacidad Total:</strong> ${serverData.total_gb || 0} GB</p>
        <p style="margin-bottom: 8px;"><strong>Espacio Libre:</strong> ${serverData.free_gb || 0} GB</p>
        <p style="margin-bottom: 8px;"><strong>IOPS Registrados:</strong> ${serverData.iops || 'N/A'}</p>
        <p style="margin-bottom: 8px;"><strong>Tipo de Disco:</strong> ${serverData.disk_type || 'Desconocido'}</p>
    `;

    // Renderizar gráfico de uso individual
    const ctx = document.getElementById('individualChart').getContext('2d');
    if (individualChartInstance) individualChartInstance.destroy();
    
    individualChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Ocupado (GB)', 'Libre (GB)'],
            datasets: [{
                label: 'Distribución de Almacenamiento',
                data: [serverData.used_gb || 0, serverData.free_gb || 0],
                backgroundColor: ['#ef4444', '#22c55e']
            }]
        }
    });
}

// 6. Configuración del Auto-Refresh
// Esto permite consultar al servidor cada 3 segundos (3000 ms)
setInterval(fetchDashboardData, CONFIG_REFRESH_RATE);

// Ejecutar la primera carga inmediatamente al abrir
fetchDashboardData();