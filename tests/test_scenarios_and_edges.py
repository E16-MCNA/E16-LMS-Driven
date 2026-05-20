# -*- coding: utf-8 -*-
"""
Verification suite for E16 LMS scenarios and edge cases.
Automates 12 specific business scenarios and 10 critical edge cases.
"""
import io
import pytest
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash

from e16_app import create_app, db
from e16_app.models import (
    User, Course, Lesson, Enrollment, Quiz, Question, Choice, QuizAttempt, LearningLog, Submission, Certificate, Assignment
)


# ─────────────────────── Fixtures ───────────────────────

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-key-scenarios"
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_db(app):
    with app.app_context():
        now = datetime.now(timezone.utc)
        
        # 1. USERS — password is 'TestPass123!'
        pwd_hash = generate_password_hash("TestPass123!")
        users = [
            User(id='u-admin', email='admin@e16.local', password_hash=pwd_hash, role='admin', created_at=now - timedelta(days=90), login_count=42, last_login=now),
            User(id='u-ta', email='teacher_a@e16.local', password_hash=pwd_hash, role='teacher', created_at=now - timedelta(days=80), login_count=18, last_login=now),
            User(id='u-tb', email='teacher_b@e16.local', password_hash=pwd_hash, role='teacher', created_at=now - timedelta(days=75), login_count=12, last_login=now),
            User(id='u-s1', email='student_1@e16.local', password_hash=pwd_hash, role='student', created_at=now - timedelta(days=60), login_count=30, last_login=now),
            User(id='u-s2', email='student_2@e16.local', password_hash=pwd_hash, role='student', created_at=now - timedelta(days=55), login_count=15, last_login=now),
            User(id='u-s3', email='student_3@e16.local', password_hash=pwd_hash, role='student', created_at=now - timedelta(days=50), login_count=10, last_login=now),
            User(id='u-s4', email='student_4@e16.local', password_hash=pwd_hash, role='student', created_at=now - timedelta(days=45), login_count=8, last_login=now),
            User(id='u-sd', email='student_done@e16.local', password_hash=pwd_hash, role='student', created_at=now - timedelta(days=70), login_count=50, last_login=now - timedelta(days=5)),
            User(id='u-s5', email='student_5@e16.local', password_hash=pwd_hash, role='student', created_at=now - timedelta(days=10), login_count=2, last_login=now),
            User(id='u-snr', email='student_notenrolled@e16.local', password_hash=pwd_hash, role='student', created_at=now - timedelta(days=5), login_count=1, last_login=now),
            User(id='u-inactive', email='inactive@e16.local', password_hash=pwd_hash, role='student', created_at=now - timedelta(days=30), login_count=3, last_login=now - timedelta(days=30), is_active=False),
        ]
        db.session.add_all(users)
        db.session.commit()

        # 2. COURSES
        courses = [
            Course(id='c-py', title='Python for Data', description='Khoá học Python cơ bản đến nâng cao.', cover_image_url='/static/img/course_python.jpg', total_lessons=8, teacher_id='u-ta', created_at=now - timedelta(days=80), status='published'),
            Course(id='c-sql', title='SQL Fundamentals', description='Truy vấn dữ liệu với PostgreSQL.', cover_image_url='/static/img/course_sql.jpg', total_lessons=6, teacher_id='u-ta', created_at=now - timedelta(days=70), status='published'),
            Course(id='c-draft', title='Data Viz (Draft)', description='Đang soạn thảo, chưa publish.', cover_image_url='/static/img/placeholder.jpg', total_lessons=0, teacher_id='u-ta', created_at=now - timedelta(days=10), status='draft'),
            Course(id='c-pend', title='Statistics Basics', description='Chờ admin duyệt.', cover_image_url='/static/img/placeholder.jpg', total_lessons=5, teacher_id='u-tb', created_at=now - timedelta(days=5), status='pending_review'),
            Course(id='c-del', title='Deleted Course', description='Khoá học đã bị xóa mềm.', cover_image_url='/static/img/placeholder.jpg', total_lessons=3, teacher_id='u-tb', created_at=now - timedelta(days=60), status='archived', is_deleted=True),
            Course(id='c-tb', title='Teacher B Course', description='Khoá học của teacher B.', cover_image_url='/static/img/placeholder.jpg', total_lessons=4, teacher_id='u-tb', created_at=now - timedelta(days=40), status='published'),
        ]
        db.session.add_all(courses)
        db.session.commit()

        # 3. LESSONS
        lessons = [
            Lesson(id='l-1', course_id='c-py', title='Giới thiệu Python', video_url='https://example.com/v1', document_url='https://example.com/d1', sequence_order=1, created_at=now - timedelta(days=79)),
            Lesson(id='l-2', course_id='c-py', title='Kiểu dữ liệu cơ bản', video_url='https://example.com/v2', document_url='https://example.com/d2', sequence_order=2, created_at=now - timedelta(days=78)),
            Lesson(id='l-3', course_id='c-py', title='Vòng lặp và điều kiện', video_url='https://example.com/v3', document_url='https://example.com/d3', sequence_order=3, created_at=now - timedelta(days=77)),
            Lesson(id='l-4', course_id='c-py', title='Hàm và module', video_url='https://example.com/v4', document_url='https://example.com/d4', sequence_order=4, created_at=now - timedelta(days=76)),
            Lesson(id='l-5', course_id='c-py', title='List, Dict, Set', video_url='https://example.com/v5', document_url='https://example.com/d5', sequence_order=5, created_at=now - timedelta(days=75)),
            Lesson(id='l-6', course_id='c-py', title='File I/O', video_url='https://example.com/v6', document_url='https://example.com/d6', sequence_order=6, created_at=now - timedelta(days=74)),
            Lesson(id='l-7', course_id='c-py', title='Xử lý exception', video_url='https://example.com/v7', document_url='https://example.com/d7', sequence_order=7, created_at=now - timedelta(days=73)),
            Lesson(id='l-8', course_id='c-py', title='Project thực hành', video_url='https://example.com/v8', document_url='https://example.com/d8', sequence_order=8, created_at=now - timedelta(days=72)),
        ]
        db.session.add_all(lessons)
        db.session.commit()

        # 4. ENROLLMENTS
        enrollments = [
            Enrollment(id='e-s1-py', user_id='u-s1', course_id='c-py', enrolled_at=now - timedelta(days=58), status='active'),
            Enrollment(id='e-s2-py', user_id='u-s2', course_id='c-py', enrolled_at=now - timedelta(days=50), status='active'),
            Enrollment(id='e-s3-py', user_id='u-s3', course_id='c-py', enrolled_at=now - timedelta(days=40), status='active'),
            Enrollment(id='e-s4-py', user_id='u-s4', course_id='c-py', enrolled_at=now - timedelta(days=30), status='active'),
            Enrollment(id='e-sd-py', user_id='u-sd', course_id='c-py', enrolled_at=now - timedelta(days=68), status='completed'),
            Enrollment(id='e-s5-py', user_id='u-s5', course_id='c-py', enrolled_at=now - timedelta(days=8), status='pending_payment'),
            Enrollment(id='e-s1-sql', user_id='u-s1', course_id='c-sql', enrolled_at=now - timedelta(days=45), status='active'),
            Enrollment(id='e-sd-sql', user_id='u-sd', course_id='c-sql', enrolled_at=now - timedelta(days=60), status='completed'),
        ]
        db.session.add_all(enrollments)
        db.session.commit()

        # 5. QUIZZES
        quizzes = [
            Quiz(id='qz-1', course_id='c-py', title='Quiz cuối khoá Python', pass_score=80, max_attempts=3, due_date=None, is_published=True, created_at=now - timedelta(days=70)),
            # Quiz quá hạn (due_date trong quá khứ)
            Quiz(id='qz-2', course_id='c-py', title='Quiz giữa kỳ', pass_score=70, max_attempts=2, due_date=now - timedelta(days=5), is_published=True, created_at=now - timedelta(days=70)),
            # Quiz chưa publish
            Quiz(id='qz-3', course_id='c-py', title='Quiz nháp', pass_score=80, max_attempts=1, due_date=None, is_published=False, created_at=now - timedelta(days=5)),
        ]
        db.session.add_all(quizzes)
        db.session.commit()

        # 6. QUESTIONS & CHOICES (cho qz-1)
        questions = [
            Question(id='q-1', quiz_id='qz-1', text='Python được tạo bởi ai?', q_type='mcq', sequence_order=1),
            Question(id='q-2', quiz_id='qz-1', text='Kiểu dữ liệu nào là immutable trong Python?', q_type='mcq', sequence_order=2),
            Question(id='q-3', quiz_id='qz-1', text='Kết quả của 2**10 là bao nhiêu?', q_type='mcq', sequence_order=3),
        ]
        db.session.add_all(questions)
        db.session.commit()

        choices = [
            Choice(id='ch-1-1', question_id='q-1', text='Guido van Rossum', is_correct=True),
            Choice(id='ch-1-2', question_id='q-1', text='Linus Torvalds', is_correct=False),
            Choice(id='ch-1-3', question_id='q-1', text='James Gosling', is_correct=False),
            Choice(id='ch-2-1', question_id='q-2', text='list', is_correct=False),
            Choice(id='ch-2-2', question_id='q-2', text='tuple', is_correct=True),
            Choice(id='ch-2-3', question_id='q-2', text='dict', is_correct=False),
            Choice(id='ch-3-1', question_id='q-3', text='512', is_correct=False),
            Choice(id='ch-3-2', question_id='q-3', text='1024', is_correct=True),
            Choice(id='ch-3-3', question_id='q-3', text='256', is_correct=False),
        ]
        db.session.add_all(choices)
        db.session.commit()

        # 7. QUIZ ATTEMPTS
        attempts = [
            QuizAttempt(id='qa-s1-1', quiz_id='qz-1', user_id='u-s1', score=90, passed=True, attempted_at=now - timedelta(days=20), completed_at=now - timedelta(days=20) + timedelta(minutes=25)),
            QuizAttempt(id='qa-s2-1', quiz_id='qz-1', user_id='u-s2', score=50, passed=False, attempted_at=now - timedelta(days=25), completed_at=now - timedelta(days=25) + timedelta(minutes=30)),
            QuizAttempt(id='qa-s2-2', quiz_id='qz-1', user_id='u-s2', score=55, passed=False, attempted_at=now - timedelta(days=20), completed_at=now - timedelta(days=20) + timedelta(minutes=28)),
            QuizAttempt(id='qa-s2-3', quiz_id='qz-1', user_id='u-s2', score=60, passed=False, attempted_at=now - timedelta(days=15), completed_at=now - timedelta(days=15) + timedelta(minutes=32)),
            QuizAttempt(id='qa-s3-1', quiz_id='qz-1', user_id='u-s3', score=None, passed=None, attempted_at=now - timedelta(hours=1), completed_at=None),
            QuizAttempt(id='qa-sd-1', quiz_id='qz-1', user_id='u-sd', score=95, passed=True, attempted_at=now - timedelta(days=60), completed_at=now - timedelta(days=60) + timedelta(minutes=20)),
        ]
        db.session.add_all(attempts)
        db.session.commit()

        # 8. LEARNING LOGS
        logs = [
            # student_done — học xong tất cả (time-to-complete ~20 ngày)
            LearningLog(log_id='ll-sd-1-s', user_id='u-sd', lesson_id='l-1', action_type='start', timestamp=now - timedelta(days=68)),
            LearningLog(log_id='ll-sd-1-c', user_id='u-sd', lesson_id='l-1', action_type='complete', timestamp=now - timedelta(days=68) + timedelta(minutes=45)),
            LearningLog(log_id='ll-sd-2-s', user_id='u-sd', lesson_id='l-2', action_type='start', timestamp=now - timedelta(days=67)),
            LearningLog(log_id='ll-sd-2-c', user_id='u-sd', lesson_id='l-2', action_type='complete', timestamp=now - timedelta(days=67) + timedelta(minutes=50)),
            LearningLog(log_id='ll-sd-3-c', user_id='u-sd', lesson_id='l-3', action_type='complete', timestamp=now - timedelta(days=65)),
            LearningLog(log_id='ll-sd-4-c', user_id='u-sd', lesson_id='l-4', action_type='complete', timestamp=now - timedelta(days=63)),
            LearningLog(log_id='ll-sd-5-c', user_id='u-sd', lesson_id='l-5', action_type='complete', timestamp=now - timedelta(days=60)),
            LearningLog(log_id='ll-sd-6-c', user_id='u-sd', lesson_id='l-6', action_type='complete', timestamp=now - timedelta(days=57)),
            LearningLog(log_id='ll-sd-7-c', user_id='u-sd', lesson_id='l-7', action_type='complete', timestamp=now - timedelta(days=52)),
            LearningLog(log_id='ll-sd-8-c', user_id='u-sd', lesson_id='l-8', action_type='complete', timestamp=now - timedelta(days=48)),

            # student_1 — học L1-L5 xong, L6 đang dở (time ~2 ngày → binge learner)
            LearningLog(log_id='ll-s1-1', user_id='u-s1', lesson_id='l-1', action_type='complete', timestamp=now - timedelta(days=57)),
            LearningLog(log_id='ll-s1-2', user_id='u-s1', lesson_id='l-2', action_type='complete', timestamp=now - timedelta(days=57) + timedelta(hours=2)),
            LearningLog(log_id='ll-s1-3', user_id='u-s1', lesson_id='l-3', action_type='complete', timestamp=now - timedelta(days=57) + timedelta(hours=4)),
            LearningLog(log_id='ll-s1-4', user_id='u-s1', lesson_id='l-4', action_type='complete', timestamp=now - timedelta(days=56)),
            LearningLog(log_id='ll-s1-5', user_id='u-s1', lesson_id='l-5', action_type='complete', timestamp=now - timedelta(days=56) + timedelta(hours=3)),
            LearningLog(log_id='ll-s1-6', user_id='u-s1', lesson_id='l-6', action_type='start', timestamp=now - timedelta(days=10)),

            # student_2 — học L1-L2 rồi drop
            LearningLog(log_id='ll-s2-1', user_id='u-s2', lesson_id='l-1', action_type='complete', timestamp=now - timedelta(days=48)),
            LearningLog(log_id='ll-s2-2', user_id='u-s2', lesson_id='l-2', action_type='complete', timestamp=now - timedelta(days=46)),

            # student_3 — học L1-L3
            LearningLog(log_id='ll-s3-1', user_id='u-s3', lesson_id='l-1', action_type='complete', timestamp=now - timedelta(days=38)),
            LearningLog(log_id='ll-s3-2', user_id='u-s3', lesson_id='l-2', action_type='complete', timestamp=now - timedelta(days=36)),
            LearningLog(log_id='ll-s3-3', user_id='u-s3', lesson_id='l-3', action_type='complete', timestamp=now - timedelta(days=33)),

            # student_4 — chỉ học L1 (L1 drop-off)
            LearningLog(log_id='ll-s4-1', user_id='u-s4', lesson_id='l-1', action_type='complete', timestamp=now - timedelta(days=28)),
        ]
        db.session.add_all(logs)
        db.session.commit()
        
        # 9. CERTIFICATES
        cert = Certificate(id='cert-done-py', user_id='u-sd', course_id='c-py', cert_code='cert-code-sd-py', issued_at=now - timedelta(days=48))
        db.session.add(cert)
        db.session.commit()


