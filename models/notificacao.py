# app/models/notificacao.py
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app import db

class Notificacao(db.Model):
    """Model de Notificação"""
    
    __tablename__ = 'notificacoes'
    
    TIPO_NOTIF_ENUM = ENUM('nova_os', 'os_atribuida', 'os_concluida', 
                           'os_aprovada', 'os_rejeitada', 'ocorrencia_urgente',
                           name='tipo_notificacao_enum', create_type=False)
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), 
                          nullable=False, index=True)
    tipo = db.Column(TIPO_NOTIF_ENUM, nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    lida = db.Column(db.Boolean, default=False, nullable=False, index=True)
    os_id = db.Column(UUID(as_uuid=True), db.ForeignKey('ordens_servico.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, 
                          nullable=False, index=True)
    
    ordem_servico = db.relationship('OrdemServico', backref='notificacoes')
    
    def marcar_como_lida(self):
        """Marca notificação como lida"""
        self.lida = True
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'tipo': self.tipo,
            'titulo': self.titulo,
            'mensagem': self.mensagem,
            'lida': self.lida,
            'os_id': str(self.os_id) if self.os_id else None,
            'created_at': self.created_at.isoformat()
        }