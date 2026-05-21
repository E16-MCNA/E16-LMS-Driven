# -*- coding: utf-8 -*-
from datetime import timedelta

from werkzeug.security import generate_password_hash

from e16_app.extensions import db
from e16_app.models import AuditLog, Course, LearningLog, SystemSetting, User
from e16_app.services.demo_data import DEMO_ENRICHMENT_KEY, enrich_demo_data_once
from e16_app.time_utils import utcnow


def test_demo_enrichment_creates_login_history_and_teacher_courses(app):
    with app.app_context():
        pwd = generate_password_hash("pass123abc")
        teacher = User(email="teacher.demo@e16.test", password_hash=pwd, role="teacher")
        students = [
            User(email=f"student{i}.demo@e16.test", password_hash=pwd, role="student")
            for i in range(10)
        ]
        db.session.add(teacher)
        db.session.add_all(students)
        db.session.commit()

        result = enrich_demo_data_once(force=True, rng_seed=123)

        users = db.session.query(User).all()
        assert all(u.created_at < u.last_login for u in users)
        assert all(u.login_count > 0 for u in users)
        assert db.session.query(AuditLog).filter_by(action="login_success").count() >= len(users)

        teacher_courses = db.session.query(Course).filter_by(teacher_id=teacher.id, is_deleted=False).all()
        assert teacher_courses
        assert all(c.status in ("published", "running") for c in teacher_courses)
        assert result["courses"] >= 1

        today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        assert db.session.query(LearningLog).filter(LearningLog.timestamp >= today_start - timedelta(seconds=1)).count() > 0

        marker = db.session.query(SystemSetting).filter_by(key=DEMO_ENRICHMENT_KEY).one()
        assert marker.value.startswith("completed:")


def test_demo_enrichment_respects_user_limit(app, monkeypatch):
    monkeypatch.setenv("E16_DEMO_USER_LIMIT", "5")

    with app.app_context():
        pwd = generate_password_hash("pass123abc")
        db.session.add(User(email="teacher.limit@e16.test", password_hash=pwd, role="teacher"))
        for i in range(20):
            db.session.add(User(email=f"student{i}.limit@e16.test", password_hash=pwd, role="student"))
        db.session.commit()

        result = enrich_demo_data_once(force=True, rng_seed=456)

        assert result["users"] == 5
        assert db.session.query(AuditLog).filter_by(action="login_success").count() >= 5
