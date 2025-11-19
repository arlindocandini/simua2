# app/models/equipe.py
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app import db

class Equipe(db.Model):
    """Model de Equipe Responsável"""
    
    __tablename__ = 'equipes'
    
    TIPO_SERVICO_ENUM = ENUM('asfalto', 'bueiro', 'eletrica', 'limpeza', 
                             'iluminacao', name='tipo_servico_enum', 
                             create_type=False)
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = db.Column(db.String(100), nullable=False)
    tipo_servico = db.Column(TIPO_SERVICO_ENUM, nullable=False)
    responsavel_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    telefone_emergencia = db.Column(db.String(20))
    ativa = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, 
                          onupdate=datetime.utcnow)
    
    responsavel = db.relationship('User', foreign_keys=[responsavel_id])
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'nome': self.nome,
            'tipo_servico': self.tipo_servico,
            'telefone_emergencia': self.telefone_emergencia,
            'ativa': self.ativa
        }