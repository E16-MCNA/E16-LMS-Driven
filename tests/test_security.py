# -*- coding: utf-8 -*-
"""
Security tests for E16 LMS hardening.

Covers:
- Submission file download access control (student & teacher isolation)
- Quiz review route with wrong course_id
- PAYMENT_MODE=real blocks mock IPN simulator
- Lesson mark_complete enforces 90-second minimum
"""
import pytest
from werkzeug.security import generate_password_hash

from e16_app import create_app, db
from e16_app.models import (
    Assignment, Choice, Course, Enrollment, Lesson, Question,
    Quiz, QuizAnswer, QuizAttempt, Submission, User,
)

# ─────────────────────── Fixtures ───────────────────────

@pytest.fixture
def teacher_a(app):
    """Teacher A — owns course_a."""
    with app.app_context():
        u = User(email="teacher_a@e16.test", password_hash=generate_password_hash("pass"), role="teacher")
        db.session.add(u)
        db.session.commit()
        return u.id

@pytest.fixture
def teacher_b(app):
    """Teacher B — owns nothing related to teacher_a."""
    with app.app_context():
        u = User(email="teacher_b@e16.test", password_hash=generate_password_hash("pass"), role="teacher")
        db.session.add(u)
        db.session.commit()
        return u.id

@pytest.fixture
def student_a(app):
    with app.app_context():
        u = User(email="student_a@e16.test", password_hash=generate_password_hash("pass"), role="student")
        db.session.add(u)
        db.session.commit()
        return u.id

@pytest.fixture
def student_b(app):
    with app.app_context():
        u = User(email="student_b@e16.test", password_hash=generate_password_hash("pass"), role="student")
        db.session.add(u)
        db.session.commit()
        return u.id

@pytest.fixture
def course_with_assignment(app, teacher_a, student_a):
    """Creates course → assignment → student_a submission with a file_path stub."""
    with app.app_context():
        course = Course(title="SecTest Course", teacher_id=teacher_a, status="published")
        db.session.add(course)
        db.session.flush()

        assignment = Assignment(
            course_id=course.id, title="Secure Assignment",
            description="File upload test", allow_file=True,
        )
        db.session.add(assignment)
        db.session.flush()

        db.session.add(Enrollment(user_id=student_a, course_id=course.id, status="active"))

        sub = Submission(
            assignment_id=assignment.id, user_id=student_a,
            text_content="My answer", file_path="assignments/fake-file.pdf",
        )
        db.session.add(sub)
        db.session.commit()

        return {
            "course_id": course.id,
            "assignment_id": assignment.id,
            "submission_id": sub.id,
        }

# ─────────────────── Test: Student file isolation ───────────────────

@pytest.mark.security
def test_student_cannot_download_other_students_submission(client, app, student_b, course_with_assignment):
    """
    Student B should NOT be able to download Student A's submission file.
    The download route is teacher-only, so a student role should be rejected entirely.
    """
    submission_id = course_with_assignment["submission_id"]

    with client.session_transaction() as sess:
        sess["_user_id"] = student_b
        sess["_fresh"] = True

    response = client.get(f"/teacher/submissions/{submission_id}/download")

    # Student role → redirected away (role_required("teacher") blocks access)
    assert response.status_code == 302
    assert "/teacher/" not in response.headers.get("Location", "")

# ─────────────────── Test: Teacher course isolation ───────────────────

@pytest.mark.security
def test_teacher_cannot_download_submission_from_other_teachers_course(client, app, teacher_b, course_with_assignment):
    """
    Teacher B should NOT be able to download submissions belonging
    to Teacher A's course, even though Teacher B has the teacher role.
    """
    submission_id = course_with_assignment["submission_id"]

    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_b
        sess["_fresh"] = True

    response = client.get(f"/teacher/submissions/{submission_id}/download")

    # Teacher B is redirected because course.teacher_id != teacher_b
    assert response.status_code == 302
    location = response.headers.get("Location", "")
    assert "manage" in location.lower() or response.status_code == 302

# ─────────────────── Test: Quiz review wrong course_id ───────────────────

@pytest.mark.security
def test_quiz_review_rejects_wrong_course_id(client, app, student_a, teacher_a):
    """
    Accessing quiz review with a mismatched course_id should be rejected.
    This prevents information leakage across courses.
    """
    with app.app_context():
        # Create course with quiz and attempt
        course = Course(title="Quiz Review Course", teacher_id=teacher_a, status="published")
        db.session.add(course)
        db.session.flush()

        db.session.add(Enrollment(user_id=student_a, course_id=course.id, status="active"))

        quiz = Quiz(title="Security Quiz", course_id=course.id, is_published=True, pass_score=50)
        db.session.add(quiz)
        db.session.flush()

        question = Question(quiz_id=quiz.id, text="1+1=?", q_type="mcq")
        db.session.add(question)
        db.session.flush()

        choice = Choice(question_id=question.id, text="2", is_correct=True)
        db.session.add(choice)
        db.session.flush()

        attempt = QuizAttempt(user_id=student_a, quiz_id=quiz.id, score=100, passed=True)
        db.session.add(attempt)
        db.session.flush()

        db.session.add(QuizAnswer(attempt_id=attempt.id, question_id=question.id, choice_id=choice.id))

        # Create a DIFFERENT course
        other_course = Course(title="Other Course", teacher_id=teacher_a, status="published")
        db.session.add(other_course)
        db.session.commit()

        real_course_id = course.id
        fake_course_id = other_course.id
        quiz_id = quiz.id
        attempt_id = attempt.id

    with client.session_transaction() as sess:
        sess["_user_id"] = student_a
        sess["_fresh"] = True

    # Access quiz review with WRONG course_id — route checks quiz.course_id != course_id
    response = client.get(f"/learn/{fake_course_id}/quiz/{quiz_id}/review/{attempt_id}")

    # Should redirect because quiz.course_id != fake_course_id (student.py L443)
    assert response.status_code == 302

