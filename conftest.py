import os
import sys
import pytest
from e16_app import create_app
from e16_app.extensions import db as _db

# Thiết lập môi trường kiểm thử để cô lập hoàn toàn cơ sở dữ liệu vật lý
os.environ["APP_ENV"] = "testing"

# Thêm thư mục hiện tại vào sys.path để pytest tìm thấy e16_app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

@pytest.fixture(scope="function")
def app():
    # CI: DATABASE_URL từ env (PostgreSQL service)
    # Local: fallback về SQLite in-memory để chạy nhanh
    test_db_url = os.environ.get(
        "DATABASE_URL",
        "sqlite:///:memory:"
    )
    app = create_app()
    app.config.update({
        "SQLALCHEMY_DATABASE_URI": test_db_url,
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture(scope="function")
def client(app):
    return app.test_client()

@pytest.fixture(scope="function")
def db(app):
    yield _db
    _db.session.rollback()
