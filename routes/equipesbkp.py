from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy import func, desc
from app import db
from app.models import Equipe, User, OrdemServico
from app.utils.decorators import admin_required, role_required
from datetime import datetime, timedelta

equipes_bp = Blueprint('equipes', __name__)

@equipes_bp.route('/')
@equipes_bp.route('/lista')
@login_required
@role_required(['admin', 'gestor'])
def lista():
    """Lista todas as equipes"""
    equipes = Equipe.query.all()
    
    # Adicionar estatísticas a cada equipe
    for equipe in equipes:
        equipe.total_membros = User.query.filter_by(equipe_id=equipe.id).count()
        equipe.os_ativas = OrdemServico.query.filter(
            OrdemServico.equipe_id == equipe.id,
            OrdemServico.status.in_(['criada', 'atribuida', 'em_andamento'])
        ).count()
    
    return render_template('equipes/lista.html', equipes=equipes)

@equipes_bp.route('/<uuid:id>')
@login_required
@role_required(['admin', 'gestor'])
def detalhes(id):
    """Detalhes de uma equipe"""
    equipe = Equipe.query.get_or_404(id)
    
    # Membros da equipe
    membros = User.query.filter_by(equipe_id=id).all()
    
    # Estatísticas
    total_os = OrdemServico.query.filter_by(equipe_id=id).count()
    
    os_concluidas = OrdemServico.query.filter_by(
        equipe_id=id,
        status='aprovada'
    ).count()
    
    os_ativas = OrdemServico.query.filter(
        OrdemServico.equipe_id == id,
        OrdemServico.status.in_(['criada', 'atribuida', 'em_andamento'])
    ).count()
    
    # Taxa de conclusão
    taxa_conclusao = 0
    if total_os > 0:
        taxa_conclusao = round((os_concluidas / total_os) * 100, 1)
    
    # Últimas OS
    ultimas_os = OrdemServico.query.filter_by(
        equipe_id=id
    ).order_by(desc(OrdemServico.created_at)).limit(10).all()
    
    return render_template('equipes/detalhes.html',
                         equipe=equipe,
                         membros=membros,
                         total_os=total_os,
                         os_concluidas=os_concluidas,
                         os_ativas=os_ativas,
                         taxa_conclusao=taxa_conclusao,
                         ultimas_os=ultimas_os)

