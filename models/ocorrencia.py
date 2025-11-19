# app/models/ocorrencia.py
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app import db

class Ocorrencia(db.Model):
    """Model de Ocorrência Detectada"""
    
    __tablename__ = 'ocorrencias'
    
    CATEGORIA_ENUM = ENUM('asfalto_dano', 'calcada_dano', 'iluminacao_publica', 'fiacao_exposta',
    'lixo_irregular', 'arvore_dano', 'mato_alto', 'ponto_onibus_dano',
    'vazamento_agua', 'fruta_na_pista', 'placa_dano', 'semaforo_defeito',
    'sinalizacao_apagada', 'objeto_na_pista', 'animal_na_pista',
    'bueiro_entupido', 'bueiro_dano', 'queimada', 'obra_irregular',
    'desconhecido',
    name='categoria_ocorrencia_enum', create_type=False)

    URGENCIA_ENUM = ENUM('nao_urgente', 'pouco_urgente', 'urgente', 'emergencia',
                         name='urgencia_enum', create_type=False)
    STATUS_ENUM = ENUM('pendente', 'em_os', 'resolvida', 'cancelada',
                       name='status_ocorrencia_enum', create_type=False)
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = db.Column(UUID(as_uuid=True), db.ForeignKey('cameras.id'), 
                          nullable=True)
    imagem_path = db.Column(db.String(500), nullable=False)
    imagem_miniatura_path = db.Column(db.String(500))
    latitude = db.Column(db.Numeric(10, 8), nullable=False, index=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=False, index=True)
    endereco_completo = db.Column(db.String(500))
    categoria = db.Column(CATEGORIA_ENUM, nullable=False, index=True)
    urgencia = db.Column(URGENCIA_ENUM, nullable=False)
    status = db.Column(STATUS_ENUM, default='pendente', nullable=False, index=True)
    descricao_ia = db.Column(db.Text)
    confidence_score = db.Column(db.Float)
    metadados_exif = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, 
                          nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, 
                          onupdate=datetime.utcnow)
    
    ordem_servico = db.relationship('OrdemServico', backref='ocorrencia', 
                                   uselist=False)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'camera_id': str(self.camera_id) if self.camera_id else None,
            'imagem_path': self.imagem_path,
            'imagem_miniatura_path': self.imagem_miniatura_path,
            'latitude': float(self.latitude),
            'longitude': float(self.longitude),
            'endereco_completo': self.endereco_completo,
            'categoria': self.categoria,
            'urgencia': self.urgencia,
            'status': self.status,
            'descricao_ia': self.descricao_ia,
            'confidence_score': self.confidence_score,
            'created_at': self.created_at.isoformat()
        }