# -*- coding: utf-8 -*-
import pytest
from e16_app import create_app, db
from e16_app.models import User

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False # Disable for easier testing
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_auth_pages_load(client):
    """Check if main auth pages are accessible."""
    responses = [client.get("/auth/login"), client.get("/auth/register")]
    for r in responses:
        assert r.status_code == 200

def test_user_registration(client, app):
    """Verify that a user can register."""
    response = client.post("/auth/register", data={
        "email": "test@e16.edu.vn",
        "password": "password123",
        "confirm_password": "password123",
        "role": "student"
    }, follow_redirects=True)
    
    assert response.status_code == 200
    with app.app_context():
        user = db.session.query(User).filter_by(email="test@e16.edu.vn").first()
        assert user is not None
        assert user.role == "student"

def test_login_logout(client, app):
    """Verify login flow."""
    # First register
    client.post("/auth/register", data={
        "email": "user@e16.edu.vn",
        "password": "password123",
        "confirm_password": "password123",
        "role": "teacher"
    })
    
    # Login
    response = client.post("/auth/login", data={
        "email": "user@e16.edu.vn",
        "password": "password123"
    }, follow_redirects=True)
    assert "Hệ thống" in response.data.decode("utf-8") or "Quản lý" in response.data.decode("utf-8")
    
    # Logout
    response = client.get("/auth/logout", follow_redirects=True)
    assert "Đăng nhập" in response.data.decode("utf-8")
