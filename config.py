import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///db.sqlite3'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY') or 'd1d3ap9r01qic6lgtil0d1d3ap9r01qic6lgtilg'
    
    # Mail settings
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'your-email@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'your-app-password'
    
    # Performance settings
    ENABLE_CACHING = True
    CACHE_TIMEOUT = 300  # 5 minutes
    ENABLE_PERFORMANCE_MONITORING = True
    MAIL_DEFAULT_SENDER = "afsalhameeth271103@gmail.com"
    WTF_CSRF_ENABLED = False
