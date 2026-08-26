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
            const isInactive = srv.status === 'No reporta';
            
            // Lógica semántica de colores para la barra
            let barColorClass = 'fill-empty';
            if (!isInactive) {
                if (srv.pct < 50) barColorClass = 'fill-green';
                else if (srv.pct < 80) barColorClass = 'fill-orange';
                else barColorClass = 'fill-red';
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
                    
                    ${isInactive 
                        ? `<div class="status-text">No reporta</div>` 
                        : `<div class="metrics-text">
                              ${srv.total}<br>
                              ${srv.used}<br>
                              ${srv.free}
                           </div>`
                    }

                    <div class="progress-bar">
                        <div class="progress-fill ${barColorClass}" style="width: ${isInactive ? 0 : srv.pct}%;"></div>
                    </div>
                </div>
            `;
            container.innerHTML += card;
        });
    } catch (err) {
        console.error("Error obteniendo métricas del cluster:", err);
    }
}

// 6. Configuración del Auto-Refresh
// Esto permite consultar al servidor cada 3 segundos (3000 ms)
const refreshRate = 3000;
setInterval(fetchDashboardData, refreshRate);

// Ejecutar la primera carga inmediatamente al abrir
fetchDashboardData();