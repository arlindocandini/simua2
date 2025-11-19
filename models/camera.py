# app/models/camera.py
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app import db

class Camera(db.Model):
    """Model de Câmera de Monitoramento"""
    
    __tablename__ = 'cameras'
    
    STATUS_ENUM = ENUM('online', 'offline', 'manutencao', 
                       name='camera_status_enum', create_type=False)
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = db.Column(db.String(100), nullable=False)
    url_stream = db.Column(db.String(500), nullable=False)
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    localizacao_descritiva = db.Column(db.String(500))
    status = db.Column(STATUS_ENUM, default='offline')
    ultima_captura_at = db.Column(db.DateTime)
    ativa = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, 
                          onupdate=datetime.utcnow)
    
    ocorrencias = db.relationship('Ocorrencia', backref='camera', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'nome': self.nome,
            'url_stream': self.url_stream,
            'latitude': float(self.latitude),
            'longitude': float(self.longitude),
            'localizacao_descritiva': self.localizacao_descritiva,
            'status': self.status,
            'ultima_captura_at': self.ultima_captura_at.isoformat() if self.ultima_captura_at else None
        }