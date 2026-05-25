# -*- coding: utf-8 -*-
from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import current_user
from sqlalchemy import func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import Notification, Announcement, ForumThread, ForumReply, Course, Enrollment, User
from ..pagination import get_pagination, paginate_query
from ..services.audit import log_action
from ..services.notifications import notify

bp = Blueprint("communication", __name__)


def _can_access_course(course):
    if not course or not current_user.is_authenticated:
        return False
    if course.is_deleted:
        return False
    if current_user.role == "admin":
        return True
    if current_user.role == "teacher" and course.teacher_id == current_user.id:
        return True
    enrollment = db.session.query(Enrollment).filter_by(user_id=current_user.id, course_id=course.id).first()
    return enrollment is not None and enrollment.status in ("active", "completed")

# --- Notifications ---

@bp.route("/notifications")
@login_required
def list_notifications():
    page, per_page = get_pagination(default_per_page=20, max_per_page=100)
    query = db.session.query(Notification).filter_by(user_id=current_user.id).order_by(Notification.created_at.desc())
    pagination = paginate_query(query, page, per_page)
    return render_template("notifications.html", notifications=pagination["items"], pagination=pagination)

@bp.get("/notifications/unread-count")
@login_required
def unread_count():
    count = db.session.query(func.count(Notification.id)).filter_by(
        user_id=current_user.id,
        is_read=False,
    ).scalar() or 0
    return jsonify({"count": int(count)})

@bp.post("/notifications/<notif_id>/read")
@login_required
def mark_read(notif_id):
    notif = db.session.get(Notification, notif_id)
    if notif and notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    return redirect(request.referrer or url_for("communication.list_notifications"))

@bp.post("/notifications/read-all")
@login_required
def read_all():
    db.session.query(Notification).filter_by(user_id=current_user.id).update({Notification.is_read: True})
    db.session.commit()
    return redirect(url_for("communication.list_notifications"))

# --- Announcements ---

@bp.route("/courses/<course_id>/announcements")
@login_required
def list_announcements(course_id):
    course = db.session.get(Course, course_id)
    if not _can_access_course(course):
        flash("Bạn không có quyền xem thông báo của khóa học này.", "error")
        return redirect(url_for("auth.home"))
    announcements = db.session.query(Announcement).filter_by(course_id=course_id).order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).all()
    return render_template("announcements.html", course=course, announcements=announcements)

