# -*- coding: utf-8 -*-
import pytest

from e16_app import create_app, db
from e16_app.models import Course, Enrollment, ForumThread, ForumReply, Notification, User

def test_teacher_can_hide_forum_thread(client, app):
    with app.app_context():
        teacher = User(email="mod_teacher@e16.edu.vn", password_hash="hash", role="teacher")
        student = User(email="mod_student@e16.edu.vn", password_hash="hash", role="student")
        db.session.add_all([teacher, student])
        db.session.flush()
        course = Course(title="Moderated", teacher_id=teacher.id, status="published")
        db.session.add(course)
        db.session.flush()
        db.session.add(Enrollment(user_id=student.id, course_id=course.id))
        thread = ForumThread(course_id=course.id, author_id=student.id, title="Bad", body="Hidden")
        db.session.add(thread)
        db.session.commit()
        teacher_id = teacher.id
        course_id = course.id
        thread_id = thread.id

    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_id
        sess["_fresh"] = True

    response = client.post(f"/courses/{course_id}/forum/{thread_id}/hide")

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(ForumThread, thread_id).is_hidden is True

def test_student_cannot_hide_forum_reply(client, app):
    with app.app_context():
        teacher = User(email="reply_teacher@e16.edu.vn", password_hash="hash", role="teacher")
        student = User(email="reply_student@e16.edu.vn", password_hash="hash", role="student")
        db.session.add_all([teacher, student])
        db.session.flush()
        course = Course(title="Replies", teacher_id=teacher.id, status="published")
        db.session.add(course)
        db.session.flush()
        db.session.add(Enrollment(user_id=student.id, course_id=course.id))
        thread = ForumThread(course_id=course.id, author_id=student.id, title="Thread", body="Body")
        db.session.add(thread)
        db.session.flush()
        reply = ForumReply(thread_id=thread.id, author_id=student.id, body="Reply")
        db.session.add(reply)
        db.session.commit()
        student_id = student.id
        course_id = course.id
        reply_id = reply.id

    with client.session_transaction() as sess:
        sess["_user_id"] = student_id
        sess["_fresh"] = True

    response = client.post(f"/courses/{course_id}/forum/replies/{reply_id}/hide")

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(ForumReply, reply_id).is_hidden is False

def test_notifications_are_paginated(client, app):
    with app.app_context():
        user = User(email="notif_user@e16.edu.vn", password_hash="hash", role="student")
        db.session.add(user)
        db.session.flush()
        for idx in range(25):
            db.session.add(Notification(user_id=user.id, type="announcement", message=f"Notification {idx}"))
        db.session.commit()
        user_id = user.id

    with client.session_transaction() as sess:
        sess["_user_id"] = user_id
        sess["_fresh"] = True

    response = client.get("/notifications?page=2&per_page=10")

    assert response.status_code == 200
    assert "Trang 2/3".encode("utf-8") in response.data

