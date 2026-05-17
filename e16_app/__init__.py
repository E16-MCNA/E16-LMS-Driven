import os
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_login import current_user

from .extensions import db, login_manager, migrate, oauth, mail, csrf, limiter, talisman

def create_app():
    load_dotenv()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    
    # Use APP_ENV instead of deprecated FLASK_ENV for environment configuration mapping
    app_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "production")).lower()
    if app.config.get("TESTING"):
        app_env = "testing"
        
    from .config import config_dict
    app_config = config_dict.get(app_env, config_dict["default"])
    app.config.from_object(app_config)
    
    # Fail-fast security check: SECRET_KEY must be set in non-development environments
    secret_key = app.config.get("SECRET_KEY")
    if app_env != "development" and (not secret_key or secret_key == "dev-change-me"):
        if app_env == "testing":
            app.config["SECRET_KEY"] = "testing-fallback-key-for-ci"
        else:
            raise RuntimeError(
                f"Security Risk: SECRET_KEY is missing or insecure ('{secret_key}') in non-development environment '{app_env}'!"
            )
            
    app_config.init_app(app)

    # --- Initialize extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    mail.init_app(app)
    limiter.init_app(app)
    
    # --- Security Headers (Talisman) ---
    csp = {
        'default-src': '\'self\'',
        'script-src': [
            '\'self\'',
            'https://cdn.jsdelivr.net',
            'https://code.jquery.com',
            'https://cdnjs.cloudflare.com',
            '\'unsafe-inline\'' # Cần thiết nếu có script trong template, nhưng nên tránh
        ],
        'style-src': [
            '\'self\'',
            'https://fonts.googleapis.com',
            'https://cdn.jsdelivr.net',
            '\'unsafe-inline\''
        ],
        'font-src': [
            '\'self\'',
            'https://fonts.gstatic.com',
            'https://cdn.jsdelivr.net'
        ],
        'img-src': [
            '\'self\'',
            'data:',
            'https://images.unsplash.com',
            'https://*.unsplash.com',
            'https://cdn.jsdelivr.net',
            'https://res.cloudinary.com'
        ],
        'frame-src': ['\'self\'', 'https://www.youtube.com', 'https://player.vimeo.com']
    }
    talisman.init_app(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=['script-src', 'style-src'],
        force_https=(app_env == "production"),
        session_cookie_secure=(app_env == "production")
    )
    
    @app.route("/")
    def index():
        from flask import redirect, url_for
        return redirect(url_for("auth.home"))

    # IMPORT MODELS HERE so they register with SQLAlchemy metadata
    from . import models
    
    # --- Register Blueprints ---
    from .blueprints.auth import bp as auth_bp
    from .blueprints.student import bp as student_bp
    from .blueprints.teacher import bp as teacher_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.analytics import bp as analytics_bp
    from .blueprints.communication import bp as communication_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(communication_bp)
    
    @app.template_filter("get_choices")
    def get_choices(question_id):
        from .models import Choice
        return db.session.query(Choice).filter_by(question_id=question_id).all()

    # --- Error handlers ---
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    # --- Context processor ---
    @app.context_processor
    def inject_global_data():
        from .services.settings import get_setting
        data = {
            "site_name": get_setting("site_name", "E16 LMS"),
            "site_logo": get_setting("site_logo_url", ""),
            "unread_notifs_count": 0
        }
        if current_user.is_authenticated:
            from .models import Notification
            data["unread_notifs_count"] = db.session.query(Notification).filter_by(user_id=current_user.id, is_read=False).count()
        return data

    # --- Structured JSON Logging & Request ID correlation ---
    import logging
    import json
    import uuid
    from flask import g, jsonify

    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            try:
                from flask import has_request_context
                if has_request_context() and hasattr(g, "request_id"):
                    log_data["request_id"] = g.request_id
            except Exception:
                pass
            return json.dumps(log_data)

    if app_env == "production":
        # Configure app logger to output structured JSON in production for ELK/Cloud logging integration
        from logging import StreamHandler
        handler = StreamHandler()
        handler.setFormatter(JSONFormatter())
        app.logger.handlers = [handler]
        app.logger.setLevel(logging.INFO)

    @app.before_request
    def add_request_id():
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    @app.after_request
    def append_request_id_header(response):
        if hasattr(g, "request_id"):
            response.headers["X-Request-ID"] = g.request_id
        return response

    # --- Health Check Endpoints (/healthz, /readyz) ---
    @app.route("/healthz")
    def healthz():
        """Liveness check: simple heartbeat return."""
        return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()}), 200

    @app.route("/readyz")
    def readyz():
        """Readiness check: check backend database connectivity."""
        try:
            from sqlalchemy import text
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "ready", "database": "connected"}), 200
        except Exception as e:
            app.logger.error(f"Readiness check failed: {str(e)}")
            return jsonify({"status": "unready", "database": "disconnected", "error": str(e)}), 503

    # --- CLI commands ---
    _register_cli(app)

    return app


def _register_cli(app):
    """Register custom Flask CLI commands."""
    import click

    @app.cli.command("seed")
    @click.option("--key", default=None, help="Seed password (or set E16_SEED_PASSWORD env)")
    def seed_command(key):
        """Seed the database with demo data."""
        import os as _os
        seed_password = key or _os.getenv("E16_SEED_PASSWORD", "demo-password")

        # Re-use existing seed logic from auth blueprint
        from .blueprints.auth import _run_seed
        result = _run_seed(seed_password)
        click.echo(result)


@login_manager.user_loader
def load_user(user_id: str):
    from .models import User
    return db.session.get(User, user_id)
