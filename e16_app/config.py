# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base config."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    
    # Application Environment
    APP_ENV = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "production")).lower()
    
    # Database
    db_url = os.environ.get("DATABASE_URL", "sqlite:///e16.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False") == "True"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # Payment mode: "mock" (development/testing) or "real" (production — not yet implemented)
    PAYMENT_MODE = os.environ.get("PAYMENT_MODE", "mock").lower()
    
    # Email
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)
    
    # Rate Limiting
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    
    # OAuth
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    @classmethod
    def init_app(cls, app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True
    APP_ENV = "development"

class ProductionConfig(Config):
    DEBUG = False
    PAYMENT_MODE = os.environ.get("PAYMENT_MODE", "real").lower()
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    
    @classmethod
    def init_app(cls, app):
        if not os.environ.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY environment variable must be set in production!")

class TestingConfig(Config):
    TESTING = True
    APP_ENV = "testing"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False

config_dict = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": ProductionConfig
}