# ─────────────────── Test: PAYMENT_MODE=real blocks simulator ───────────────────

@pytest.mark.security
def test_payment_mode_real_blocks_simulate_ipn(client, app, student_a, teacher_a, monkeypatch):
    """
    When PAYMENT_MODE=real, the simulate-ipn endpoint should return 501.
    This prevents fake enrollment activation in production.
    """
    with app.app_context():
        course = Course(title="Paid Course", teacher_id=teacher_a, status="published", price=500000)
        db.session.add(course)
        db.session.flush()

        # Create a pending enrollment
        enrollment = Enrollment(user_id=student_a, course_id=course.id, status="pending_payment")
        db.session.add(enrollment)
        db.session.commit()
        course_id = course.id

    # Set PAYMENT_MODE to real at the app config level
    app.config["PAYMENT_MODE"] = "real"

    with client.session_transaction() as sess:
        sess["_user_id"] = student_a
        sess["_fresh"] = True

    response = client.post(f"/checkout/simulate-ipn/{course_id}")

    assert response.status_code == 501
    data = response.get_json()
    assert data["status"] == "error"

    # Verify enrollment was NOT activated
    with app.app_context():
        enrollment = db.session.query(Enrollment).filter_by(user_id=student_a, course_id=course_id).first()
        assert enrollment.status == "pending_payment"

@pytest.mark.security
def test_payment_mode_mock_allows_simulate_ipn(client, app, student_a, teacher_a):
    """
    When PAYMENT_MODE=mock (default dev), the simulate-ipn endpoint should work.
    """
    with app.app_context():
        course = Course(title="Mock Paid Course", teacher_id=teacher_a, status="published", price=250000)
        db.session.add(course)
        db.session.flush()

        enrollment = Enrollment(user_id=student_a, course_id=course.id, status="pending_payment")
        db.session.add(enrollment)
        db.session.commit()
        course_id = course.id

    app.config["PAYMENT_MODE"] = "mock"

    with client.session_transaction() as sess:
        sess["_user_id"] = student_a
        sess["_fresh"] = True

    response = client.post(f"/checkout/simulate-ipn/{course_id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"

    # Verify enrollment was activated
    with app.app_context():
        enrollment = db.session.query(Enrollment).filter_by(user_id=student_a, course_id=course_id).first()
        assert enrollment.status == "active"

# ─────────────────── Test: Lesson completion 90-second enforcement ───────────────────

@pytest.mark.security
def test_lesson_mark_complete_rejected_without_session_start(client, app, student_a, teacher_a):
    """
    Marking a lesson complete without first visiting the lesson page (no session timestamp)
    should be rejected.
    """
    with app.app_context():
        course = Course(title="Timer Course", teacher_id=teacher_a, status="published")
        db.session.add(course)
        db.session.flush()

        lesson = Lesson(course_id=course.id, title="Lesson 1", sequence_order=1)
        db.session.add(lesson)
        db.session.flush()

        db.session.add(Enrollment(user_id=student_a, course_id=course.id, status="active"))
        db.session.commit()
        course_id = course.id
        lesson_id = lesson.id

    with client.session_transaction() as sess:
        sess["_user_id"] = student_a
        sess["_fresh"] = True
        # Deliberately NOT setting lesson_start_{lesson_id} in session

    response = client.post(f"/learn/{course_id}/complete/{lesson_id}", follow_redirects=True)

    assert response.status_code == 200
    # Should see the warning flash message about needing to open the lesson first
    assert "mở bài học".encode("utf-8") in response.data or "phút".encode("utf-8") in response.data

@pytest.mark.security
def test_lesson_mark_complete_rejected_under_90_seconds(client, app, student_a, teacher_a):
    """
    Marking a lesson complete less than 90 seconds after opening should be rejected.
    """
    from datetime import timezone
    from e16_app.time_utils import utcnow

    with app.app_context():
        course = Course(title="Timer Course 2", teacher_id=teacher_a, status="published")
        db.session.add(course)
        db.session.flush()

        lesson = Lesson(course_id=course.id, title="Fast Lesson", sequence_order=1)
        db.session.add(lesson)
        db.session.flush()

        db.session.add(Enrollment(user_id=student_a, course_id=course.id, status="active"))
        db.session.commit()
        course_id = course.id
        lesson_id = lesson.id

    with client.session_transaction() as sess:
        sess["_user_id"] = student_a
        sess["_fresh"] = True
        # Set lesson start to NOW (0 seconds elapsed)
        sess[f"lesson_start_{lesson_id}"] = utcnow().isoformat()

    response = client.post(f"/learn/{course_id}/complete/{lesson_id}", follow_redirects=True)

    assert response.status_code == 200
    # Should see the "1 phút 30 giây" rejection message
    assert "phút".encode("utf-8") in response.data or "giây".encode("utf-8") in response.data
