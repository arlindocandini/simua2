let map = null;
let markersLayer = new L.LayerGroup();
let selectedOccurrence = null;
let currentStatusFilter = 'Todos';
let currentLocalizacaoFilter = 'Todos'; // Este filtro não está sendo usado no HTML, mas mantido
let currentCategoriaFilter = 'Todos';
let currentSearchTerm = '';
let currentRankingMode = 'irl';
let occurrences = [];
let processedOccurrences = [];
let filteredOccurrences = [];
let focusedOccurrenceId = null;

// Mapeamento de Cores de Risco
const RISK_COLORS = {
    low: 'risk-low',
    medium: 'risk-medium',
    high: 'risk-high',
    extreme: 'risk-extreme'
};

function getRiskColorHex(irlScore) {
    if (irlScore >= 86) return '#8b5cf6'; // Roxo (Extremo)
    if (irlScore >= 61) return '#ef4444'; // Vermelho (Alto)
    if (irlScore >= 31) return '#facc15'; // Amarelo (Médio)
    return '#10b981'; // Verde (Baixo)
}

function calculateIRL(item) {
    // ⚠️ ATENÇÃO: Conforme sugestão anterior, essa lógica de negócio DEVERIA estar no backend
    // Mantida aqui para a funcionalidade do frontend atual.
    const exposureScore = Math.min(25, (item.exposureDays || 0) * 0.25);
    const traffic = item.trafficScore || 0;
    const proximity = item.proximityScore || 0;
    return Math.min(100, Math.round(exposureScore + traffic + proximity));
}

function getRiskLevel(irlScore) {
    if (irlScore >= 86) return { color: RISK_COLORS.extreme, description: 'RISCO CRÍTICO (Extremo)' };
    if (irlScore >= 61) return { color: RISK_COLORS.high, description: 'RISCO ALTO' };
    if (irlScore >= 31) return { color: RISK_COLORS.medium, description: 'RISCO MODERADO' };
    return { color: RISK_COLORS.low, description: 'RISCO BAIXO' };
}

function processOccurrences(data) {
    return data.map(item => {
        const irlScore = calculateIRL(item);
        const risk = getRiskLevel(irlScore);
        
        return {
            ...item,
            irlScore: irlScore,
            riskLevel: risk.description,
            riskColor: risk.color,
            exposureScore: Math.min(25, (item.exposureDays || 0) * 0.25), // Adiciona score de exposição
        };
    });
}

// ----------------------------------------------------
// NOVO: Renderização do Cartão de Detalhes (Foco Visual)
// ----------------------------------------------------

