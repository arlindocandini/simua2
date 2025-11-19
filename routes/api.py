from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import desc, func
from app import db
from app.models import Ocorrencia, OrdemServico, Camera, Equipe, User, Notificacao
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__)

# ========== OCORRÊNCIAS ==========

@api_bp.route('/ocorrencias', methods=['GET'])
@login_required
def api_listar_ocorrencias():
    """Lista ocorrências (com paginação e filtros) - ATUALIZADO com filtro sem_ocorrencias"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    limit = request.args.get('limit', type=int)
    sort = request.args.get('sort', 'desc')
    
    # Filtros
    status = request.args.get('status')
    categoria = request.args.get('categoria')
    urgencia = request.args.get('urgencia')
    
    # 🔹 NOVO: Filtro para incluir/excluir sem_ocorrencias
    incluir_sem_ocorrencias = request.args.get('incluir_sem_ocorrencias', 'false').lower() == 'true'
    
    # Query
    query = Ocorrencia.query
    
    # 🔹 NOVO: Por padrão, ocultar sem_ocorrencias (exceto se filtrado especificamente)
    if not incluir_sem_ocorrencias and categoria != 'sem_ocorrencias':
        query = query.filter(Ocorrencia.categoria != 'sem_ocorrencias')
    
    if status:
        query = query.filter(Ocorrencia.status == status)
    if categoria:
        query = query.filter(Ocorrencia.categoria == categoria)
    if urgencia:
        query = query.filter(Ocorrencia.urgencia == urgencia)
    
    # Ordenação
    if sort == 'asc':
        query = query.order_by(Ocorrencia.created_at)
    else:
        query = query.order_by(desc(Ocorrencia.created_at))
    
    # Limite ou paginação
    if limit:
        ocorrencias = query.limit(limit).all()
        return jsonify([occ.to_dict() for occ in ocorrencias])
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            'items': [occ.to_dict() for occ in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })

@api_bp.route('/ocorrencias/<uuid:id>', methods=['GET'])
@login_required
def api_obter_ocorrencia(id):
    """Obtém detalhes de uma ocorrência"""
    ocorrencia = Ocorrencia.query.get_or_404(id)
    return jsonify(ocorrencia.to_dict())

@api_bp.route('/ocorrencias/<uuid:id>', methods=['DELETE'])
@login_required
def api_deletar_ocorrencia(id):
    """Deleta uma ocorrência"""
    if not current_user.is_gestor:
        return jsonify({'erro': 'Permissão negada'}), 403
    
    ocorrencia = Ocorrencia.query.get_or_404(id)
    
    # Verificar se tem OS
    if ocorrencia.ordem_servico:
        return jsonify({'erro': 'Não é possível deletar ocorrência com OS associada'}), 400
    
    try:
        db.session.delete(ocorrencia)
        db.session.commit()
        return jsonify({'mensagem': 'Ocorrência deletada com sucesso'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500

# ========== ORDENS DE SERVIÇO ==========

@api_bp.route('/os', methods=['GET'])
@login_required
def api_listar_os():
    """Lista ordens de serviço"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    limit = request.args.get('limit', type=int)
    
    # Filtros
    status = request.args.get('status')
    prioridade = request.args.get('prioridade')
    equipe_id = request.args.get('equipe_id')
    
    # Query (filtrar por tipo de usuário)
    if current_user.is_campo:
        query = OrdemServico.query.filter(
            (OrdemServico.responsavel_campo_id == current_user.id) |
            (OrdemServico.equipe_id == current_user.equipe_id)
        )
    else:
        query = OrdemServico.query
    
    # Filtros adicionais
    if status:
        # Suporta múltiplos status separados por vírgula
        status_list = status.split(',')
        query = query.filter(OrdemServico.status.in_(status_list))
    
    if prioridade:
        prioridade_list = prioridade.split(',')
        query = query.filter(OrdemServico.prioridade.in_(prioridade_list))
    
    if equipe_id:
        query = query.filter(OrdemServico.equipe_id == equipe_id)
    
    # Ordenar
    query = query.order_by(desc(OrdemServico.created_at))
    
    # Limite ou paginação
    if limit:
        ordens = query.limit(limit).all()
        return jsonify([os.to_dict() for os in ordens])
    else:
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({
            'items': [os.to_dict() for os in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })

@api_bp.route('/os/<uuid:id>', methods=['GET'])
@login_required
def api_obter_os(id):
    """Obtém detalhes de uma OS"""
    os = OrdemServico.query.get_or_404(id)
    
    # Verificar permissão
    if current_user.is_campo:
        if os.responsavel_campo_id != current_user.id and os.equipe_id != current_user.equipe_id:
            return jsonify({'erro': 'Acesso negado'}), 403
    
    return jsonify(os.to_dict())

# ========== CÂMERAS ==========

@api_bp.route('/cameras', methods=['GET'])
@login_required
def api_listar_cameras():
    """Lista câmeras"""
    cameras = Camera.query.filter_by(ativa=True).all()
    return jsonify([camera.to_dict() for camera in cameras])

@api_bp.route('/cameras/<uuid:id>', methods=['GET'])
@login_required
def api_obter_camera(id):
    """Obtém detalhes de uma câmera"""
    camera = Camera.query.get_or_404(id)
    return jsonify(camera.to_dict())

@api_bp.route('/cameras/<uuid:id>/status', methods=['GET'])
@login_required
def api_status_camera(id):
    """Verifica status da câmera"""
    camera = Camera.query.get_or_404(id)
    
    # Verificar se última captura < 5 min
    if camera.ultima_captura_at:
        diff = datetime.utcnow() - camera.ultima_captura_at
        online = diff.total_seconds() < 300
    else:
        online = False
    
    return jsonify({
        'id': str(camera.id),
        'nome': camera.nome,
        'status': camera.status,
        'online': online,
        'ultima_captura': camera.ultima_captura_at.isoformat() if camera.ultima_captura_at else None
    })

# ========== EQUIPES ==========

@api_bp.route('/equipes', methods=['GET'])
@login_required
def api_listar_equipes():
    """Lista equipes ativas"""
    equipes = Equipe.query.filter_by(ativa=True).all()
    return jsonify([equipe.to_dict() for equipe in equipes])

@api_bp.route('/equipes/<uuid:id>/membros', methods=['GET'])
@login_required
def api_membros_equipe(id):
    """Lista membros de uma equipe"""
    equipe = Equipe.query.get_or_404(id)
    membros = User.query.filter_by(equipe_id=id, ativo=True).all()
    
    return jsonify({
        'equipe': equipe.to_dict(),
        'membros': [user.to_dict() for user in membros]
    })

# ========== NOTIFICAÇÕES ==========

@api_bp.route('/notificacoes', methods=['GET'])
@login_required
def api_listar_notificacoes():
    """Lista notificações do usuário"""
    limit = request.args.get('limit', 10, type=int)
    apenas_nao_lidas = request.args.get('nao_lidas', 'false').lower() == 'true'
    
    query = Notificacao.query.filter_by(usuario_id=current_user.id)
    
    if apenas_nao_lidas:
        query = query.filter_by(lida=False)
    
    notificacoes = query.order_by(desc(Notificacao.created_at)).limit(limit).all()
    
    # Contar não lidas
    nao_lidas = Notificacao.query.filter_by(
        usuario_id=current_user.id,
        lida=False
    ).count()
    
    return jsonify({
        'notificacoes': [notif.to_dict() for notif in notificacoes],
        'nao_lidas': nao_lidas
    })

@api_bp.route('/notificacoes/<uuid:id>/ler', methods=['POST'])
@login_required
def api_marcar_notificacao_lida(id):
    """Marca notificação como lida"""
    notificacao = Notificacao.query.get_or_404(id)
    
    if notificacao.usuario_id != current_user.id:
        return jsonify({'erro': 'Acesso negado'}), 403
    
    notificacao.marcar_como_lida()
    return jsonify({'mensagem': 'Notificação marcada como lida'})

@api_bp.route('/notificacoes/marcar-todas-lidas', methods=['POST'])
@login_required
def api_marcar_todas_lidas():
    """Marca todas as notificações como lidas"""
    Notificacao.query.filter_by(
        usuario_id=current_user.id,
        lida=False
    ).update({'lida': True})
    
    db.session.commit()
    
    return jsonify({'mensagem': 'Todas as notificações marcadas como lidas'})

# ========== ESTATÍSTICAS ==========

@api_bp.route('/estatisticas/resumo', methods=['GET'])
@login_required
def api_estatisticas_resumo():
    """Estatísticas gerais do sistema - ATUALIZADO para excluir sem_ocorrencias"""
    hoje = datetime.now().date()
    inicio_mes = datetime(hoje.year, hoje.month, 1)
    
    stats = {
        'ocorrencias': {
            'total': Ocorrencia.query.filter(Ocorrencia.categoria != 'sem_ocorrencias').count(),
            'hoje': Ocorrencia.query.filter(
                func.date(Ocorrencia.created_at) == hoje,
                Ocorrencia.categoria != 'sem_ocorrencias'
            ).count(),
            'mes_atual': Ocorrencia.query.filter(
                Ocorrencia.created_at >= inicio_mes,
                Ocorrencia.categoria != 'sem_ocorrencias'
            ).count(),
            'pendentes': Ocorrencia.query.filter_by(
                status='pendente'
            ).filter(
                Ocorrencia.categoria != 'sem_ocorrencias'
            ).count(),
            'sem_ocorrencias': Ocorrencia.query.filter_by(categoria='sem_ocorrencias').count()
        },
        'os': {
            'total': OrdemServico.query.count(),
            'ativas': OrdemServico.query.filter(
                OrdemServico.status.in_(['criada', 'atribuida', 'em_andamento'])
            ).count(),
            'aguardando_aprovacao': OrdemServico.query.filter_by(
                status='aguardando_aprovacao'
            ).count(),
            'concluidas_mes': OrdemServico.query.filter(
                OrdemServico.status == 'aprovada',
                OrdemServico.data_aprovacao >= inicio_mes
            ).count()
        },
        'cameras': {
            'total': Camera.query.filter_by(ativa=True).count(),
            'online': Camera.query.filter_by(status='online').count(),
            'offline': Camera.query.filter_by(status='offline').count()
        }
    }
    
    return jsonify(stats)

@api_bp.route('/estatisticas/grafico-temporal', methods=['GET'])
@login_required
def api_grafico_temporal():
    """Dados para gráfico temporal de ocorrências e OS"""
    dias = request.args.get('dias', 30, type=int)
    
    data_fim = datetime.now()
    data_inicio = data_fim - timedelta(days=dias)
    
    # Ocorrências por dia (excluindo sem_ocorrencias)
    ocorrencias_por_dia = db.session.query(
        func.date(Ocorrencia.created_at).label('data'),
        func.count(Ocorrencia.id).label('total')
    ).filter(
        Ocorrencia.created_at >= data_inicio,
        Ocorrencia.created_at <= data_fim,
        Ocorrencia.categoria != 'sem_ocorrencias'
    ).group_by(func.date(Ocorrencia.created_at)).all()
    
    # OS por dia
    os_por_dia = db.session.query(
        func.date(OrdemServico.created_at).label('data'),
        func.count(OrdemServico.id).label('total')
    ).filter(
        OrdemServico.created_at >= data_inicio,
        OrdemServico.created_at <= data_fim
    ).group_by(func.date(OrdemServico.created_at)).all()
    
    return jsonify({
        'ocorrencias': [
            {'data': str(data), 'total': total}
            for data, total in ocorrencias_por_dia
        ],
        'os': [
            {'data': str(data), 'total': total}
            for data, total in os_por_dia
        ]
    })

# ========== MAPA ==========

@api_bp.route('/mapa/pontos', methods=['GET'])
@login_required
def api_pontos_mapa():
    """Retorna pontos para exibição no mapa - ATUALIZADO com filtro sem_ocorrencias"""
    tipo = request.args.get('tipo', 'todos')  # ocorrencias, os, todos
    incluir_sem_ocorrencias = request.args.get('incluir_sem_ocorrencias', 'false').lower() == 'true'
    
    pontos = []
    
    if tipo in ['ocorrencias', 'todos']:
        # Ocorrências pendentes
        query = Ocorrencia.query.filter(
            Ocorrencia.status.in_(['pendente', 'em_os'])
        )
        
        # Filtrar sem_ocorrencias por padrão
        if not incluir_sem_ocorrencias:
            query = query.filter(Ocorrencia.categoria != 'sem_ocorrencias')
        
        ocorrencias = query.all()
        
        for occ in ocorrencias:
            pontos.append({
                'tipo': 'ocorrencia',
                'id': str(occ.id),
                'latitude': float(occ.latitude),
                'longitude': float(occ.longitude),
                'categoria': occ.categoria,
                'urgencia': occ.urgencia,
                'status': occ.status,
                'endereco': occ.endereco_completo,
                'imagem_url': occ.imagem_miniatura_path
            })
    
    if tipo in ['os', 'todos']:
        # OS em andamento
        ordens = OrdemServico.query.filter(
            OrdemServico.status.in_(['criada', 'atribuida', 'em_andamento', 'aguardando_aprovacao'])
        ).all()
        
        for os in ordens:
            pontos.append({
                'tipo': 'os',
                'id': str(os.id),
                'numero_os': os.numero_os,
                'latitude': float(os.latitude),
                'longitude': float(os.longitude),
                'categoria': os.categoria,
                'prioridade': os.prioridade,
                'status': os.status,
                'endereco': os.endereco_completo
            })
    
    return jsonify(pontos)

# ========== BUSCA ==========

@api_bp.route('/busca', methods=['GET'])
@login_required
def api_busca_global():
    """Busca global no sistema"""
    q = request.args.get('q', '')
    
    if len(q) < 3:
        return jsonify({'erro': 'Query muito curta (mínimo 3 caracteres)'}), 400
    
    resultados = {
        'ocorrencias': [],
        'os': [],
        'usuarios': []
    }
    
    # Buscar ocorrências (excluindo sem_ocorrencias)
    ocorrencias = Ocorrencia.query.filter(
        Ocorrencia.endereco_completo.ilike(f'%{q}%'),
        Ocorrencia.categoria != 'sem_ocorrencias'
    ).limit(10).all()
    resultados['ocorrencias'] = [occ.to_dict() for occ in ocorrencias]
    
    # Buscar OS
    ordens = OrdemServico.query.filter(
        (OrdemServico.numero_os.ilike(f'%{q}%')) |
        (OrdemServico.endereco_completo.ilike(f'%{q}%'))
    ).limit(10).all()
    resultados['os'] = [os.to_dict() for os in ordens]
    
    # Buscar usuários (apenas admin/gestor)
    if current_user.is_admin or current_user.is_gestor:
        usuarios = User.query.filter(
            (User.nome_completo.ilike(f'%{q}%')) |
            (User.email.ilike(f'%{q}%'))
        ).limit(10).all()
        resultados['usuarios'] = [user.to_dict() for user in usuarios]
    
    return jsonify(resultados)

# ========== HEALTH CHECK ==========

@api_bp.route('/health', methods=['GET'])
def api_health():
    """Verifica saúde do sistema"""
    try:
        # Testar conexão com banco
        db.session.execute('SELECT 1')
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'disconnected',
            'erro': str(e)
        }), 500
    

    # ========================================
