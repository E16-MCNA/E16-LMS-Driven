# -*- coding: utf-8 -*-
import pytest
from sqlalchemy.exc import IntegrityError
from e16_app import create_app, db
from e16_app.models import User, Course, Lesson, Enrollment, LearningLog, Quiz, Assignment, Question, Choice, Certificate, Submission

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def teacher_user(app):
    with app.app_context():
        user = User(email="teacher_test@e16.edu.vn", password_hash="hash", role="teacher")
        db.session.add(user)
        db.session.commit()
        return user.id

@pytest.fixture
def student_user(app):
    with app.app_context():
        user = User(email="student_test@e16.edu.vn", password_hash="hash", role="student")
        db.session.add(user)
        db.session.commit()
        return user.id

def test_teacher_create_course(client, app, teacher_user):
    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_user
        sess["_fresh"] = True
    
    response = client.post("/teacher/courses/new", data={"title": "Test Course 101"})
    assert response.status_code == 302
    
    with app.app_context():
        course = db.session.query(Course).filter_by(title="Test Course 101").first()
        assert course is not None
        assert course.teacher_id == teacher_user
        assert course.status == "draft"

def test_student_enrollment(client, app, student_user, teacher_user):
    with app.app_context():
        course = Course(title="Learn Python", teacher_id=teacher_user, status="published")
        db.session.add(course)
        db.session.commit()
        course_id = course.id

    with client.session_transaction() as sess:
        sess["_user_id"] = student_user
        sess["_fresh"] = True

    checkout_response = client.get(f"/checkout/{course_id}")
    assert checkout_response.status_code == 200

    response = client.post(f"/enroll/{course_id}")
    assert response.status_code == 302

    with app.app_context():
        enrollment = db.session.query(Enrollment).filter_by(user_id=student_user, course_id=course_id).first()
        assert enrollment is not None
        assert enrollment.status == "active"


def test_student_cannot_access_unenrolled_quiz_or_assignment(client, app, student_user, teacher_user):
    with app.app_context():
        course = Course(title="Private Course", teacher_id=teacher_user, status="published")
        db.session.add(course)
        db.session.flush()
        quiz = Quiz(title="Private Quiz", course_id=course.id, is_published=True)
        assignment = Assignment(title="Private Assignment", description="Secret", course_id=course.id)
        db.session.add_all([quiz, assignment])
        db.session.commit()
        course_id = course.id
        quiz_id = quiz.id
        assignment_id = assignment.id

    with client.session_transaction() as sess:
        sess["_user_id"] = student_user
        sess["_fresh"] = True

    quiz_response = client.get(f"/learn/{course_id}/quiz/{quiz_id}")
    assignment_response = client.get(f"/learn/{course_id}/assignment/{assignment_id}")

    assert quiz_response.status_code == 302
    assert assignment_response.status_code == 302


def test_teacher_reorder_lessons_updates_sequence_order(client, app, teacher_user):
    with app.app_context():
        course = Course(title="Ordering", teacher_id=teacher_user, status="draft")
        db.session.add(course)
        db.session.flush()
        first = Lesson(course_id=course.id, title="First", sequence_order=1)
        second = Lesson(course_id=course.id, title="Second", sequence_order=2)
        db.session.add_all([first, second])
        db.session.commit()
        course_id = course.id
        first_id = first.id
        second_id = second.id

    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_user
        sess["_fresh"] = True

    response = client.post(
        f"/teacher/courses/{course_id}/lessons/reorder",
        data={"lesson_ids[]": [second_id, first_id]},
    )

    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Lesson, second_id).sequence_order == 1
        assert db.session.get(Lesson, first_id).sequence_order == 2


def test_teacher_cannot_add_question_to_other_teachers_quiz(client, app, teacher_user):
    with app.app_context():
        other_teacher = User(email="other_teacher@e16.edu.vn", password_hash="hash", role="teacher")
        db.session.add(other_teacher)
        db.session.flush()
        course = Course(title="Other Teacher Course", teacher_id=other_teacher.id, status="draft")
        db.session.add(course)
        db.session.flush()
        quiz = Quiz(title="Other Quiz", course_id=course.id)
        db.session.add(quiz)
        db.session.commit()
        quiz_id = quiz.id

    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_user
        sess["_fresh"] = True

    response = client.post(
        f"/teacher/quizzes/{quiz_id}/questions/add",
        data={"text": "1+1?", "choice_text": ["2"], "correct_choices": ["0"]},
    )

    assert response.status_code == 403
    with app.app_context():
        assert db.session.query(Question).filter_by(quiz_id=quiz_id).count() == 0