function renderDetailCard(occurrence) {
    const detailCard = document.getElementById('detail-card');

    if (!occurrence) {
        detailCard.innerHTML = `
            <div class="empty-state detail-panel" style="margin-top: 20px; text-align: center;">
                <i class="fas fa-arrow-left text-3xl text-gray-400 mb-4"></i>
                <h4>Selecione uma ocorrência</h4>
                <p class="text-gray-500">Clique em um item da lista ou no mapa para analisar os detalhes jurídicos e custos simulados.</p>
            </div>
        `;
        return;
    }

    const { irlScore, riskLevel, riskColor, title, numero_os, location, bairro, exposureDays, trafficScore, proximityScore, proximityText, baseIndemnization, repairCost } = occurrence;
    const colorHex = getRiskColorHex(irlScore);

    // Formatação de Moeda
    const formatCurrency = (value) => {
        if (typeof value !== 'number') return 'R$ N/A';
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
    };

    // Fatores de IRL (Para o componente Fatores de Risco)
    const factorItems = [
        { name: 'Exposição (Dias Aberto)', value: occurrence.exposureScore.toFixed(1), max: 25, unit: 'pts', status: `${exposureDays} dias` },
        { name: 'Risco de Tráfego', value: trafficScore, max: 50, unit: 'pts', status: 'Área Movimentada' },
        { name: 'Risco de Proximidade', value: proximityScore, max: 25, unit: 'pts', status: proximityText || 'Nenhum próximo' }
    ];

    detailCard.innerHTML = `
        <div class="detail-panel">
            <h3 class="text-xl font-bold mb-1 text-gray-800">${title}</h3>
            <p class="text-sm text-gray-500 mb-4">OS #${numero_os} | ${location}, ${bairro}</p>

            <!-- 1. Score IRL Visual (Principal Foco) -->
            <div class="irl-score-display transition-all" style="background-color: ${colorHex};">
                <div class="irl-score-value">${irlScore}</div>
                <div class="irl-score-label">${riskLevel}</div>
            </div>

            <!-- 2. Fatores de Risco Detalhados -->
            <div class="mb-6">
                <h4 class="font-bold text-lg text-gray-700 mb-2">Fatores Contribuintes</h4>
                <div class="bg-white p-3 rounded-lg border border-gray-200">
                    <div class="factor-item font-semibold text-sm text-indigo-700">
                        <span class="factor-name">Fator</span>
                        <span class="factor-score">Pontuação</span>
                        <span class="factor-status">Detalhe</span>
                    </div>
                    ${factorItems.map(f => `
                        <div class="factor-item">
                            <span class="factor-name">${f.name}</span>
                            <span class="factor-score text-${f.value > 0 ? 'red' : 'green'}-600">${f.value} ${f.unit}</span>
                            <span class="factor-status text-gray-500">${f.status}</span>
                        </div>
                    `).join('')}
                    <div class="factor-item mt-2 pt-3 border-t border-gray-300">
                        <span class="factor-name font-bold text-lg text-indigo-700">IRL TOTAL</span>
                        <span class="factor-score font-bold text-lg text-indigo-700">${irlScore}</span>
                        <span></span>
                    </div>
                </div>
            </div>
            

            <!-- 3. Simulação de Custos -->
            <div class="mb-4">
                <h4 class="font-bold text-lg text-gray-700 mb-2">Simulação de Custos (Jurídico/Reparo)</h4>
                <div class="bg-white p-4 rounded-lg border border-gray-200">
                    <div class="cost-item">
                        <span class="cost-label flex items-center"><i class="fas fa-hammer mr-2 text-blue-500"></i> Custo Estimado de Reparo (Direto)</span>
                        <span class="cost-value text-blue-600">${formatCurrency(repairCost)}</span>
                    </div>
                    <div class="cost-item">
                        <span class="cost-label flex items-center"><i class="fas fa-gavel mr-2 text-red-500"></i> Indenização Base (Risco Jurídico)</span>
                        <span class="cost-value text-red-600">${formatCurrency(baseIndemnization)}</span>
                    </div>
                    <div class="cost-item border-none pt-3">
                        <span class="cost-label text-lg font-extrabold text-gray-800 flex items-center"><i class="fas fa-hand-holding-usd mr-2 text-green-600"></i> Custo Total Simulado (R + I)</span>
                        <span class="cost-value text-green-600 text-lg">${formatCurrency(repairCost + baseIndemnization)}</span>
                    </div>
                </div>
            </div>
            <p class="text-xs text-gray-400 mt-4 text-center">Os valores simulados representam o potencial impacto financeiro. A pontuação IRL indica a probabilidade de conversão do risco.</p>
        </div>
    `;
}

// ----------------------------------------------------
// Funções de Renderização Existentes (Ajustadas para novo CSS)
// ----------------------------------------------------

function renderKPIs() {
    const totalOccurrences = processedOccurrences.length;
    
    // Calcula a média do IRL
    const totalIRLScore = processedOccurrences.reduce((sum, item) => sum + item.irlScore, 0);
    const mediaIRL = totalOccurrences > 0 ? (totalIRLScore / totalOccurrences).toFixed(0) : 0;

    // Criticas (IRL Alto/Crítico >= 61)
    const criticasCount = processedOccurrences.filter(item => item.irlScore >= 61).length;
    const criticasPercent = totalOccurrences > 0 ? ((criticasCount / totalOccurrences) * 100).toFixed(0) : 0;

    // Custo
    const totalRepairCost = processedOccurrences.reduce((sum, item) => sum + item.repairCost, 0);
    const mediaRepairCost = totalOccurrences > 0 ? (totalRepairCost / totalOccurrences) : 0;
    
    const totalOS = totalOccurrences; // Usando as ocorrências filtradas
    
    // Formatação de Moeda
    const formatCurrency = (value) => {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value);
    };

    document.getElementById('kpi-criticas').innerHTML = `${criticasCount} <span class="text-base text-gray-500">(${criticasPercent}%)</span>`;
    document.getElementById('kpi-media-irl').textContent = `${mediaIRL} / 100`;
    document.getElementById('kpi-baixo-custo').textContent = formatCurrency(mediaRepairCost);
    document.getElementById('kpi-alto-custo').textContent = totalOS;
}