# ADICIONAR AO FINAL DO ARQUIVO app/routes/api.py
# ========================================

# ========================================
# DASHBOARD API - MAPEAMENTOS
# ========================================

CATEGORIA_LABELS = {
    'asfalto_dano': 'Buracos e crateras',
    'calcada_dano': 'Buracos e crateras',
    'iluminacao_publica': 'Iluminação pública',
    'fiacao_exposta': 'Iluminação pública',
    'lixo_irregular': 'Lixo e entulho',
    'arvore_dano': 'Árvores e vegetação',
    'mato_alto': 'Árvores e vegetação',
    'placa_dano': 'Sinalização',
    'sinalizacao_apagada': 'Sinalização',
    'semaforo_defeito': 'Sinalização',
    'ponto_onibus_dano': 'Outros',
    'vazamento_agua': 'Outros',
    'bueiro_dano': 'Outros',
    'bueiro_entupido': 'Outros',
    'queimada': 'Outros',
    'obra_irregular': 'Outros',
    'fruta_na_pista': 'Outros',
    'objeto_na_pista': 'Outros',
    'animal_na_pista': 'Outros',
    'desconhecido': 'Outros'
}

CORES_CATEGORIAS = {
    'Buracos e crateras': '#EF4444',
    'Iluminação pública': '#F59E0B',
    'Sinalização': '#4F46E5',
    'Lixo e entulho': '#10B981',
    'Árvores e vegetação': '#8B5CF6',
    'Outros': '#06B6D4'
}

# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def obter_periodo_dashboard(periodo_param):
    """Retorna data_inicio e data_fim baseado no parâmetro de período"""
    from datetime import datetime, timedelta
    
    data_fim = datetime.now()
    
    if periodo_param == 'ano':
        data_inicio = datetime(data_fim.year, 1, 1)
    else:
        dias = int(periodo_param) if periodo_param.isdigit() else 30
        data_inicio = data_fim - timedelta(days=dias)
    
    return data_inicio, data_fim

def aplicar_filtros_dashboard(query, filtros):
    """Aplica filtros à query de ocorrências"""
    if filtros.get('tipo'):
        query = query.filter(Ocorrencia.categoria == filtros['tipo'])
    
    if filtros.get('prioridade'):
        query = query.filter(Ocorrencia.urgencia == filtros['prioridade'])
    
    if filtros.get('status'):
        query = query.filter(Ocorrencia.status == filtros['status'])
    
    if filtros.get('regiao'):
        query = query.filter(Ocorrencia.endereco_completo.ilike(f'%{filtros["regiao"]}%'))
    
    return query

def calcular_trend(valor_atual, valor_anterior):
    """Calcula a variação percentual"""
    if valor_anterior == 0:
        return 100.0 if valor_atual > 0 else 0.0
    return ((valor_atual - valor_anterior) / valor_anterior) * 100