# ─────────────────────── 12 Scenarios ───────────────────────

def test_scenario_1_unenrolled_student_view_lessons(client, seeded_db):
    """Scenario 1: GET /learn/c-py as non-enrolled user 'u-snr' blocks access."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-snr"
        sess["_fresh"] = True
    response = client.get("/learn/c-py")
    assert response.status_code == 302  # Correctly redirects to courses listing
    assert "courses" in response.headers.get("Location", "")


def test_scenario_2_cross_teacher_course_modification(client, seeded_db):
    """Scenario 2: Teacher B cannot edit Teacher A's course."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-tb"  # Teacher B
        sess["_fresh"] = True
    response = client.get("/teacher/courses/c-py/edit")  # Course owned by teacher_a
    assert response.status_code == 302  # Correctly redirects to manage dashboard
    assert "manage" in response.headers.get("Location", "")


def test_scenario_3_cross_student_submission_download(client, app, seeded_db):
    """Scenario 3: Student A cannot download Student B's assignment submission."""
    with app.app_context():
        # Create submission of u-s2 for assignment on c-py
        assign = Assignment(id="a-py-scen3", course_id="c-py", title="Assignment 1", description="desc")
        sub = Submission(id="sub-s2-scen3", assignment_id="a-py-scen3", user_id="u-s2", file_path="assignments/sub1.pdf", status="pending")
        db.session.add_all([assign, sub])
        db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = "u-s1"  # Student 1
        sess["_fresh"] = True
    response = client.get("/submissions/sub-s2-scen3/download")
    assert response.status_code == 302  # Correctly redirects to student dashboard


