import os

from dotenv import load_dotenv
from flask import Flask

from .auth_utils import load_current_user
from .blueprints.analytics import bp as analytics_bp
from .blueprints.auth import bp as auth_bp
from .blueprints.student import bp as student_bp
from .blueprints.teacher import bp as teacher_bp
from .extensions import db, login_manager, migrate
from .models import User


def create_app():
    load_dotenv()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    
    # Production database URL fix (postgres:// -> postgresql://)
    db_url = os.getenv("DATABASE_URL", "sqlite:///e16.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    app.before_request(load_current_user)

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(analytics_bp)
    
    with app.app_context():
        db.create_all()
        
    return app


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, user_id)
