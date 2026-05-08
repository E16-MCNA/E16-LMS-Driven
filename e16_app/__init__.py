from flask import Flask

from .auth_utils import load_current_user
from .blueprints.analytics import bp as analytics_bp
from .blueprints.auth import bp as auth_bp
from .blueprints.student import bp as student_bp
from .blueprints.teacher import bp as teacher_bp
from .extensions import db, migrate


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = "e16-dev-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///e16.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)
    app.before_request(load_current_user)

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(analytics_bp)
    return app