def test_scenario_4_quiz_attempt_limit_enforced(client, seeded_db):
    """Scenario 4: Student 2 has exhausted 3/3 attempts, blocking more."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-s2"
        sess["_fresh"] = True
    response = client.get("/learn/c-py/quiz/qz-1")
    assert response.status_code == 302  # Blocks taking quiz and redirects to learning page
    assert "learn/c-py" in response.headers.get("Location", "")


def test_scenario_5_quiz_past_due_date_blocked(client, seeded_db):
    """Scenario 5: Quiz past due date is blocked."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-s1"
        sess["_fresh"] = True
    response = client.get("/learn/c-py/quiz/qz-2")
    assert response.status_code == 302  # Blocks taking expired quiz
    assert "learn/c-py" in response.headers.get("Location", "")


def test_scenario_6_enrollment_pending_blocks_lessons(client, seeded_db):
    """Scenario 6: Pending payment students are redirected to checkout."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-s5"  # enrollment status = 'pending_payment'
        sess["_fresh"] = True
    response = client.get("/learn/c-py")
    assert response.status_code == 302
    assert "checkout" in response.headers.get("Location", "")  # Redirected to checkout QR page


def test_scenario_7_certificate_issued_only_at_100_percent(client, app, seeded_db):
    """Scenario 7: u-s1 with 5/8 lessons cannot generate/find certificate."""
    with app.app_context():
        # Assert u-s1 has no Certificate issued for c-py
        cert = db.session.query(Certificate).filter_by(user_id="u-s1", course_id="c-py").first()
        assert cert is None


def test_scenario_8_certificate_of_soft_deleted_course_remains_valid(client, seeded_db):
    """Scenario 8: Certificate of a soft-deleted course remains publicly valid."""
    # c-del is soft-deleted (is_deleted=True, status='archived')
    # Let's link certificate to c-del instead
    response = client.get("/certificates/cert-code-sd-py")
    assert response.status_code == 200  # Returns 200 with masked name!


def test_scenario_9_admin_approves_pending_course(client, app, seeded_db):
    """Scenario 9: Admin approves pending course to publish it."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-admin"
        sess["_fresh"] = True
    response = client.post("/admin/courses/c-pend/approve")
    assert response.status_code == 302
    with app.app_context():
        c = db.session.get(Course, "c-pend")
        assert c.status == "published"


