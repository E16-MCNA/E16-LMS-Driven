# -*- coding: utf-8 -*-
import pytest
from io import BytesIO

from e16_app import create_app, db
from e16_app.models import AuditLog, Course, LearningLog, Lesson, User

def test_seed_route_is_forbidden_in_production(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    response = client.get("/admin/seed")

    assert response.status_code == 404

def test_import_users_validates_csv_and_imports_optional_fields(client, app):
    with app.app_context():
        admin = User(email="admin@e16.local", password_hash="hash", role="admin")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as sess:
        sess["_user_id"] = admin_id
        sess["_fresh"] = True

    csv_bytes = "\ufeffemail,role,phone,is_active\nnew_student@e16.edu.vn,student,0901234567,false\nbad_role@e16.edu.vn,owner,,true\n".encode("utf-8")
    response = client.post(
        "/admin/users/import",
        data={"file": (BytesIO(csv_bytes), "users.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        imported = db.session.query(User).filter_by(email="new_student@e16.edu.vn").first()
        rejected = db.session.query(User).filter_by(email="bad_role@e16.edu.vn").first()
        assert imported is not None
        assert imported.role == "student"
        assert imported.phone == "0901234567"
        assert imported.is_active is False
        assert rejected is None

def test_import_users_rejects_missing_required_headers(client, app):
    with app.app_context():
        admin = User(email="admin2@e16.local", password_hash="hash", role="admin")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as sess:
        sess["_user_id"] = admin_id
        sess["_fresh"] = True

    response = client.post(
        "/admin/users/import",
        data={"file": (BytesIO(b"email\nuser@e16.edu.vn\n"), "users.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        assert db.session.query(User).filter_by(email="user@e16.edu.vn").first() is None

def test_delete_user_soft_deletes_account(client, app):
    with app.app_context():
        admin = User(email="soft_admin@e16.local", password_hash="hash", role="admin")
        user = User(email="delete_me@e16.local", password_hash="hash", role="student", is_active=True)
        db.session.add_all([admin, user])
        db.session.commit()
        admin_id = admin.id
        user_id = user.id

    with client.session_transaction() as sess:
        sess["_user_id"] = admin_id
        sess["_fresh"] = True

    response = client.post(f"/admin/users/{user_id}/delete")

    assert response.status_code == 302
    with app.app_context():
        deleted = db.session.get(User, user_id)
        assert deleted is not None
        assert deleted.is_active is False

def test_admin_users_are_paginated(client, app):
    with app.app_context():
        admin = User(email="page_admin@e16.local", password_hash="hash", role="admin")
        db.session.add(admin)
        db.session.flush()
        for idx in range(25):
            db.session.add(User(email=f"user{idx}@e16.local", password_hash="hash", role="student"))
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as sess:
        sess["_user_id"] = admin_id
        sess["_fresh"] = True

    response = client.get("/admin/users?page=2&per_page=10")

    assert response.status_code == 200
    assert "Trang 2/3".encode("utf-8") in response.data

def test_audit_log_is_paginated(client, app):
    with app.app_context():
        admin = User(email="audit_admin@e16.local", password_hash="hash", role="admin")
        db.session.add(admin)
        db.session.flush()
        for idx in range(60):
            db.session.add(AuditLog(actor_id=admin.id, action=f"action_{idx}"))
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as sess:
        sess["_user_id"] = admin_id
        sess["_fresh"] = True

    response = client.get("/admin/audit-log?page=2&per_page=25")

    assert response.status_code == 200
    assert "Trang 2/3".encode("utf-8") in response.data

def test_metricsz_requires_admin_or_token(client, app, monkeypatch):
    monkeypatch.setenv("METRICS_TOKEN", "test-token")
    forbidden = client.get("/metricsz")
    assert forbidden.status_code == 403

    token_response = client.get("/metricsz", headers={"X-Metrics-Token": "test-token"})
    assert token_response.status_code == 200
    assert "users_active" in token_response.json

def test_admin_export_is_audited(client, app):
    with app.app_context():
        admin = User(email="export_admin@e16.local", password_hash="hash", role="admin")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as sess:
        sess["_user_id"] = admin_id
        sess["_fresh"] = True

    response = client.get("/analytics/export?type=general")

    assert response.status_code == 200
    with app.app_context():
        log = db.session.query(AuditLog).filter_by(action="admin_export", target_type="Analytics", target_id="general").first()
        assert log is not None

def test_admin_export_respects_max_rows(client, app, monkeypatch):
    monkeypatch.setenv("EXPORT_MAX_ROWS", "2")
    with app.app_context():
        admin = User(email="limited_export_admin@e16.local", password_hash="hash", role="admin")
        teacher = User(email="limited_teacher@e16.local", password_hash="hash", role="teacher")
        student = User(email="limited_student@e16.local", password_hash="hash", role="student")
        db.session.add_all([admin, teacher, student])
        db.session.flush()
        course = Course(title="Limited", teacher_id=teacher.id)
        db.session.add(course)
        db.session.flush()
        lesson = Lesson(course_id=course.id, title="L", sequence_order=1)
        db.session.add(lesson)
        db.session.flush()
        for _ in range(3):
            db.session.add(LearningLog(user_id=student.id, lesson_id=lesson.id, action_type="complete"))
        db.session.commit()
        admin_id = admin.id

    with client.session_transaction() as sess:
        sess["_user_id"] = admin_id
        sess["_fresh"] = True

    response = client.get("/analytics/export?type=learning_logs")

    assert response.status_code == 200
    assert len(response.data.decode("utf-8").splitlines()) == 3

def test_permission_denied_is_audited(client, app):
    with app.app_context():
        teacher = User(email="denied_teacher@e16.local", password_hash="hash", role="teacher")
        db.session.add(teacher)
        db.session.commit()
        teacher_id = teacher.id

    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_id
        sess["_fresh"] = True

    response = client.get("/admin/users")

    assert response.status_code == 302
    with app.app_context():
        log = db.session.query(AuditLog).filter_by(action="permission_denied", target_type="endpoint").first()
        assert log is not None
