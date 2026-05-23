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

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import (
    VALID_ROLES, Course, Enrollment, User,
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
    pending_courses = db.session.query(Course).filter(
        Course.status == "pending_review",
        Course.is_deleted == False,
    ).count()
    active_courses = db.session.query(Course).filter(
        Course.status.in_(["published", "running"]),
        Course.is_deleted == False,
    ).count()

    return render_template(
        "hocvu_dashboard.html",
        pending_courses=pending_courses,
        active_courses=active_courses,
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
