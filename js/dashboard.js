// Dashboard JavaScript

let chartsInstances = {};

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    configurarFiltros();
    atualizarDashboard();
    
    // Atualizar a cada 2 minutos
    setInterval(atualizarDashboard, 120000);
});

function configurarFiltros() {
    const periodFilter = document.getElementById('periodFilter');
    const customDateRange = document.getElementById('customDateRange');
    
    if (periodFilter) {
        periodFilter.addEventListener('change', function() {
            if (this.value === 'custom') {
                customDateRange.style.display = 'flex';
            } else {
                customDateRange.style.display = 'none';
                atualizarDashboard();
            }
        });
    }
}

async function atualizarDashboard() {
    mostrarLoading();
    
    try {
        const params = obterParametrosFiltro();
        const response = await fetch(`/dashboard/api/metricas?${params}`);
        
        if (!response.ok) {
            throw new Error('Erro ao buscar dados');
        }
        
        const data = await response.json();
        
        atualizarMetricas(data);
        atualizarGraficos(data);
        await atualizarTabelas();
        
    } catch (error) {
        console.error('Erro:', error);
        mostrarErro('Erro ao atualizar dashboard');
    } finally {
        esconderLoading();
    }
}

function obterParametrosFiltro() {
    const periodFilter = document.getElementById('periodFilter');
    const dataInicio = document.getElementById('dataInicio');
    const dataFim = document.getElementById('dataFim');
    
    let params = new URLSearchParams();
    
    if (periodFilter.value === 'custom' && dataInicio && dataFim) {
        params.append('data_inicio', dataInicio.value);
        params.append('data_fim', dataFim.value);
    } else {
        const dias = parseInt(periodFilter.value);
        const fim = new Date();
        const inicio = new Date(fim);
        inicio.setDate(inicio.getDate() - dias);
        
        params.append('data_inicio', inicio.toISOString());
        params.append('data_fim', fim.toISOString());
    }
    
    return params.toString();
}

function atualizarMetricas(data) {
    // Ocorrências por urgência
    document.getElementById('metricEmergencia').textContent = 
        data.ocorrencias.por_urgencia.emergencia || 0;
    document.getElementById('metricUrgente').textContent = 
        data.ocorrencias.por_urgencia.urgente || 0;
    document.getElementById('metricPoucoUrgente').textContent = 
        data.ocorrencias.por_urgencia.pouco_urgente || 0;
    document.getElementById('metricNaoUrgente').textContent = 
        data.ocorrencias.por_urgencia.nao_urgente || 0;
    document.getElementById('metricTotal').textContent = 
        data.ocorrencias.total || 0;
    
    // OS
    const osAndamento = (data.ordens_servico.por_status.em_andamento || 0) +
                        (data.ordens_servico.por_status.atribuida || 0);
    document.getElementById('metricOSAndamento').textContent = osAndamento;
    
    document.getElementById('metricOSAguardando').textContent = 
        data.ordens_servico.por_status.aguardando_aprovacao || 0;
    
    document.getElementById('metricOSConcluidas').textContent = 
        data.ordens_servico.por_status.concluida || 0;
}

