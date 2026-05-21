# -*- coding: utf-8 -*-
"""
Course lifecycle state-machine service.

Handles validated transitions, auto-transitions by date,
and auto-certificate issuance when a course closes.
"""
from flask import url_for

from ..extensions import db
from ..models import (
    COURSE_TRANSITIONS, Course, Certificate, Enrollment, User,
)
from ..services.audit import log_action
from ..services.notifications import notify
from ..time_utils import utcnow


class InvalidTransitionError(Exception):
    """Raised when a course status transition is not allowed."""


def transition_course(course_id: str, new_status: str, actor_id: str,
                      note: str | None = None) -> Course:
    """
    Validate and execute a course status transition.

    Raises InvalidTransitionError if the transition is not allowed.
    """
    course = db.session.get(Course, course_id)
    if not course:
        raise ValueError(f"Course {course_id} not found")

    allowed = COURSE_TRANSITIONS.get(course.status, [])
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot transition from '{course.status}' to '{new_status}'. "
            f"Allowed: {allowed}"
        )

    old_status = course.status
    course.status = new_status

    # Set metadata based on transition type
    now = utcnow()

    if new_status == "approved":
        course.reviewed_by = actor_id
        course.reviewed_at = now
        course.review_note = note

    elif new_status == "rejected":
        course.reviewed_by = actor_id
        course.reviewed_at = now
        course.review_note = note
        course.rejection_note = note  # backward compat

    elif new_status == "published":
        course.published_at = now

    elif new_status == "closed":
        # Auto-issue certificates for students at 100% completion
        issue_certificates_on_close(course_id)

    db.session.commit()

    log_action(
        "course_status_changed", "Course", course_id,
        {"old": old_status, "new": new_status, "actor": actor_id, "note": note},
    )

    # Notify teacher about status changes triggered by reviewer
    if new_status in ("approved", "rejected", "suspended"):
        _notify_teacher(course, new_status, note)

    return course


def _notify_teacher(course: Course, new_status: str, note: str | None):
    """Send notification to course teacher about status change."""
    messages = {
        "approved": f"Khóa học '{course.title}' đã được duyệt!",
        "rejected": f"Khóa học '{course.title}' bị từ chối. Lý do: {note or '—'}",
        "suspended": f"Khóa học '{course.title}' đã bị tạm đình chỉ. Lý do: {note or '—'}",
    }
    msg = messages.get(new_status)
    if msg:
        notify(course.teacher_id, "announcement", msg,
               url_for("teacher.manage_courses"))


def auto_transition_courses():
    """
    Cron-callable function: check dates and auto-transition courses.

    - published → running   when starts_at <= now
    - running   → closed    when ends_at   <= now
    """
    now = utcnow()
    changed = 0

    # published → running
    courses_to_start = db.session.query(Course).filter(
        Course.status == "published",
        Course.starts_at.isnot(None),
        Course.starts_at <= now,
        Course.is_deleted == False,
    ).all()
    for c in courses_to_start:
        try:
            transition_course(c.id, "running", "system", "Tự động khai giảng theo lịch")
            changed += 1
        except InvalidTransitionError:
            pass

    # running → closed
    courses_to_close = db.session.query(Course).filter(
        Course.status == "running",
        Course.ends_at.isnot(None),
        Course.ends_at <= now,
        Course.is_deleted == False,
    ).all()
    for c in courses_to_close:
        try:
            transition_course(c.id, "closed", "system", "Tự động kết thúc theo lịch")
            changed += 1
        except InvalidTransitionError:
            pass

    return changed


def issue_certificates_on_close(course_id: str):
    """
    When a course moves to 'closed', auto-issue certificates
    for all students who have completed 100% of lessons.
    """
    from ..services.course import student_completion_rate

    enrollments = db.session.query(Enrollment).filter_by(
        course_id=course_id, status="active"
    ).all()

    course = db.session.get(Course, course_id)
    course_title = course.title if course else f"ID {course_id}"
    issued = 0

    for en in enrollments:
        rate = student_completion_rate(en.user_id, course_id)
        if rate >= 100:
            en.status = "completed"
            existing = db.session.query(Certificate).filter_by(
                user_id=en.user_id, course_id=course_id
            ).first()
            if not existing:
                cert = Certificate(user_id=en.user_id, course_id=course_id)
                db.session.add(cert)
                notify(
                    en.user_id, "announcement",
                    f"Chúc mừng! Bạn đã nhận được chứng chỉ hoàn thành khóa học {course_title}",
                    url_for("student.view_certificates"),
                )
                issued += 1

    if issued:
        db.session.flush()

    return issued
