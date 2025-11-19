// ========================================
// SIMUA Dashboard - Modern JavaScript
// ========================================

// Variáveis globais
let map;
let mapOcorrencias = [];
let mapMarkers = [];
let charts = {
    type: null,
    priority: null,
    evolution: null
};
let socket;
let currentFilters = {
    periodo: 30,
    tipo: '',
    prioridade: '',
    status: '',
    regiao: ''
};

// ========================================
// REGIÕES (BAIRROS)
// ========================================

async function carregarRegioes() {
    try {
        const select = document.getElementById('filterRegiao');
        if (!select) return;

        const response = await fetch('/api/dashboard/regioes');
        const data = await response.json();

        if (data.status === 'success' && data.regioes.length > 0) {
            data.regioes.forEach(nome => {
                const opt = document.createElement('option');
                opt.value = nome;
                opt.textContent = nome;
                select.appendChild(opt);
            });
            console.log(`✅ ${data.total} regiões carregadas`);
        } else {
            console.warn('Nenhuma região encontrada ou erro no servidor.');
        }
    } catch (error) {
        console.error('Erro ao carregar regiões:', error);
    }
}


// ========================================
// INICIALIZAÇÃO
// ========================================

document.addEventListener('DOMContentLoaded', function() {
 
    console.log('Dashboard inicializado');

    carregarRegioes();
    initMap();
    initCharts();
    initWebSocket();
    carregarDados();
    carregarBadges();
    conectarEventosFiltros();
    
    // Atualizar dados a cada 5 minutos
    setInterval(carregarDados, 300000);
});

// ========================================
// MAPA
// ========================================

function initMap() {
    // Inicializar mapa centrado em Goiânia
    map = L.map('map').setView([-16.6869, -49.2648], 12);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
}

function atualizarMapa(respostaMapa) {
    if (!respostaMapa) {
        mapOcorrencias = [];
        return;
    }

    // Novo formato da API: { status, total, ocorrencias }
    const lista = Array.isArray(respostaMapa)
        ? respostaMapa
        : Array.isArray(respostaMapa.ocorrencias)
            ? respostaMapa.ocorrencias
            : [];

    mapOcorrencias = lista;
    renderizarMarcadores();
}

function renderizarMarcadores() {
    // Remover marcadores existentes
    mapMarkers.forEach(marker => map.removeLayer(marker));
    mapMarkers = [];

    if (!map || mapOcorrencias.length === 0) return;

    const ocorrenciasAjustadas = ajustarPosicoesDuplicadas(mapOcorrencias);

    ocorrenciasAjustadas.forEach(oc => {
        const color = getPrioridadeColor(oc.urgencia);

        const icon = L.divIcon({
            html: `<div style="width: 30px; height: 30px; background: ${color}; border: 3px solid white; border-radius: 50%; box-shadow: 0 2px 8px rgba(0,0,0,0.3);"></div>`,
            iconSize: [30, 30],
            className: 'custom-marker'
        });

        const marker = L.marker([oc.latitude, oc.longitude], { icon })
            .bindPopup(`
                <div style="min-width: 200px;">
                    <strong>${getCategoriaLabel(oc.categoria)}</strong><br>
                    <small>${oc.endereco}</small><br>
                    <span class="badge priority-badge ${getPrioridadeClass(oc.urgencia)}">
                        ${getUrgenciaLabel(oc.urgencia)}
                    </span>
                    <span class="badge ${getStatusClass(oc.status)}">
                        ${getStatusLabel(oc.status)}
                    </span><br>
                    <a href="/ocorrencias/${oc.id}" style="color: #4F46E5; text-decoration: none;">
                        Ver detalhes →
                    </a>
                </div>
            `)
            .addTo(map);

        mapMarkers.push(marker);
    });
}

function adicionarMarcadorMapa(ocorrencia) {
    if (!ocorrencia) return;

    if (!Array.isArray(mapOcorrencias)) {
        mapOcorrencias = [];
    }

    mapOcorrencias.push(ocorrencia);
    renderizarMarcadores();
}

function ajustarPosicoesDuplicadas(ocorrencias) {
    const grupos = {};

    ocorrencias.forEach(oc => {
        const key = `${Number(oc.latitude).toFixed(6)}|${Number(oc.longitude).toFixed(6)}`;
        if (!grupos[key]) {
            grupos[key] = [];
        }
        grupos[key].push(oc);
    });

    const ajustadas = [];
    const raio = 0.0004;

    Object.values(grupos).forEach(lista => {
        const total = lista.length;

        lista.forEach((oc, index) => {
            if (total === 1) {
                ajustadas.push(oc);
                return;
            }

            const angle = (2 * Math.PI * index) / total;
            const latOffset = raio * Math.cos(angle);
            const lngOffset = (raio * Math.sin(angle)) / Math.cos(Number(oc.latitude) * Math.PI / 180);

            ajustadas.push({
                ...oc,
                latitude: Number(oc.latitude) + latOffset,
                longitude: Number(oc.longitude) + lngOffset
            });
        });
    });

    return ajustadas;
}

