# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request
from flask_login import current_user

from .extensions import db, login_manager, migrate, oauth, mail, csrf, limiter, talisman
from .time_utils import utcnow

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
    
    # Automatically create missing tables and seed basic settings in development/Vercel
    if app_env == "development" or os.environ.get("VERCEL"):
        with app.app_context():
            try:
                db.create_all()
            except Exception as e:
                app.logger.warning(f"db.create_all() failed during startup: {str(e)}")
            # Self-healing column migrations for Vercel/database instances that have
            # not run Alembic yet. Use SQLAlchemy inspection instead of probing with
            # SELECT missing_column, which aborts the current PostgreSQL transaction.
            from sqlalchemy import inspect, text

            def ensure_column(table_name, column_name, ddl_fragment):
                try:
                    inspector = inspect(db.engine)
                    columns = {col["name"] for col in inspector.get_columns(table_name)}
                    if column_name in columns:
                        return
                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl_fragment}"))
                    db.session.commit()
                    app.logger.info(f"Self-healing added {table_name}.{column_name}")
                except Exception as ex:
                    db.session.rollback()
                    app.logger.warning(f"Self-healing {table_name}.{column_name} migration failed: {str(ex)}")

            bool_default_false = "0" if db.engine.dialect.name == "sqlite" else "false"
            timestamp_type = "DATETIME" if db.engine.dialect.name == "sqlite" else "TIMESTAMP"
            _self_heal_cols = [
                ("courses", "price", "INTEGER DEFAULT 250000"),
                ("courses", "tags", "VARCHAR(500) DEFAULT ''"),
                ("courses", "level", "VARCHAR(20) DEFAULT ''"),
                ("users", "must_change_password", f"BOOLEAN NOT NULL DEFAULT {bool_default_false}"),
                ("users", "created_by", "VARCHAR(36) DEFAULT NULL"),
                ("users", "temp_password_hash", "VARCHAR(255) DEFAULT NULL"),
                ("courses", "reviewed_by", "VARCHAR(36) DEFAULT NULL"),
                ("courses", "reviewed_at", f"{timestamp_type} DEFAULT NULL"),
                ("courses", "review_note", "TEXT DEFAULT NULL"),
                ("courses", "starts_at", f"{timestamp_type} DEFAULT NULL"),
                ("courses", "ends_at", f"{timestamp_type} DEFAULT NULL"),
                ("courses", "enrollment_deadline", f"{timestamp_type} DEFAULT NULL"),
                ("courses", "max_students", "INTEGER DEFAULT NULL"),
            ]
            for tbl, col, ddl in _self_heal_cols:
                ensure_column(tbl, col, ddl)

            try:
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_users_created_by ON users (created_by)"))
                db.session.commit()
            except Exception as ex:
                db.session.rollback()
                app.logger.warning(f"Self-healing users.created_by index failed: {str(ex)}")
            
            # Auto-seed initial users, categories, and settings if DB is completely empty (no users)
            from .models import User, Category, SystemSetting
            try:
                user_count = db.session.query(User).count()
                if user_count == 0:
                    app.logger.info("Database is empty. Automatically seeding initial categories, settings, and users...")
                    # Seed Categories
                    cats = [
                        {"name": "Công nghệ thông tin", "slug": "it", "icon": "💻", "sort_order": 1},
                        {"name": "Kinh doanh & Khởi nghiệp", "slug": "business", "icon": "📈", "sort_order": 2},
                        {"name": "Ngoại ngữ", "slug": "languages", "icon": "🌍", "sort_order": 3},
                        {"name": "Thiết kế đồ họa", "slug": "design", "icon": "🎨", "sort_order": 4}
                    ]
                    for c_data in cats:
                        if not db.session.query(Category).filter_by(slug=c_data["slug"]).first():
                            db.session.add(Category(**c_data))
                            
                    # Seed Settings
                    settings = [
                        {"key": "site_name", "value": "E16 LMS", "description": "Tên nền tảng hiển thị trên tiêu đề và sidebar."},
                        {"key": "site_logo_url", "value": "https://images.unsplash.com/photo-1614850523296-d8c1af93d400?q=80&w=2070&auto=format&fit=crop", "description": "URL ảnh logo của hệ thống."},
                        {"key": "allow_registration", "value": "True", "description": "Cho phép người dùng tự đăng ký tài khoản."},
                        {"key": "require_course_approval", "value": "True", "description": "Yêu cầu admin duyệt khóa học trước khi xuất bản."}
                    ]
                    for s_data in settings:
                        if not db.session.query(SystemSetting).filter_by(key=s_data["key"]).first():
                            db.session.add(SystemSetting(**s_data))
                            
                    # Seed Users
                    from werkzeug.security import generate_password_hash
                    seed_password = os.getenv("E16_SEED_PASSWORD") or "demo-password"
                    users = [
                        {"email": "admin@e16.local", "password_hash": generate_password_hash(seed_password), "role": "admin", "must_change_password": False},
                        {"email": "teacher@e16.local", "password_hash": generate_password_hash(seed_password), "role": "teacher", "must_change_password": False},
                        {"email": "student@e16.local", "password_hash": generate_password_hash(seed_password), "role": "student", "must_change_password": False},
                        {"email": "hocvu@e16.local", "password_hash": generate_password_hash(seed_password), "role": "hoc_vu", "must_change_password": False},
                    ]
                    for u_data in users:
                        if not db.session.query(User).filter_by(email=u_data["email"]).first():
                            db.session.add(User(**u_data))
                            
                    for i in range(1, 6):
                        email = f"student{i}@e16.local"
                        if not db.session.query(User).filter_by(email=email).first():
                            db.session.add(User(email=email, password_hash=generate_password_hash(seed_password), role="student"))
                    
                    db.session.commit()
                    app.logger.info("Database auto-seeding completed successfully.")

                if os.environ.get("VERCEL") and os.getenv("E16_SEED_PASSWORD"):
                    from werkzeug.security import check_password_hash, generate_password_hash

                    seed_password = os.getenv("E16_SEED_PASSWORD")
                    core_users = [
                        ("admin@e16.local", "admin"),
                        ("teacher@e16.local", "teacher"),
                        ("student@e16.local", "student"),
                        ("hocvu@e16.local", "hoc_vu"),
                    ]
                    core_users.extend((f"student{i}@e16.local", "student") for i in range(1, 6))

                    mutated = False
                    for email, role in core_users:
                        user = db.session.query(User).filter_by(email=email).first()
                        if user is None:
                            db.session.add(User(
                                email=email,
                                password_hash=generate_password_hash(seed_password),
                                role=role,
                                is_active=True,
                                must_change_password=False,
                            ))
                            mutated = True
                            continue

                        if user.role != role:
                            user.role = role
                            mutated = True
                        if not user.is_active:
                            user.is_active = True
                            mutated = True
                        if getattr(user, "must_change_password", False):
                            user.must_change_password = False
                            mutated = True
                        if not check_password_hash(user.password_hash, seed_password):
                            user.password_hash = generate_password_hash(seed_password)
                            mutated = True

                    if mutated:
                        db.session.commit()
                        app.logger.info("Vercel core demo accounts synchronized from E16_SEED_PASSWORD.")

                if os.environ.get("VERCEL") and os.getenv("E16_DEMO_ENRICHMENT", "True") == "True":
                    from .services.demo_data import enrich_demo_data_once
                    enrich_demo_data_once(app)
            except Exception as e:
                app.logger.error(f"Error during auto-seeding: {str(e)}")

            default_settings = [
                {"key": "site_name", "value": "E16 LMS", "description": "Tên hệ thống"},
                {"key": "site_logo_url", "value": "", "description": "URL logo hệ thống"}
            ]
            mutated = False
            for s_data in default_settings:
                try:
                    if not db.session.query(SystemSetting).filter_by(key=s_data["key"]).first():
                        db.session.add(SystemSetting(**s_data))
                        mutated = True
                except Exception:
                    pass
            if mutated:
                try:
                    db.session.commit()
                except Exception:
                    pass

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
        'base-uri': '\'self\'',
        'object-src': '\'none\'',
        'form-action': '\'self\'',
        'frame-ancestors': '\'self\'',
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
            'https://res.cloudinary.com',
            'https://img.vietqr.io',
            'https://api.qrserver.com'
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
    from .blueprints.hoc_vu import bp as hoc_vu_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(communication_bp)
    app.register_blueprint(hoc_vu_bp)
    
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
        try:
            if current_user.is_authenticated:
                from .models import Notification
                data["unread_notifs_count"] = db.session.query(Notification).filter_by(user_id=current_user.id, is_read=False).count()
        except Exception:
            pass
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
            if record.exc_info:
                import traceback as tb
                log_data["traceback"] = "".join(tb.format_exception(*record.exc_info))
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

    @app.before_request
    def check_must_change_password():
        """Force users with must_change_password=True to change their password."""
        EXEMPT = {
            'auth.change_password', 'auth.logout', 'static',
            'healthz', 'readyz', 'metricsz',
        }
        if not current_user.is_authenticated:
            return
        if not getattr(current_user, 'must_change_password', False):
            return
        if request.endpoint in EXEMPT:
            return
        from flask import redirect as _redirect, url_for as _url_for
        return _redirect(_url_for('auth.change_password', next=request.path))

    @app.after_request
    def append_request_id_header(response):
        if hasattr(g, "request_id"):
            response.headers["X-Request-ID"] = g.request_id
        return response

    # --- Health Check Endpoints (/healthz, /readyz) ---
    @app.route("/healthz")
    def healthz():
        """Liveness check: simple heartbeat return."""
        return jsonify({"status": "healthy", "timestamp": utcnow().isoformat()}), 200

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

    @app.route("/metricsz")
    def metricsz():
        """Operational counters for monitoring. Protect with METRICS_TOKEN or admin session."""
        metrics_token = os.getenv("METRICS_TOKEN")
        authorized_by_token = bool(metrics_token and request.headers.get("X-Metrics-Token") == metrics_token)
        authorized_by_admin = current_user.is_authenticated and current_user.role == "admin"
        if not authorized_by_token and not authorized_by_admin:
            return jsonify({"error": "forbidden"}), 403

        from .models import Course, Enrollment, LearningLog, Notification, User
        today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return jsonify({
            "users_total": db.session.query(User).count(),
            "users_active": db.session.query(User).filter_by(is_active=True).count(),
            "courses_published": db.session.query(Course).filter_by(status="published", is_deleted=False).count(),
            "enrollments_total": db.session.query(Enrollment).count(),
            "learning_logs_today": db.session.query(LearningLog).filter(LearningLog.timestamp >= today_start).count(),
            "notifications_unread": db.session.query(Notification).filter_by(is_read=False).count(),
        }), 200

    # --- CLI commands ---
    _register_cli(app)

    # --- Background worker thread (for local dev mode) ---
    if app.config.get("RUN_BG_DAEMON"):
        from .services.jobs import start_background_worker
        start_background_worker(app)

    return app


def _register_cli(app):
    """Register custom Flask CLI commands."""
    from .cli import init_app as init_cli

    init_cli(app)


@login_manager.user_loader
def load_user(user_id: str):
    from .models import User
    return db.session.get(User, user_id)
