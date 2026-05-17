# -*- coding: utf-8 -*-
import pytest
from flask import request
from e16_app import create_app, db
from e16_app.models import User

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False  # Disable for easier testing
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def assert_login_redirect(client, email, password, expected_path):
    """Helper to check if a user is redirected to the correct path based on role."""
    response = client.post("/auth/login", data={
        "email": email,
        "password": password
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert request.path == expected_path

@pytest.mark.auth
@pytest.mark.smoke
def test_auth_pages_load(client):
    """Check if main auth pages are accessible."""
    responses = [client.get("/auth/login"), client.get("/auth/register")]
    for r in responses:
        assert r.status_code == 200

@pytest.mark.auth
@pytest.mark.smoke
def test_user_registration(client, app):
    """Verify that a user can register with matching password confirmation."""
    response = client.post("/auth/register", data={
        "email": "test@e16.edu.vn",
        "password": "password123",
        "confirm_password": "password123",
        "role": "student"
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert request.path == "/auth/login"
    
    with app.app_context():
        user = db.session.query(User).filter_by(email="test@e16.edu.vn").first()
        assert user is not None
        assert user.role == "student"

@pytest.mark.auth
def test_register_password_confirm_mismatch(client, app):
    """Negative Test: Registration should fail if password and confirm_password do not match."""
    response = client.post("/auth/register", data={
        "email": "mismatch@e16.edu.vn",
        "password": "password123",
        "confirm_password": "different_password",
        "role": "student"
    }, follow_redirects=True)
    
    # Registration should fail and redirect back to register page
    assert response.status_code == 200
    assert request.path == "/auth/register"
    
    with app.app_context():
        user = db.session.query(User).filter_by(email="mismatch@e16.edu.vn").first()
        assert user is None

@pytest.mark.auth
@pytest.mark.smoke
def test_login_logout(client, app):
    """Verify login and logout flow for a teacher redirecting to teacher dashboard."""
    # First register
    client.post("/auth/register", data={
        "email": "user@e16.edu.vn",
        "password": "password123",
        "confirm_password": "password123",
        "role": "teacher"
    })
    
    # Login and check redirect path using the helper
    assert_login_redirect(client, "user@e16.edu.vn", "password123", "/teacher/dashboard")
    
    # Logout
    response = client.get("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert request.path == "/auth/login"

@pytest.mark.auth
def test_login_incorrect_password(client, app):
    """Negative Test: Login should fail with incorrect password and redirect back to login page."""
    # Register first
    client.post("/auth/register", data={
        "email": "wrongpwd@e16.edu.vn",
        "password": "password123",
        "confirm_password": "password123",
        "role": "student"
    })
    
    # Attempt login with incorrect password
    response = client.post("/auth/login", data={
        "email": "wrongpwd@e16.edu.vn",
        "password": "wrong_password"
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert request.path == "/auth/login"

@pytest.mark.auth
def test_login_inactive_user(client, app):
    """Negative Test: Inactive user (is_active=False) should not be allowed to log in."""
    # Register first
    client.post("/auth/register", data={
        "email": "inactive@e16.edu.vn",
        "password": "password123",
        "confirm_password": "password123",
        "role": "student"
    })
    
    # Set user as inactive in database
    with app.app_context():
        user = db.session.query(User).filter_by(email="inactive@e16.edu.vn").first()
        assert user is not None
        user.is_active = False
        db.session.commit()
        
    # Attempt login as the inactive user
    response = client.post("/auth/login", data={
        "email": "inactive@e16.edu.vn",
        "password": "password123"
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert request.path == "/auth/login"