// ========================================
// GRÁFICOS
// ========================================

function initCharts() {
    // Gráfico de Tipos (Doughnut)
    const ctxType = document.getElementById('typeChart').getContext('2d');
    charts.type = new Chart(ctxType, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: []
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
    
    // Gráfico de Prioridades (Bar)
    const ctxPriority = document.getElementById('priorityChart').getContext('2d');
    charts.priority = new Chart(ctxPriority, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Quantidade',
                data: [],
                backgroundColor: []
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Gráfico de Evolução (Line)
    const ctxEvolution = document.getElementById('evolutionChart').getContext('2d');
    charts.evolution = new Chart(ctxEvolution, {
        type: 'line',
        data: {
            labels: [],
            datasets: []
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function atualizarGraficos(data) {
    // Atualizar gráfico de tipos
    if (data.por_tipo) {
        charts.type.data.labels = data.por_tipo.labels;
        charts.type.data.datasets[0].data = data.por_tipo.data;
        charts.type.data.datasets[0].backgroundColor = data.por_tipo.colors;
        charts.type.update();
    }
    
    // Atualizar gráfico de prioridades
    if (data.por_prioridade) {
        charts.priority.data.labels = data.por_prioridade.labels;
        charts.priority.data.datasets[0].data = data.por_prioridade.data;
        charts.priority.data.datasets[0].backgroundColor = [
            '#EF4444', '#F59E0B', '#06B6D4', '#10B981'
        ];
        charts.priority.update();
    }
    
    // Atualizar gráfico de evolução
    if (data.evolucao) {
        charts.evolution.data.labels = data.evolucao.labels;
        charts.evolution.data.datasets = [
            {
                label: 'Registradas',
                data: data.evolucao.registradas,
                borderColor: '#4F46E5',
                backgroundColor: 'rgba(79, 70, 229, 0.1)',
                tension: 0.4,
                fill: true
            },
            {
                label: 'Resolvidas',
                data: data.evolucao.resolvidas,
                borderColor: '#10B981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.4,
                fill: true
            }
        ];
        charts.evolution.update();
    }
}

// ========================================
// CARREGAMENTO DE DADOS
// ========================================
async function carregarDados() {
    try {
        // ================================
        // 1. ESTATÍSTICAS (ENDPOINT ANTIGO CORRETO)
        // ================================
        const periodo = currentFilters.periodo || '30';

        const dataFim = new Date();
        const dataInicio = new Date();
        dataInicio.setDate(dataFim.getDate() - Number(periodo));

        const params = new URLSearchParams({
            data_inicio: dataInicio.toISOString(),
            data_fim: dataFim.toISOString()
        });

        const statsResponse = await fetch('/dashboard/api/metricas?' + params.toString());
        const stats = await statsResponse.json();

        // ---- TOTAL ----
        const total = stats.ocorrencias.total || 0;

        // ---- CRÍTICAS (emergência + urgente) ----
        const criticas =
            (stats.ocorrencias.por_urgencia.emergencia || 0) +
            (stats.ocorrencias.por_urgencia.urgente || 0);

        // ---- AGUARDANDO (pendente + validada) ----
        const aguardando =
            (stats.ocorrencias.por_status.pendente || 0) +
            (stats.ocorrencias.por_status.validada || 0);

        // ---- RESOLVIDAS (30 dias) ----
        const resolvidas =
            (stats.ordens_servico.por_status.concluida || 0);

        atualizarEstatisticas({
            total_ocorrencias: total,
            criticas_urgente: criticas,
            aguardando_validacao: aguardando,
            resolvidas_30dias: resolvidas,
            total_ocorrencias_trend: 0,
            criticas_urgente_trend: 0,
            aguardando_validacao_trend: 0,
            resolvidas_30dias_trend: 0
        });

        // ================================
        // 2. MAPA
        // ================================
        const mapaResponse = await fetch('/api/dashboard/mapa/ocorrencias?' + new URLSearchParams(currentFilters));
        if (!mapaResponse.ok) {
            throw new Error(`Falha ao carregar mapa (${mapaResponse.status})`);
        }

        const mapaData = await mapaResponse.json();

        if (mapaData.error) {
            throw new Error(mapaData.error);
        }

        atualizarMapa(mapaData);

        // ================================
        // 3. RECENTES
        // ================================
        const recentesResponse = await fetch('/api/dashboard/ocorrencias/recentes?limit=5');
        const recentes = await recentesResponse.json();
        atualizarTabelaRecentes(recentes);

        // ================================
        // 4. GRÁFICOS
        // ================================
        const chartsResponse = await fetch('/api/dashboard/charts?' + new URLSearchParams(currentFilters));
        const chartsData = await chartsResponse.json();
        atualizarGraficos(chartsData);

    } catch (error) {
        console.error('Erro ao carregar dados:', error);
        mostrarErro('Erro ao carregar dados do dashboard');
    }
}



function atualizarEstatisticas(stats) {
    // Atualizar valores
    document.getElementById('statTotal').textContent = formatarNumero(stats.total_ocorrencias || 0);
    document.getElementById('statCriticas').textContent = formatarNumero(stats.criticas_urgente || 0);
    document.getElementById('statAguardando').textContent = formatarNumero(stats.aguardando_validacao || 0);
    document.getElementById('statResolvidas').textContent = formatarNumero(stats.resolvidas_30dias || 0);
    
    // Atualizar trends
    atualizarTrend('trendTotal', stats.total_ocorrencias_trend);
    atualizarTrend('trendCriticas', stats.criticas_urgente_trend);
    atualizarTrend('trendAguardando', stats.aguardando_validacao_trend);
    atualizarTrend('trendResolvidas', stats.resolvidas_30dias_trend);
}

function atualizarTrend(elementId, value) {
    const element = document.getElementById(elementId);
    const isPositive = value >= 0;
    
    element.className = `stat-trend ${isPositive ? 'up' : 'down'}`;
    element.innerHTML = `
        <i class="fas fa-arrow-${isPositive ? 'up' : 'down'}"></i> 
        ${Math.abs(value).toFixed(1)}%
    `;
}

function atualizarTabelaRecentes(ocorrencias) {
    const tbody = document.getElementById('tableRecentes');
    
    if (ocorrencias.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">Nenhuma ocorrência encontrada</td></tr>';
        return;
    }
    
    tbody.innerHTML = ocorrencias.map(oc => `
        <tr onclick="window.location.href='/ocorrencias/${oc.id}'">
            <td><strong>#${oc.numero || oc.id.substr(0, 8)}</strong></td>
            <td>${getCategoriaLabel(oc.categoria)}</td>
            <td>${oc.endereco_resumido || 'N/A'}</td>
            <td>
                <span class="badge priority-badge ${getPrioridadeClass(oc.urgencia)}">
                    ${getUrgenciaLabel(oc.urgencia)}
                </span>
            </td>
            <td>
                <span class="badge ${getStatusClass(oc.status)}">
                    ${getStatusLabel(oc.status)}
                </span>
            </td>
            <td>${formatarData(oc.created_at)}</td>
        </tr>
    `).join('');
}

// ========================================
// FILTROS
// ========================================

function aplicarFiltros() {
    currentFilters = {
        periodo: document.getElementById('filterPeriodo').value,
        tipo: document.getElementById('filterTipo').value,
        prioridade: document.getElementById('filterPrioridade').value,
        status: document.getElementById('filterStatus').value,
        regiao: document.getElementById('filterRegiao').value
    };
    
    carregarDados();
}

function limparFiltros() {
    document.getElementById('filterPeriodo').value = '30';
    document.getElementById('filterTipo').value = '';
    document.getElementById('filterPrioridade').value = '';
    document.getElementById('filterStatus').value = '';
    document.getElementById('filterRegiao').value = '';
    
    currentFilters = {
        periodo: 30,
        tipo: '',
        prioridade: '',
        status: '',
        regiao: ''
    };
    
    carregarDados();
}

// ========================================
// WEBSOCKET
// ========================================

function initWebSocket() {
    socket = io('/dashboard');
    
    socket.on('connect', function() {
        console.log('WebSocket conectado');
    });
    
    socket.on('nova_ocorrencia', function(data) {
        console.log('Nova ocorrência recebida:', data);

        const ocorrencias = normalizarOcorrencias(data);

        ocorrencias.forEach(function(item) {
            // Mostrar notificação
            mostrarNotificacao('Nova Ocorrência',
                `${getCategoriaLabel(item.categoria)} - ${item.endereco || item.camera_nome || ''}`);

            // Atualizar dados
            carregarDados();
            carregarBadges();
        });
    });
    
    socket.on('ocorrencia_atualizada', function(data) {
        console.log('Ocorrência atualizada:', data);
        carregarDados();
    });
    
    socket.on('disconnect', function() {
        console.log('WebSocket desconectado');
    });
}

function normalizarOcorrencias(data) {
    if (!data) return [];

    if (Array.isArray(data)) {
        return data;
    }

    if (Array.isArray(data.ocorrencias)) {
        return data.ocorrencias;
    }

    return [data];
}

// ========================================
// BADGES
// ========================================

async function carregarBadges() {
    try {
        const response = await fetch('/api/ocorrencias/count');
        const counts = await response.json();
        
        const total = (counts.novas || 0) + (counts.pendentes || 0) + (counts.em_analise || 0);
        
        const badge = document.getElementById('badgeOcorrencias');
        if (total > 0) {
            badge.textContent = total;
            badge.style.display = 'inline-block';
        } else {
            badge.style.display = 'none';
        }
    } catch (error) {
        console.error('Erro ao carregar badges:', error);
    }
}

// ========================================
// UTILITÁRIOS
// ========================================

function getCategoriaLabel(categoria) {
    const labels = {
    "asfalto_dano": "🕳️ Buraco / Asfalto Danificado",
    "calcada_dano": "🚶‍♀️ Calçada Danificada",
    "iluminacao_publica": "💡 Iluminação Pública",
    "fiacao_exposta": "⚡ Fiação Exposta",
    "lixo_irregular": "🗑️ Lixo / Entulho Irregular",
    "arvore_dano": "🌳 Árvore / Galhos Danificados",
    "mato_alto": "🌿 Mato Alto",
    "ponto_onibus_dano": "🚌 Ponto de Ônibus Danificado",
    "vazamento_agua": "💧 Vazamento de Água",
    "fruta_na_pista": "🍂 Frutas / Resíduos na Pista",
    "placa_dano": "🚧 Placa de Trânsito Danificada",
    "semaforo_defeito": "🚦 Semáforo com Defeito",
    "sinalizacao_apagada": "〰️ Sinalização Apagada",
    "objeto_na_pista": "🧱 Objeto / Obstrução na Pista",
    "animal_na_pista": "🐕 Animal na Pista",
    "bueiro_entupido": "🕳️ Bueiro Entupido",
    "bueiro_dano": "🕳️ Bueiro Danificado",
    "queimada": "🔥 Queimada / Foco de Incêndio",
    "obra_irregular": "🏗️ Obra Irregular",
    "desconhecido": "❓ Desconhecido"
    };
    return labels[categoria] || categoria;
}

function getUrgenciaLabel(urgencia) {
    const labels = {
        'emergencia': 'Crítica',
        'urgente': 'Alta',
        'pouco_urgente': 'Média',
        'nao_urgente': 'Baixa'
    };
    return labels[urgencia] || urgencia;
}

function getStatusLabel(status) {
    const labels = {
        'pendente': 'Nova',
        'validada': 'Em Análise',
        'aprovada': 'Validada',
        'resolvida': 'Resolvida',
        'rejeitada': 'Rejeitada'
    };
    return labels[status] || status;
}

function getPrioridadeColor(urgencia) {
    const colors = {
        'emergencia': '#EF4444',
        'urgente': '#F59E0B',
        'pouco_urgente': '#06B6D4',
        'nao_urgente': '#10B981'
    };
    return colors[urgencia] || '#94A3B8';
}

function getPrioridadeClass(urgencia) {
    const classes = {
        'emergencia': 'critical',
        'urgente': 'high',
        'pouco_urgente': 'medium',
        'nao_urgente': 'low'
    };
    return classes[urgencia] || 'low';
}

function getStatusClass(status) {
    const classes = {
        'pendente': 'primary',
        'validada': 'warning',
        'aprovada': 'info',
        'resolvida': 'success',
        'rejeitada': 'danger'
    };
    return classes[status] || 'primary';
}

function formatarNumero(num) {
    return new Intl.NumberFormat('pt-BR').format(num);
}

function formatarData(dataStr) {
    const data = new Date(dataStr);
    return data.toLocaleDateString('pt-BR');
}

function mostrarNotificacao(titulo, mensagem) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(titulo, {
            body: mensagem,
            icon: '/static/img/logo.png'
        });
    }
}

function mostrarErro(mensagem) {
    console.error(mensagem);
    // Aqui você pode adicionar um toast/alert para o usuário
}

// Solicitar permissão para notificações
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}