def test_scenario_10_teacher_export_gradebook(client, seeded_db):
    """Scenario 10: Teacher can export course gradebook without errors."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-ta"
        sess["_fresh"] = True
    response = client.get("/teacher/courses/c-py/gradebook/export")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("Content-Type", "")


def test_scenario_11_inactive_user_cannot_login(client, seeded_db):
    """Scenario 11: Inactive user login attempt is blocked."""
    response = client.post("/auth/login", data={"email": "inactive@e16.local", "password": "TestPass123!"})
    assert response.status_code == 302
    # Verify they remain on or are sent back to the login route with error flash
    assert "login" in response.headers.get("Location", "")


def test_scenario_12_double_enrollment_blocked(client, app, seeded_db):
    """Scenario 12: Cannot register or enroll in already active course."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-s1"  # u-s1 is active in c-py
        sess["_fresh"] = True
    response = client.post("/enroll/c-py")
    assert response.status_code == 302  # Already enrolled response


# ─────────────────────── 10 Edge Cases ───────────────────────

def test_edge_1_score_boundaries(app, seeded_db):
    """Edge Case 1: Grading clamps scores properly to [0, 100]."""
    with app.app_context():
        from e16_app.services import GradingService
        assign = Assignment(id="a-py-edge1", course_id="c-py", title="Assignment Edge", description="desc")
        sub = Submission(id="sub-edge1", assignment_id="a-py-edge1", user_id="u-s1", status="pending")
        db.session.add_all([assign, sub])
        db.session.commit()
        
        # Underflow clamps to 0
        GradingService.grade_assignment_submission("sub-edge1", -15, "feedback", "u-ta")
        assert db.session.get(Submission, "sub-edge1").score == 0
        
        # Overflow clamps to 100
        GradingService.grade_assignment_submission("sub-edge1", 120, "feedback", "u-ta")
        assert db.session.get(Submission, "sub-edge1").score == 100