function renderRanking() {
    const list = document.getElementById('top-10-list');
    list.innerHTML = '';
    
    // 1. Definição do critério de ordenação
    let sortedList;
    let sortLabel;
    
    switch (currentRankingMode) {
        case 'custo':
            sortedList = filteredOccurrences.sort((a, b) => (b.repairCost + b.baseIndemnization) - (a.repairCost + a.baseIndemnization));
            sortLabel = 'Total Custo';
            break;
        case 'exposicao':
            sortedList = filteredOccurrences.sort((a, b) => b.exposureDays - a.exposureDays);
            sortLabel = 'Dias de Exposição';
            break;
        case 'irl':
        default:
            sortedList = filteredOccurrences.sort((a, b) => b.irlScore - a.irlScore);
            sortLabel = 'Score IRL';
            break;
    }

    // Pega os 10 primeiros ou todos
    const topItems = sortedList.slice(0, 10);
    
    if (topItems.length === 0) {
        list.innerHTML = `
            <li class="empty-state p-4 text-center text-gray-500">
                <i class="fas fa-search-minus text-3xl text-gray-400 mb-3"></i>
                <h4>Nenhum resultado encontrado</h4>
                <p>Ajuste seus filtros ou termos de busca.</p>
            </li>
        `;
        return;
    }

    topItems.forEach((item, index) => {
        let value = '';
        switch (currentRankingMode) {
            case 'custo':
                value = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 0 }).format(item.repairCost + item.baseIndemnization);
                break;
            case 'exposicao':
                value = `${item.exposureDays} dias`;
                break;
            case 'irl':
            default:
                value = `${item.irlScore}%`;
                break;
        }

        const li = document.createElement('li');
        li.className = `ranking-item ${item.id === focusedOccurrenceId ? 'active' : ''}`;
        li.setAttribute('data-id', item.id);
        
        // Estilo de Risco no Ranking
        const riskBadge = `<span class="risk-badge ${item.riskColor}">${item.riskLevel.replace(' (Extremo)', '')}</span>`;

        li.innerHTML = `
            <div class="flex justify-between items-start">
                <div class="flex items-start">
                    <span class="text-xl font-bold mr-3 text-indigo-700">${index + 1}.</span>
                    <div>
                        <div class="font-semibold text-gray-800">${item.title}</div>
                        <div class="text-xs text-gray-500">${item.location}, ${item.bairro}</div>
                    </div>
                </div>
                <div class="text-right">
                    ${riskBadge}
                    <div class="ranking-score mt-1 text-gray-800">${value}</div>
                    <div class="text-xs text-gray-400">${sortLabel}</div>
                </div>
            </div>
        `;
        
        li.addEventListener('click', () => {
            selectOccurrence(item);
        });
        
        list.appendChild(li);
    });
}

// ----------------------------------------------------
// Funções de Controle (Filtros, Mapa, Seleção)
// ----------------------------------------------------

function initMap() {
    map = L.map('irl-map').setView([-16.6869, -49.2648], 12); // Coordenadas de Goiânia (exemplo)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap'
    }).addTo(map);

    markersLayer.addTo(map);
}

