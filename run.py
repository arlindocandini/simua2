#!/usr/bin/env python
"""
Entry point da aplicação
Execute: python run.py
"""
import os
from app import create_app, socketio, db
from app.models import *  # Importa todos os models

# Criar aplicação
app = create_app(os.getenv('FLASK_ENV', 'development'))

@app.shell_context_processor
def make_shell_context():
    """
    Cria contexto para o shell interativo do Flask
    Uso: flask shell
    """
    from app.models import User, Equipe, Ocorrencia, OrdemServico, HistoricoOS, Notificacao, Relatorio
    
    return {
        'db': db,
        'User': User,
        'Equipe': Equipe,
        'Ocorrencia': Ocorrencia,
        'OrdemServico': OrdemServico,
        'HistoricoOS': HistoricoOS,
        'Notificacao': Notificacao,
        'Relatorio': Relatorio
    }

if __name__ == '__main__':
    # Rodar com SocketIO (suporte para WebSocket)
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=app.config['DEBUG']
    )