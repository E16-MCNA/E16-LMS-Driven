# -*- coding: utf-8 -*-
"""
Certificate and completion rate service for E16 LMS.
Handles calculating course completion progress, updating enrollment statuses,
and issuing secure certificates.
"""
from flask import url_for
from sqlalchemy import func
from ..extensions import db
from ..models import Course, Enrollment, LearningLog, Lesson, Certificate


def get_student_completion_rate(user_id, course_id) -> float:
    """Calculate progress percentage of a student in a course based on completed lessons."""
    total = db.session.query(Lesson).filter_by(course_id=course_id).count()
    if total == 0:
        return 0.0
    completed = db.session.query(func.distinct(LearningLog.lesson_id)).join(Lesson).filter(
        LearningLog.user_id == user_id, 
        Lesson.course_id == course_id, 
        LearningLog.action_type == "complete"
    ).count()
    return (completed / total) * 100.0


def get_class_average_completion_rate(course_id) -> float:
    """Calculate the average completion progress of all active students in a course."""
    students = db.session.query(Enrollment.user_id).filter_by(course_id=course_id, status="active").all()
    if not students:
        return 0.0
    total_rate = sum(get_student_completion_rate(s.user_id, course_id) for s in students)
    return total_rate / len(students)


def check_and_issue_certificate(user_id, course_id) -> bool:
    """Check if the student has reached 100% completion rate. If so, updates enrollment and issues certificate."""
    rate = get_student_completion_rate(user_id, course_id)
    if rate >= 100:
        en = db.session.query(Enrollment).filter_by(user_id=user_id, course_id=course_id).first()
        if en and en.status != "completed":
            en.status = "completed"
            
            # Issue Certificate
            exists = db.session.query(Certificate).filter_by(user_id=user_id, course_id=course_id).first()
            if not exists:
                cert = Certificate(user_id=user_id, course_id=course_id)
                db.session.add(cert)
                db.session.flush()  # Trigger column defaults (like cert_code generator)
                
                # Notify student
                from ..services.notifications import notify
                course = db.session.get(Course, course_id)
                course_title = course.title if course else f"ID {course_id}"
                notify(
                    user_id, 
                    "announcement", 
                    f"Chúc mừng! Bạn đã nhận được chứng chỉ hoàn thành khóa học {course_title}", 
                    url_for("student.view_certificates")
                )
                
            db.session.commit()
            return True
    return False
