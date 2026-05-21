# -*- coding: utf-8 -*-
import pytest
from e16_app import create_app, db
from e16_app.models import User, Quiz, Question, Choice, Assignment, Submission
from e16_app.services import GradingService

def test_quiz_grading(app):
    """Verify that GradingService calculates scores correctly."""
    with app.app_context():
        # Setup dummy data
        u = User(email="s@e16.edu.vn", role="student", password_hash="dummy")
        db.session.add(u)
        db.session.flush()
        
        from e16_app.models import Course
        c = Course(title="Dummy Course", teacher_id=u.id)
        db.session.add(c)
        db.session.flush()
        
        q = Quiz(title="Test Quiz", course_id=c.id, is_published=True)
        db.session.add(q)
        db.session.flush()
        
        qn = Question(quiz_id=q.id, text="1+1=?")
        db.session.add(qn)
        db.session.flush()
        
        c1 = Choice(question_id=qn.id, text="2", is_correct=True)
        c2 = Choice(question_id=qn.id, text="3", is_correct=False)
        db.session.add_all([c1, c2])
        db.session.commit()
        
        # Test Correct Answer
        attempt = GradingService.grade_quiz_attempt(u.id, q.id, {f"question_{qn.id}": str(c1.id)})
        assert attempt.score == 100
        assert attempt.passed is True
        
        # Test Wrong Answer
        attempt2 = GradingService.grade_quiz_attempt(u.id, q.id, {f"question_{qn.id}": str(c2.id)})
        assert attempt2.score == 0
        assert attempt2.passed is False

def test_quiz_grading_ignores_served_questions_from_other_quizzes(app):
    with app.app_context():
        u = User(email="served@e16.edu.vn", role="student", password_hash="dummy")
        teacher = User(email="teacher@e16.edu.vn", role="teacher", password_hash="dummy")
        db.session.add_all([u, teacher])
        db.session.flush()

        from e16_app.models import Course
        c = Course(title="Course", teacher_id=teacher.id)
        db.session.add(c)
        db.session.flush()

        quiz = Quiz(title="Real Quiz", course_id=c.id, is_published=True)
        other_quiz = Quiz(title="Other Quiz", course_id=c.id, is_published=True)
        db.session.add_all([quiz, other_quiz])
        db.session.flush()

        other_question = Question(quiz_id=other_quiz.id, text="Other?")
        db.session.add(other_question)
        db.session.flush()
        other_choice = Choice(question_id=other_question.id, text="Correct", is_correct=True)
        db.session.add(other_choice)
        db.session.commit()

        attempt = GradingService.grade_quiz_attempt(
            u.id,
            quiz.id,
            {f"question_{other_question.id}": str(other_choice.id)},
            served_q_ids=[other_question.id],
        )

        assert attempt.score == 0
        assert attempt.passed is False

def test_assignment_grading_clamps_score_and_sets_status(app):
    with app.app_context():
        teacher = User(email="grader@e16.edu.vn", role="teacher", password_hash="dummy")
        student = User(email="submitter@e16.edu.vn", role="student", password_hash="dummy")
        db.session.add_all([teacher, student])
        db.session.flush()

        from e16_app.models import Course
        course = Course(title="Assignments", teacher_id=teacher.id)
        db.session.add(course)
        db.session.flush()
        assignment = Assignment(course_id=course.id, title="Essay", description="Write")
        db.session.add(assignment)
        db.session.flush()
        submission = Submission(assignment_id=assignment.id, user_id=student.id, status="pending")
        db.session.add(submission)
        db.session.commit()

        assert GradingService.grade_assignment_submission(submission.id, 130, "Good", teacher.id) is True

        graded = db.session.get(Submission, submission.id)
        assert graded.score == 100
        assert graded.status == "graded"
        assert graded.graded_by == teacher.id