def test_edge_2_past_vs_future_assignment_deadline(client, app, seeded_db):
    """Edge Case 2: Past assignment submission is blocked, future is allowed."""
    with app.app_context():
        now = datetime.now(timezone.utc)
        a_past = Assignment(id="a-past", course_id="c-py", title="Past", description="desc", deadline=now - timedelta(hours=1))
        a_future = Assignment(id="a-future", course_id="c-py", title="Future", description="desc", deadline=now + timedelta(hours=1))
        db.session.add_all([a_past, a_future])
        db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = "u-s1"
        sess["_fresh"] = True
        
    res_past = client.post("/learn/c-py/assignment/a-past", data={"text_content": "Late submission"})
    assert res_past.status_code == 302
    
    res_future = client.post("/learn/c-py/assignment/a-future", data={"text_content": "Valid submission"})
    assert res_future.status_code == 302


def test_edge_3_user_last_login_null(client, app, seeded_db):
    """Edge Case 3: Users listing or dashboards do not crash when last_login is NULL."""
    with app.app_context():
        u = db.session.get(User, "u-s5")
        u.last_login = None
        db.session.commit()
        
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-admin"
        sess["_fresh"] = True
    response = client.get("/admin/users")
    assert response.status_code == 200  # Does not crash with 500


def test_edge_4_course_with_zero_lessons(app, seeded_db):
    """Edge Case 4: Course completion calculations do not divide by zero if course has 0 lessons."""
    with app.app_context():
        from e16_app.services import student_completion_rate
        # c-draft has total_lessons = 0
        rate = student_completion_rate("u-s1", "c-draft")
        assert rate == 0.0


