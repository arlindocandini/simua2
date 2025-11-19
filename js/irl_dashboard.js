let map = null;
let markersLayer = new L.LayerGroup();
let selectedOccurrence = null;
let currentStatusFilter = 'Todos';
let currentCategoriaFilter = 'Todos';
let currentRiskFilter = 'Todos';
let currentBairroFilter = 'Todos';
let currentSearchTerm = '';
let currentRankingMode = 'irl';
let occurrences = [];
let processedOccurrences = [];
let filteredOccurrences = [];
let focusedOccurrenceId = null;
let currentIRLRange = [0, 100];
let currentCostRange = [0, 50000];
let dynamicCostUpperBound = 50000;

const currencyFormatter = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0
});

// Mapeamento de Cores de Risco
const RISK_COLORS = {
    low: 'risk-low',
    medium: 'risk-medium',
    high: 'risk-high',
    extreme: 'risk-extreme'
};

function formatCurrency(value) {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return currencyFormatter.format(0);
    }
    return currencyFormatter.format(value);
}

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
                <h4 class="font-bold text-lg text-gray-700 mb-3">Impacto financeiro projetado</h4>
                <div class="cost-grid">
                    <div class="cost-pill repair">
                        <span class="cost-label"><i class="fas fa-hammer"></i> Reparo estimado</span>
                        <span class="cost-value">${formatCurrency(repairCost)}</span>
                        <small>Infraestrutura e manutenção</small>
                    </div>
                    <div class="cost-pill legal">
                        <span class="cost-label"><i class="fas fa-scale-balanced"></i> Exposição jurídica</span>
                        <span class="cost-value">${formatCurrency(baseIndemnization)}</span>
                        <small>Indenizações e acordos</small>
                    </div>
                </div>
                <div class="cost-total-card">
                    <div>
                        <p>Total projetado</p>
                        <h3>${formatCurrency(repairCost + baseIndemnization)}</h3>
                        <small>Considerando probabilidade IRL ${irlScore}%</small>
                    </div>
                    <span class="badge-soft">${riskLevel}</span>
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
    const totalRepairCost = processedOccurrences.reduce((sum, item) => sum + (item.repairCost || 0), 0);
    const totalIndemnizations = processedOccurrences.reduce((sum, item) => sum + (item.baseIndemnization || 0), 0);
    const totalFinanceImpact = totalRepairCost + totalIndemnizations;
    const mediaRepairCost = totalOccurrences > 0 ? (totalRepairCost / totalOccurrences) : 0;
    const mediaFinanceImpact = totalOccurrences > 0 ? (totalFinanceImpact / totalOccurrences) : 0;

    const totalOS = totalOccurrences; // Usando as ocorrências filtradas

    if (document.getElementById('kpi-impacto-total')) {
        document.getElementById('kpi-impacto-total').textContent = formatCurrency(totalFinanceImpact);
        document.getElementById('kpi-impacto-medio').textContent = `Média por ocorrência — ${formatCurrency(mediaFinanceImpact)}`;
    }
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
                value = formatCurrency((item.repairCost || 0) + (item.baseIndemnization || 0));
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
        const normalizedTerm = currentSearchTerm.toLowerCase();
        const searchMatch = !currentSearchTerm ||
                            (item.title || '').toLowerCase().includes(normalizedTerm) ||
                            (item.location || '').toLowerCase().includes(normalizedTerm) ||
                            (item.bairro || '').toLowerCase().includes(normalizedTerm) ||
                            (item.numero_os && item.numero_os.toLowerCase().includes(normalizedTerm));

        // Filtro de Status da OS
        const statusMatch = currentStatusFilter === 'Todos' || item.osStatus === currentStatusFilter;

        // Filtro de Categoria
        const categoriaMatch = currentCategoriaFilter === 'Todos' || item.category === currentCategoriaFilter || item.categoryLabel === currentCategoriaFilter;

        // Filtro de Bairro
        const bairroMatch = currentBairroFilter === 'Todos' || (item.bairro && item.bairro.toLowerCase() === currentBairroFilter.toLowerCase());

        // Filtro de risco
        let riskMatch = true;
        if (currentRiskFilter !== 'Todos') {
            if (currentRiskFilter === 'extremo') riskMatch = item.irlScore >= 86;
            else if (currentRiskFilter === 'alto') riskMatch = item.irlScore >= 61 && item.irlScore <= 85;
            else if (currentRiskFilter === 'medio') riskMatch = item.irlScore >= 31 && item.irlScore <= 60;
            else if (currentRiskFilter === 'baixo') riskMatch = item.irlScore <= 30;
        }

        const irlRangeMatch = item.irlScore >= currentIRLRange[0] && item.irlScore <= currentIRLRange[1];

        const totalCost = (item.repairCost || 0) + (item.baseIndemnization || 0);
        const costRangeMatch = totalCost >= currentCostRange[0] && totalCost <= currentCostRange[1];

        return searchMatch && statusMatch && categoriaMatch && bairroMatch && riskMatch && irlRangeMatch && costRangeMatch;
    });
}

function populateBairroFilter() {
    const bairroSelect = document.getElementById('filtroBairro');
    if (!bairroSelect) return;
    const bairros = Array.from(new Set(processedOccurrences.map(item => item.bairro).filter(Boolean))).sort();
    const options = ['<option value="Todos">Todos os bairros</option>', ...bairros.map(b => `<option value="${b}">${b}</option>`)];
    bairroSelect.innerHTML = options.join('');
}