def test_student_can_report_thread_and_reply(client, app):
    with app.app_context():
        teacher = User(email="rep_teacher@e16.edu.vn", password_hash="hash", role="teacher")
        student = User(email="rep_student@e16.edu.vn", password_hash="hash", role="student")
        db.session.add_all([teacher, student])
        db.session.flush()
        course = Course(title="Reports Course", teacher_id=teacher.id, status="published")
        db.session.add(course)
        db.session.flush()
        db.session.add(Enrollment(user_id=student.id, course_id=course.id))
        thread = ForumThread(course_id=course.id, author_id=student.id, title="Offensive Thread", body="Spam content")
        db.session.add(thread)
        db.session.flush()
        reply = ForumReply(thread_id=thread.id, author_id=student.id, body="Offensive Reply")
        db.session.add(reply)
        db.session.commit()
        student_id = student.id
        course_id = course.id
        thread_id = thread.id
        reply_id = reply.id

    with client.session_transaction() as sess:
        sess["_user_id"] = student_id
        sess["_fresh"] = True

    # 1. Report Thread
    response = client.post(f"/courses/{course_id}/forum/{thread_id}/report", data={
        "reason": "Spam",
        "detail": "This is spam thread"
    }, follow_redirects=True)
    assert response.status_code == 200

    # 2. Report Reply
    response2 = client.post(f"/courses/{course_id}/forum/replies/{reply_id}/report", data={
        "reason": "Toxic",
        "detail": "This is toxic reply"
    }, follow_redirects=True)
    assert response2.status_code == 200

    with app.app_context():
        from e16_app.models import ContentReport
        reports = db.session.query(ContentReport).all()
        assert len(reports) == 2
        
        thread_report = next(r for r in reports if r.target_type == "thread")
        assert thread_report.reason == "Spam"
        assert thread_report.detail == "This is spam thread"
        assert thread_report.reporter_id == student_id
        
        reply_report = next(r for r in reports if r.target_type == "reply")
        assert reply_report.reason == "Toxic"
        assert reply_report.detail == "This is toxic reply"
        assert reply_report.reporter_id == student_id

def test_admin_can_resolve_content_report_hide_and_dismiss(client, app):
    with app.app_context():
        admin = User(email="admin_mod@e16.edu.vn", password_hash="hash", role="admin")
        teacher = User(email="rep_teacher2@e16.edu.vn", password_hash="hash", role="teacher")
        student = User(email="rep_student2@e16.edu.vn", password_hash="hash", role="student")
        db.session.add_all([admin, teacher, student])
        db.session.flush()
        course = Course(title="Moderation Course", teacher_id=teacher.id, status="published")
        db.session.add(course)
        db.session.flush()
        thread = ForumThread(course_id=course.id, author_id=student.id, title="Offensive Thread", body="Spam content")
        db.session.add(thread)
        db.session.flush()
        reply = ForumReply(thread_id=thread.id, author_id=student.id, body="Offensive Reply")
        db.session.add(reply)
        db.session.flush()
        
        from e16_app.models import ContentReport
        report_thread_obj = ContentReport(reporter_id=student.id, target_type="thread", target_id=thread.id, reason="Spam")
        report_reply_obj = ContentReport(reporter_id=student.id, target_type="reply", target_id=reply.id, reason="Toxic")
        db.session.add_all([report_thread_obj, report_reply_obj])
        db.session.commit()
        
        admin_id = admin.id
        report_thread_id = report_thread_obj.id
        report_reply_id = report_reply_obj.id
        thread_id = thread.id
        reply_id = reply.id

    with client.session_transaction() as sess:
        sess["_user_id"] = admin_id
        sess["_fresh"] = True

    # 1. Admin views reports page
    response = client.get("/admin/reports")
    assert response.status_code == 200
    assert "Offensive Thread".encode("utf-8") in response.data

    # 2. Admin resolves thread report by hiding it
    response2 = client.post(f"/admin/reports/{report_thread_id}/resolve", data={"action": "hide"}, follow_redirects=True)
    assert response2.status_code == 200

    # 3. Admin dismisses reply report
    response3 = client.post(f"/admin/reports/{report_reply_id}/resolve", data={"action": "dismiss"}, follow_redirects=True)
    assert response3.status_code == 200

    with app.app_context():
        from e16_app.models import ContentReport
        r_thread = db.session.get(ContentReport, report_thread_id)
        assert r_thread.status == "resolved"
        assert r_thread.action_taken == "hide"
        assert r_thread.resolved_by == admin_id
        
        # Thread should now be hidden
        assert db.session.get(ForumThread, thread_id).is_hidden is True
        
        r_reply = db.session.get(ContentReport, report_reply_id)
        assert r_reply.status == "dismissed"
        assert r_reply.action_taken == "dismiss"
        
        # Reply should NOT be hidden
        assert db.session.get(ForumReply, reply_id).is_hidden is False

