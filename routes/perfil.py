from flask import Blueprint, jsonify, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import User, OrdemServico, Notificacao
from app.services.image_service import ImageService
from datetime import datetime, timedelta
import os

perfil_bp = Blueprint('perfil', __name__)

@perfil_bp.route('/')
@login_required
def index():
    """Perfil do usuário"""
    
    # Estatísticas pessoais
    estatisticas = obter_estatisticas_usuario(current_user)
    
    # Últimas atividades
    atividades = obter_ultimas_atividades(current_user)
    
    # Notificações recentes
    notificacoes = Notificacao.query.filter_by(
        usuario_id=current_user.id
    ).order_by(Notificacao.created_at.desc()).limit(5).all()
    
    return render_template('perfil/index.html',
                         usuario=current_user,
                         estatisticas=estatisticas,
                         atividades=atividades,
                         notificacoes=notificacoes)

@perfil_bp.route('/editar', methods=['GET', 'POST'])
@login_required
def editar():
    """Editar dados do perfil"""
    if request.method == 'POST':
        try:
            # Atualizar dados básicos
            current_user.nome_completo = request.form.get('nome_completo', current_user.nome_completo)
            current_user.telefone = request.form.get('telefone', current_user.telefone)
            
            # Upload de foto de perfil
            if 'foto_perfil' in request.files:
                file = request.files['foto_perfil']
                
                if file and file.filename != '':
                    if ImageService.allowed_file(file.filename):
                        # Deletar foto antiga
                        if current_user.foto_perfil_url and os.path.exists(current_user.foto_perfil_url):
                            os.remove(current_user.foto_perfil_url)
                        
                        # Salvar nova foto
                        filename = secure_filename(f"perfil_{current_user.id}_{file.filename}")
                        foto_path = os.path.join('app/static/uploads/perfis', filename)
                        file.save(foto_path)
                        
                        # Criar miniatura
                        ImageService.criar_miniatura(foto_path, foto_path, tamanho=(200, 200))
                        
                        current_user.foto_perfil_url = foto_path
                    else:
                        flash('Formato de imagem não permitido. Use JPG, JPEG ou PNG.', 'warning')
                        return redirect(request.url)
            
            db.session.commit()
            
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('perfil.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar perfil: {str(e)}', 'danger')
            return redirect(request.url)
    
    return render_template('perfil/editar.html', usuario=current_user)

@perfil_bp.route('/alterar-senha', methods=['GET', 'POST'])
@login_required
def alterar_senha():
    """Alterar senha"""
    if request.method == 'POST':
        try:
            senha_atual = request.form.get('senha_atual')
            senha_nova = request.form.get('senha_nova')
            senha_confirmacao = request.form.get('senha_confirmacao')
            
            # Validações
            if not all([senha_atual, senha_nova, senha_confirmacao]):
                flash('Preencha todos os campos.', 'warning')
                return redirect(request.url)
            
            # Verificar senha atual
            if not current_user.check_senha(senha_atual):
                flash('Senha atual incorreta.', 'danger')
                return redirect(request.url)
            
            # Verificar se nova senha coincide com confirmação
            if senha_nova != senha_confirmacao:
                flash('Nova senha e confirmação não coincidem.', 'warning')
                return redirect(request.url)
            
            # Verificar tamanho mínimo
            if len(senha_nova) < 6:
                flash('A senha deve ter no mínimo 6 caracteres.', 'warning')
                return redirect(request.url)
            
            # Atualizar senha
            current_user.set_senha(senha_nova)
            db.session.commit()
            
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('perfil.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao alterar senha: {str(e)}', 'danger')
            return redirect(request.url)
    
    return render_template('perfil/alterar_senha.html')

@perfil_bp.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    """Configurações do perfil (notificações, etc)"""
    # TODO: Implementar tabela de configurações de usuário
    # Por enquanto, apenas placeholder
    
    if request.method == 'POST':
        flash('Configurações salvas!', 'success')
        return redirect(url_for('perfil.index'))
    
    return render_template('perfil/configuracoes.html')

