# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base config."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    RUN_BG_DAEMON = os.environ.get("RUN_BG_DAEMON", "False" if os.environ.get("VERCEL") else "True") == "True"
    SITE_NAME = os.environ.get("SITE_NAME", "E16 LMS")
    APP_BASE_URL = os.environ.get("APP_BASE_URL") or os.environ.get("APP_URL")
    PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL")
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "https" if os.environ.get("VERCEL") else "http")
    
    # Application Environment
    APP_ENV = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "production")).lower()
    
    # Database
    db_url = os.environ.get("DATABASE_URL", "sqlite:///e16.db")
    if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        try:
            import urllib.parse
            # Standardize protocol
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
                
            # Parse the URL
            parsed = urllib.parse.urlparse(db_url)
            
            # Reconstruct the connection string credentials safely (encoding password)
            netloc = parsed.netloc
            if "@" in netloc:
                credentials, host_part = netloc.rsplit("@", 1)
                if ":" in credentials:
                    username, password = credentials.split(":", 1)
                    unquoted_password = urllib.parse.unquote(password)
                    encoded_password = urllib.parse.quote(unquoted_password, safe="")
                    netloc = f"{username}:{encoded_password}@{host_part}"
            
            # Parse and clean query parameters (psycopg2 crashes on non-libpq options like pgbouncer)
            query_params = urllib.parse.parse_qsl(parsed.query)
            cleaned_params = [(k, v) for k, v in query_params if k.lower() != "pgbouncer"]
            new_query = urllib.parse.urlencode(cleaned_params)
            
            # Rebuild URL
            parsed = parsed._replace(netloc=netloc, query=new_query)
            db_url = urllib.parse.urlunparse(parsed)
        except Exception:
            pass

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
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://" if os.environ.get("VERCEL") else "redis://localhost:6379/0")
    
    # Configure SQLAlchemy to avoid keeping stale serverless connections open on Vercel.
    # prepare_threshold is a psycopg v3 option; this project uses psycopg2-binary.
    if os.environ.get("VERCEL"):
        from sqlalchemy.pool import NullPool
        SQLALCHEMY_ENGINE_OPTIONS = {
            "poolclass": NullPool
        }
    
    @classmethod
    def init_app(cls, app):
        if not os.environ.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY environment variable must be set in production!")

class TestingConfig(Config):
    TESTING = True
    APP_ENV = "testing"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RUN_BG_DAEMON = False

config_dict = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": ProductionConfig
}
