from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc, or_
from app import db, socketio
from app.models import OrdemServico, Ocorrencia, Equipe, User, HistoricoOS, Notificacao
from app.services.image_service import ImageService
from app.utils.decorators import gestor_required, campo_required
from datetime import datetime, date
import os

os_bp = Blueprint('os', __name__)



# =========================================================
# LISTAGEM / DETALHES
# =========================================================
@os_bp.route('/')
@os_bp.route('/lista')
@login_required
def lista():
    """Lista todas as OS (view diferente para gestor vs campo)"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Filtros
    status = request.args.get('status')
    prioridade = request.args.get('prioridade')
    equipe_id = request.args.get('equipe_id')
    
    # Query base (diferente por tipo de usuário)
    if current_user.is_campo:
        # Equipe de campo vê apenas suas OS
        query = OrdemServico.query.filter(
            or_(
                OrdemServico.responsavel_campo_id == current_user.id,
                OrdemServico.equipe_id == current_user.equipe_id
            )
        )
    else:
        # Gestor/Admin vê todas
        query = OrdemServico.query
    
    # Aplicar filtros
    if status:
        query = query.filter(OrdemServico.status == status)
    
    if prioridade:
        query = query.filter(OrdemServico.prioridade == prioridade)
    
    if equipe_id:
        query = query.filter(OrdemServico.equipe_id == equipe_id)
    
    # Ordenar por data de criação (mais recentes primeiro)
    query = query.order_by(desc(OrdemServico.created_at))
    
    # Paginar
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    ordens = pagination.items
    
    # Buscar equipes para filtro
    equipes = Equipe.query.filter_by(ativa=True).all()
    
    return render_template('ordens_servico/lista.html',
                         ordens=ordens,
                         pagination=pagination,
                         equipes=equipes)

@os_bp.route('/<uuid:id>')
@login_required
def detalhes(id):
    """Detalhes de uma OS específica"""
    os = OrdemServico.query.get_or_404(id)
    
    # Verificar permissão
    if current_user.is_campo:
        if os.responsavel_campo_id != current_user.id and os.equipe_id != current_user.equipe_id:
            flash('Você não tem permissão para visualizar esta OS.', 'danger')
            return redirect(url_for('os.lista'))
    
    # Buscar histórico
    historico = HistoricoOS.query.filter_by(os_id=id).order_by(HistoricoOS.created_at).all()
    
    return render_template('ordens_servico/detalhes.html',
                         os=os,
                         historico=historico)

# =========================================================
# CRIAÇÃO / ATRIBUIÇÃO / EXECUÇÃO
# =========================================================
@os_bp.route('/criar', methods=['GET', 'POST'])
@login_required
@gestor_required
def criar():
    """Criar nova OS a partir de ocorrência"""
    if request.method == 'POST':
        try:
            ocorrencia_id = request.form.get('ocorrencia_id')
            
            # Validar ocorrência
            ocorrencia = Ocorrencia.query.get_or_404(ocorrencia_id)
            
            if ocorrencia.status == 'em_os':
                flash('Esta ocorrência já possui uma OS associada.', 'warning')
                return redirect(url_for('ocorrencias.detalhes', id=ocorrencia_id))
            
            # Criar OS
            os = OrdemServico(
                ocorrencia_id=ocorrencia_id,
                categoria=request.form.get('categoria', ocorrencia.categoria),
                prioridade=request.form.get('prioridade', 'media'),
                equipe_id=request.form.get('equipe_id'),
                responsavel_campo_id=request.form.get('responsavel_campo_id'),
                gestor_criador_id=current_user.id,
                descricao=request.form.get('descricao'),
                observacoes_criacao=request.form.get('observacoes_criacao'),
                prazo_execucao=datetime.strptime(
                    request.form.get('prazo_execucao'), '%Y-%m-%d'
                ).date() if request.form.get('prazo_execucao') else None,
                latitude=ocorrencia.latitude,
                longitude=ocorrencia.longitude,
                endereco_completo=ocorrencia.endereco_completo,
                foto_antes_url=ocorrencia.imagem_path,
                status='criada'
            )
            
            # Gerar número único
            os.gerar_numero_os()
            
            db.session.add(os)
            db.session.flush()  # ✅ Garante que os.id seja gerado antes do histórico
            
            # Atualizar status da ocorrência
            ocorrencia.status = 'em_os'
            
            # Criar registro no histórico
            historico = HistoricoOS(
                os_id=os.id,
                status_anterior=None,
                status_novo='criada',
                usuario_id=current_user.id,
                comentario='OS criada'
            )
            db.session.add(historico)
            
            # Criar notificação para equipe
            if os.responsavel_campo_id:
                notificacao = Notificacao(
                    usuario_id=os.responsavel_campo_id,
                    tipo='os_atribuida',
                    titulo='Nova OS atribuída',
                    mensagem=f'Você foi designado para a OS #{os.numero_os}',
                    os_id=os.id
                )
                db.session.add(notificacao)
            
            db.session.commit()
            
            # Emitir evento WebSocket
            socketio.emit('nova_os', {
                'id': str(os.id),
                'numero_os': os.numero_os,
                'categoria': os.categoria,
                'prioridade': os.prioridade
            }, namespace='/dashboard')
            
            flash(f'OS {os.numero_os} criada com sucesso!', 'success')
            return redirect(url_for('os.detalhes', id=os.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar OS: {str(e)}', 'danger')
            return redirect(request.referrer or url_for('ocorrencias.lista'))
    
    # GET - mostrar formulário
    ocorrencia_id = request.args.get('ocorrencia_id')
    ocorrencia = None
    
    if ocorrencia_id:
        ocorrencia = Ocorrencia.query.get(ocorrencia_id)
    
    equipes = Equipe.query.filter_by(ativa=True).all()
    
    return render_template('ordens_servico/criar.html',
                         ocorrencia=ocorrencia,
                         equipes=equipes)


@os_bp.route('/<uuid:id>/atribuir', methods=['POST'])
@login_required
@gestor_required
def atribuir(id):
    """Atribuir OS a um responsável"""
    os = OrdemServico.query.get_or_404(id)
    
    try:
        responsavel_id = request.form.get('responsavel_campo_id')
        
        if not responsavel_id:
            flash('Selecione um responsável.', 'warning')
            return redirect(url_for('os.detalhes', id=id))
        
        # Atualizar OS
        status_anterior = os.status
        os.responsavel_campo_id = responsavel_id
        os.status = 'atribuida'
        os.data_atribuicao = datetime.utcnow()
        
        # Histórico
        historico = HistoricoOS(
            os_id=os.id,
            status_anterior=status_anterior,
            status_novo='atribuida',
            usuario_id=current_user.id,
            comentario=f'OS atribuída ao responsável'
        )
        db.session.add(historico)
        
        # Notificação
        notificacao = Notificacao(
            usuario_id=responsavel_id,
            tipo='os_atribuida',
            titulo='OS atribuída a você',
            mensagem=f'Você foi designado para executar a OS #{os.numero_os}',
            os_id=os.id
        )
        db.session.add(notificacao)
        
        db.session.commit()
        
        flash('OS atribuída com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atribuir OS: {str(e)}', 'danger')
    
    return redirect(url_for('os.detalhes', id=id))



@os_bp.route('/<uuid:id>/iniciar', methods=['POST'])
@login_required
@campo_required
def iniciar(id):
    """Permite que qualquer membro da equipe inicie a OS se ainda não tiver responsável."""
    os = OrdemServico.query.get_or_404(id)

    # Impede iniciar se já está em andamento
    if os.status == 'em_andamento':
        flash('Esta OS já foi iniciada por outro membro da equipe.', 'warning')
        return redirect(url_for('os.detalhes', id=id))

    # Permite iniciar se:
    # - o usuário é o responsável direto, ou
    # - a OS não tem responsável e pertence à mesma equipe do usuário
    if os.responsavel_campo_id and os.responsavel_campo_id != current_user.id:
        flash('Você não tem permissão para iniciar esta OS.', 'danger')
        return redirect(url_for('os.detalhes', id=id))

    if not os.equipe_id or os.equipe_id != current_user.equipe_id:
        flash('Você não pertence à equipe designada para esta OS.', 'danger')
        return redirect(url_for('os.detalhes', id=id))

    try:
        status_anterior = os.status
        os.status = 'em_andamento'
        os.data_inicio_execucao = datetime.utcnow()

        # Se ninguém ainda é responsável, define o atual
        if not os.responsavel_campo_id:
            os.responsavel_campo_id = current_user.id

        historico = HistoricoOS(
            os_id=os.id,
            status_anterior=status_anterior,
            status_novo='em_andamento',
            usuario_id=current_user.id,
            comentario=f'Execução iniciada por {current_user.nome_completo}'
        )
        db.session.add(historico)
        db.session.commit()

        flash('Execução da OS iniciada com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao iniciar OS: {str(e)}', 'danger')

    return redirect(url_for('os.detalhes', id=id))

# =========================================================
# CONCLUSÃO (CAMPO OU APP)
# =========================================================
@os_bp.route('/<uuid:id>/concluir', methods=['POST'])
@login_required
@campo_required
def concluir(id):
    """Concluir execução da OS"""
    os = OrdemServico.query.get_or_404(id)
    if os.responsavel_campo_id != current_user.id:
        flash('Você não tem permissão para concluir esta OS.', 'danger')
        return redirect(url_for('os.detalhes', id=id))

    try:
        if 'foto_depois' in request.files:
            file = request.files['foto_depois']
            if file and ImageService.allowed_file(file.filename):
                filename = f"os_{os.numero_os}_depois_{secure_filename(file.filename)}"
                foto_path = os.path.join('app/static/uploads/os_fotos', filename)
                file.save(foto_path)
                os.foto_depois_url = foto_path

        os.status = 'aguardando_aprovacao'
        os.data_conclusao_execucao = datetime.utcnow()
        os.observacoes_execucao = request.form.get('observacoes_execucao', '')
        db.session.add(HistoricoOS(os_id=os.id, status_novo='aguardando_aprovacao', usuario_id=current_user.id, comentario='Execução concluída'))
        db.session.add(Notificacao(usuario_id=os.gestor_criador_id, tipo='os_concluida', titulo='OS aguardando aprovação', mensagem=f'A OS #{os.numero_os} foi concluída.', os_id=os.id))
        db.session.commit()
        socketio.emit('os_atualizada', {'id': str(os.id), 'status': os.status, 'foto_depois_url': os.foto_depois_url}, namespace='/dashboard')
        flash('OS concluída! Aguardando aprovação do gestor.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao concluir OS: {e}', 'danger')
    return redirect(url_for('os.detalhes', id=id))


# =========================================================
# API MOBILE UPLOAD
# =========================================================
@os_bp.route('/api/<uuid:id>/upload-foto', methods=['POST'])
@login_required
@campo_required
def upload_foto_mobile(id):
    """Endpoint de upload de foto via app mobile"""
    os = OrdemServico.query.get_or_404(id)
    if os.responsavel_campo_id != current_user.id:
        return jsonify({'erro': 'Sem permissão'}), 403
    if 'foto' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    file = request.files['foto']
    if not ImageService.allowed_file(file.filename):
        return jsonify({'erro': 'Formato inválido'}), 400

    try:
        filename = f"os_{os.numero_os}_depois_{secure_filename(file.filename)}"
        foto_path = os.path.join('app/static/uploads/os_fotos', filename)
        file.save(foto_path)
        os.foto_depois_url = foto_path
        os.data_conclusao_execucao = datetime.utcnow()
        os.status = 'aguardando_aprovacao'
        db.session.commit()
        socketio.emit('os_atualizada', {'id': str(os.id), 'status': os.status, 'foto_depois_url': os.foto_depois_url}, namespace='/dashboard')
        return jsonify({'mensagem': 'Foto enviada com sucesso', 'foto_url': foto_path})
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500



@os_bp.route('/<uuid:id>/aprovar', methods=['POST'])
@login_required
@gestor_required
def aprovar(id):
    """Aprovar OS concluída"""
    os = OrdemServico.query.get_or_404(id)
    
    try:
        status_anterior = os.status
        os.status = 'aprovada'
        os.gestor_aprovador_id = current_user.id
        os.data_aprovacao = datetime.utcnow()
        os.observacoes_aprovacao = request.form.get('observacoes_aprovacao', '')
        
        # Atualizar ocorrência
        if os.ocorrencia:
            os.ocorrencia.status = 'resolvida'
        
        # Histórico
        historico = HistoricoOS(
            os_id=os.id,
            status_anterior=status_anterior,
            status_novo='aprovada',
            usuario_id=current_user.id,
            comentario=f'OS aprovada: {os.observacoes_aprovacao}'
        )
        db.session.add(historico)
        
        # Notificar responsável
        if os.responsavel_campo_id:
            notificacao = Notificacao(
                usuario_id=os.responsavel_campo_id,
                tipo='os_aprovada',
                titulo='OS aprovada',
                mensagem=f'Sua OS #{os.numero_os} foi aprovada',
                os_id=os.id
            )
            db.session.add(notificacao)
        
        db.session.commit()
        
        flash('OS aprovada com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao aprovar OS: {str(e)}', 'danger')
    
    return redirect(url_for('os.detalhes', id=id))

@os_bp.route('/<uuid:id>/rejeitar', methods=['POST'])
@login_required
@gestor_required
def rejeitar(id):
    """Rejeitar OS concluída"""
    os = OrdemServico.query.get_or_404(id)
    
    try:
        motivo = request.form.get('motivo_rejeicao', '')
        
        if not motivo:
            flash('Informe o motivo da rejeição.', 'warning')
            return redirect(url_for('os.detalhes', id=id))
        
        status_anterior = os.status
        os.status = 'em_andamento'  # Volta para execução
        os.gestor_aprovador_id = current_user.id
        os.observacoes_aprovacao = f'REJEITADA: {motivo}'
        
        # Histórico
        historico = HistoricoOS(
            os_id=os.id,
            status_anterior=status_anterior,
            status_novo='em_andamento',
            usuario_id=current_user.id,
            comentario=f'OS rejeitada: {motivo}'
        )
        db.session.add(historico)
        
        # Notificar responsável
        if os.responsavel_campo_id:
            notificacao = Notificacao(
                usuario_id=os.responsavel_campo_id,
                tipo='os_rejeitada',
                titulo='OS rejeitada',
                mensagem=f'Sua OS #{os.numero_os} foi rejeitada. Motivo: {motivo}',
                os_id=os.id
            )
            db.session.add(notificacao)
        
        db.session.commit()
        
        flash('OS rejeitada. O responsável foi notificado.', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao rejeitar OS: {str(e)}', 'danger')
    
    return redirect(url_for('os.detalhes', id=id))

@os_bp.route('/minhas-os')
@login_required
@campo_required
def minhas_os():
    """Lista OS do usuário (equipe de campo)"""
    # OS atribuídas a mim
    minhas = OrdemServico.query.filter(
        OrdemServico.responsavel_campo_id == current_user.id,
        OrdemServico.status.in_(['atribuida', 'em_andamento'])
    ).order_by(OrdemServico.prazo_execucao).all()
    
    # OS da minha equipe (não atribuídas a mim)
    equipe = []
    if current_user.equipe_id:
        equipe = OrdemServico.query.filter(
            OrdemServico.equipe_id == current_user.equipe_id,
            OrdemServico.status.in_(['criada', 'atribuida']),
            OrdemServico.responsavel_campo_id != current_user.id
        ).order_by(OrdemServico.prazo_execucao).all()
    
    return render_template('ordens_servico/campo_minhas.html',
                         minhas=minhas,
                         equipe=equipe)

@os_bp.route('/mapa-campo')
@login_required
@campo_required
def mapa_campo():
    """Mapa de OS para equipe de campo"""
    return render_template('ordens_servico/mapa_campo.html')