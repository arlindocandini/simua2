from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def role_required(roles):
    """
    Decorator para verificar se o usuário tem permissão baseada em role
    
    Args:
        roles: Lista de roles permitidas ['gestor', 'admin', 'equipe_campo']
    
    Usage:
        @role_required(['gestor', 'admin'])
        def criar_os():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Por favor, faça login para acessar esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            if current_user.tipo_usuario not in roles:
                flash('Você não tem permissão para acessar esta página.', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def gestor_required(f):
    """Decorator simplificado para exigir gestor ou admin"""
    return role_required(['gestor', 'admin'])(f)

def admin_required(f):
    """Decorator para exigir apenas admin"""
    return role_required(['admin'])(f)

def campo_required(f):
    """Decorator para exigir equipe de campo"""
    return role_required(['equipe_campo'])(f)