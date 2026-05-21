# -*- coding: utf-8 -*-
"""
Auth tests — updated for post-register-disable architecture.
Users are now created directly in DB (simulating Học vụ provisioning).
"""
import pytest
from werkzeug.security import generate_password_hash

from e16_app import create_app, db
from e16_app.models import User

def _create_user(app, email, password, role, must_change_password=False):
    """Helper: create user directly in DB (simulating Học vụ provisioning)."""
    with app.app_context():
        u = User(
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            must_change_password=must_change_password,
        )
        db.session.add(u)
        db.session.commit()
        return u.id

# ─────────── Register is disabled ───────────

@pytest.mark.auth
@pytest.mark.smoke
def test_register_is_disabled(client):
    """GET /auth/register should return 410 Gone."""
    response = client.get("/auth/register")
    assert response.status_code == 410

@pytest.mark.auth
def test_register_post_is_disabled(client, app):
    """POST /auth/register should return 410 Gone and not create any user."""
    response = client.post("/auth/register", data={
        "email": "test@e16.edu.vn",
        "password": "password123",
        "confirm_password": "password123",
        "role": "student"
    })

    assert response.status_code == 410

    with app.app_context():
        user = db.session.query(User).filter_by(email="test@e16.edu.vn").first()
        assert user is None

# ─────────── Login / Logout ───────────

@pytest.mark.auth
@pytest.mark.smoke
def test_login_page_loads(client):
    """Login page should load successfully."""
    response = client.get("/auth/login")
    assert response.status_code == 200

@pytest.mark.auth
@pytest.mark.smoke
def test_login_logout_student(client, app):
    """Verify login and logout flow for a student."""
    _create_user(app, "student@e16.test", "pass123abc", "student")

    response = client.post("/auth/login", data={
        "email": "student@e16.test",
        "password": "pass123abc"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert response.request.path == "/dashboard"

    # Logout
    response = client.get("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert response.request.path == "/auth/login"

@pytest.mark.auth
@pytest.mark.smoke
def test_login_teacher_redirect(client, app):
    """Teacher should be redirected to teacher dashboard."""
    _create_user(app, "teacher@e16.test", "pass123abc", "teacher")

    response = client.post("/auth/login", data={
        "email": "teacher@e16.test",
        "password": "pass123abc"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert response.request.path == "/teacher/dashboard"

@pytest.mark.auth
def test_login_hocvu_redirect(client, app):
    """Học vụ should be redirected to hoc_vu dashboard."""
    _create_user(app, "hocvu@e16.test", "pass123abc", "hoc_vu")

    response = client.post("/auth/login", data={
        "email": "hocvu@e16.test",
        "password": "pass123abc"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert response.request.path == "/hoc-vu/dashboard"

@pytest.mark.auth
def test_login_incorrect_password(client, app):
    """Login with wrong password should stay on login page."""
    _create_user(app, "user@e16.test", "correct_password", "student")

    response = client.post("/auth/login", data={
        "email": "user@e16.test",
        "password": "wrong_password"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert response.request.path == "/auth/login"

@pytest.mark.auth
def test_login_inactive_user(client, app):
    """Inactive user should be blocked from login."""
    uid = _create_user(app, "inactive@e16.test", "pass123abc", "student")

    with app.app_context():
        user = db.session.get(User, uid)
        user.is_active = False
        db.session.commit()

    response = client.post("/auth/login", data={
        "email": "inactive@e16.test",
        "password": "pass123abc"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert response.request.path == "/auth/login"

# ─────────── Security Headers ───────────

def test_security_headers_include_hardened_csp(client):
    response = client.get("/auth/login")
    csp = response.headers.get("Content-Security-Policy", "")

    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "form-action 'self'" in csp
    assert "frame-ancestors 'self'" in csp
