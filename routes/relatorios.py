from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from app import db
from app.models import Ocorrencia, OrdemServico, Equipe, Relatorio, User
from app.utils.decorators import gestor_required
from datetime import datetime, timedelta
import os
from io import BytesIO

relatorios_bp = Blueprint('relatorios', __name__)

@relatorios_bp.route('/')
@login_required
@gestor_required
def index():
    """Página principal de relatórios"""
    # Relatórios salvos (últimos 10)
    relatorios_salvos = Relatorio.query.filter_by(
        gerado_por_id=current_user.id
    ).order_by(desc(Relatorio.created_at)).limit(10).all()
    
    # Estatísticas rápidas
    hoje = datetime.now().date()
    mes_atual_inicio = datetime(hoje.year, hoje.month, 1)
    
    stats = {
        'ocorrencias_hoje': Ocorrencia.query.filter(
            func.date(Ocorrencia.created_at) == hoje
        ).count(),
        'ocorrencias_mes': Ocorrencia.query.filter(
            Ocorrencia.created_at >= mes_atual_inicio
        ).count(),
        'os_pendentes': OrdemServico.query.filter(
            OrdemServico.status.in_(['criada', 'atribuida', 'em_andamento'])
        ).count(),
        'os_mes': OrdemServico.query.filter(
            OrdemServico.created_at >= mes_atual_inicio
        ).count()
    }
    
    return render_template('relatorios/index.html',
                         relatorios_salvos=relatorios_salvos,
                         stats=stats)

@relatorios_bp.route('/ocorrencias', methods=['GET', 'POST'])
@login_required
@gestor_required
def relatorio_ocorrencias():
    """Relatório de ocorrências"""
    if request.method == 'POST':
        try:
            # Parâmetros
            data_inicio = datetime.fromisoformat(request.form.get('data_inicio'))
            data_fim = datetime.fromisoformat(request.form.get('data_fim'))
            categoria = request.form.get('categoria')
            urgencia = request.form.get('urgencia')
            formato = request.form.get('formato', 'pdf')  # pdf, excel, csv
            
            # Gerar relatório
            dados = gerar_dados_ocorrencias(data_inicio, data_fim, categoria, urgencia)
            
            if formato == 'pdf':
                arquivo = gerar_pdf_ocorrencias(dados, data_inicio, data_fim)
                nome_arquivo = f'relatorio_ocorrencias_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            elif formato == 'excel':
                arquivo = gerar_excel_ocorrencias(dados)
                nome_arquivo = f'relatorio_ocorrencias_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            else:  # csv
                arquivo = gerar_csv_ocorrencias(dados)
                nome_arquivo = f'relatorio_ocorrencias_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            
            # Salvar registro no banco
            relatorio = Relatorio(
                titulo=f'Relatório de Ocorrências - {data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}',
                tipo='personalizado',
                data_inicio=data_inicio.date(),
                data_fim=data_fim.date(),
                gerado_por_id=current_user.id,
                arquivo_path=arquivo if formato == 'pdf' else None,
                parametros={
                    'categoria': categoria,
                    'urgencia': urgencia,
                    'formato': formato
                }
            )
            db.session.add(relatorio)
            db.session.commit()
            
            # Enviar arquivo para download
            if formato == 'pdf':
                return send_file(
                    arquivo,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=nome_arquivo
                )
            else:
                return send_file(
                    BytesIO(arquivo),
                    mimetype='application/octet-stream',
                    as_attachment=True,
                    download_name=nome_arquivo
                )
            
        except Exception as e:
            flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
            return redirect(request.url)
    
    return render_template('relatorios/ocorrencias.html')

@relatorios_bp.route('/ordens-servico', methods=['GET', 'POST'])
@login_required
@gestor_required
def relatorio_os():
    """Relatório de ordens de serviço"""
    if request.method == 'POST':
        try:
            # Parâmetros
            data_inicio = datetime.fromisoformat(request.form.get('data_inicio'))
            data_fim = datetime.fromisoformat(request.form.get('data_fim'))
            equipe_id = request.form.get('equipe_id')
            prioridade = request.form.get('prioridade')
            status = request.form.get('status')
            formato = request.form.get('formato', 'pdf')
            
            # Gerar dados
            dados = gerar_dados_os(data_inicio, data_fim, equipe_id, prioridade, status)
            
            if formato == 'pdf':
                arquivo = gerar_pdf_os(dados, data_inicio, data_fim)
                nome_arquivo = f'relatorio_os_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
                mimetype = 'application/pdf'
            elif formato == 'excel':
                arquivo = gerar_excel_os(dados)
                nome_arquivo = f'relatorio_os_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                arquivo = gerar_csv_os(dados)
                nome_arquivo = f'relatorio_os_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                mimetype = 'text/csv'
            
            # Salvar registro
            relatorio = Relatorio(
                titulo=f'Relatório de OS - {data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}',
                tipo='personalizado',
                data_inicio=data_inicio.date(),
                data_fim=data_fim.date(),
                gerado_por_id=current_user.id,
                arquivo_path=arquivo if formato == 'pdf' else None,
                parametros={
                    'equipe_id': equipe_id,
                    'prioridade': prioridade,
                    'status': status,
                    'formato': formato
                }
            )
            db.session.add(relatorio)
            db.session.commit()
            
            return send_file(
                arquivo if formato == 'pdf' else BytesIO(arquivo),
                mimetype=mimetype,
                as_attachment=True,
                download_name=nome_arquivo
            )
            
        except Exception as e:
            flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
            return redirect(request.url)
    
    equipes = Equipe.query.filter_by(ativa=True).all()
    return render_template('relatorios/ordens_servico.html', equipes=equipes)

