"""
Dashboard API - Endpoints para o dashboard moderno do SIMUA
VERSÃO CORRIGIDA - SEM DUPLICAÇÃO
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from app import db
from app.models import Ocorrencia, OrdemServico, Camera, User
from app.utils.decorators import role_required

dashboard_api_bp = Blueprint('dashboard_api', __name__, url_prefix='/api/dashboard')

# ========================================
# MAPEAMENTOS DE CATEGORIAS
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

PRIORIDADE_PESOS = {
    'critica': 40,
    'alta': 32,
    'media': 24,
    'baixa': 16
}

URGENCIA_PESOS = {
    'emergencia': 40,
    'urgente': 30,
    'pouco_urgente': 22,
    'nao_urgente': 14
}

BASE_INDENIZACAO = {
    'critica': 26000,
    'alta': 19000,
    'media': 12000,
    'baixa': 8000
}

BASE_REPARO = {
    'asfalto_dano': 5200,
    'calcada_dano': 1800,
    'iluminacao_publica': 1400,
    'fiacao_exposta': 3500,
    'lixo_irregular': 900,
    'arvore_dano': 2200,
    'mato_alto': 800,
    'placa_dano': 1300,
    'sinalizacao_apagada': 1300,
    'semaforo_defeito': 4200,
    'ponto_onibus_dano': 2800,
    'vazamento_agua': 2600,
    'bueiro_dano': 2400,
    'bueiro_entupido': 2100,
    'queimada': 1600,
    'obra_irregular': 3000,
    'objeto_na_pista': 1100,
    'animal_na_pista': 1200,
    'desconhecido': 1600,
    'fruta_na_pista': 1000
}

# ========================================
# UTILITÁRIOS
# ========================================

def obter_periodo(periodo_param):
    """Retorna data_inicio e data_fim baseado no parâmetro de período"""
    data_fim = datetime.now()
    
    if periodo_param == 'ano':
        data_inicio = datetime(data_fim.year, 1, 1)
    else:
        dias = int(periodo_param) if periodo_param.isdigit() else 30
        data_inicio = data_fim - timedelta(days=dias)
    
    return data_inicio, data_fim

def aplicar_filtros_query(query, filtros):
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

def extrair_regiao(endereco):
    """Extrai uma descrição curta de região/bairro a partir do endereço completo"""
    if not endereco:
        return 'Localização não informada'

    for separador in [' - ', ' – ', ',', ' / ']:
        if separador in endereco:
            partes = [p.strip() for p in endereco.split(separador) if p.strip()]
            if len(partes) >= 2:
                return partes[-1]

    return endereco.strip()

def extrair_bairro_irl(endereco):
    """
    Extrai o bairro real de endereços no formato:
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
    if len(partes) >= 3:
        for i, parte in enumerate(partes):
            if 'Goiânia' in parte or 'Goiania' in parte:
                if i > 0:
                    return partes[i-1].strip()
    
    # Se tudo falhar, retornar a segunda parte (geralmente é o bairro)
    if len(partes) >= 2:
        return partes[1].strip()
    
    return "Sem bairro"

def calcular_proximidade(endereco):
    """Calcula score socioterritorial a partir de palavras-chave do endereço"""
    if not endereco:
        return 8, 'Área residencial/comercial'

    texto = endereco.lower()
    proximidade = 8
    descritores = []

    palavras_chave = {
        'escola': ('Próximo a escola', 14),
        'colegio': ('Próximo a escola', 12),
        'hospital': ('Próximo a hospital', 18),
        'upa': ('Unidade de pronto atendimento próxima', 14),
        'pronto socorro': ('Pronto-socorro nas proximidades', 16),
        'posto de saude': ('Posto de saúde próximo', 12),
        'faixa': ('Faixa de pedestre próxima', 10),
        'creche': ('Creche / escola infantil próxima', 12),
        'universidade': ('Universidade próxima', 10),
        'campus': ('Campus universitário próximo', 10),
        'estadio': ('Área de grande fluxo (estádio)', 8),
        'shopping': ('Área comercial intensa', 8)
    }

    for chave, (descricao, pontos) in palavras_chave.items():
        if chave in texto:
            proximidade += pontos
            descritores.append(descricao)

    proximidade = min(35, proximidade)
    if descritores:
        return proximidade, ' / '.join(sorted(set(descritores)))

    return proximidade, 'Área residencial/comercial'


def calcular_trafego(prioridade, urgencia):
    """Score de risco de tráfego baseado em prioridade da OS e urgência da ocorrência"""
    base_prioridade = PRIORIDADE_PESOS.get(prioridade, 20)
    base_urgencia = URGENCIA_PESOS.get(urgencia, 18)

    score = (base_prioridade * 0.6) + (base_urgencia * 0.4)
    return min(40, round(score))


