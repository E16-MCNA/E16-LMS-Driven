import os
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_login import current_user

from .extensions import db, login_manager, migrate, oauth, mail, csrf, limiter, talisman

def create_app():
    load_dotenv()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    
    flask_env = os.getenv("FLASK_ENV", "production")
    if app.config.get("TESTING"):
        flask_env = "testing"
        
    from .config import config_dict
    app_config = config_dict.get(flask_env, config_dict["default"])
    app.config.from_object(app_config)
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
        'img-src': ['\'self\'', 'data:', 'https:', '*'],
        'frame-src': ['\'self\'', 'https://www.youtube.com', 'https://player.vimeo.com']
    }
    talisman.init_app(
        app,
        content_security_policy=csp,
        force_https=os.getenv("FLASK_ENV") == "production",
        session_cookie_secure=os.getenv("FLASK_ENV") == "production"
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