@relatorios_bp.route('/equipes', methods=['GET', 'POST'])
@login_required
@gestor_required
def relatorio_equipes():
    """Relatório de performance de equipes"""
    if request.method == 'POST':
        try:
            data_inicio = datetime.fromisoformat(request.form.get('data_inicio'))
            data_fim = datetime.fromisoformat(request.form.get('data_fim'))
            equipe_id = request.form.get('equipe_id')
            formato = request.form.get('formato', 'pdf')
            
            dados = gerar_dados_equipes(data_inicio, data_fim, equipe_id)
            
            if formato == 'pdf':
                arquivo = gerar_pdf_equipes(dados, data_inicio, data_fim)
                nome_arquivo = f'relatorio_equipes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
                mimetype = 'application/pdf'
            else:
                arquivo = gerar_excel_equipes(dados)
                nome_arquivo = f'relatorio_equipes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            
            # Salvar registro
            relatorio = Relatorio(
                titulo=f'Relatório de Equipes - {data_inicio.strftime("%d/%m/%Y")} a {data_fim.strftime("%d/%m/%Y")}',
                tipo='personalizado',
                data_inicio=data_inicio.date(),
                data_fim=data_fim.date(),
                gerado_por_id=current_user.id,
                arquivo_path=arquivo if formato == 'pdf' else None,
                parametros={'equipe_id': equipe_id, 'formato': formato}
            )
            db.session.add(relatorio)
            db.session.commit()
            
            return send_file(
                arquivo if formato == 'pdf' else BytesIO(arquivo),
                mimetype=mimetype,
                as_attachment=True,
                download_name=nome_arquivo
            )
            
        except Exception as e:
            flash(f'Erro ao gerar relatório: {str(e)}', 'danger')
            return redirect(request.url)
    
    equipes = Equipe.query.filter_by(ativa=True).all()
    return render_template('relatorios/equipes.html', equipes=equipes)

@relatorios_bp.route('/<uuid:id>/download')
@login_required
def download(id):
    """Download de relatório salvo"""
    relatorio = Relatorio.query.get_or_404(id)
    
    # Verificar permissão
    if relatorio.gerado_por_id != current_user.id and not current_user.is_admin:
        flash('Você não tem permissão para acessar este relatório.', 'danger')
        return redirect(url_for('relatorios.index'))
    
    if not relatorio.arquivo_path or not os.path.exists(relatorio.arquivo_path):
        flash('Arquivo de relatório não encontrado.', 'warning')
        return redirect(url_for('relatorios.index'))
    
    return send_file(
        relatorio.arquivo_path,
        as_attachment=True,
        download_name=os.path.basename(relatorio.arquivo_path)
    )

# Funções auxiliares de geração de dados

def gerar_dados_ocorrencias(data_inicio, data_fim, categoria=None, urgencia=None):
    """Gera dados para relatório de ocorrências"""
    query = Ocorrencia.query.filter(
        Ocorrencia.created_at >= data_inicio,
        Ocorrencia.created_at <= data_fim
    )
    
    if categoria:
        query = query.filter(Ocorrencia.categoria == categoria)
    
    if urgencia:
        query = query.filter(Ocorrencia.urgencia == urgencia)
    
    ocorrencias = query.all()
    
    # Estatísticas agregadas
    por_categoria = db.session.query(
        Ocorrencia.categoria,
        func.count(Ocorrencia.id)
    ).filter(
        Ocorrencia.created_at >= data_inicio,
        Ocorrencia.created_at <= data_fim
    ).group_by(Ocorrencia.categoria).all()
    
    por_urgencia = db.session.query(
        Ocorrencia.urgencia,
        func.count(Ocorrencia.id)
    ).filter(
        Ocorrencia.created_at >= data_inicio,
        Ocorrencia.created_at <= data_fim
    ).group_by(Ocorrencia.urgencia).all()
    
    por_status = db.session.query(
        Ocorrencia.status,
        func.count(Ocorrencia.id)
    ).filter(
        Ocorrencia.created_at >= data_inicio,
        Ocorrencia.created_at <= data_fim
    ).group_by(Ocorrencia.status).all()
    
    return {
        'ocorrencias': ocorrencias,
        'total': len(ocorrencias),
        'por_categoria': dict(por_categoria),
        'por_urgencia': dict(por_urgencia),
        'por_status': dict(por_status),
        'periodo': {
            'inicio': data_inicio,
            'fim': data_fim
        }
    }