function calibrateCostSlider() {
    const costValues = processedOccurrences.map(item => (item.repairCost || 0) + (item.baseIndemnization || 0));
    const maxCost = costValues.length ? Math.max(...costValues) : 50000;
    dynamicCostUpperBound = Math.max(5000, Math.ceil(maxCost / 1000) * 1000);
    const costMinInput = document.getElementById('filtroCustoMin');
    const costMaxInput = document.getElementById('filtroCustoMax');
    if (costMinInput && costMaxInput) {
        costMinInput.max = dynamicCostUpperBound;
        costMaxInput.max = dynamicCostUpperBound;
        costMaxInput.value = dynamicCostUpperBound;
    }
    currentCostRange = [0, dynamicCostUpperBound];
    updateCostRangeLabel();
}

function updateIRLRangeLabel() {
    const label = document.getElementById('rangeIrlLabel');
    if (label) {
        label.textContent = `${currentIRLRange[0]} - ${currentIRLRange[1]} pts`;
    }
}

function updateCostRangeLabel() {
    const label = document.getElementById('rangeCustoLabel');
    if (label) {
        label.textContent = `${formatCurrency(currentCostRange[0])} - ${formatCurrency(currentCostRange[1])}`;
    }
}

function setupRangeInputs(minId, maxId, callback) {
    const minInput = document.getElementById(minId);
    const maxInput = document.getElementById(maxId);
    if (!minInput || !maxInput) return;

    const handler = (event) => {
        let min = Number(minInput.value);
        let max = Number(maxInput.value);
        if (min > max) {
            if (event.target === minInput) {
                max = min;
                maxInput.value = max;
            } else {
                min = max;
                minInput.value = min;
            }
        }
        callback([min, max]);
    };

    minInput.addEventListener('input', handler);
    maxInput.addEventListener('input', handler);
}

function handlePillGroup(containerId, callback) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.querySelectorAll('.pill-filter').forEach(button => {
        button.addEventListener('click', () => {
            container.querySelectorAll('.pill-filter').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            callback(button.getAttribute('data-value'));
        });
    });
}

function setActivePill(containerId, value) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.querySelectorAll('.pill-filter').forEach(button => {
        if (button.getAttribute('data-value') === value) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });
}

function resetFilters(skipRender = false) {
    currentStatusFilter = 'Todos';
    currentRiskFilter = 'Todos';
    currentCategoriaFilter = 'Todos';
    currentBairroFilter = 'Todos';
    currentIRLRange = [0, 100];
    currentCostRange = [0, dynamicCostUpperBound];
    currentSearchTerm = '';

    const searchInput = document.getElementById('filtroBusca');
    if (searchInput) searchInput.value = '';

    const categoriaSelect = document.getElementById('filtroCategoria');
    if (categoriaSelect) categoriaSelect.value = 'Todos';

    const bairroSelect = document.getElementById('filtroBairro');
    if (bairroSelect) bairroSelect.value = 'Todos';

    const irlMinInput = document.getElementById('filtroIrlMin');
    const irlMaxInput = document.getElementById('filtroIrlMax');
    if (irlMinInput && irlMaxInput) {
        irlMinInput.value = currentIRLRange[0];
        irlMaxInput.value = currentIRLRange[1];
    }
    updateIRLRangeLabel();

    const costMinInput = document.getElementById('filtroCustoMin');
    const costMaxInput = document.getElementById('filtroCustoMax');
    if (costMinInput && costMaxInput) {
        costMinInput.value = currentCostRange[0];
        costMaxInput.value = currentCostRange[1];
        costMinInput.max = dynamicCostUpperBound;
        costMaxInput.max = dynamicCostUpperBound;
    }
    updateCostRangeLabel();

    setActivePill('statusFilters', 'Todos');
    setActivePill('riskFilters', 'Todos');

    if (!skipRender) {
        applyFiltersAndRender();
    }
}

function setupFilterInteractions() {
    const searchInput = document.getElementById('filtroBusca');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            currentSearchTerm = e.target.value.trim();
            applyFiltersAndRender();
        });
    }

    const categoriaSelect = document.getElementById('filtroCategoria');
    if (categoriaSelect) {
        categoriaSelect.addEventListener('change', (e) => {
            currentCategoriaFilter = e.target.value;
            applyFiltersAndRender();
        });
    }

    const bairroSelect = document.getElementById('filtroBairro');
    if (bairroSelect) {
        bairroSelect.addEventListener('change', (e) => {
            currentBairroFilter = e.target.value;
            applyFiltersAndRender();
        });
    }

    const resetButton = document.getElementById('btnLimparFiltros');
    if (resetButton) {
        resetButton.addEventListener('click', () => resetFilters());
    }

    handlePillGroup('statusFilters', (value) => {
        currentStatusFilter = value;
        applyFiltersAndRender();
    });

    handlePillGroup('riskFilters', (value) => {
        currentRiskFilter = value;
        applyFiltersAndRender();
    });

    setupRangeInputs('filtroIrlMin', 'filtroIrlMax', (range) => {
        currentIRLRange = range;
        updateIRLRangeLabel();
        applyFiltersAndRender();
    });

    setupRangeInputs('filtroCustoMin', 'filtroCustoMax', (range) => {
        currentCostRange = range;
        updateCostRangeLabel();
        applyFiltersAndRender();
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
            populateBairroFilter();
            calibrateCostSlider();
            resetFilters(true);
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

    setupFilterInteractions();

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