@equipes_bp.route('/criar', methods=['GET', 'POST'])
@login_required
@admin_required
def criar():
    """Criar nova equipe"""
    if request.method == 'POST':
        try:
            nome = request.form.get('nome')
            tipo_servico = request.form.get('tipo_servico')
            telefone_emergencia = request.form.get('telefone_emergencia')
            responsavel_id = request.form.get('responsavel_id')
            
            # Validações
            if not all([nome, tipo_servico]):
                flash('Preencha os campos obrigatórios.', 'warning')
                return redirect(request.url)
            
            # 🚫 Evitar duplicação de nomes
            if Equipe.query.filter(func.lower(Equipe.nome) == nome.lower()).first():
                flash('Já existe uma equipe com este nome.', 'warning')
                return redirect(request.url)



            # Criar equipe
            equipe = Equipe(
                nome=nome,
                tipo_servico=tipo_servico,
                telefone_emergencia=telefone_emergencia,
                responsavel_id=responsavel_id if responsavel_id else None,
                ativa=True
            )
            
            db.session.add(equipe)
            db.session.commit()
            
            flash(f'Equipe "{nome}" criada com sucesso!', 'success')
            return redirect(url_for('equipes.detalhes', id=equipe.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar equipe: {str(e)}', 'danger')
            return redirect(request.url)
    
    # GET - buscar usuários para responsável
    usuarios = User.query.filter_by(ativo=True).all()
    
    return render_template('equipes/criar.html', usuarios=usuarios)


@equipes_bp.route('/<uuid:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar(id):
    """Editar equipe"""
    equipe = Equipe.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome', equipe.nome)
            tipo_servico = request.form.get('tipo_servico', equipe.tipo_servico)
            telefone_emergencia = request.form.get('telefone_emergencia', equipe.telefone_emergencia)
            responsavel_id = request.form.get('responsavel_id')
            
            # 🚫 Evitar duplicação de nome em outra equipe
            if Equipe.query.filter(func.lower(Equipe.nome) == nome.lower(), Equipe.id != id).first():
                flash('Já existe outra equipe com este nome.', 'warning')
                return redirect(request.url)
            
            # ✅ Atualizar dados
            equipe.nome = nome.strip()
            equipe.tipo_servico = tipo_servico.strip()
            equipe.telefone_emergencia = telefone_emergencia.strip() if telefone_emergencia else None
            equipe.responsavel_id = responsavel_id if responsavel_id else None
            
            db.session.commit()
            flash('Equipe atualizada com sucesso!', 'success')
            return redirect(url_for('equipes.detalhes', id=id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar equipe: {str(e)}', 'danger')
            return redirect(request.url)
    
    # GET — listar usuários para seleção de responsável
    usuarios = User.query.filter_by(ativo=True).all()
    return render_template('equipes/editar.html', equipe=equipe, usuarios=usuarios)



@equipes_bp.route('/<uuid:id>/desativar', methods=['POST'])
@login_required
@admin_required
def desativar(id):
    """Desativar equipe"""
    equipe = Equipe.query.get_or_404(id)
    
    try:
        # Verificar se tem OS ativas
        os_ativas = OrdemServico.query.filter(
            OrdemServico.equipe_id == id,
            OrdemServico.status.in_(['criada', 'atribuida', 'em_andamento'])
        ).count()
        
        if os_ativas > 0:
            flash(f'Não é possível desativar equipe com {os_ativas} OS ativas.', 'warning')
            return redirect(url_for('equipes.detalhes', id=id))
        
        equipe.ativa = False
        db.session.commit()
        
        flash('Equipe desativada com sucesso.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao desativar: {str(e)}', 'danger')
    
    return redirect(url_for('equipes.lista'))


@equipes_bp.route('/<uuid:id>/excluir', methods=['POST'])
@login_required
@role_required(['admin'])
def excluir(id):
    """Exclui completamente uma equipe (se não tiver OS ativas)"""
    equipe = Equipe.query.get_or_404(id)

    os_ativas = OrdemServico.query.filter(
        OrdemServico.equipe_id == id,
        OrdemServico.status.in_(['criada', 'atribuida', 'em_andamento'])
    ).count()

    if os_ativas > 0:
        flash(f'Não é possível excluir. A equipe possui {os_ativas} OS ativas.', 'warning')
        return redirect(url_for('equipes.detalhes', id=id))

    try:
        # Desvincular todos os membros
        membros = User.query.filter_by(equipe_id=id).all()
        for m in membros:
            m.equipe_id = None

        db.session.delete(equipe)
        db.session.commit()
        flash('Equipe excluída com sucesso!', 'success')
        return redirect(url_for('equipes.lista'))
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir equipe: {str(e)}', 'danger')
        return redirect(url_for('equipes.detalhes', id=id))



@equipes_bp.route('/<uuid:id>/ativar', methods=['POST'])
@login_required
@admin_required
def ativar(id):
    """Ativar equipe"""
    equipe = Equipe.query.get_or_404(id)
    
    try:
        equipe.ativa = True
        db.session.commit()
        flash('Equipe ativada com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao ativar: {str(e)}', 'danger')
    
    return redirect(url_for('equipes.detalhes', id=id))

@equipes_bp.route('/<uuid:id>/adicionar-membro', methods=['POST'])
@login_required
@role_required(['admin'])
def adicionar_membro(id):
    """Adiciona um membro a uma equipe (somente admin)"""
    equipe = Equipe.query.get_or_404(id)
    usuario_id = request.form.get('usuario_id')

    if not usuario_id:
        flash('Selecione um usuário válido.', 'warning')
        return redirect(url_for('equipes.detalhes', id=id))

    usuario = User.query.get_or_404(usuario_id)

    if usuario.equipe_id and usuario.equipe_id != id:
        flash(f'{usuario.nome_completo} já pertence a outra equipe.', 'warning')
        return redirect(url_for('equipes.detalhes', id=id))

    try:
        usuario.equipe_id = id
        db.session.commit()
        flash(f'{usuario.nome_completo} foi adicionado à equipe "{equipe.nome}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao adicionar membro: {str(e)}', 'danger')

    return redirect(url_for('equipes.detalhes', id=id))


@equipes_bp.route('/<uuid:id>/remover-membro/<uuid:usuario_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def remover_membro(id, usuario_id):
    """Remove membro da equipe (somente admin)"""
    equipe = Equipe.query.get_or_404(id)
    usuario = User.query.get_or_404(usuario_id)

    # Não permitir remover o responsável da equipe
    if equipe.responsavel_id == usuario_id:
        flash('Não é possível remover o responsável da equipe.', 'warning')
        return redirect(url_for('equipes.detalhes', id=id))

    # Verificar se o usuário tem OS pendentes
    os_ativas = OrdemServico.query.filter(
        OrdemServico.responsavel_campo_id == usuario_id,
        OrdemServico.status.in_(['atribuida', 'em_andamento'])
    ).count()

    if os_ativas > 0:
        flash(f'Não é possível remover {usuario.nome_completo}, pois possui {os_ativas} OS ativas.', 'warning')
        return redirect(url_for('equipes.detalhes', id=id))

    try:
        usuario.equipe_id = None
        db.session.commit()
        flash(f'{usuario.nome_completo} foi removido da equipe "{equipe.nome}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover membro: {str(e)}', 'danger')

    return redirect(url_for('equipes.detalhes', id=id))


@equipes_bp.route('/<uuid:id>/performance')
@login_required
@admin_required
def performance(id):
    """Relatório de performance da equipe"""
    equipe = Equipe.query.get_or_404(id)
    
    # Período (últimos 30 dias)
    data_fim = datetime.now()
    data_inicio = data_fim - timedelta(days=30)
    
    # OS no período
    os_periodo = OrdemServico.query.filter(
        OrdemServico.equipe_id == id,
        OrdemServico.created_at >= data_inicio,
        OrdemServico.created_at <= data_fim
    ).all()
    
    # Métricas
    total = len(os_periodo)
    concluidas = sum(1 for os in os_periodo if os.status == 'aprovada')
    rejeitadas = sum(1 for os in os_periodo if os.status == 'rejeitada')
    
    taxa_aprovacao = (concluidas / total * 100) if total > 0 else 0
    
    # Tempo médio de conclusão
    tempos = []
    for os in os_periodo:
        if os.status == 'aprovada' and os.data_aprovacao and os.created_at:
            diff = os.data_aprovacao - os.created_at
            tempos.append(diff.total_seconds() / 3600)
    
    tempo_medio = sum(tempos) / len(tempos) if tempos else 0
    
    # Performance por membro
    membros = User.query.filter_by(equipe_id=id).all()
    performance_membros = []
    
    for membro in membros:
        os_membro = [os for os in os_periodo if os.responsavel_campo_id == membro.id]
        concluidas_membro = sum(1 for os in os_membro if os.status == 'aprovada')
        
        performance_membros.append({
            'membro': membro,
            'total_os': len(os_membro),
            'concluidas': concluidas_membro,
            'taxa': (concluidas_membro / len(os_membro) * 100) if len(os_membro) > 0 else 0
        })
    
    return render_template('equipes/performance.html',
                         equipe=equipe,
                         total=total,
                         concluidas=concluidas,
                         rejeitadas=rejeitadas,
                         taxa_aprovacao=round(taxa_aprovacao, 1),
                         tempo_medio=round(tempo_medio, 1),
                         performance_membros=performance_membros,
                         data_inicio=data_inicio,
                         data_fim=data_fim)