function atualizarGraficos(data) {
    // Gráfico de Evolução de Ocorrências
    criarGraficoLinha(
        'chartEvolucaoOcorrencias',
        data.ocorrencias.evolucao.map(e => e.data),
        [{
            label: 'Ocorrências',
            data: data.ocorrencias.evolucao.map(e => e.total),
            borderColor: '#667eea',
            backgroundColor: 'rgba(102, 126, 234, 0.1)',
            tension: 0.4
        }]
    );
    
    // Gráfico de Categorias
// Gráfico de Categorias (todas as 20 categorias com nomes legíveis e emojis)
const categoriasData = data.ocorrencias.por_categoria;

const nomesLegiveis = {
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

const coresCategorias = [
    "#ef4444","#3b82f6","#f59e0b","#10b981","#8b5cf6","#f97316","#06b6d4",
    "#84cc16","#ec4899","#6366f1","#22d3ee","#16a34a","#fbbf24","#eab308",
    "#94a3b8","#dc2626","#2563eb","#14b8a6","#d946ef","#9ca3af"
];

// Cria arrays em ordem fixa para manter consistência
const categoriasKeys = Object.keys(categoriasData);
const labelsCategorias = categoriasKeys.map(c => nomesLegiveis[c] || c);
const valoresCategorias = categoriasKeys.map(c => categoriasData[c] || 0);

criarGraficoPizza(
    'chartCategorias',
    labelsCategorias,
    valoresCategorias,
    coresCategorias.slice(0, categoriasKeys.length)
);




    // Gráfico de Status OS
    const statusOS = data.ordens_servico.por_status;
    criarGraficoBarra(
        'chartStatusOS',
        ['Criada', 'Atribuída', 'Em Andamento', 'Aguardando', 'Concluída'],
        [{
            label: 'Quantidade',
            data: [
                statusOS.criada || 0,
                statusOS.atribuida || 0,
                statusOS.em_andamento || 0,
                statusOS.aguardando_aprovacao || 0,
                statusOS.concluida || 0
            ],
            backgroundColor: [
                '#1E90FF',
                '#FFD700',
                '#FFA500',
                '#9370DB',
                '#00A86B'
            ]
        }]
    );
    
    // Gráfico de Prioridades
    const prioridades = data.ordens_servico.por_prioridade;
    criarGraficoPizza(
        'chartPrioridades',
        ['Crítica', 'Alta', 'Média', 'Baixa'],
        [
            prioridades.critica || 0,
            prioridades.alta || 0,
            prioridades.media || 0,
            prioridades.baixa || 0
        ],
        ['#FF4C4C', '#FFA500', '#FFD700', '#4CAF50']
    );
}

function criarGraficoLinha(canvasId, labels, datasets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    
    // Destruir gráfico existente
    if (chartsInstances[canvasId]) {
        chartsInstances[canvasId].destroy();
    }
    
    chartsInstances[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

function criarGraficoPizza(canvasId, labels, data, colors) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    
    if (chartsInstances[canvasId]) {
        chartsInstances[canvasId].destroy();
    }
    
    chartsInstances[canvasId] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function criarGraficoBarra(canvasId, labels, datasets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    
    if (chartsInstances[canvasId]) {
        chartsInstances[canvasId].destroy();
    }
    
    chartsInstances[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
}

async function atualizarTabelas() {
    // Últimas Ocorrências
    try {
        const response = await fetch('/api/ocorrencias?limit=5&sort=desc');
        const ocorrencias = await response.json();
        
        const tbody = document.querySelector('#tableUltimasOcorrencias tbody');
        if (tbody) {
            if (ocorrencias.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">Nenhuma ocorrência</td></tr>';
            } else {
                tbody.innerHTML = ocorrencias.map(occ => `
                    <tr onclick="verOcorrencia('${occ.id}')">
                        <td>${formatarData(occ.created_at)}</td>
                        <td>${formatarCategoria(occ.categoria)}</td>
                        <td><span class="badge badge-${occ.urgencia}">${formatarUrgencia(occ.urgencia)}</span></td>
                        <td>${occ.endereco_completo || 'Endereço não disponível'}</td>
                        <td><span class="badge badge-${occ.status}">${formatarStatus(occ.status)}</span></td>
                    </tr>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Erro ao carregar ocorrências:', error);
    }
    
    // OS Críticas
    try {
        const response = await fetch('/api/os?status=em_andamento,aguardando_aprovacao&prioridade=critica,alta&limit=5');
        const ordens = await response.json();
        
        const tbody = document.querySelector('#tableOSCriticas tbody');
        if (tbody) {
            if (ordens.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center">Nenhuma OS crítica</td></tr>';
            } else {
                tbody.innerHTML = ordens.map(os => `
                    <tr onclick="verOS('${os.id}')">
                        <td><strong>${os.numero_os}</strong></td>
                        <td>${formatarCategoria(os.categoria)}</td>
                        <td>${formatarData(os.prazo_execucao)}</td>
                        <td><span class="badge badge-${os.status}">${formatarStatusOS(os.status)}</span></td>
                        <td><button class="btn-ver" onclick="event.stopPropagation(); verOS('${os.id}')">Ver</button></td>
                    </tr>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Erro ao carregar OS:', error);
    }
}

// Funções auxiliares
function formatarData(data) {
    return new Date(data).toLocaleDateString('pt-BR');
}

function formatarCategoria(categoria) {
    const map = {
        'buraco': 'Buraco',
        'bueiro': 'Bueiro',
        'fio_solto': 'Fio Solto',
        'mato_alto': 'Mato Alto'
    };
    return map[categoria] || categoria;
}

function formatarUrgencia(urgencia) {
    const map = {
        'emergencia': 'Emergência',
        'urgente': 'Urgente',
        'pouco_urgente': 'Pouco Urgente',
        'nao_urgente': 'Não Urgente'
    };
    return map[urgencia] || urgencia;
}

function formatarStatus(status) {
    const map = {
        'pendente': 'Pendente',
        'em_os': 'Em OS',
        'resolvida': 'Resolvida',
        'cancelada': 'Cancelada'
    };
    return map[status] || status;
}

function formatarStatusOS(status) {
    const map = {
        'criada': 'Criada',
        'atribuida': 'Atribuída',
        'em_andamento': 'Em Andamento',
        'aguardando_aprovacao': 'Aguardando',
        'aprovada': 'Aprovada',
        'rejeitada': 'Rejeitada',
        'concluida': 'Concluída'
    };
    return map[status] || status;
}

function verOcorrencia(id) {
    window.location.href = `/ocorrencias/${id}`;
}

function verOS(id) {
    window.location.href = `/os/${id}`;
}

function mostrarLoading() {
    // Implementar indicador de loading
}

function esconderLoading() {
    // Esconder indicador de loading
}

function mostrarErro(mensagem) {
    alert(mensagem); // Substituir por toast/notificação melhor
}