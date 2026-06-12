# -*- coding: utf-8 -*-
"""
Blueprint for Học vụ (Academic Affairs) role.

Provides: account creation (single + CSV), course approval,
and dashboard overview.  Accessible by `hoc_vu` and `admin` roles.
"""
import csv
import io
import os
import random
import string

from flask import (
    Blueprint, current_app, flash, redirect,
    render_template, request, url_for,
)
from flask_login import current_user
from werkzeug.security import generate_password_hash
from sqlalchemy import case, func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import (
    VALID_ROLES, Course, CourseClass, Enrollment, User,
)
from ..pagination import get_pagination, paginate_query
from ..services.audit import log_action
from ..time_utils import utcnow
from ..urls import app_url_for

bp = Blueprint("hoc_vu", __name__, url_prefix="/hoc-vu")

# Roles that Học vụ is allowed to create (cannot create admin or hoc_vu)
CREATABLE_ROLES = {"student", "teacher", "le_tan", "ke_toan"}


def _gen_temp_password(length: int = 10) -> str:
    """Generate a random temporary password."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def _send_welcome_email(email: str, temp_password: str, role: str):
    """Try to send a welcome email.  Silently falls back to logger."""
    try:
        if current_app.config.get("MAIL_USERNAME"):
            from ..services.mail import send_email
            send_email(
                to=email,
                subject="E16 LMS — Tài khoản mới",
                template_name="welcome_account",
                email=email,
                temp_password=temp_password,
                role=role,
                login_url=app_url_for("auth.login"),
                site_name=current_app.config.get("SITE_NAME", "E16 LMS"),
            )
        else:
            if current_app.debug:
                current_app.logger.debug(
                    f"Welcome email for {email}: temp_password={temp_password}"
                )
    except Exception as e:
        current_app.logger.error(f"Failed to send welcome email to {email}: {e}")


# ── Dashboard ────────────────────────────────────────────

@bp.route("/dashboard")
@login_required
@role_required("hoc_vu", "admin")
def dashboard():
    course_stats = db.session.query(
        func.sum(case((Course.status == "pending_review", 1), else_=0)),
        func.sum(case((Course.status.in_(["published", "running"]), 1), else_=0)),
    ).filter(Course.is_deleted == False).one()
    user_stats = db.session.query(
        func.sum(case((User.role == "student", 1), else_=0)),
        func.sum(case((User.role == "teacher", 1), else_=0)),
    ).one()
    total_enrollments = db.session.query(func.count(Enrollment.id)).filter(
        Enrollment.status.in_(["active", "completed", "pending_payment"])
    ).scalar() or 0
    recent_pending = (
        db.session.query(Course, User)
        .join(User, User.id == Course.teacher_id)
        .filter(Course.status == "pending_review", Course.is_deleted == False)
        .order_by(Course.submitted_at.desc().nullslast(), Course.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "hocvu_dashboard.html",
        pending_courses=course_stats[0] or 0,
        active_courses=course_stats[1] or 0,
        total_students=user_stats[0] or 0,
        total_teachers=user_stats[1] or 0,
        total_enrollments=total_enrollments,
        recent_pending=recent_pending,
    )




# ── Course approval ──────────────────────────────────────

@bp.route("/courses/pending")
@login_required
@role_required("hoc_vu", "admin")
def pending_courses():
    courses = (
        db.session.query(Course, User)
        .join(User, User.id == Course.teacher_id)
        .filter(
            Course.status == "pending_review",
            Course.is_deleted == False,
        )
        .all()
    )
    return render_template("hocvu_pending_courses.html", courses=courses)


@bp.route("/class-placement")
@login_required
@role_required("hoc_vu", "admin")
def class_placement():
    pending_enrollments = (
        db.session.query(Enrollment, User, Course)
        .join(User, User.id == Enrollment.user_id)
        .join(Course, Course.id == Enrollment.course_id)
        .filter(
            Enrollment.status.in_(["active", "completed"]),
            Enrollment.class_id == None,
            Course.is_deleted == False,
        )
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    classes = (
        db.session.query(CourseClass, Course)
        .join(Course, Course.id == CourseClass.course_id)
        .filter(Course.is_deleted == False)
        .order_by(Course.title.asc(), CourseClass.name.asc())
        .all()
    )
    courses = (
        db.session.query(Course)
        .filter(Course.status.in_(["published", "running"]), Course.is_deleted == False)
        .order_by(Course.title.asc())
        .all()
    )
    teachers = db.session.query(User).filter(User.role == "teacher").order_by(User.email.asc()).all()
    classes_by_course = {}
    for course_class, course in classes:
        classes_by_course.setdefault(course.id, []).append(course_class)
    return render_template(
        "hocvu_class_placement.html",
        pending_enrollments=pending_enrollments,
        courses=courses,
        teachers=teachers,
        classes_by_course=classes_by_course,
    )


@bp.post("/classes/new")
@login_required
@role_required("hoc_vu", "admin")
def create_course_class():
    course_id = request.form.get("course_id")
    course = db.session.get(Course, course_id)
    name = (request.form.get("name") or "").strip()
    if not course or course.is_deleted or not name:
        flash("Thông tin lớp học không hợp lệ.", "error")
        return redirect(url_for("hoc_vu.class_placement"))

    advisor_id = request.form.get("advisor_id") or course.teacher_id
    advisor = db.session.get(User, advisor_id) if advisor_id else None
    course_class = CourseClass(
        course_id=course.id,
        advisor_id=advisor.id if advisor and advisor.role == "teacher" else course.teacher_id,
        name=name,
        status=request.form.get("status") or "active",
    )
    db.session.add(course_class)
    db.session.commit()
    log_action("course_class_created_by_hoc_vu", "CourseClass", course_class.id, {"course_id": course.id, "name": name})
    flash("Đã tạo lớp học.", "success")
    return redirect(url_for("hoc_vu.class_placement"))


@bp.post("/enrollments/<enrollment_id>/assign-class")
@login_required
@role_required("hoc_vu", "admin")
def assign_enrollment_class(enrollment_id):
    enrollment = db.session.get(Enrollment, enrollment_id)
    course_class = db.session.get(CourseClass, request.form.get("class_id"))
    if not enrollment or not course_class or course_class.course_id != enrollment.course_id:
        flash("Không thể xếp lớp cho học viên này.", "error")
        return redirect(url_for("hoc_vu.class_placement"))

    enrollment.class_id = course_class.id
    db.session.commit()
    log_action("enrollment_class_assigned", "Enrollment", enrollment.id, {"class_id": course_class.id})
    flash("Đã xếp học viên vào lớp.", "success")
    return redirect(url_for("hoc_vu.class_placement"))


@bp.route("/courses/<course_id>/review", methods=["POST"])
@login_required
@role_required("hoc_vu", "admin")
def review_course(course_id):
    from ..services.course_lifecycle import transition_course, InvalidTransitionError

    action = request.form.get("action")  # "approve" or "reject"
    note = request.form.get("review_note", "").strip()

    if action == "approve":
        try:
            transition_course(course_id, "approved", current_user.id, note or None)
            transition_course(course_id, "published", current_user.id)
            flash("Đã duyệt khóa học.", "success")
        except InvalidTransitionError as e:
            flash(str(e), "error")

    elif action == "reject":
        if not note:
            flash("Vui lòng nhập lý do từ chối.", "error")
            return redirect(url_for("hoc_vu.pending_courses"))
        try:
            transition_course(course_id, "rejected", current_user.id, note)
            flash("Đã từ chối khóa học.", "info")
        except InvalidTransitionError as e:
            flash(str(e), "error")
    else:
        flash("Hành động không hợp lệ.", "error")

    return redirect(url_for("hoc_vu.pending_courses"))
