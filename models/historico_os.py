# app/models/historico_os.py
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app import db

class HistoricoOS(db.Model):
    """Model de Histórico de Mudanças de Status da OS"""
    
    __tablename__ = 'historico_os'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    os_id = db.Column(UUID(as_uuid=True), db.ForeignKey('ordens_servico.id'), 
                      nullable=False)
    status_anterior = db.Column(db.String(50))
    status_novo = db.Column(db.String(50), nullable=False)
    usuario_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), 
                          nullable=False)
    comentario = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    usuario = db.relationship('User', backref='historicos')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'status_anterior': self.status_anterior,
            'status_novo': self.status_novo,
            'usuario': self.usuario.nome_completo if self.usuario else None,
            'comentario': self.comentario,
            'created_at': self.created_at.isoformat()
        }


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


class Relatorio(db.Model):
    """Model de Relatório Gerado"""
    
    __tablename__ = 'relatorios'
    
    TIPO_RELAT_ENUM = ENUM('mensal', 'trimestral', 'anual', 'personalizado',
                           name='tipo_relatorio_enum', create_type=False)
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titulo = db.Column(db.String(200), nullable=False)
    tipo = db.Column(TIPO_RELAT_ENUM, nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    gerado_por_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), 
                             nullable=False)
    arquivo_path = db.Column(db.String(500))
    parametros = db.Column(db.JSON)  # Filtros aplicados
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    gerado_por = db.relationship('User', backref='relatorios')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'titulo': self.titulo,
            'tipo': self.tipo,
            'data_inicio': self.data_inicio.isoformat(),
            'data_fim': self.data_fim.isoformat(),
            'gerado_por': self.gerado_por.nome_completo if self.gerado_por else None,
            'arquivo_path': self.arquivo_path,
            'created_at': self.created_at.isoformat()
        }