from sqlalchemy import func

from .extensions import db
from .models import Course, Enrollment, LearningLog, Lesson


def recalc_total_lessons(course_id: str):
    total = db.session.query(func.count(Lesson.id)).filter(Lesson.course_id == course_id).scalar() or 0
    course = db.session.get(Course, course_id)
    if course:
        course.total_lessons = total
        db.session.commit()


def completion_rate_for_course(course_id: str):
    total = db.session.query(func.count(Enrollment.id)).filter(Enrollment.course_id == course_id).scalar() or 0
    completed = (
        db.session.query(func.count(Enrollment.id))
        .filter(Enrollment.course_id == course_id, Enrollment.status == "completed")
        .scalar()
        or 0
    )
    return (completed / total * 100.0) if total else 0.0


def student_completion_rate(user_id: str, course_id: str):
    total_lessons = db.session.query(func.count(Lesson.id)).filter(Lesson.course_id == course_id).scalar() or 0
    if total_lessons == 0:
        return 0.0
    completed_lessons = (
        db.session.query(func.count(func.distinct(LearningLog.lesson_id)))
        .join(Lesson, Lesson.id == LearningLog.lesson_id)
        .filter(
            LearningLog.user_id == user_id,
            LearningLog.action_type == "complete",
            Lesson.course_id == course_id,
        )
        .scalar()
        or 0
    )
    return completed_lessons / total_lessons * 100.0


def class_average_completion_rate(course_id: str):
    enrollments = db.session.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    if not enrollments:
        return 0.0
    rates = [student_completion_rate(en.user_id, course_id) for en in enrollments]
    return sum(rates) / len(rates) if rates else 0.0


def update_enrollment_if_completed(user_id: str, course_id: str):
    total_lessons = db.session.query(func.count(Lesson.id)).filter(Lesson.course_id == course_id).scalar() or 0
    completed_lessons = (
        db.session.query(func.count(func.distinct(LearningLog.lesson_id)))
        .join(Lesson, Lesson.id == LearningLog.lesson_id)
        .filter(
            Lesson.course_id == course_id,
            LearningLog.user_id == user_id,
            LearningLog.action_type == "complete",
        )
        .scalar()
        or 0
    )
    enrollment = (
        db.session.query(Enrollment).filter(Enrollment.user_id == user_id, Enrollment.course_id == course_id).first()
    )
    if enrollment and total_lessons > 0 and completed_lessons >= total_lessons:
        enrollment.status = "completed"
        db.session.commit()