@bp.post("/teacher/courses/<course_id>/announcements/new")
@login_required
@role_required("teacher")
def create_announcement(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
        
    title = request.form.get("title")
    body = request.form.get("body")
    is_pinned = 'is_pinned' in request.form
    
    announcement = Announcement(
        course_id=course_id,
        author_id=current_user.id,
        title=title,
        body=body,
        is_pinned=is_pinned
    )
    db.session.add(announcement)
    db.session.commit()
    
    # Notify all enrolled students
    students = db.session.query(Enrollment).filter_by(course_id=course_id).all()
    for en in students:
        notify(
            user_id=en.user_id,
            type="announcement",
            message=f"Thông báo mới từ giảng viên trong khóa học {course.title}: {title}",
            link=url_for("communication.list_announcements", course_id=course_id)
        )
        
    flash("Đã đăng thông báo mới!", "success")
    return redirect(url_for("communication.list_announcements", course_id=course_id))

# --- Forum ---

@bp.route("/courses/<course_id>/forum")
@login_required
def course_forum(course_id):
    course = db.session.get(Course, course_id)
    if not _can_access_course(course):
        flash("Bạn cần đăng ký khóa học để tham gia diễn đàn.", "warning")
        return redirect(url_for("student.list_courses"))
        
    threads = db.session.query(ForumThread, User).join(User, User.id == ForumThread.author_id).filter(
        ForumThread.course_id == course_id,
        ForumThread.is_hidden == False,
    ).order_by(ForumThread.is_pinned.desc(), ForumThread.created_at.desc()).all()
    return render_template("forum.html", course=course, threads=threads)

@bp.post("/courses/<course_id>/forum/new")
@login_required
def create_thread(course_id):
    course = db.session.get(Course, course_id)
    if not _can_access_course(course):
        flash("Bạn không có quyền đăng chủ đề trong khóa học này.", "error")
        return redirect(url_for("student.list_courses"))

    title = request.form.get("title")
    body = request.form.get("body")
    
    thread = ForumThread(
        course_id=course_id,
        author_id=current_user.id,
        title=title,
        body=body
    )
    db.session.add(thread)
    db.session.commit()
    flash("Đã đăng chủ đề mới!", "success")
    return redirect(url_for("communication.course_forum", course_id=course_id))

@bp.route("/courses/<course_id>/forum/<thread_id>")
@login_required
def view_thread(course_id, thread_id):
    course = db.session.get(Course, course_id)
    if not _can_access_course(course):
        flash("Bạn không có quyền xem chủ đề này.", "error")
        return redirect(url_for("student.list_courses"))
    thread = db.session.query(ForumThread, User).join(User, User.id == ForumThread.author_id).filter(ForumThread.id == thread_id).first()
    if not thread or thread[0].course_id != course_id or thread[0].is_hidden:
        return redirect(url_for("communication.course_forum", course_id=course_id))
    replies = db.session.query(ForumReply, User).join(User, User.id == ForumReply.author_id).filter(
        ForumReply.thread_id == thread_id,
        ForumReply.is_hidden == False,
    ).order_by(ForumReply.created_at.asc()).all()
    return render_template("forum_thread.html", course=course, thread=thread, replies=replies)

@bp.post("/courses/<course_id>/forum/<thread_id>/reply")
@login_required
def create_reply(course_id, thread_id):
    course = db.session.get(Course, course_id)
    if not _can_access_course(course):
        flash("Bạn không có quyền phản hồi chủ đề này.", "error")
        return redirect(url_for("student.list_courses"))

    body = request.form.get("body")
    thread = db.session.get(ForumThread, thread_id)
    if not thread or thread.course_id != course_id or thread.is_hidden:
        return redirect(url_for("communication.course_forum", course_id=course_id))
    
    reply = ForumReply(
        thread_id=thread_id,
        author_id=current_user.id,
        body=body
    )
    db.session.add(reply)
    db.session.commit()
    
    # Notify thread author if someone else replies
    if thread.author_id != current_user.id:
        notify(
            user_id=thread.author_id,
            type="forum_reply",
            message=f"Có phản hồi mới trong chủ đề '{thread.title}' của bạn.",
            link=url_for("communication.view_thread", course_id=course_id, thread_id=thread_id)
        )
        
    return redirect(url_for("communication.view_thread", course_id=course_id, thread_id=thread_id))

@bp.post("/teacher/forum/<thread_id>/pin")
@login_required
@role_required("teacher")
def pin_thread(thread_id):
    thread = db.session.get(ForumThread, thread_id)
    if not thread:
        return redirect(url_for("teacher.manage_courses"))
    course = db.session.get(Course, thread.course_id)
    if course and course.teacher_id == current_user.id:
        thread.is_pinned = not thread.is_pinned
        db.session.commit()
        return redirect(url_for("communication.course_forum", course_id=course.id))
    return "Unauthorized", 403


@bp.post("/courses/<course_id>/forum/<thread_id>/hide")
@login_required
@role_required("teacher", "admin")
def hide_thread(course_id, thread_id):
    course = db.session.get(Course, course_id)
    thread = db.session.get(ForumThread, thread_id)
    if not thread or thread.course_id != course_id:
        return redirect(url_for("communication.course_forum", course_id=course_id))
    if current_user.role != "admin" and (not course or course.teacher_id != current_user.id):
        return "Unauthorized", 403

    thread.is_hidden = True
    db.session.commit()
    log_action("forum_thread_hidden", "ForumThread", thread.id, {"course_id": course_id})
    flash("Đã ẩn chủ đề.", "success")
    return redirect(url_for("communication.course_forum", course_id=course_id))


@bp.post("/courses/<course_id>/forum/replies/<reply_id>/hide")
@login_required
@role_required("teacher", "admin")
def hide_reply(course_id, reply_id):
    course = db.session.get(Course, course_id)
    reply = db.session.get(ForumReply, reply_id)
    thread = db.session.get(ForumThread, reply.thread_id) if reply else None
    if not reply or not thread or thread.course_id != course_id:
        return redirect(url_for("communication.course_forum", course_id=course_id))
    if current_user.role != "admin" and (not course or course.teacher_id != current_user.id):
        return "Unauthorized", 403

    reply.is_hidden = True
    db.session.commit()
    log_action("forum_reply_hidden", "ForumReply", reply.id, {"course_id": course_id, "thread_id": thread.id})
    flash("Đã ẩn phản hồi.", "success")
    return redirect(url_for("communication.view_thread", course_id=course_id, thread_id=thread.id))


@bp.post("/courses/<course_id>/forum/<thread_id>/report")
@login_required
def report_thread(course_id, thread_id):
    course = db.session.get(Course, course_id)
    if not _can_access_course(course):
        flash("Bạn không có quyền báo cáo trong khóa học này.", "error")
        return redirect(url_for("student.list_courses"))

    thread = db.session.get(ForumThread, thread_id)
    if not thread or thread.course_id != course_id or thread.is_hidden:
        return redirect(url_for("communication.course_forum", course_id=course_id))

    reason = request.form.get("reason", "Spam / Toxic")
    detail = request.form.get("detail", "")

    from ..models import ContentReport
    report = ContentReport(
        reporter_id=current_user.id,
        target_type="thread",
        target_id=thread_id,
        reason=reason,
        detail=detail
    )
    db.session.add(report)
    db.session.commit()
    
    log_action("forum_thread_reported", "ForumThread", thread_id, {"reason": reason})
    flash("Cảm ơn bạn. Báo cáo của bạn đã được gửi tới ban quản trị.", "success")
    return redirect(url_for("communication.view_thread", course_id=course_id, thread_id=thread_id))


@bp.post("/courses/<course_id>/forum/replies/<reply_id>/report")
@login_required
def report_reply(course_id, reply_id):
    course = db.session.get(Course, course_id)
    if not _can_access_course(course):
        flash("Bạn không có quyền báo cáo trong khóa học này.", "error")
        return redirect(url_for("student.list_courses"))

    reply = db.session.get(ForumReply, reply_id)
    thread = db.session.get(ForumThread, reply.thread_id) if reply else None
    if not reply or not thread or thread.course_id != course_id or reply.is_hidden:
        return redirect(url_for("communication.course_forum", course_id=course_id))

    reason = request.form.get("reason", "Spam / Toxic")
    detail = request.form.get("detail", "")

    from ..models import ContentReport
    report = ContentReport(
        reporter_id=current_user.id,
        target_type="reply",
        target_id=reply_id,
        reason=reason,
        detail=detail
    )
    db.session.add(report)
    db.session.commit()
    
    log_action("forum_reply_reported", "ForumReply", reply_id, {"reason": reason})
    flash("Cảm ơn bạn. Báo cáo của bạn đã được gửi tới ban quản trị.", "success")
    return redirect(url_for("communication.view_thread", course_id=course_id, thread_id=thread.id))
