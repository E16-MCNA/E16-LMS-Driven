import csv
from io import StringIO

from flask import Blueprint, Response, g, render_template
from sqlalchemy import func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import Course, LearningLog, Lesson, User
from ..services import completion_rate_for_course

bp = Blueprint("analytics", __name__, url_prefix="/analytics")


@bp.route("")
@login_required
@role_required("admin")
def dashboard():
    course_stats = []
    courses = db.session.query(Course).order_by(Course.created_at.desc()).all()
    for course in courses:
        lessons = db.session.query(Lesson).filter(Lesson.course_id == course.id).order_by(Lesson.sequence_order.asc()).all()
        funnel_labels = []
        funnel_values = []
        for lesson in lessons:
            users_completed = (
                db.session.query(func.count(func.distinct(LearningLog.user_id)))
                .filter(LearningLog.lesson_id == lesson.id, LearningLog.action_type == "complete")
                .scalar()
                or 0
            )
            funnel_labels.append(lesson.title)
            funnel_values.append(users_completed)
        course_stats.append(
            {
                "course": course,
                "completion_rate": completion_rate_for_course(course.id),
                "funnel_labels": funnel_labels,
                "funnel_values": funnel_values,
            }
        )
    return render_template("analytics.html", course_stats=course_stats, user=g.user)


@bp.get("/export.csv")
@login_required
@role_required("admin")
def export_csv():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_email", "course_title", "lesson_title", "action_type", "timestamp"])
    rows = (
        db.session.query(User.email, Course.title, Lesson.title, LearningLog.action_type, LearningLog.timestamp)
        .join(LearningLog, LearningLog.user_id == User.id)
        .join(Lesson, Lesson.id == LearningLog.lesson_id)
        .join(Course, Course.id == Lesson.course_id)
        .order_by(LearningLog.timestamp.desc())
        .all()
    )
    for row in rows:
        writer.writerow([row[0], row[1], row[2], row[3], row[4].isoformat()])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=learning_logs_export.csv"},
    )
