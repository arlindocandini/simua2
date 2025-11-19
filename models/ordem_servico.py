import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app import db

class OrdemServico(db.Model):
    """Model de Ordem de Serviço"""
    
    __tablename__ = 'ordens_servico'
    
    PRIORIDADE_ENUM = ENUM(
        'baixa', 'media', 'alta', 'critica',
        name='prioridade_enum', create_type=False
    )
    STATUS_OS_ENUM = ENUM(
        'criada', 'atribuida', 'em_andamento',
        'aguardando_aprovacao', 'aprovada', 'rejeitada',
        'concluida', name='status_os_enum', create_type=False
    )
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_os = db.Column(db.String(50), unique=True, nullable=False, index=True)
    ocorrencia_id = db.Column(UUID(as_uuid=True), db.ForeignKey('ocorrencias.id'), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    prioridade = db.Column(PRIORIDADE_ENUM, nullable=False)
    status = db.Column(STATUS_OS_ENUM, default='criada', nullable=False, index=True)
    
    # Relacionamentos com usuários/equipe
    equipe_id = db.Column(UUID(as_uuid=True), db.ForeignKey('equipes.id'))
    responsavel_campo_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    gestor_criador_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    gestor_aprovador_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    
    # Descrições e observações
    descricao = db.Column(db.Text)
    observacoes_criacao = db.Column(db.Text)
    observacoes_execucao = db.Column(db.Text)
    observacoes_aprovacao = db.Column(db.Text)
    
    # Datas
    prazo_execucao = db.Column(db.Date)
    data_atribuicao = db.Column(db.DateTime)
    data_inicio_execucao = db.Column(db.DateTime)
    data_conclusao_execucao = db.Column(db.DateTime)
    data_aprovacao = db.Column(db.DateTime)
    
    # Fotos
    foto_antes_url = db.Column(db.String(500))
    foto_depois_url = db.Column(db.String(500))
    
    # Localização
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    endereco_completo = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    equipe = db.relationship('Equipe', backref='ordens_servico')
    
    # ⚠️ Corrigido: usar back_populates para casar com User.os_criadas / os_atribuidas / os_aprovadas_por
    criador = db.relationship(
        'User',
        foreign_keys=[gestor_criador_id],
        back_populates='os_criadas'
    )
    
    responsavel_campo = db.relationship(
        'User',
        foreign_keys=[responsavel_campo_id],
        back_populates='os_atribuidas'
    )
    
    aprovador = db.relationship(
        'User',
        foreign_keys=[gestor_aprovador_id],
        back_populates='os_aprovadas_por'
    )
    
    historico = db.relationship(
        'HistoricoOS',
        backref='ordem_servico',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    def gerar_numero_os(self):
        """Gera número único da OS (OS-YYYY-NNNNN)"""
        ano = datetime.now().year
        ultima_os = OrdemServico.query.filter(
            OrdemServico.numero_os.like(f'OS-{ano}-%')
        ).order_by(OrdemServico.created_at.desc()).first()
        
        if ultima_os:
            ultimo_num = int(ultima_os.numero_os.split('-')[-1])
            proximo = ultimo_num + 1
        else:
            proximo = 1
        
        self.numero_os = f'OS-{ano}-{proximo:05d}'
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'numero_os': self.numero_os,
            'categoria': self.categoria,
            'prioridade': self.prioridade,
            'status': self.status,
            'endereco_completo': self.endereco_completo,
            'prazo_execucao': self.prazo_execucao.isoformat() if self.prazo_execucao else None,
            'created_at': self.created_at.isoformat()
        }
