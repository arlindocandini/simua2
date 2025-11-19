import uuid
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app import db

class User(UserMixin, db.Model):
    """Model de Usuário do Sistema"""
    
    __tablename__ = 'users'
    
    # Enums
    TIPO_USUARIO_ENUM = ENUM(
        'gestor', 'equipe_campo', 'admin',
        name='tipo_usuario_enum', create_type=False
    )
    
    # Colunas
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome_completo = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    tipo_usuario = db.Column(TIPO_USUARIO_ENUM, nullable=False, default='gestor')
    
    # Relacionamentos
    equipe_id = db.Column(UUID(as_uuid=True), db.ForeignKey('equipes.id'), nullable=True)
    
    # Informações adicionais
    telefone = db.Column(db.String(20))
    foto_perfil_url = db.Column(db.String(500))
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    ultimo_login = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)
    
    # Relacionamentos reversos
    equipe = db.relationship('Equipe', foreign_keys=[equipe_id], backref='membros')
    
    # ⚠️ Corrigido: usar back_populates (sem backref) para evitar conflito com 'criador' em OrdemServico
    os_criadas = db.relationship(
        'OrdemServico',
        foreign_keys='OrdemServico.gestor_criador_id',
        back_populates='criador',
        lazy='dynamic'
    )
    
    # Relacionamento com o responsável de campo
    os_atribuidas = db.relationship(
        'OrdemServico',
        foreign_keys='OrdemServico.responsavel_campo_id',
        back_populates='responsavel_campo',
        lazy='dynamic'
    )
    
    # (Opcional, mas útil) Relacionamento com o aprovador
    os_aprovadas_por = db.relationship(
        'OrdemServico',
        foreign_keys='OrdemServico.gestor_aprovador_id',
        back_populates='aprovador',
        lazy='dynamic'
    )
    
    notificacoes = db.relationship(
        'Notificacao',
        backref='usuario',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if 'senha' in kwargs:
            self.set_senha(kwargs['senha'])
    
    def set_senha(self, senha):
        """Define a senha do usuário (hash)"""
        self.senha_hash = generate_password_hash(senha)
    
    def check_senha(self, senha):
        """Verifica se a senha está correta"""
        return check_password_hash(self.senha_hash, senha)
    
    def get_id(self):
        """Retorna o ID para Flask-Login"""
        return str(self.id)
    
    @property
    def is_gestor(self):
        """Verifica se é gestor"""
        return self.tipo_usuario in ['gestor', 'admin']
    
    @property
    def is_admin(self):
        """Verifica se é admin"""
        return self.tipo_usuario == 'admin'
    
    @property
    def is_campo(self):
        """Verifica se é equipe de campo"""
        return self.tipo_usuario == 'equipe_campo'
    
    def atualizar_ultimo_login(self):
        """Atualiza timestamp do último login"""
        self.ultimo_login = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Serializa o usuário para dicionário"""
        return {
            'id': str(self.id),
            'nome_completo': self.nome_completo,
            'email': self.email,
            'tipo_usuario': self.tipo_usuario,
            'equipe_id': str(self.equipe_id) if self.equipe_id else None,
            'telefone': self.telefone,
            'foto_perfil_url': self.foto_perfil_url,
            'ativo': self.ativo,
            'ultimo_login': self.ultimo_login.isoformat() if self.ultimo_login else None,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<User {self.email}>'
