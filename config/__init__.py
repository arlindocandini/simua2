import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuração base da aplicação"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-this')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 
                                        'postgresql://localhost/ocorrencias_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Session
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.getenv('PERMANENT_SESSION_LIFETIME', '7200'))
    )
    
    # Upload
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))  # 16MB
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'app/static/uploads')
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
    
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o')
    
    # Celery
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 
                                      'redis://localhost:6379/0')
    
    # Security
    BCRYPT_LOG_ROUNDS = int(os.getenv('BCRYPT_LOG_ROUNDS', 12))
    
    # Pagination
    ITEMS_PER_PAGE = int(os.getenv('ITEMS_PER_PAGE', 20))
    
    # Image Processing
    THUMBNAIL_SIZE = int(os.getenv('THUMBNAIL_SIZE', 150))
    IMAGE_QUALITY = int(os.getenv('IMAGE_QUALITY', 85))
    
    # Geocoding
    NOMINATIM_USER_AGENT = os.getenv('NOMINATIM_USER_AGENT', 
                                      'ocorrencias_urbanas/1.0')
    
    # SocketIO
    SOCKETIO_MESSAGE_QUEUE = os.getenv('SOCKETIO_MESSAGE_QUEUE', 
                                        'redis://localhost:6379/0')
    
    # Email (opcional)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

class DevelopmentConfig(Config):
    """Configuração de desenvolvimento"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    """Configuração de produção"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    
class TestingConfig(Config):
    """Configuração de testes"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost/ocorrencias_test'
    WTF_CSRF_ENABLED = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}