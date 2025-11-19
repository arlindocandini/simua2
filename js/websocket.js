// WebSocket para atualizações em tempo real

let socket;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// Inicializar conexão
document.addEventListener('DOMContentLoaded', function() {
    conectarWebSocket();
});

function conectarWebSocket() {
    // Conectar ao servidor Socket.IO
    socket = io({
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: MAX_RECONNECT_ATTEMPTS
    });
    
    // Eventos de conexão
    socket.on('connect', function() {
        console.log('✅ WebSocket conectado');
        reconnectAttempts = 0;
        mostrarStatusConexao('online');
    });
    
    socket.on('disconnect', function() {
        console.log('❌ WebSocket desconectado');
        mostrarStatusConexao('offline');
    });
    
    socket.on('connect_error', function(error) {
        console.error('❌ Erro de conexão:', error);
        reconnectAttempts++;
        
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            console.error('❌ Máximo de tentativas de reconexão atingido');
            mostrarStatusConexao('erro');
        }
    });
    
    socket.on('reconnect', function(attemptNumber) {
        console.log(`✅ Reconectado após ${attemptNumber} tentativa(s)`);
        mostrarStatusConexao('online');
    });
    
    // Eventos de negócio
    registrarEventos();
}

function registrarEventos() {
    // Nova ocorrência
    socket.on('nova_ocorrencia', function(data) {
        console.log('🆕 Nova ocorrência:', data);

        const ocorrencias = normalizarOcorrencias(data);

        ocorrencias.forEach(function(item) {
            // Atualizar contador
            incrementarContador('ocorrencias');

            // Mostrar notificação
            mostrarNotificacao(
                'Nova Ocorrência Detectada',
                `${formatarCategoria(item.categoria)} - ${formatarUrgencia(item.urgencia)}`,
                item.urgencia === 'emergencia' ? 'danger' : 'warning'
            );

            // Adicionar ao mapa se estiver visível
            if (typeof adicionarMarcadorMapa === 'function') {
                adicionarMarcadorMapa(item);
            }

            // Atualizar dashboard se estiver visível
            if (typeof atualizarDashboard === 'function') {
                atualizarDashboard();
            }

            // Tocar som de notificação (apenas para emergência)
            if (item.urgencia === 'emergencia') {
                tocarSomNotificacao();
            }
        });
    });
    
    // Nova OS
    socket.on('nova_os', function(data) {
        console.log('📋 Nova OS:', data);
        
        incrementarContador('os');
        
        mostrarNotificacao(
            'Nova Ordem de Serviço',
            `OS #${data.numero_os} criada`,
            'info'
        );
        
        if (typeof atualizarDashboard === 'function') {
            atualizarDashboard();
        }
    });
    
    // OS atualizada
    socket.on('os_atualizada', function(data) {
        console.log('📝 OS atualizada:', data);
        
        // Se for do usuário atual, notificar
        if (data.responsavel_id === usuarioAtualId) {
            mostrarNotificacao(
                'OS Atualizada',
                `OS #${data.numero_os} foi atualizada`,
                'info'
            );
        }
        
        // Atualizar página de detalhes se estiver aberta
        if (window.location.pathname.includes(`/os/${data.id}`)) {
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
    });
    
    // Câmera offline
    socket.on('camera_offline', function(data) {
        console.log('📹 Câmera offline:', data);
        
        mostrarNotificacao(
            'Câmera Offline',
            `${data.nome} está offline`,
            'warning'
        );
    });
    
    // Notificação genérica
    socket.on('notificacao', function(data) {
        console.log('🔔 Notificação:', data);
        
        mostrarNotificacao(data.titulo, data.mensagem, data.tipo || 'info');
        
        // Atualizar badge de notificações
        atualizarBadgeNotificacoes();
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

// Funções auxiliares

function mostrarStatusConexao(status) {
    let statusElement = document.getElementById('websocket-status');
    
    if (!statusElement) {
        // Criar elemento de status se não existir
        statusElement = document.createElement('div');
        statusElement.id = 'websocket-status';
        statusElement.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            z-index: 9999;
            transition: all 0.3s ease;
            display: none;
        `;
        document.body.appendChild(statusElement);
    }
    
    if (status === 'online') {
        statusElement.style.display = 'block';
        statusElement.style.background = '#4CAF50';
        statusElement.style.color = 'white';
        statusElement.innerHTML = '🟢 Conectado';
        
        // Esconder após 3 segundos
        setTimeout(() => {
            statusElement.style.display = 'none';
        }, 3000);
    } else if (status === 'offline') {
        statusElement.style.display = 'block';
        statusElement.style.background = '#FF4C4C';
        statusElement.style.color = 'white';
        statusElement.innerHTML = '🔴 Desconectado';
    } else if (status === 'erro') {
        statusElement.style.display = 'block';
        statusElement.style.background = '#FFA500';
        statusElement.style.color = 'white';
        statusElement.innerHTML = '⚠️ Erro de conexão';
    }
}

function mostrarNotificacao(titulo, mensagem, tipo = 'info') {
    // Criar elemento de notificação toast
    const toast = document.createElement('div');
    toast.className = `toast toast-${tipo}`;
    toast.style.cssText = `
        position: fixed;
        top: 100px;
        right: 30px;
        min-width: 300px;
        max-width: 400px;
        background: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 9999;
        animation: slideInRight 0.3s ease;
        border-left: 4px solid ${getTipoColor(tipo)};
    `;
    
    toast.innerHTML = `
        <div style="display: flex; align-items: start; gap: 10px;">
            <div style="font-size: 20px;">${getTipoIcon(tipo)}</div>
            <div style="flex: 1;">
                <strong style="display: block; margin-bottom: 5px;">${titulo}</strong>
                <p style="margin: 0; font-size: 14px; color: #666;">${mensagem}</p>
            </div>
            <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; font-size: 20px; cursor: pointer; opacity: 0.5;">×</button>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Remover após 5 segundos
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function getTipoColor(tipo) {
    const cores = {
        'success': '#4CAF50',
        'danger': '#FF4C4C',
        'warning': '#FFD700',
        'info': '#1E90FF'
    };
    return cores[tipo] || cores.info;
}

function getTipoIcon(tipo) {
    const icones = {
        'success': '✅',
        'danger': '🚨',
        'warning': '⚠️',
        'info': 'ℹ️'
    };
    return icones[tipo] || icones.info;
}

function incrementarContador(tipo) {
    const elemento = document.getElementById(`contador-${tipo}`);
    if (elemento) {
        const atual = parseInt(elemento.textContent) || 0;
        elemento.textContent = atual + 1;
        
        // Animação de pulso
        elemento.style.transform = 'scale(1.3)';
        setTimeout(() => {
            elemento.style.transform = 'scale(1)';
        }, 300);
    }
}

function tocarSomNotificacao() {
    // Tocar som apenas se usuário permitir
    try {
        const audio = new Audio('/static/sounds/notification.mp3');
        audio.volume = 0.3;
        audio.play().catch(e => console.log('Áudio bloqueado pelo navegador'));
    } catch (e) {
        console.log('Erro ao tocar som:', e);
    }
}

async function atualizarBadgeNotificacoes() {
    try {
        const response = await fetch('/api/notificacoes?nao_lidas=true');
        const data = await response.json();
        
        const badge = document.getElementById('notificationCount');
        if (badge) {
            const count = data.nao_lidas;
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.classList.add('show');
            } else {
                badge.classList.remove('show');
            }
        }
    } catch (error) {
        console.error('Erro ao atualizar badge de notificações:', error);
    }
}

// Funções de formatação
function formatarCategoria(categoria) {
    const map = {
        'buraco': 'Buraco na Pista',
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

// Adicionar estilos de animação
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Expor função para uso externo
window.emitirEvento = function(evento, dados) {
    if (socket && socket.connected) {
        socket.emit(evento, dados);
    } else {
        console.warn('WebSocket não está conectado');
    }
};

console.log('📡 WebSocket inicializado');