from sqlalchemy import func
from ..extensions import db
from ..models import Course, Enrollment, LearningLog, Lesson

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

def update_enrollment_if_completed(user_id: str, course_id: str):
    rate = student_completion_rate(user_id, course_id)
    if rate >= 100:
        enrollment = db.session.query(Enrollment).filter_by(user_id=user_id, course_id=course_id).first()
        if enrollment and enrollment.status != "completed":
            enrollment.status = "completed"
            
            # Issue Certificate
            from ..models import Certificate, Course as CourseModel
            exists = db.session.query(Certificate).filter_by(user_id=user_id, course_id=course_id).first()
            if not exists:
                cert = Certificate(user_id=user_id, course_id=course_id)
                db.session.add(cert)
                from .notifications import notify
                from flask import url_for
                notify(user_id, "announcement", f"Chúc mừng! Bạn đã nhận được chứng chỉ cho khóa học {db.session.get(CourseModel, course_id).title}", url_for("student.view_certificates"))
            
            db.session.commit()

def class_average_completion_rate(course_id: str):
    students = db.session.query(Enrollment.user_id).filter_by(course_id=course_id, status="active").all()
    if not students:
        return 0.0
    total_rate = sum(student_completion_rate(s.user_id, course_id) for s in students)
    return total_rate / len(students)
