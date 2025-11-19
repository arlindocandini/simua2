from flask import Blueprint, redirect, render_template, jsonify, request, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta
from app import db
from app.models import Ocorrencia, OrdemServico, User, Equipe
from app.utils.decorators import role_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard principal - redireciona baseado no tipo de usuário"""
    if current_user.is_campo:
        return redirect(url_for('dashboard.campo'))
    else:
        return redirect(url_for('dashboard.gestor'))

@dashboard_bp.route('/gestor')
@login_required
@role_required(['gestor', 'admin'])
def gestor():
    """Dashboard do gestor com métricas e gráficos"""
    return render_template('dashboard/gestor.html')


@dashboard_bp.route('/aru')
@login_required
@role_required(['gestor', 'admin'])
def aru():
    """Tela do Alerta de Reincidência Urbana (ARU)"""
    periodo_dias = request.args.get('dias', type=int, default=180)

    def parse_data(valor, fallback):
        try:
            return datetime.fromisoformat(valor)
        except (TypeError, ValueError):
            return fallback

    data_fim = parse_data(request.args.get('fim'), datetime.now())
    data_inicio = parse_data(
        request.args.get('inicio'),
        data_fim - timedelta(days=periodo_dias)
    )

    filtros = {
        'regiao': request.args.get('regiao', ''),
        'equipe_id': request.args.get('equipe_id', ''),
        'categorias': [c for c in request.args.getlist('categoria') if c],
        'inicio': data_inicio.date().isoformat(),
        'fim': data_fim.date().isoformat()
    }

    base_query = OrdemServico.query.filter(
        OrdemServico.created_at >= data_inicio,
        OrdemServico.created_at <= data_fim
    )

    if filtros['regiao']:
        base_query = base_query.filter(OrdemServico.endereco_completo.ilike(f"%{filtros['regiao']}%"))

    if filtros['equipe_id']:
        base_query = base_query.filter(OrdemServico.equipe_id == filtros['equipe_id'])

    if filtros['categorias']:
        base_query = base_query.filter(OrdemServico.categoria.in_(filtros['categorias']))

    agrupamento = base_query.with_entities(
        func.round(OrdemServico.latitude, 5).label('lat_cluster'),
        func.round(OrdemServico.longitude, 5).label('lon_cluster'),
        OrdemServico.categoria.label('categoria'),
        func.count(OrdemServico.id).label('total'),
        func.max(OrdemServico.created_at).label('ultima_data')
    ).group_by(
        func.round(OrdemServico.latitude, 5),
        func.round(OrdemServico.longitude, 5),
        OrdemServico.categoria
    ).having(func.count(OrdemServico.id) >= 2).order_by(func.count(OrdemServico.id).desc())

    clusters = []
    categorias_heat = {}

    for grupo in agrupamento.all():
        os_cluster = base_query.filter(
            func.round(OrdemServico.latitude, 5) == grupo.lat_cluster,
            func.round(OrdemServico.longitude, 5) == grupo.lon_cluster,
            OrdemServico.categoria == grupo.categoria
        ).order_by(OrdemServico.created_at.desc()).all()

        if not os_cluster:
            continue

        ultima_os = os_cluster[0]
        primeira_os = os_cluster[-1]
        abertas = [os for os in os_cluster if os.status not in ['concluida', 'aprovada']]
        intervalo_medio = None
        if len(os_cluster) > 1:
            intervalo_total = (ultima_os.created_at - primeira_os.created_at).total_seconds() / 86400
            intervalo_medio = round(intervalo_total / (len(os_cluster) - 1), 1)

        categorias_heat[grupo.categoria] = categorias_heat.get(grupo.categoria, 0) + len(os_cluster)

        clusters.append({
            'categoria': grupo.categoria,
            'endereco': ultima_os.endereco_completo,
            'latitude': float(ultima_os.latitude),
            'longitude': float(ultima_os.longitude),
            'recorrencias': len(os_cluster),
            'abertas': len(abertas),
            'ultima_data': grupo.ultima_data,
            'ultima_os': ultima_os,
            'timeline': os_cluster,
            'intervalo_medio': intervalo_medio
        })

    clusters.sort(key=lambda c: (c['abertas'] > 0, c['recorrencias']), reverse=True)

    resumo = {
        'total_pontos': len(clusters),
        'pontos_criticos': len([c for c in clusters if c['recorrencias'] >= 3]),
        'ocorrencias_abertas': sum(c['abertas'] for c in clusters),
        'dias_monitorados': max((data_fim - data_inicio).days, 0)
    }

    categorias_heat = dict(sorted(categorias_heat.items(), key=lambda item: item[1], reverse=True))
    max_calor = max(categorias_heat.values()) if categorias_heat else 1

    equipes = Equipe.query.filter_by(ativa=True).order_by(Equipe.nome).all()
    categorias_disponiveis = [
        cat[0] for cat in db.session.query(OrdemServico.categoria).distinct().all()
    ]

    return render_template(
        'dashboard/aru.html',
        clusters=clusters,
        clusters_mapa=clusters, 
        resumo=resumo,
        categorias_heat=categorias_heat,
        max_calor=max_calor,
        filtros=filtros,
        equipes=equipes,
        categorias_disponiveis=sorted(categorias_disponiveis)
    )


@dashboard_bp.route('/irl')
@login_required
@role_required(['gestor', 'admin'])
def irl():
    """Tela do Índice de Risco Legal (IRL)"""
    return render_template('dashboard/irl.html')

@dashboard_bp.route('/campo')
@login_required
@role_required(['equipe_campo'])
def campo():
    """Dashboard da equipe de campo (mobile-friendly)"""
    # Buscar OS atribuídas ao usuário atual
    os_minhas = OrdemServico.query.filter(
        OrdemServico.responsavel_campo_id == current_user.id,
        OrdemServico.status.in_(['atribuida', 'em_andamento'])
    ).order_by(OrdemServico.prazo_execucao).all()
    
    # Buscar OS da equipe
    os_equipe = []
    if current_user.equipe_id:
        os_equipe = OrdemServico.query.filter(
            OrdemServico.equipe_id == current_user.equipe_id,
            OrdemServico.status.in_(['criada', 'atribuida', 'em_andamento']),
            OrdemServico.responsavel_campo_id != current_user.id
        ).order_by(OrdemServico.prazo_execucao).all()
    
    return render_template('dashboard/campo.html', 
                         os_minhas=os_minhas, 
                         os_equipe=os_equipe)

@dashboard_bp.route('/api/metricas')
@login_required
def api_metricas():
    """API para métricas do dashboard"""
    # Parâmetros de filtro
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    # Converter datas
    if data_inicio:
        data_inicio = datetime.fromisoformat(data_inicio)
    else:
        data_inicio = datetime.now() - timedelta(days=30)
    
    if data_fim:
        data_fim = datetime.fromisoformat(data_fim)
    else:
        data_fim = datetime.now()
    
    # Query base de ocorrências
    query_ocorrencias = Ocorrencia.query.filter(
        Ocorrencia.created_at >= data_inicio,
        Ocorrencia.created_at <= data_fim
    )
    
    # Contar por urgência
    ocorrencias_por_urgencia = db.session.query(
        Ocorrencia.urgencia,
        func.count(Ocorrencia.id)
    ).filter(
        Ocorrencia.created_at >= data_inicio,
        Ocorrencia.created_at <= data_fim
    ).group_by(Ocorrencia.urgencia).all()
    
    urgencias = {
        'emergencia': 0,
        'urgente': 0,
        'pouco_urgente': 0,
        'nao_urgente': 0
    }
    
    for urgencia, count in ocorrencias_por_urgencia:
        urgencias[urgencia] = count
    
    # Contar por categoria
    # Contar por categoria (completando com zero para ausentes)
    ocorrencias_por_categoria = db.session.query(
        Ocorrencia.categoria,
        func.count(Ocorrencia.id)
    ).filter(
        Ocorrencia.created_at >= data_inicio,
        Ocorrencia.created_at <= data_fim
    ).group_by(Ocorrencia.categoria).all()

    todas_categorias = [
        'asfalto_dano', 'calcada_dano', 'iluminacao_publica', 'fiacao_exposta',
        'lixo_irregular', 'arvore_dano', 'mato_alto', 'ponto_onibus_dano',
        'vazamento_agua', 'fruta_na_pista', 'placa_dano', 'semaforo_defeito',
        'sinalizacao_apagada', 'objeto_na_pista', 'animal_na_pista',
        'bueiro_entupido', 'bueiro_dano', 'queimada', 'obra_irregular', 'desconhecido'
    ]

    categorias = {cat: 0 for cat in todas_categorias}
    for cat, count in ocorrencias_por_categoria:
        categorias[cat] = count

    # Contar por status
    ocorrencias_por_status = db.session.query(
        Ocorrencia.status,
        func.count(Ocorrencia.id)
    ).filter(
        Ocorrencia.created_at >= data_inicio,
        Ocorrencia.created_at <= data_fim
    ).group_by(Ocorrencia.status).all()
    
    status_occ = {st: count for st, count in ocorrencias_por_status}
    
    # Métricas de OS
    query_os = OrdemServico.query.filter(
        OrdemServico.created_at >= data_inicio,
        OrdemServico.created_at <= data_fim
    )
    
    # Contar OS por status
    os_por_status = db.session.query(
        OrdemServico.status,
        func.count(OrdemServico.id)
    ).filter(
        OrdemServico.created_at >= data_inicio,
        OrdemServico.created_at <= data_fim
    ).group_by(OrdemServico.status).all()
    
    status_os = {st: count for st, count in os_por_status}
    
    # Contar OS por prioridade
    os_por_prioridade = db.session.query(
        OrdemServico.prioridade,
        func.count(OrdemServico.id)
    ).filter(
        OrdemServico.created_at >= data_inicio,
        OrdemServico.created_at <= data_fim
    ).group_by(OrdemServico.prioridade).all()
    
    prioridades = {pr: count for pr, count in os_por_prioridade}
    
    # Tempo médio de resolução
    os_concluidas = OrdemServico.query.filter(
        OrdemServico.status == 'concluida',
        OrdemServico.created_at >= data_inicio,
        OrdemServico.created_at <= data_fim,
        OrdemServico.data_aprovacao.isnot(None)
    ).all()
    
    tempo_medio_resolucao = None
    if os_concluidas:
        tempos = [
            (os.data_aprovacao - os.created_at).total_seconds() / 3600  # em horas
            for os in os_concluidas
        ]
        tempo_medio_resolucao = sum(tempos) / len(tempos)
    
    # Evolução temporal (últimos 30 dias)
    evolucao_ocorrencias = []
    evolucao_os = []
    
    for i in range(30):
        dia = data_fim - timedelta(days=i)
        dia_inicio = dia.replace(hour=0, minute=0, second=0, microsecond=0)
        dia_fim = dia.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        count_occ = Ocorrencia.query.filter(
            Ocorrencia.created_at >= dia_inicio,
            Ocorrencia.created_at <= dia_fim
        ).count()
        
        count_os = OrdemServico.query.filter(
            OrdemServico.created_at >= dia_inicio,
            OrdemServico.created_at <= dia_fim
        ).count()
        
        evolucao_ocorrencias.insert(0, {
            'data': dia.strftime('%d/%m'),
            'total': count_occ
        })
        
        evolucao_os.insert(0, {
            'data': dia.strftime('%d/%m'),
            'total': count_os
        })
    
    return jsonify({
        'ocorrencias': {
            'total': query_ocorrencias.count(),
            'por_urgencia': urgencias,
            'por_categoria': categorias,
            'por_status': status_occ,
            'evolucao': evolucao_ocorrencias
        },
        'ordens_servico': {
            'total': query_os.count(),
            'por_status': status_os,
            'por_prioridade': prioridades,
            'tempo_medio_resolucao': tempo_medio_resolucao,
            'evolucao': evolucao_os
        }
    })