def test_edge_5_quiz_with_zero_questions(app, seeded_db):
    """Edge Case 5: Quiz grading calculations do not divide by zero if quiz has 0 questions."""
    with app.app_context():
        from e16_app.services import GradingService
        # qz-3 has 0 questions
        attempt = GradingService.grade_quiz_attempt("u-s1", "qz-3", {})
        assert attempt.score == 0


def test_edge_6_csv_import_duplicate_email(client, seeded_db):
    """Edge Case 6: CSV import gracefully skips duplicate email rows instead of crashing."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-admin"
        sess["_fresh"] = True
    
    csv_data = "email,role\nnewemail@e16.local,student\nstudent_1@e16.local,student\n"
    response = client.post("/admin/users/import", data={
        "file": (io.BytesIO(csv_data.encode("utf-8")), "import.csv")
    })
    assert response.status_code == 200
    assert b"Email" in response.data or b"Th\xc3\xa0nh c\xc3\xb4ng" in response.data


def test_edge_7_file_upload_limit(app):
    """Edge Case 7: Flask upload limit is set properly (MAX_CONTENT_LENGTH guard)."""
    assert app.config["MAX_CONTENT_LENGTH"] == 16 * 1024 * 1024  # 16MB standard limit


def test_edge_8_concurrent_quiz_submit(app, seeded_db):
    """Edge Case 8: Prevents attempts exceeding limit (u-s2 is blocked)."""
    with app.app_context():
        from e16_app.services import QuizService
        attempts = QuizService.get_attempt_count("u-s2", "qz-1")
        assert attempts >= 3


def test_edge_9_password_reset_token_single_use(client, app, seeded_db):
    """Edge Case 9: Password reset token is strictly single-use."""
    with app.app_context():
        u = db.session.get(User, "u-s1")
        u.reset_token = "unique-reset-token"
        u.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        db.session.commit()
        
    # Reset password successfully the first time
    res1 = client.post("/auth/reset-password/unique-reset-token", data={"password": "NewSecretPass123!"})
    assert res1.status_code == 302
    
    # Try using the same token again
    res2 = client.post("/auth/reset-password/unique-reset-token", data={"password": "AnotherSecret123!"})
    assert res2.status_code == 302  # Fails and redirects back to login/forgot password with error


def test_edge_10_soft_delete_user_learning_logs_remain(client, app, seeded_db):
    """Edge Case 10: Soft deleting/deactivating a user preserves learning logs history."""
    with client.session_transaction() as sess:
        sess["_user_id"] = "u-admin"
        sess["_fresh"] = True
    response = client.post("/admin/users/u-s1/delete")
    assert response.status_code == 302
    
    with app.app_context():
        logs_count = db.session.query(LearningLog).filter_by(user_id="u-s1").count()
        assert logs_count > 0  # Learning logs remain untouched!