@perfil_bp.route('/notificacoes')
@login_required
def notificacoes():
    """Ver todas as notificações"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    pagination = Notificacao.query.filter_by(
        usuario_id=current_user.id
    ).order_by(Notificacao.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    notificacoes = pagination.items
    
    return render_template('perfil/notificacoes.html',
                         notificacoes=notificacoes,
                         pagination=pagination)

@perfil_bp.route('/notificacoes/<uuid:id>/ler', methods=['POST'])
@login_required
def marcar_notificacao_lida(id):
    """Marcar notificação como lida"""
    notificacao = Notificacao.query.get_or_404(id)
    
    # Verificar se é do usuário atual
    if notificacao.usuario_id != current_user.id:
        return jsonify({'erro': 'Acesso negado'}), 403
    
    notificacao.marcar_como_lida()
    
    return jsonify({'sucesso': True})

@perfil_bp.route('/historico-os')
@login_required
def historico_os():
    """Histórico de OS do usuário (para equipe de campo)"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Apenas para equipe de campo
    if not current_user.is_campo:
        flash('Esta página é apenas para equipe de campo.', 'warning')
        return redirect(url_for('perfil.index'))
    
    # Buscar OS do usuário (todas as finalizadas)
    pagination = OrdemServico.query.filter(
        OrdemServico.responsavel_campo_id == current_user.id,
        OrdemServico.status.in_(['aprovada', 'rejeitada', 'concluida'])
    ).order_by(OrdemServico.data_aprovacao.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    ordens = pagination.items
    
    return render_template('perfil/historico_os.html',
                         ordens=ordens,
                         pagination=pagination)

# Funções auxiliares

def obter_estatisticas_usuario(usuario):
    """
    Obtém estatísticas do usuário
    
    Args:
        usuario: Objeto User
        
    Returns:
        dict: Dicionário com estatísticas
    """
    estatisticas = {
        'total_os': 0,
        'os_concluidas': 0,
        'os_em_andamento': 0,
        'taxa_aprovacao': 0,
        'tempo_medio_conclusao': 0
    }
    
    if usuario.is_campo:
        # Estatísticas para equipe de campo
        estatisticas['total_os'] = OrdemServico.query.filter_by(
            responsavel_campo_id=usuario.id
        ).count()
        
        estatisticas['os_concluidas'] = OrdemServico.query.filter_by(
            responsavel_campo_id=usuario.id,
            status='aprovada'
        ).count()
        
        estatisticas['os_em_andamento'] = OrdemServico.query.filter(
            OrdemServico.responsavel_campo_id == usuario.id,
            OrdemServico.status.in_(['atribuida', 'em_andamento', 'aguardando_aprovacao'])
        ).count()
        
        # Taxa de aprovação
        total_finalizadas = OrdemServico.query.filter(
            OrdemServico.responsavel_campo_id == usuario.id,
            OrdemServico.status.in_(['aprovada', 'rejeitada'])
        ).count()
        
        if total_finalizadas > 0:
            estatisticas['taxa_aprovacao'] = round(
                (estatisticas['os_concluidas'] / total_finalizadas) * 100, 1
            )
        
        # Tempo médio de conclusão
        os_aprovadas = OrdemServico.query.filter_by(
            responsavel_campo_id=usuario.id,
            status='aprovada'
        ).all()
        
        if os_aprovadas:
            tempos = []
            for os in os_aprovadas:
                if os.data_aprovacao and os.created_at:
                    diff = os.data_aprovacao - os.created_at
                    tempos.append(diff.total_seconds() / 3600)  # em horas
            
            if tempos:
                estatisticas['tempo_medio_conclusao'] = round(sum(tempos) / len(tempos), 1)
    
    elif usuario.is_gestor or usuario.is_admin:
        # Estatísticas para gestor
        estatisticas['total_os'] = OrdemServico.query.filter_by(
            gestor_criador_id=usuario.id
        ).count()
        
        estatisticas['os_concluidas'] = OrdemServico.query.filter_by(
            gestor_criador_id=usuario.id,
            status='aprovada'
        ).count()
        
        estatisticas['os_em_andamento'] = OrdemServico.query.filter(
            OrdemServico.gestor_criador_id == usuario.id,
            OrdemServico.status.in_(['criada', 'atribuida', 'em_andamento', 'aguardando_aprovacao'])
        ).count()
    
    return estatisticas

def obter_ultimas_atividades(usuario, limite=10):
    """
    Obtém últimas atividades do usuário
    
    Args:
        usuario: Objeto User
        limite: Número de atividades a retornar
        
    Returns:
        list: Lista de atividades
    """
    atividades = []
    
    if usuario.is_campo:
        # Últimas OS atribuídas/modificadas
        os_recentes = OrdemServico.query.filter_by(
            responsavel_campo_id=usuario.id
        ).order_by(OrdemServico.updated_at.desc()).limit(limite).all()
        
        for os in os_recentes:
            atividades.append({
                'tipo': 'os',
                'descricao': f'OS #{os.numero_os} - {os.status}',
                'data': os.updated_at,
                'link': url_for('os.detalhes', id=os.id)
            })
    
    elif usuario.is_gestor or usuario.is_admin:
        # Últimas OS criadas
        os_criadas = OrdemServico.query.filter_by(
            gestor_criador_id=usuario.id
        ).order_by(OrdemServico.created_at.desc()).limit(limite).all()
        
        for os in os_criadas:
            atividades.append({
                'tipo': 'os_criada',
                'descricao': f'Criou OS #{os.numero_os}',
                'data': os.created_at,
                'link': url_for('os.detalhes', id=os.id)
            })
    
    return atividades