def estimar_indenizacao(prioridade):
    """Valor base de indenização estimada considerando a prioridade"""
    return BASE_INDENIZACAO.get(prioridade, 9000)


def estimar_custo_reparo(categoria):
    """Estimativa de custo de reparo baseada na categoria da OS"""
    return BASE_REPARO.get(categoria, 1800)

# ========================================
# ENDPOINT 1: ESTATÍSTICAS PRINCIPAIS
# ========================================

@dashboard_api_bp.route('/stats')
@login_required
@role_required(['gestor', 'admin'])
def get_stats():
    """Retorna estatísticas gerais do sistema"""
    try:
        # Obter período
        periodo = request.args.get('periodo', '30')
        data_inicio, data_fim = obter_periodo(periodo)
        
        # Total de ocorrências no período
        total_ocorrencias = Ocorrencia.query.filter(
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim
        ).count()
        
        # Ocorrências por status
        pendentes = Ocorrencia.query.filter(
            Ocorrencia.status == 'pendente',
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim
        ).count()
        
        validadas = Ocorrencia.query.filter(
            Ocorrencia.status == 'validada',
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim
        ).count()
        
        resolvidas = Ocorrencia.query.filter(
            Ocorrencia.status == 'resolvida',
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim
        ).count()
        
        # Total de OS
        total_os = OrdemServico.query.filter(
            OrdemServico.created_at >= data_inicio,
            OrdemServico.created_at <= data_fim
        ).count()
        
        # OS por status
        os_criadas = OrdemServico.query.filter(
            OrdemServico.status == 'criada',
            OrdemServico.created_at >= data_inicio,
            OrdemServico.created_at <= data_fim
        ).count()
        
        os_em_andamento = OrdemServico.query.filter(
            OrdemServico.status.in_(['atribuida', 'em_andamento']),
            OrdemServico.created_at >= data_inicio,
            OrdemServico.created_at <= data_fim
        ).count()
        
        os_concluidas = OrdemServico.query.filter(
            OrdemServico.status.in_(['concluida', 'aprovada']),
            OrdemServico.created_at >= data_inicio,
            OrdemServico.created_at <= data_fim
        ).count()
        
        # Câmeras ativas
        cameras_ativas = Camera.query.filter_by(ativa=True).count()
        
        # Taxa de resolução
        taxa_resolucao = (resolvidas / total_ocorrencias * 100) if total_ocorrencias > 0 else 0
        
        return jsonify({
            'periodo': {
                'inicio': data_inicio.isoformat(),
                'fim': data_fim.isoformat(),
                'dias': (data_fim - data_inicio).days
            },
            'ocorrencias': {
                'total': total_ocorrencias,
                'pendentes': pendentes,
                'validadas': validadas,
                'resolvidas': resolvidas,
                'taxa_resolucao': round(taxa_resolucao, 1)
            },
            'ordens_servico': {
                'total': total_os,
                'criadas': os_criadas,
                'em_andamento': os_em_andamento,
                'concluidas': os_concluidas
            },
            'cameras': {
                'ativas': cameras_ativas
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# ENDPOINT 2: MAPA DE OCORRÊNCIAS
# ========================================

@dashboard_api_bp.route('/mapa/ocorrencias')
@login_required
def get_mapa_ocorrencias():
    """Retorna ocorrências para exibição no mapa"""
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
        data_inicio, data_fim = obter_periodo(periodo)
        
        # Query base
        query = Ocorrencia.query.filter(
            Ocorrencia.created_at >= data_inicio,
            Ocorrencia.created_at <= data_fim,
            Ocorrencia.latitude.isnot(None),
            Ocorrencia.longitude.isnot(None)
        )
        
        # Aplicar filtros
        query = aplicar_filtros_query(query, filtros)
        
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

        return jsonify({
            'status': 'success',
            'total': len(resultado),
            'ocorrencias': resultado
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# ENDPOINT 3: OCORRÊNCIAS RECENTES
# ========================================

@dashboard_api_bp.route('/ocorrencias/recentes')
@login_required
def get_ocorrencias_recentes():
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

@dashboard_api_bp.route('/charts')
@login_required
@role_required(['gestor', 'admin'])
def get_charts_data():
    """Retorna dados para todos os gráficos"""
    try:
        # Obter período
        periodo = request.args.get('periodo', '30')
        data_inicio, data_fim = obter_periodo(periodo)
        
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
        query = aplicar_filtros_query(query, filtros)
        
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
# ENDPOINT 5: CONTADORES PARA BADGES
# ========================================

@dashboard_api_bp.route('/badges')
@login_required
def get_badges():
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

# ========================================
# ENDPOINT 6: CONTAGEM DE OCORRÊNCIAS
# ========================================

@dashboard_api_bp.route('/ocorrencias/count', methods=['GET'])
@login_required
def count_ocorrencias():
    """Endpoint alternativo para contagem (compatibilidade)"""
    return get_badges()

# ========================================
# ENDPOINT 7: DADOS DO IRL (ÍNDICE DE RISCO LEGAL)
# ========================================

@dashboard_api_bp.route('/dados_irl')
@login_required
@role_required(['gestor', 'admin'])
def dados_irl():
    """
    Retorna dados completos para o dashboard IRL (Índice de Risco Legal)
    com cálculo de exposição, tráfego, proximidade e custos.
    """
    try:
        # Buscar todas as ordens de serviço com ocorrências associadas
        ordens = OrdemServico.query.join(Ocorrencia).filter(
            OrdemServico.latitude.isnot(None),
            OrdemServico.longitude.isnot(None),
            Ocorrencia.categoria != 'sem_ocorrencias'  # Excluir sem ocorrências
        ).all()

        resultado = []

        for os in ordens:
            ocorrencia = os.ocorrencia
            if not ocorrencia:
                continue

            # 1. CALCULAR DIAS DE EXPOSIÇÃO
            dias_expostos = (datetime.now() - os.created_at).days
            
            # 2. EXTRAIR BAIRRO DO ENDEREÇO
            bairro = extrair_bairro_irl(os.endereco_completo)
            
            # 3. CALCULAR SCORE DE PROXIMIDADE (pontos críticos)
            proximidade_score, proximidade_texto = calcular_proximidade(os.endereco_completo)
            
            # 4. CALCULAR SCORE DE TRÁFEGO
            trafego_score = calcular_trafego(os.prioridade, ocorrencia.urgencia)
            
            # 5. ESTIMAR CUSTOS
            base_indenizacao = estimar_indenizacao(os.prioridade)
            custo_reparo = estimar_custo_reparo(os.categoria)
            
            # 6. TRADUZIR STATUS DA OS
            status_map = {
                'criada': 'Nova',
                'atribuida': 'Aberta',
                'em_andamento': 'Aberta',
                'aguardando_aprovacao': 'Em Atraso',
                'concluida': 'Concluída',
                'aprovada': 'Concluída',
                'cancelada': 'Cancelada'
            }
            os_status = status_map.get(os.status, os.status.title())
            
            # 7. LABEL DA CATEGORIA
            categoria_label = CATEGORIA_LABELS.get(os.categoria, 'Outros')
            
            # 8. TÍTULO DA OCORRÊNCIA
            titulo_map = {
                'asfalto_dano': 'Buraco na pista',
                'calcada_dano': 'Buraco na calçada',
                'iluminacao_publica': 'Iluminação apagada',
                'fiacao_exposta': 'Fiação exposta',
                'lixo_irregular': 'Lixo e entulho',
                'arvore_dano': 'Árvore danificada',
                'mato_alto': 'Mato alto',
                'placa_dano': 'Placa danificada',
                'sinalizacao_apagada': 'Sinalização apagada',
                'semaforo_defeito': 'Semáforo com defeito',
                'ponto_onibus_dano': 'Ponto de ônibus danificado',
                'vazamento_agua': 'Vazamento de água',
                'bueiro_dano': 'Bueiro danificado',
                'bueiro_entupido': 'Bueiro entupido',
                'queimada': 'Queimada',
                'obra_irregular': 'Obra irregular',
                'objeto_na_pista': 'Objeto na pista',
                'animal_na_pista': 'Animal na pista',
                'fruta_na_pista': 'Fruta na pista',
                'desconhecido': 'Ocorrência desconhecida'
            }
            titulo = titulo_map.get(os.categoria, os.categoria.replace('_', ' ').title())
            
            # Montar objeto para retornar
            item = {
                'id': str(os.id),
                'title': titulo,
                'category': os.categoria,
                'categoryLabel': categoria_label,
                'osStatus': os_status,
                'location': os.endereco_completo.split(',')[0] if os.endereco_completo else 'N/A',
                'bairro': bairro,
                'latitude': float(os.latitude),
                'longitude': float(os.longitude),
                'exposureDays': dias_expostos,
                'trafficScore': trafego_score,
                'proximityScore': proximidade_score,
                'proximityText': proximidade_texto,
                'baseIndemnization': base_indenizacao,
                'repairCost': custo_reparo,
                'created_at': os.created_at.isoformat(),
                'numero_os': os.numero_os
            }
            
            resultado.append(item)

        return jsonify({
            'status': 'success',
            'total': len(resultado),
            'occurrences': resultado
        })

    except Exception as e:
        print(f"❌ Erro no endpoint dados_irl: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500