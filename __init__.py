import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from config import config
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf


csrf = CSRFProtect()

# Inicialização das extensões
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
socketio = SocketIO()
csrf = CSRFProtect()

def create_app(config_name=None):
    """
    Factory function para criar a aplicação Flask
    
    Args:
        config_name: Nome da configuração ('development', 'production', 'testing')
    
    Returns:
        app: Instância configurada da aplicação Flask
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    

    csrf.init_app(app)
    app.jinja_env.globals['csrf_token'] = generate_csrf

    # Inicializar extensões
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # Configurar Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'warning'
    
    # Configurar SocketIO
    socketio.init_app(
        app,
        #message_queue=app.config['SOCKETIO_MESSAGE_QUEUE'],
        cors_allowed_origins="*",  # Configurar adequadamente em produção
        async_mode='threading'
    )
    
    # Criar diretórios necessários
    create_directories(app)
    
    # Registrar blueprints
    register_blueprints(app)
    
    # Registrar filtros Jinja
    register_template_filters(app)
    
    # Registrar error handlers
    register_error_handlers(app)
    
    # Registrar rota raiz
    register_root_route(app)
    
    # Registrar comandos CLI
    register_cli_commands(app)
    
    return app

@login_manager.user_loader
def load_user(user_id):
    """Callback para recarregar o usuário da sessão"""
    from app.models import User
    try:
        from uuid import UUID
        user_uuid = UUID(user_id)
        return User.query.get(user_uuid)
    except (ValueError, AttributeError):
        return None

def create_directories(app):
    """Cria diretórios necessários para a aplicação"""
    directories = [
        app.config['UPLOAD_FOLDER'],
        os.path.join(app.config['UPLOAD_FOLDER'], 'ocorrencias'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'miniaturas'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'perfis'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'relatorios'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'os_fotos'),
        'logs'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def register_blueprints(app):
    """Registra todos os blueprints da aplicação"""
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.dashboard_api import dashboard_api_bp
    from app.routes.ocorrencias import ocorrencias_bp
    from app.routes.ordens_servico import os_bp
    from app.routes.cameras import cameras_bp
    from app.routes.perfil import perfil_bp
    from app.routes.relatorios import relatorios_bp
    from app.routes.equipes import equipes_bp
    from app.routes.api import api_bp
    

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(dashboard_api_bp)
    app.register_blueprint(ocorrencias_bp, url_prefix='/ocorrencias')
    app.register_blueprint(os_bp, url_prefix='/os')
    app.register_blueprint(cameras_bp, url_prefix='/cameras')
    app.register_blueprint(perfil_bp, url_prefix='/perfil')
    app.register_blueprint(relatorios_bp, url_prefix='/relatorios')
    app.register_blueprint(equipes_bp, url_prefix='/equipes')
    app.register_blueprint(api_bp, url_prefix='/api')
    

def register_template_filters(app):
    """Registra filtros customizados para templates Jinja"""
    from datetime import datetime
    
    @app.template_filter('datetime')
    def format_datetime(value, format='%d/%m/%Y %H:%M'):
        """Formata datetime"""
        if value is None:
            return ''
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return value.strftime(format)
    
    @app.template_filter('date')
    def format_date(value, format='%d/%m/%Y'):
        """Formata date"""
        if value is None:
            return ''
        return value.strftime(format)
    
    @app.template_filter('urgencia_cor')
    def urgencia_cor(urgencia):
        """Retorna cor baseada na urgência"""
        cores = {
            'emergencia': '#FF4C4C',
            'urgente': '#FFD700',
            'pouco_urgente': '#4CAF50',
            'nao_urgente': '#1E90FF'
        }
        return cores.get(urgencia, '#808080')
    
    @app.template_filter('status_cor')
    def status_cor(status):
        """Retorna cor baseada no status"""
        cores = {
            'pendente': '#FFA500',
            'em_os': '#1E90FF',
            'resolvida': '#4CAF50',
            'cancelada': '#808080',
            'criada': '#1E90FF',
            'atribuida': '#FFD700',
            'em_andamento': '#FFA500',
            'aguardando_aprovacao': '#9370DB',
            'aprovada': '#4CAF50',
            'rejeitada': '#FF4C4C',
            'concluida': '#008000'
        }
        return cores.get(status, '#808080')

def register_error_handlers(app):
    """Registra handlers para erros HTTP"""
    from flask import render_template, jsonify, request
    
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Recurso não encontrado'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Acesso negado'}), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Erro interno do servidor'}), 500
        return render_template('errors/500.html'), 500

def register_root_route(app):
    """Registra rota raiz que redireciona para login ou dashboard"""
    @app.route('/')
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

def register_cli_commands(app):
    """Registra comandos CLI customizados"""
    import click
    
    @app.cli.command('seed')
    def seed_database():
        """Popula banco de dados com dados iniciais"""
        from seed_database import seed
        seed()
        click.echo('✅ Banco de dados populado com sucesso!')
    
    @app.cli.command('create-admin')
    @click.option('--email', prompt=True)
    @click.option('--senha', prompt=True, hide_input=True, 
                  confirmation_prompt=True)
    @click.option('--nome', prompt=True)
    def create_admin(email, senha, nome):
        """Cria usuário administrador"""
        from app.models import User
        
        if User.query.filter_by(email=email).first():
            click.echo('❌ Email já existe!')
            return
        
        admin = User(
            nome_completo=nome,
            email=email,
            tipo_usuario='admin',
            ativo=True
        )
        admin.set_senha(senha)
        
        db.session.add(admin)
        db.session.commit()
        
        click.echo(f'✅ Admin {nome} criado com sucesso!')
    
    @app.cli.command('init-db')
    def init_database():
        """Inicializa banco de dados (cria todas as tabelas)"""
        db.create_all()
        click.echo('✅ Banco de dados inicializado!')
    
    @app.cli.command('test-db')
    def test_database():
        """Testa conexão com o banco de dados"""
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            click.echo('✅ Conexão com banco de dados OK!')
        except Exception as e:
            click.echo(f'❌ Erro na conexão: {str(e)}')