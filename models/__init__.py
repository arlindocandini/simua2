"""
Exporta todos os models para facilitar imports
"""
from .user import User
from .equipe import Equipe
from .camera import Camera
from .ocorrencia import Ocorrencia
from .ordem_servico import OrdemServico
from .historico_os import HistoricoOS, Notificacao, Relatorio

__all__ = [
    'User',
    'Equipe', 
    'Camera',
    'Ocorrencia',
    'OrdemServico',
    'HistoricoOS',
    'Notificacao',
    'Relatorio'
]