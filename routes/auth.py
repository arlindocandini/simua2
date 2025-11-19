from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from urllib.parse import urlparse  # Use urllib.parse ao invés de werkzeug.urls

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login de usuário"""
    # Se já está logado, redireciona
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        lembrar = request.form.get('lembrar', False)
        
        # Validações básicas
        if not email or not senha:
            flash('Por favor, preencha todos os campos.', 'warning')
            return render_template('auth/login.html')
        
        # Buscar usuário
        user = User.query.filter_by(email=email.lower()).first()
        
        # Verificar credenciais
        if user is None or not user.check_senha(senha):
            flash('Email ou senha incorretos.', 'danger')
            return render_template('auth/login.html')
        
        # Verificar se está ativo
        if not user.ativo:
            flash('Sua conta está desativada. Contate o administrador.', 'warning')
            return render_template('auth/login.html')
        
        # Login do usuário
        login_user(user, remember=lembrar)
        user.atualizar_ultimo_login()
        
        flash(f'Bem-vindo, {user.nome_completo}!', 'success')
        
        # Redirecionar para próxima página ou dashboard
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':  # Mudança aqui
            next_page = url_for('dashboard.index')
        
        return redirect(next_page)
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Logout de usuário"""
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de novo usuário (apenas admin pode acessar via interface)"""
    # Em produção, deve ser restrito apenas para admins
    # Por enquanto, vamos permitir auto-registro para desenvolvimento
    
    if request.method == 'POST':
        nome = request.form.get('nome_completo')
        email = request.form.get('email')
        senha = request.form.get('senha')
        senha_confirm = request.form.get('senha_confirm')
        tipo_usuario = request.form.get('tipo_usuario', 'gestor')
        
        # Validações
        if not all([nome, email, senha, senha_confirm]):
            flash('Por favor, preencha todos os campos.', 'warning')
            return render_template('auth/register.html')
        
        if senha != senha_confirm:
            flash('As senhas não coincidem.', 'warning')
            return render_template('auth/register.html')
        
        if len(senha) < 6:
            flash('A senha deve ter no mínimo 6 caracteres.', 'warning')
            return render_template('auth/register.html')
        
        # Verificar se email já existe
        if User.query.filter_by(email=email.lower()).first():
            flash('Este email já está cadastrado.', 'warning')
            return render_template('auth/register.html')
        
        # Criar usuário
        user = User(
            nome_completo=nome,
            email=email.lower(),
            tipo_usuario=tipo_usuario,
            ativo=True
        )
        user.set_senha(senha)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Conta criada com sucesso! Faça login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    """Recuperação de senha (placeholder - implementar envio de email)"""
    if request.method == 'POST':
        email = request.form.get('email')
        
        user = User.query.filter_by(email=email.lower()).first()
        
        if user:
            # TODO: Implementar envio de email com token de recuperação
            flash('Instruções de recuperação foram enviadas para seu email.', 'info')
        else:
            # Por segurança, sempre mostrar mensagem de sucesso
            flash('Se este email estiver cadastrado, você receberá instruções.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/recuperar_senha.html')