def gerar_dados_os(data_inicio, data_fim, equipe_id=None, prioridade=None, status=None):
    """Gera dados para relatório de OS"""
    query = OrdemServico.query.filter(
        OrdemServico.created_at >= data_inicio,
        OrdemServico.created_at <= data_fim
    )
    
    if equipe_id:
        query = query.filter(OrdemServico.equipe_id == equipe_id)
    
    if prioridade:
        query = query.filter(OrdemServico.prioridade == prioridade)
    
    if status:
        query = query.filter(OrdemServico.status == status)
    
    ordens = query.all()
    
    # KPIs
    total = len(ordens)
    concluidas = sum(1 for os in ordens if os.status == 'aprovada')
    taxa_conclusao = (concluidas / total * 100) if total > 0 else 0
    
    # Tempo médio
    tempos = []
    for os in ordens:
        if os.status == 'aprovada' and os.data_aprovacao and os.created_at:
            diff = os.data_aprovacao - os.created_at
            tempos.append(diff.total_seconds() / 3600)
    
    tempo_medio = sum(tempos) / len(tempos) if tempos else 0
    
    return {
        'ordens': ordens,
        'total': total,
        'concluidas': concluidas,
        'taxa_conclusao': round(taxa_conclusao, 1),
        'tempo_medio_horas': round(tempo_medio, 1),
        'periodo': {
            'inicio': data_inicio,
            'fim': data_fim
        }
    }

def gerar_dados_equipes(data_inicio, data_fim, equipe_id=None):
    """Gera dados para relatório de equipes"""
    if equipe_id:
        equipes = [Equipe.query.get(equipe_id)]
    else:
        equipes = Equipe.query.filter_by(ativa=True).all()
    
    dados_equipes = []
    
    for equipe in equipes:
        os_equipe = OrdemServico.query.filter(
            OrdemServico.equipe_id == equipe.id,
            OrdemServico.created_at >= data_inicio,
            OrdemServico.created_at <= data_fim
        ).all()
        
        total = len(os_equipe)
        concluidas = sum(1 for os in os_equipe if os.status == 'aprovada')
        taxa_aprovacao = (concluidas / total * 100) if total > 0 else 0
        
        dados_equipes.append({
            'equipe': equipe,
            'total_os': total,
            'os_concluidas': concluidas,
            'taxa_aprovacao': round(taxa_aprovacao, 1)
        })
    
    return {
        'equipes': dados_equipes,
        'periodo': {
            'inicio': data_inicio,
            'fim': data_fim
        }
    }

# Funções de geração de arquivos (placeholders - implementar com bibliotecas)

def gerar_pdf_ocorrencias(dados, data_inicio, data_fim):
    """Gera PDF de relatório de ocorrências"""
    # TODO: Implementar com reportlab ou weasyprint
    # Por enquanto, retorna placeholder
    return 'app/static/uploads/relatorios/placeholder.pdf'

def gerar_excel_ocorrencias(dados):
    """Gera Excel de ocorrências"""
    # TODO: Implementar com openpyxl ou pandas
    return b'placeholder excel content'

def gerar_csv_ocorrencias(dados):
    """Gera CSV de ocorrências"""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Data', 'Categoria', 'Urgência', 'Status', 'Endereço'])
    
    # Dados
    for occ in dados['ocorrencias']:
        writer.writerow([
            occ.created_at.strftime('%d/%m/%Y %H:%M'),
            occ.categoria,
            occ.urgencia,
            occ.status,
            occ.endereco_completo or ''
        ])
    
    return output.getvalue().encode('utf-8')

def gerar_pdf_os(dados, data_inicio, data_fim):
    """Gera PDF de relatório de OS"""
    return 'app/static/uploads/relatorios/placeholder_os.pdf'

def gerar_excel_os(dados):
    """Gera Excel de OS"""
    return b'placeholder excel os content'

def gerar_csv_os(dados):
    """Gera CSV de OS"""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Número OS', 'Categoria', 'Prioridade', 'Status', 'Data Criação', 'Equipe'])
    
    for os in dados['ordens']:
        writer.writerow([
            os.numero_os,
            os.categoria,
            os.prioridade,
            os.status,
            os.created_at.strftime('%d/%m/%Y'),
            os.equipe.nome if os.equipe else ''
        ])
    
    return output.getvalue().encode('utf-8')

def gerar_pdf_equipes(dados, data_inicio, data_fim):
    """Gera PDF de relatório de equipes"""
    return 'app/static/uploads/relatorios/placeholder_equipes.pdf'

def gerar_excel_equipes(dados):
    """Gera Excel de equipes"""
    return b'placeholder excel equipes content'