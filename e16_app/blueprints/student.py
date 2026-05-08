from datetime import datetime

from flask import Blueprint, g, redirect, render_template, request, url_for
from sqlalchemy import func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import Course, Enrollment, LearningLog, Lesson
from ..services import class_average_completion_rate, student_completion_rate, update_enrollment_if_completed

bp = Blueprint("student", __name__)


@bp.route("/dashboard")
@login_required
@role_required("student")
def dashboard():
    enrollments = db.session.query(Enrollment).filter(Enrollment.user_id == g.user.id).all()
    rows = []
    for en in enrollments:
        course = db.session.get(Course, en.course_id)
        if not course:
            continue
        rows.append(
            {
                "course": course,
                "enrollment": en,
                "my_rate": student_completion_rate(g.user.id, course.id),
                "avg_rate": class_average_completion_rate(course.id),
            }
        )
    enrolled_course_ids = {row["course"].id for row in rows}
    available_courses = db.session.query(Course).order_by(Course.created_at.desc()).all()
    return render_template(
        "student_dashboard.html",
        rows=rows,
        user=g.user,
        available_courses=available_courses,
        enrolled_course_ids=enrolled_course_ids,
    )


@bp.post("/enroll/<course_id>")
@login_required
@role_required("student")
def enroll(course_id):
    exists = db.session.query(Enrollment).filter(Enrollment.user_id == g.user.id, Enrollment.course_id == course_id).first()
    if not exists:
        db.session.add(Enrollment(user_id=g.user.id, course_id=course_id, status="in_progress"))
        db.session.commit()
    return redirect(url_for("student.dashboard"))


@bp.route("/learn/<course_id>")
@login_required
@role_required("student")
def learn(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return redirect(url_for("student.dashboard"))
    enrollment = db.session.query(Enrollment).filter(Enrollment.user_id == g.user.id, Enrollment.course_id == course_id).first()
    if not enrollment:
        db.session.add(Enrollment(user_id=g.user.id, course_id=course_id, status="in_progress"))
        db.session.commit()
    lessons = db.session.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.sequence_order.asc()).all()
    if not lessons:
        return redirect(url_for("student.dashboard"))

    selected_id = request.args.get("lesson") or lessons[0].id
    selected_lesson = next((ls for ls in lessons if ls.id == selected_id), lessons[0])
    db.session.add(LearningLog(user_id=g.user.id, lesson_id=selected_lesson.id, action_type="start", timestamp=datetime.utcnow()))
    db.session.commit()

    completed_ids = {
        row[0]
        for row in db.session.query(func.distinct(LearningLog.lesson_id))
        .join(Lesson, Lesson.id == LearningLog.lesson_id)
        .filter(LearningLog.user_id == g.user.id, Lesson.course_id == course_id, LearningLog.action_type == "complete")
        .all()
    }
    return render_template(
        "learning_page.html",
        course=course,
        lessons=lessons,
        selected_lesson=selected_lesson,
        completed_ids=completed_ids,
        user=g.user,
    )


@bp.post("/learn/<course_id>/complete/<lesson_id>")
@login_required
@role_required("student")
def mark_complete(course_id, lesson_id):
    db.session.add(LearningLog(user_id=g.user.id, lesson_id=lesson_id, action_type="complete", timestamp=datetime.utcnow()))
    db.session.commit()
    update_enrollment_if_completed(g.user.id, course_id)
    return redirect(url_for("student.learn", course_id=course_id, lesson=lesson_id))
