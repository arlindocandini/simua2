# app/models/relatorio.py
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app import db

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
    parametros = db.Column(db.JSON)
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