function renderMap(occurrencesToRender) {
    markersLayer.clearLayers();
    
    // Re-calcula bounds para centralizar o mapa, se houver dados
    let bounds = [];

    occurrencesToRender.forEach(item => {
        if (item.latitude && item.longitude) {
            bounds.push([item.latitude, item.longitude]);
            const colorHex = getRiskColorHex(item.irlScore);

            const markerHtmlStyles = `
                background-color: ${colorHex};
                width: 30px;
                height: 30px;
                display: block;
                left: -15px;
                top: -15px;
                position: relative;
                border-radius: 30px 30px 0;
                transform: rotate(45deg);
                border: 2px solid white;
                box-shadow: 0 0 5px rgba(0,0,0,0.3);
            `;

            const icon = L.divIcon({
                className: "custom-div-icon",
                html: `<div style="${markerHtmlStyles}"></div>`,
                iconSize: [30, 42],
                iconAnchor: [15, 21]
            });

            const marker = L.marker([item.latitude, item.longitude], { icon: icon });
            
            // Popup simplificado
            const popupContent = `
                <div style="font-family: 'Poppins', sans-serif;">
                    <h4 style="font-weight: 600; margin: 0 0 5px 0;">${item.title} (IRL: ${item.irlScore}%)</h4>
                    <p style="font-size: 12px; color: #555;">${item.location}, ${item.bairro}</p>
                    <button id="detail-btn-${item.id}" class="mt-2 text-xs font-semibold text-indigo-600 hover:text-indigo-800">Ver Detalhes</button>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            
            marker.on('click', () => {
                selectOccurrence(item);
                // Fecha o popup (se for o caso)
                // marker.closePopup(); 
            });

            marker.on('popupopen', () => {
                document.getElementById(`detail-btn-${item.id}`).addEventListener('click', () => {
                    selectOccurrence(item);
                    map.closePopup(marker.getPopup());
                });
            });

            markersLayer.addLayer(marker);
        }
    });

    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

function filterOccurrences() {
    filteredOccurrences = processedOccurrences.filter(item => {
        // Filtro de Busca por Texto (Título, Endereço, OS)
        const searchMatch = !currentSearchTerm || 
                            item.title.toLowerCase().includes(currentSearchTerm.toLowerCase()) ||
                            item.location.toLowerCase().includes(currentSearchTerm.toLowerCase()) ||
                            (item.numero_os && item.numero_os.toLowerCase().includes(currentSearchTerm.toLowerCase()));

        // Filtro de Status da OS
        const statusMatch = currentStatusFilter === 'Todos' || item.osStatus === currentStatusFilter;

        // Filtro de Categoria (Não implementado no HTML, mas mantido na lógica)
        const categoriaMatch = currentCategoriaFilter === 'Todos' || item.categoryLabel === currentCategoriaFilter;

        return searchMatch && statusMatch && categoriaMatch;
    });
}

function applyFiltersAndRender() {
    filterOccurrences();
    renderKPIs();
    renderMap(filteredOccurrences);
    renderRanking();

    // Se o item focado ainda estiver na lista filtrada, re-selecione-o
    if (focusedOccurrenceId) {
        const item = filteredOccurrences.find(o => o.id === focusedOccurrenceId);
        if (item) {
            selectOccurrence(item, false); // Não move o mapa
        } else {
            selectOccurrence(null);
        }
    } else {
        // Garante que o painel de detalhes esteja vazio se não houver seleção
        renderDetailCard(null); 
    }
}

function selectOccurrence(occurrence, moveMap = true) {
    // 1. Atualiza o estado da seleção
    selectedOccurrence = occurrence;
    focusedOccurrenceId = occurrence ? occurrence.id : null;

    // 2. Renderiza o cartão de detalhes
    renderDetailCard(occurrence);
    
    // 3. Atualiza o ranking para destacar o item
    renderRanking(); 

    // 4. Centraliza o mapa
    if (moveMap && occurrence && map) {
        map.setView([occurrence.latitude, occurrence.longitude], 15);
    }
}

// ----------------------------------------------------
// Inicialização e Event Listeners
// ----------------------------------------------------

async function fetchData() {
    try {
        // Mostrar estado de carregamento inicial
        // (Já está no HTML, apenas garantir que não haja bug)

        const response = await fetch('/api/dashboard/dados_irl'); 
        const json = await response.json();

        if (json.status === 'success') {
            occurrences = json.occurrences;
            processedOccurrences = processOccurrences(occurrences);
            
            applyFiltersAndRender();
        } else {
            console.error('Erro ao buscar dados IRL:', json.message);
            // Mostrar mensagem de erro no painel
            document.getElementById('top-10-list').innerHTML = `<li class="empty-state p-4 text-center text-red-500">Erro: ${json.message || 'Falha ao carregar dados.'}</li>`;
        }

    } catch (error) {
        console.error('Erro de rede ao buscar dados IRL:', error);
        document.getElementById('top-10-list').innerHTML = `<li class="empty-state p-4 text-center text-red-500">Erro de Conexão: Verifique o servidor.</li>`;
    }
}

window.onload = function() {
    initMap();
    fetchData();

    // Adiciona o evento de reset para o detalhe
    selectOccurrence(null);

    // Event Listeners para Filtros
    document.getElementById('filtroStatus').addEventListener('change', (e) => {
        currentStatusFilter = e.target.value;
        applyFiltersAndRender();
    });
    // O filtroLocalizacao e filtroCategoria estão no JS mas não no HTML atual.
    // document.getElementById('filtroLocalizacao').addEventListener('change', (e) => {
    //     currentLocalizacaoFilter = e.target.value;
    //     applyFiltersAndRender();
    // });
    // document.getElementById('filtroCategoria').addEventListener('change', (e) => {
    //     currentCategoriaFilter = e.target.value;
    //     applyFiltersAndRender();
    // });
    document.getElementById('filtroBusca').addEventListener('input', (e) => {
        currentSearchTerm = e.target.value;
        applyFiltersAndRender();
    });

    // Event Listeners para Abas de Ranking
    document.querySelectorAll('.ranking-tab').forEach(button => {
        button.addEventListener('click', (e) => {
            document.querySelectorAll('.ranking-tab').forEach(b => {
                b.classList.remove('active-tab');
                b.classList.remove('bg-indigo-500', 'text-white', 'shadow-md');
                b.classList.add('text-gray-600');
            });
            // Adiciona a classe ao clicado
            e.target.classList.add('active-tab', 'bg-indigo-500', 'text-white', 'shadow-md');
            e.target.classList.remove('text-gray-600');

            currentRankingMode = e.target.getAttribute('data-mode');
            applyFiltersAndRender();
        });
    });

    // Força o estilo inicial da aba ativa
    const defaultTab = document.querySelector('.ranking-tab[data-mode="irl"]');
    if (defaultTab) {
        defaultTab.classList.add('active-tab', 'bg-indigo-500', 'text-white', 'shadow-md');
        defaultTab.classList.remove('text-gray-600');
    }
};