# ========================================
# ENDPOINT 1: ESTATÍSTICAS DO DASHBOARD
# ========================================

@api_bp.route('/dashboard/stats')
@login_required
def dashboard_stats():
    """Retorna estatísticas principais do dashboard"""
    from datetime import datetime, timedelta
    
    try:
        # Obter período
        periodo = request.args.get('periodo', '30')
        data_inicio, data_fim = obter_periodo_dashboard(periodo)
        
        # Período anterior para comparação
        diferenca_dias = (data_fim - data_inicio).days
        data_inicio_anterior = data_inicio - timedelta(days=diferenca_dias)
        data_fim_anterior = data_inicio
        
        # Query base
        query_atual = Ocorrencia.query.filter(
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim
        )
        
        query_anterior = Ocorrencia.query.filter(
            Ocorrencia.created_at >= data_inicio_anterior,
            Ocorrencia.created_at < data_fim_anterior
        )
        
        # Total de ocorrências
        total_atual = query_atual.count()
        total_anterior = query_anterior.count()
        total_trend = calcular_trend(total_atual, total_anterior)
        
        # Críticas (emergência + urgente)
        criticas_atual = query_atual.filter(
            Ocorrencia.urgencia.in_(['emergencia', 'urgente'])
        ).count()
        criticas_anterior = query_anterior.filter(
            Ocorrencia.urgencia.in_(['emergencia', 'urgente'])
        ).count()
        criticas_trend = calcular_trend(criticas_atual, criticas_anterior)
        
        # Aguardando validação (pendente + validada)
        aguardando_atual = query_atual.filter(
            Ocorrencia.status.in_(['pendente', 'validada'])
        ).count()
        aguardando_anterior = query_anterior.filter(
            Ocorrencia.status.in_(['pendente', 'validada'])
        ).count()
        aguardando_trend = calcular_trend(aguardando_atual, aguardando_anterior)
        
        # Resolvidas nos últimos 30 dias
        data_inicio_30 = datetime.now() - timedelta(days=30)
        resolvidas_30 = Ocorrencia.query.filter(
            Ocorrencia.status == 'resolvida',
            Ocorrencia.updated_at >= data_inicio_30
        ).count()
        
        # Resolvidas no período anterior para trend
        data_inicio_60 = datetime.now() - timedelta(days=60)
        resolvidas_anterior = Ocorrencia.query.filter(
            Ocorrencia.status == 'resolvida',
            Ocorrencia.updated_at >= data_inicio_60,
            Ocorrencia.updated_at < data_inicio_30
        ).count()
        resolvidas_trend = calcular_trend(resolvidas_30, resolvidas_anterior)
        
        return jsonify({
            'total_ocorrencias': total_atual,
            'total_ocorrencias_trend': total_trend,
            'criticas_urgente': criticas_atual,
            'criticas_urgente_trend': criticas_trend,
            'aguardando_validacao': aguardando_atual,
            'aguardando_validacao_trend': aguardando_trend,
            'resolvidas_30dias': resolvidas_30,
            'resolvidas_30dias_trend': resolvidas_trend
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# ENDPOINT 2: MAPA DE OCORRÊNCIAS
# ========================================

@api_bp.route('/dashboard/mapa/ocorrencias')
@login_required
def dashboard_mapa_ocorrencias():
    """Retorna dados de ocorrências para exibição no mapa"""
    try:
        # Obter filtros
        filtros = {
            'tipo': request.args.get('tipo'),
            'prioridade': request.args.get('prioridade'),
            'status': request.args.get('status'),
            'regiao': request.args.get('regiao')
        }
        
        # Obter período
        periodo = request.args.get('periodo', '30')
        data_inicio, data_fim = obter_periodo_dashboard(periodo)
        
        # Query base
        query = Ocorrencia.query.filter(
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim,
            Ocorrencia.latitude.isnot(None),
            Ocorrencia.longitude.isnot(None)
        )
        
        # Aplicar filtros
        query = aplicar_filtros_dashboard(query, filtros)
        
        # Limitar a 500 ocorrências para performance
        ocorrencias = query.limit(500).all()
        
        resultado = []
        for oc in ocorrencias:
            # Extrair endereço resumido
            endereco_resumido = oc.endereco_completo.split(',')[0] if oc.endereco_completo else 'N/A'
            
            resultado.append({
                'id': str(oc.id),
                'latitude': float(oc.latitude),
                'longitude': float(oc.longitude),
                'categoria': oc.categoria,
                'urgencia': oc.urgencia,
                'status': oc.status,
                'endereco': endereco_resumido,
                'created_at': oc.created_at.isoformat()
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# ENDPOINT 3: OCORRÊNCIAS RECENTES
# ========================================

@api_bp.route('/dashboard/ocorrencias/recentes')
@login_required
def dashboard_ocorrencias_recentes():
    """Retorna as ocorrências mais recentes"""
    try:
        limit = request.args.get('limit', 5, type=int)
        
        ocorrencias = Ocorrencia.query.order_by(
            Ocorrencia.created_at.desc()
        ).limit(limit).all()
        
        resultado = []
        for oc in ocorrencias:
            # Extrair endereço resumido
            endereco_parts = oc.endereco_completo.split(',') if oc.endereco_completo else []
            endereco_resumido = ', '.join(endereco_parts[:2]) if len(endereco_parts) >= 2 else (endereco_parts[0] if endereco_parts else 'N/A')
            
            resultado.append({
                'id': str(oc.id),
                'numero': str(oc.id)[:8].upper(),
                'categoria': oc.categoria,
                'urgencia': oc.urgencia,
                'status': oc.status,
                'endereco_resumido': endereco_resumido,
                'created_at': oc.created_at.isoformat()
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# ENDPOINT 4: DADOS DOS GRÁFICOS
# ========================================

@api_bp.route('/dashboard/charts')
@login_required
def dashboard_charts():
    """Retorna dados para todos os gráficos"""
    from datetime import datetime, timedelta
    
    try:
        # Obter período
        periodo = request.args.get('periodo', '30')
        data_inicio, data_fim = obter_periodo_dashboard(periodo)
        
        # Obter filtros
        filtros = {
            'tipo': request.args.get('tipo'),
            'prioridade': request.args.get('prioridade'),
            'status': request.args.get('status'),
            'regiao': request.args.get('regiao')
        }
        
        # Query base
        query = Ocorrencia.query.filter(
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim
        )
        query = aplicar_filtros_dashboard(query, filtros)
        
        # 1. Por Tipo (agrupado)
        por_tipo_raw = db.session.query(
            Ocorrencia.categoria,
            func.count(Ocorrencia.id)
        ).filter(
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim
        ).group_by(Ocorrencia.categoria).all()
        
        # Agrupar categorias similares
        tipo_agrupado = {}
        for categoria, count in por_tipo_raw:
            grupo = CATEGORIA_LABELS.get(categoria, 'Outros')
            tipo_agrupado[grupo] = tipo_agrupado.get(grupo, 0) + count
        
        por_tipo = {
            'labels': list(tipo_agrupado.keys()),
            'data': list(tipo_agrupado.values()),
            'colors': [CORES_CATEGORIAS.get(label, '#94A3B8') for label in tipo_agrupado.keys()]
        }
        
        # 2. Por Prioridade
        por_prioridade_raw = db.session.query(
            Ocorrencia.urgencia,
            func.count(Ocorrencia.id)
        ).filter(
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim
        ).group_by(Ocorrencia.urgencia).all()
        
        urgencias_ordem = ['emergencia', 'urgente', 'pouco_urgente', 'nao_urgente']
        urgencias_labels = ['Crítica', 'Alta', 'Média', 'Baixa']
        urgencias_dict = {urg: count for urg, count in por_prioridade_raw}
        
        por_prioridade = {
            'labels': urgencias_labels,
            'data': [urgencias_dict.get(urg, 0) for urg in urgencias_ordem]
        }
        
        # 3. Evolução dos últimos 7 dias
        evolucao_labels = []
        evolucao_registradas = []
        evolucao_resolvidas = []
        
        for i in range(6, -1, -1):
            dia = datetime.now() - timedelta(days=i)
            dia_inicio = dia.replace(hour=0, minute=0, second=0, microsecond=0)
            dia_fim = dia.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Registradas no dia
            registradas = Ocorrencia.query.filter(
                Ocorrencia.created_at >= dia_inicio,
                Ocorrencia.created_at <= dia_fim
            ).count()
            
            # Resolvidas no dia
            resolvidas = Ocorrencia.query.filter(
                Ocorrencia.status == 'resolvida',
                Ocorrencia.updated_at >= dia_inicio,
                Ocorrencia.updated_at <= dia_fim
            ).count()
            
            # Label do dia
            dias_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
            label = dias_semana[dia.weekday()]
            
            evolucao_labels.append(label)
            evolucao_registradas.append(registradas)
            evolucao_resolvidas.append(resolvidas)
        
        evolucao = {
            'labels': evolucao_labels,
            'registradas': evolucao_registradas,
            'resolvidas': evolucao_resolvidas
        }
        
        return jsonify({
            'por_tipo': por_tipo,
            'por_prioridade': por_prioridade,
            'evolucao': evolucao
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# ENDPOINT 5: BADGES DA SIDEBAR
# ========================================

@api_bp.route('/dashboard/badges')
@login_required
def dashboard_badges():
    """Retorna contadores para os badges da sidebar"""
    try:
        # Ocorrências novas (pendentes)
        novas = Ocorrencia.query.filter(
            Ocorrencia.status == 'pendente'
        ).count()
        
        # Ocorrências em análise
        em_analise = Ocorrencia.query.filter(
            Ocorrencia.status == 'validada'
        ).count()
        
        # OS aguardando aprovação
        os_aguardando = OrdemServico.query.filter(
            OrdemServico.status == 'aguardando_aprovacao'
        ).count()
        
        return jsonify({
            'novas': novas,
            'em_analise': em_analise,
            'os_aguardando': os_aguardando,
            'total': novas + em_analise
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Alias para compatibilidade
@api_bp.route('/ocorrencias/count')
@login_required
def ocorrencias_count():
    """Endpoint alternativo para contagem (compatibilidade)"""
    return dashboard_badges()

# ========================================
# ENDPOINT 6: LISTA DE REGIÕES (BAIRROS)
# ========================================

@api_bp.route('/dashboard/regioes')
@login_required
def dashboard_regioes():
    """
    Retorna lista única de bairros/regiões encontrados nas ocorrências.
    Faz parsing inteligente do endereço retornado pelo OpenStreetMap,
    identificando o nome do bairro entre a rua e a cidade.
    """
    try:
        regioes_extraidas = set()

        # Busca endereços distintos
        enderecos = db.session.query(Ocorrencia.endereco_completo).distinct().all()

        for row in enderecos:
            endereco = row[0]
            if not endereco:
                continue

            partes = [p.strip() for p in endereco.split(',') if p.strip()]
            bairro = None

            # Tenta identificar “bairro” como elemento antes de "Goiânia" (ou outra cidade)
            for i, parte in enumerate(partes):
                if "Goiânia" in parte or "Trindade" in parte or "Aparecida" in parte:
                    if i > 0:
                        bairro = partes[i - 1]
                    break

            # Se não achou, tenta encontrar palavras que começam com "Setor" / "Jardim" / "Residencial"
            if not bairro:
                for parte in partes:
                    if any(palavra in parte for palavra in ["Setor", "Jardim", "Residencial", "Parque", "Vila"]):
                        bairro = parte
                        break

            if bairro and len(bairro) > 2:
                regioes_extraidas.add(bairro)

        regioes = sorted(regioes_extraidas)

        return jsonify({
            'status': 'success',
            'regioes': regioes,
            'total': len(regioes)
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@api_bp.route('/saude-ruas', methods=['GET'])
@login_required
def saude_ruas():
    """Calcula a nota de saúde das ruas"""
    try:
        # Agrupar por rua extraída do endereço
        ocorrencias = Ocorrencia.query.all()
        ruas = {}

        def extrair_rua(endereco):
            if not endereco:
                return "Desconhecido"
            return endereco.split(",")[0].strip()

        def extrair_bairro(endereco):
            """
            Extrai o bairro de endereços no formato:
            'Condomínio Edíficio Cézanne, 187, Rua 1026, Setor Pedro Ludovico, Goiânia...'
            'Rua 1024, Setor Pedro Ludovico, Goiânia...'
            'Avenida Rio Verde, Jardim das Esmeralda, Aparecida de Goiânia...'
            """
            if not endereco:
                return "Sem bairro"
            
            partes = [p.strip() for p in endereco.split(',')]
            
            # Padrões comuns de bairro em Goiânia
            padroes_bairro = [
                'Setor', 'Jardim', 'Residencial', 'Parque', 'Vila', 
                'Conjunto', 'Área', 'Região', 'Distrito'
            ]
            
            # Procurar por uma parte que comece com padrão de bairro
            for parte in partes:
                parte_limpa = parte.strip()
                for padrao in padroes_bairro:
                    if parte_limpa.startswith(padrao):
                        return parte_limpa
            
            # Se não encontrou padrão, pegar a penúltima parte antes da cidade
            # Exemplo: "Rua X, BAIRRO, Goiânia" -> retorna BAIRRO
            if len(partes) >= 3:
                # Procurar pela cidade (Goiânia, Aparecida de Goiânia, etc)
                for i, parte in enumerate(partes):
                    if 'Goiânia' in parte or 'Goiania' in parte:
                        if i > 0:
                            return partes[i-1].strip()
            
            # Se tudo falhar, retornar a segunda parte (geralmente é o bairro)
            if len(partes) >= 2:
                return partes[1].strip()
            
            return "Sem bairro"

        for occ in ocorrencias:
            rua = extrair_rua(occ.endereco_completo)
            if rua not in ruas:
                ruas[rua] = []
            ruas[rua].append(occ)

        resultado = []

        for rua, lista in ruas.items():
            total = len(lista)

            # Quantidade normalizada
            Q = total / max(1, max(len(lst) for lst in ruas.values()))

            # Gravidade média
            pesos = {
                'emergencia': 1.0,
                'urgente': 0.75,
                'pouco_urgente': 0.40,
                'nao_urgente': 0.20
            }
            G = sum(pesos.get(occ.urgencia, 0.20) for occ in lista) / total

            # Recorrência
            coords = [(round(occ.latitude, 5), round(occ.longitude, 5)) for occ in lista]
            repetidas = sum(coords.count(c) > 1 for c in coords)
            R = repetidas / total

            # Índice (invertido)
            IRU = 1 - (0.4*Q + 0.4*G + 0.2*R)
            nota = round(IRU * 100, 2)

            # Região de calor: valores 0–1
            intensidade = 1 - IRU

            # 🔹 EXTRAIR BAIRRO do primeiro endereço da lista
            bairro = extrair_bairro(lista[0].endereco_completo)

            resultado.append({
                'rua': rua,
                'bairro': bairro,  # 🔹 NOVO CAMPO
                'nota': nota,
                'intensidade': intensidade,
                'total_ocorrencias': total,
                'coordenadas': [
                    {'lat': o.latitude, 'lng': o.longitude} for o in lista
                ]
            })

        return jsonify({
            'status': 'success',
            'data': resultado
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/siu/rua/<rua>', methods=['GET'])
def siu_rua_info(rua):
    ocorrencias = Ocorrencia.query.filter(
        Ocorrencia.endereco_completo.ilike(f"%{rua}%")
    ).all()

    coords = []
    datas = []
    historico = []

    for oc in ocorrencias:
        coords.append({
            "lat": oc.latitude,
            "lng": oc.longitude,
        })

        historico.append({
            "data": oc.created_at.strftime("%d/%m/%Y"),
            "categoria": oc.categoria,
            "urgencia": oc.urgencia,
            "status": oc.status,
            "imagem": oc.imagem_miniatura_path.replace("app/static/", "")
        })

        datas.append(oc.created_at)

    return jsonify({
        "rua": rua,
        "total": len(ocorrencias),
        "coordenadas": coords,
        "historico": historico,
    })