def test_student_can_render_quiz_with_shuffled_choices(client, app, student_user, teacher_user):
    with app.app_context():
        course = Course(title="Quiz Course", teacher_id=teacher_user, status="published")
        db.session.add(course)
        db.session.flush()
        db.session.add(Enrollment(user_id=student_user, course_id=course.id, status="active"))
        quiz = Quiz(title="Runtime Quiz", course_id=course.id, is_published=True)
        db.session.add(quiz)
        db.session.flush()
        question = Question(quiz_id=quiz.id, text="1+1?")
        db.session.add(question)
        db.session.flush()
        db.session.add_all([
            Choice(question_id=question.id, text="2", is_correct=True),
            Choice(question_id=question.id, text="3", is_correct=False),
        ])
        db.session.commit()
        course_id = course.id
        quiz_id = quiz.id

    with client.session_transaction() as sess:
        sess["_user_id"] = student_user
        sess["_fresh"] = True

    response = client.get(f"/learn/{course_id}/quiz/{quiz_id}")

    assert response.status_code == 200
    assert b"Runtime Quiz" in response.data


def test_teacher_can_export_gradebook(client, app, student_user, teacher_user):
    with app.app_context():
        course = Course(title="Exportable Gradebook", teacher_id=teacher_user, status="published")
        db.session.add(course)
        db.session.flush()
        db.session.add(Enrollment(user_id=student_user, course_id=course.id, status="active"))
        db.session.commit()
        course_id = course.id

    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_user
        sess["_fresh"] = True

    response = client.get(f"/teacher/courses/{course_id}/gradebook/export")

    assert response.status_code == 200
    assert "Exportable Gradebook" not in response.data.decode("utf-8")
    assert "student_test@e16.edu.vn" in response.data.decode("utf-8")


def test_user_course_pairs_are_unique(app, student_user, teacher_user):
    with app.app_context():
        course = Course(title="Unique Course", teacher_id=teacher_user, status="published")
        db.session.add(course)
        db.session.flush()
        db.session.add(Enrollment(user_id=student_user, course_id=course.id))
        db.session.add(Certificate(user_id=student_user, course_id=course.id))
        db.session.commit()

        db.session.add(Enrollment(user_id=student_user, course_id=course.id))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

        db.session.add(Certificate(user_id=student_user, course_id=course.id))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_public_certificate_masks_student_email(client, app, student_user, teacher_user):
    with app.app_context():
        course = Course(title="Privacy Course", teacher_id=teacher_user, status="published")
        db.session.add(course)
        db.session.flush()
        lesson = Lesson(course_id=course.id, title="Intro", sequence_order=1)
        db.session.add(lesson)
        db.session.flush()
        db.session.add(LearningLog(user_id=student_user, lesson_id=lesson.id, action_type="complete"))
        cert = Certificate(user_id=student_user, course_id=course.id)
        db.session.add(cert)
        db.session.commit()
        cert_code = cert.cert_code

    response = client.get(f"/certificates/{cert_code}")

    assert response.status_code == 200
    assert b"st***@e16.edu.vn" in response.data
    assert b"student_test@e16.edu.vn" not in response.data


def test_teacher_delete_course_soft_deletes_and_hides_from_catalog(client, app, student_user, teacher_user):
    with app.app_context():
        course = Course(title="Soft Deleted Course", teacher_id=teacher_user, status="published")
        db.session.add(course)
        db.session.commit()
        course_id = course.id

    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_user
        sess["_fresh"] = True

    delete_response = client.post(f"/teacher/courses/{course_id}/delete")

    assert delete_response.status_code == 302
    with app.app_context():
        deleted = db.session.get(Course, course_id)
        assert deleted is not None
        assert deleted.is_deleted is True
        assert deleted.status == "archived"

    with client.session_transaction() as sess:
        sess["_user_id"] = student_user
        sess["_fresh"] = True

    catalog_response = client.get("/courses")

    assert catalog_response.status_code == 200
    assert b"Soft Deleted Course" not in catalog_response.data


def test_assignment_submissions_are_paginated(client, app, student_user, teacher_user):
    with app.app_context():
        course = Course(title="Paged Submissions", teacher_id=teacher_user, status="published")
        db.session.add(course)
        db.session.flush()
        assignment = Assignment(course_id=course.id, title="Paged", description="Paged")
        db.session.add(assignment)
        db.session.flush()
        for idx in range(25):
            student = User(email=f"submitter{idx}@e16.edu.vn", password_hash="hash", role="student")
            db.session.add(student)
            db.session.flush()
            db.session.add(Submission(assignment_id=assignment.id, user_id=student.id, text_content=f"Answer {idx}"))
        db.session.commit()
        assignment_id = assignment.id

    with client.session_transaction() as sess:
        sess["_user_id"] = teacher_user
        sess["_fresh"] = True

    response = client.get(f"/teacher/assignments/{assignment_id}/submissions?page=2&per_page=10")

    assert response.status_code == 200
    assert "Trang 2/3".encode("utf-8") in response.data
