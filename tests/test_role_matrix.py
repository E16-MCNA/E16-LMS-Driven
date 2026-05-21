# -*- coding: utf-8 -*-
"""
Role Matrix Validation Tests for E16 LMS.

Verifies strict route access control boundaries across Student, Teacher, Admin,
and Unauthenticated user states.
"""
import pytest
from werkzeug.security import generate_password_hash

from e16_app import create_app, db
from e16_app.models import User


# ─────────────────────── Fixtures ───────────────────────

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def student_user(app):
    with app.app_context():
        u = User(email="student@e16.test", password_hash=generate_password_hash("pass"), role="student", must_change_password=False)
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def teacher_user(app):
    with app.app_context():
        u = User(email="teacher@e16.test", password_hash=generate_password_hash("pass"), role="teacher", must_change_password=False)
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def admin_user(app):
    with app.app_context():
        u = User(email="admin@e16.test", password_hash=generate_password_hash("pass"), role="admin", must_change_password=False)
        db.session.add(u)
        db.session.commit()
        return u.id


# ─────────────────── Unauthenticated Access ───────────────────

def test_unauthenticated_user_cannot_access_protected_routes(client):
    """Anonymous visitors must be blocked and redirected to login for any private page."""
    protected_urls = [
        "/dashboard",
        "/teacher/dashboard",
        "/admin/users",
        "/admin/audit-log",
        "/calendar",
        "/transcript"
    ]
    for url in protected_urls:
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response.headers.get("Location", "").lower()


# ─────────────────── Student Role Boundaries ───────────────────

def test_student_cannot_access_teacher_or_admin_routes(client, student_user):
    """Students attempting to access management or admin panels must be redirected/rejected."""
    with client.session_transaction() as sess:
        sess["_user_id"] = student_user
        sess["_fresh"] = True

    forbidden_urls = [
        "/teacher/dashboard",
        "/admin/users",
        "/admin/audit-log"
    ]
    for url in forbidden_urls:
        response = client.get(url)
        assert response.status_code == 302


# ─────────────────── Teacher Role Boundaries ───────────────────

def test_teacher_cannot_access_admin_routes(client, teacher_user):
    """Teachers should not be allowed into administrative portals."""
    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_user
        sess["_fresh"] = True

    forbidden_urls = [
        "/admin/users",
        "/admin/audit-log"
    ]
    for url in forbidden_urls:
        response = client.get(url)
        assert response.status_code == 302


# ─────────────────── Seed Route Access Protection ───────────────────

def test_student_and_teacher_cannot_seed(client, student_user, teacher_user):
    """Only authorized administrators or CLI triggers can seed system data."""
    # Test Student block
    with client.session_transaction() as sess:
        sess["_user_id"] = student_user
        sess["_fresh"] = True
    response = client.post("/admin/seed")
    assert response.status_code == 302

    # Test Teacher block
    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_user
        sess["_fresh"] = True
    response = client.post("/admin/seed")
    assert response.status_code == 302
