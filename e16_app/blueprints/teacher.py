# -*- coding: utf-8 -*-
import csv
import io
import os
from flask import Blueprint, flash, redirect, render_template, request, url_for, make_response, jsonify, abort
from flask_login import current_user
from sqlalchemy import case, func, or_

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import (
    AttendanceRecord,
    ClassSession,
    ClassSessionLesson,
    Course,
    CourseClass,
    Enrollment,
    Lesson,
    Quiz,
    Question,
    Choice,
    Assignment,
    Submission,
    User,
    QuizAttempt,
)
from ..pagination import get_pagination, paginate_query
from ..services.audit import log_action
from ..services.course import recalc_total_lessons
from ..time_utils import parse_datetime_utc, utcnow

bp = Blueprint("teacher", __name__, url_prefix="/teacher")


def _export_max_rows() -> int:
    return max(1, int(os.getenv("EXPORT_MAX_ROWS", "50000")))


def _safe_int(val, default=0):
    try:
        return int(val) if val is not None and str(val).strip() != "" else default
    except (ValueError, TypeError):
        return default


def _teacher_course_or_redirect(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return None
    return course


def _teacher_class_or_redirect(course_id, class_id):
    course = _teacher_course_or_redirect(course_id)
    if not course:
        return None, None
    course_class = db.session.get(CourseClass, class_id)
    if not course_class or course_class.course_id != course.id:
        return course, None
    return course, course_class


def _teacher_session_or_redirect(course_id, class_id, session_id):
    course, course_class = _teacher_class_or_redirect(course_id, class_id)
    if not course or not course_class:
        return course, course_class, None
    class_session = db.session.get(ClassSession, session_id)
    if not class_session or class_session.class_id != course_class.id:
        return course, course_class, None
    return course, course_class, class_session


def _advisor_class_or_redirect(class_id):
    result = (
        db.session.query(CourseClass, Course)
        .join(Course, Course.id == CourseClass.course_id)
        .filter(
            CourseClass.id == class_id,
            Course.is_deleted == False,
            or_(CourseClass.advisor_id == current_user.id, Course.teacher_id == current_user.id),
        )
        .first()
    )
    return result if result else (None, None)


@bp.route("/dashboard")
@login_required
@role_required("teacher")
def dashboard():
    courses = db.session.query(Course).filter(Course.teacher_id == current_user.id, Course.is_deleted == False).all()
    total_courses = len(courses)
    
    course_ids = [c.id for c in courses]
    total_students = 0
    total_lessons = 0
    pending_submissions = 0
    recent_submissions = []
    if course_ids:
        total_students = db.session.query(Enrollment).filter(Enrollment.course_id.in_(course_ids), Enrollment.status.in_(["active", "completed"])).count()
        total_lessons = db.session.query(Lesson).filter(Lesson.course_id.in_(course_ids)).count()
        pending_submissions = (
            db.session.query(Submission)
            .join(Assignment, Assignment.id == Submission.assignment_id)
            .filter(Assignment.course_id.in_(course_ids), Submission.status == "pending")
            .count()
        )
        recent_submissions = (
            db.session.query(Submission, Assignment, Course, User)
            .join(Assignment, Assignment.id == Submission.assignment_id)
            .join(Course, Course.id == Assignment.course_id)
            .join(User, User.id == Submission.user_id)
            .filter(Assignment.course_id.in_(course_ids))
            .order_by(Submission.submitted_at.desc())
            .limit(5)
            .all()
        )
        
    pending_review_count = len([c for c in courses if c.status == "pending_review"])
    draft_count = len([c for c in courses if c.status == "draft"])
    advisor_classes_count = (
        db.session.query(CourseClass)
        .join(Course, Course.id == CourseClass.course_id)
        .filter(
            Course.is_deleted == False,
            or_(CourseClass.advisor_id == current_user.id, Course.teacher_id == current_user.id),
        )
        .count()
    )

    return render_template("teacher_dashboard.html", 
                           courses=courses[:5], 
                           total_courses=total_courses, 
                           total_students=total_students,
                           total_lessons=total_lessons,
                           pending_submissions=pending_submissions,
                           recent_submissions=recent_submissions,
                           pending_review_count=pending_review_count,
                           draft_count=draft_count,
                           advisor_classes_count=advisor_classes_count)

@bp.route("/manage")
@login_required
@role_required("teacher")
def manage_courses():
    courses = db.session.query(Course).filter(Course.teacher_id == current_user.id, Course.is_deleted == False).all()
    return render_template("manage_courses.html", courses=courses)


@bp.route("/advisor")
@login_required
@role_required("teacher")
def advisor_dashboard():
    rows = (
        db.session.query(CourseClass, Course)
        .join(Course, Course.id == CourseClass.course_id)
        .filter(
            Course.is_deleted == False,
            or_(CourseClass.advisor_id == current_user.id, Course.teacher_id == current_user.id),
        )
        .order_by(Course.title.asc(), CourseClass.name.asc())
        .all()
    )
    class_ids = [course_class.id for course_class, _course in rows]
    student_counts = {}
    session_counts = {}
    attention_counts = {}
    if class_ids:
        student_counts = {
            class_id: count
            for class_id, count in (
                db.session.query(Enrollment.class_id, func.count(Enrollment.id))
                .filter(Enrollment.class_id.in_(class_ids), Enrollment.status.in_(["active", "completed"]))
                .group_by(Enrollment.class_id)
                .all()
            )
        }
        session_counts = {
            class_id: count
            for class_id, count in (
                db.session.query(ClassSession.class_id, func.count(ClassSession.id))
                .filter(ClassSession.class_id.in_(class_ids))
                .group_by(ClassSession.class_id)
                .all()
            )
        }
        attention_counts = {
            class_id: count
            for class_id, count in (
                db.session.query(ClassSession.class_id, func.count(AttendanceRecord.id))
                .join(AttendanceRecord, AttendanceRecord.session_id == ClassSession.id)
                .filter(ClassSession.class_id.in_(class_ids), AttendanceRecord.status.in_(["absent", "late"]))
                .group_by(ClassSession.class_id)
                .all()
            )
        }

    return render_template(
        "teacher_advisor_dashboard.html",
        rows=rows,
        student_counts=student_counts,
        session_counts=session_counts,
        attention_counts=attention_counts,
    )


@bp.route("/advisor/classes/<class_id>")
@login_required
@role_required("teacher")
def advisor_class_detail(class_id):
    course_class, course = _advisor_class_or_redirect(class_id)
    if not course_class:
        return redirect(url_for("teacher.advisor_dashboard"))

    enrollments = (
        db.session.query(Enrollment, User)
        .join(User, User.id == Enrollment.user_id)
        .filter(Enrollment.class_id == course_class.id, Enrollment.status.in_(["active", "completed"]))
        .order_by(User.email.asc())
        .all()
    )
    sessions = (
        db.session.query(ClassSession)
        .filter(ClassSession.class_id == course_class.id)
        .order_by(ClassSession.starts_at.desc().nullslast(), ClassSession.created_at.desc())
        .all()
    )
    user_ids = [user.id for _enrollment, user in enrollments]
    attendance_summary = {}
    if user_ids:
        attendance_summary = {
            user_id: {"present": present or 0, "late": late or 0, "absent": absent or 0, "excused": excused or 0}
            for user_id, present, late, absent, excused in (
                db.session.query(
                    AttendanceRecord.user_id,
                    func.sum(case((AttendanceRecord.status == "present", 1), else_=0)),
                    func.sum(case((AttendanceRecord.status == "late", 1), else_=0)),
                    func.sum(case((AttendanceRecord.status == "absent", 1), else_=0)),
                    func.sum(case((AttendanceRecord.status == "excused", 1), else_=0)),
                )
                .join(ClassSession, ClassSession.id == AttendanceRecord.session_id)
                .filter(ClassSession.class_id == course_class.id, AttendanceRecord.user_id.in_(user_ids))
                .group_by(AttendanceRecord.user_id)
                .all()
            )
        }

    return render_template(
        "teacher_advisor_class.html",
        course=course,
        course_class=course_class,
        enrollments=enrollments,
        sessions=sessions,
        attendance_summary=attendance_summary,
    )


@bp.route("/courses/<course_id>")
@login_required
@role_required("teacher")
def course_overview(course_id):
    course = _teacher_course_or_redirect(course_id)
    if not course:
        return redirect(url_for("teacher.manage_courses"))

    classes = (
        db.session.query(CourseClass)
        .filter(CourseClass.course_id == course.id)
        .order_by(CourseClass.created_at.desc())
        .all()
    )
    assignments = (
        db.session.query(Assignment)
        .filter(Assignment.course_id == course.id)
        .order_by(Assignment.created_at.desc())
        .all()
    )
    active_students = (
        db.session.query(Enrollment)
        .filter(Enrollment.course_id == course.id, Enrollment.status.in_(["active", "completed"]))
        .count()
    )
    session_counts = {}
    if classes:
        rows = (
            db.session.query(ClassSession.class_id, func.count(ClassSession.id))
            .filter(ClassSession.class_id.in_([c.id for c in classes]))
            .group_by(ClassSession.class_id)
            .all()
        )
        session_counts = {class_id: count for class_id, count in rows}

    return render_template(
        "teacher_course_overview.html",
        course=course,
        classes=classes,
        assignments=assignments,
        active_students=active_students,
        session_counts=session_counts,
    )


@bp.post("/courses/<course_id>/classes/new")
@login_required
@role_required("teacher")
def create_course_class(course_id):
    course = _teacher_course_or_redirect(course_id)
    if not course:
        return redirect(url_for("teacher.manage_courses"))

    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Tên lớp học không được để trống.", "error")
        return redirect(url_for("teacher.course_overview", course_id=course.id))

    course_class = CourseClass(
        course_id=course.id,
        advisor_id=current_user.id,
        name=name,
        status=request.form.get("status") or "active",
    )
    db.session.add(course_class)
    db.session.commit()
    log_action("course_class_created", "CourseClass", course_class.id, {"course_id": course.id, "name": name})
    flash("Đã tạo lớp học.", "success")
    return redirect(url_for("teacher.course_overview", course_id=course.id))


@bp.route("/courses/<course_id>/classes/<class_id>")
@login_required
@role_required("teacher")
def class_detail(course_id, class_id):
    course, course_class = _teacher_class_or_redirect(course_id, class_id)
    if not course:
        return redirect(url_for("teacher.manage_courses"))
    if not course_class:
        return redirect(url_for("teacher.course_overview", course_id=course.id))

    sessions = (
        db.session.query(ClassSession)
        .filter(ClassSession.class_id == course_class.id)
        .order_by(ClassSession.starts_at.asc().nullslast(), ClassSession.created_at.asc())
        .all()
    )
    student_count = (
        db.session.query(Enrollment)
        .filter(Enrollment.course_id == course.id, Enrollment.class_id == course_class.id, Enrollment.status.in_(["active", "completed"]))
        .count()
    )
    return render_template(
        "teacher_class_detail.html",
        course=course,
        course_class=course_class,
        sessions=sessions,
        student_count=student_count,
    )


@bp.post("/courses/<course_id>/classes/<class_id>/sessions/new")
@login_required
@role_required("teacher")
def create_class_session(course_id, class_id):
    course, course_class = _teacher_class_or_redirect(course_id, class_id)
    if not course:
        return redirect(url_for("teacher.manage_courses"))
    if not course_class:
        return redirect(url_for("teacher.course_overview", course_id=course.id))

    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Tên buổi học không được để trống.", "error")
        return redirect(url_for("teacher.class_detail", course_id=course.id, class_id=course_class.id))

    class_session = ClassSession(
        class_id=course_class.id,
        title=title,
        starts_at=parse_datetime_utc(request.form.get("starts_at")),
        status=request.form.get("status") or "scheduled",
        notes=(request.form.get("notes") or "").strip(),
    )
    db.session.add(class_session)
    db.session.commit()
    log_action("class_session_created", "ClassSession", class_session.id, {"class_id": course_class.id, "title": title})
    flash("Đã tạo buổi học.", "success")
    return redirect(url_for("teacher.class_detail", course_id=course.id, class_id=course_class.id))


@bp.route("/courses/<course_id>/classes/<class_id>/sessions/<session_id>")
@login_required
@role_required("teacher")
def class_session_detail(course_id, class_id, session_id):
    course, course_class, class_session = _teacher_session_or_redirect(course_id, class_id, session_id)
    if not course:
        return redirect(url_for("teacher.manage_courses"))
    if not course_class:
        return redirect(url_for("teacher.course_overview", course_id=course.id))
    if not class_session:
        return redirect(url_for("teacher.class_detail", course_id=course.id, class_id=course_class.id))

    lesson_links = (
        db.session.query(ClassSessionLesson)
        .filter(ClassSessionLesson.session_id == class_session.id)
        .order_by(ClassSessionLesson.sequence_order.asc())
        .all()
    )
    linked_lesson_ids = {link.lesson_id for link in lesson_links}
    available_lessons = (
        db.session.query(Lesson)
        .filter(Lesson.course_id == course.id, ~Lesson.id.in_(linked_lesson_ids))
        .order_by(Lesson.sequence_order.asc())
        .all()
        if linked_lesson_ids
        else db.session.query(Lesson).filter(Lesson.course_id == course.id).order_by(Lesson.sequence_order.asc()).all()
    )
    enrollments = (
        db.session.query(Enrollment, User)
        .join(User, User.id == Enrollment.user_id)
        .filter(Enrollment.course_id == course.id, Enrollment.class_id == course_class.id, Enrollment.status.in_(["active", "completed"]))
        .order_by(User.email.asc())
        .all()
    )
    attendance_rows = db.session.query(AttendanceRecord).filter(AttendanceRecord.session_id == class_session.id).all()
    attendance_map = {row.user_id: row for row in attendance_rows}

    return render_template(
        "teacher_class_session.html",
        course=course,
        course_class=course_class,
        class_session=class_session,
        lesson_links=lesson_links,
        available_lessons=available_lessons,
        enrollments=enrollments,
        attendance_map=attendance_map,
    )


@bp.post("/courses/<course_id>/classes/<class_id>/sessions/<session_id>/lessons/add")
@login_required
@role_required("teacher")
def add_session_lesson(course_id, class_id, session_id):
    course, course_class, class_session = _teacher_session_or_redirect(course_id, class_id, session_id)
    if not course or not course_class or not class_session:
        return redirect(url_for("teacher.manage_courses"))

    lesson_id = request.form.get("lesson_id")
    lesson = db.session.get(Lesson, lesson_id)
    if not lesson or lesson.course_id != course.id:
        flash("Bài học không hợp lệ.", "error")
        return redirect(url_for("teacher.class_session_detail", course_id=course.id, class_id=course_class.id, session_id=class_session.id))

    exists = db.session.query(ClassSessionLesson).filter_by(session_id=class_session.id, lesson_id=lesson.id).first()
    if not exists:
        last_link = (
            db.session.query(ClassSessionLesson)
            .filter_by(session_id=class_session.id)
            .order_by(ClassSessionLesson.sequence_order.desc())
            .first()
        )
        next_order = (last_link.sequence_order + 1) if last_link else 1
        db.session.add(ClassSessionLesson(session_id=class_session.id, lesson_id=lesson.id, sequence_order=next_order))
        db.session.commit()
        flash("Đã thêm bài học vào buổi học.", "success")
    return redirect(url_for("teacher.class_session_detail", course_id=course.id, class_id=course_class.id, session_id=class_session.id))


@bp.post("/courses/<course_id>/classes/<class_id>/sessions/<session_id>/attendance")
@login_required
@role_required("teacher")
def update_attendance(course_id, class_id, session_id):
    course, course_class, class_session = _teacher_session_or_redirect(course_id, class_id, session_id)
    if not course or not course_class or not class_session:
        return redirect(url_for("teacher.manage_courses"))

    enrollments = (
        db.session.query(Enrollment)
        .filter(Enrollment.course_id == course.id, Enrollment.class_id == course_class.id, Enrollment.status.in_(["active", "completed"]))
        .all()
    )
    valid_user_ids = {en.user_id for en in enrollments}
    existing = {
        row.user_id: row
        for row in db.session.query(AttendanceRecord).filter(AttendanceRecord.session_id == class_session.id).all()
    }
    allowed_statuses = {"present", "late", "absent", "excused"}
    for user_id in valid_user_ids:
        status = request.form.get(f"attendance_{user_id}", "absent")
        if status not in allowed_statuses:
            status = "absent"
        note = (request.form.get(f"note_{user_id}") or "").strip()
        row = existing.get(user_id)
        if row:
            row.status = status
            row.note = note
            row.marked_at = utcnow()
            row.marked_by = current_user.id
        else:
            db.session.add(
                AttendanceRecord(
                    session_id=class_session.id,
                    user_id=user_id,
                    status=status,
                    note=note,
                    marked_by=current_user.id,
                )
            )
    db.session.commit()
    log_action("attendance_updated", "ClassSession", class_session.id, {"course_id": course.id, "class_id": course_class.id})
    flash("Đã cập nhật điểm danh.", "success")
    return redirect(url_for("teacher.class_session_detail", course_id=course.id, class_id=course_class.id, session_id=class_session.id))


@bp.post("/courses/new")
@login_required
@role_required("teacher")
def create_course():
    title = request.form.get("title")
    if title:
        new_course = Course(title=title, teacher_id=current_user.id, status="draft")
        db.session.add(new_course)
        db.session.commit()
        log_action("course_created", "Course", new_course.id, {"title": title})
        flash("Đã tạo khóa học mới (Bản nháp)!", "success")
    return redirect(url_for("teacher.manage_courses"))





@bp.route("/courses/<course_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def edit_course(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        flash("Không tìm thấy khóa học hoặc bạn không có quyền chỉnh sửa.", "error")
        return redirect(url_for("teacher.manage_courses"))
        
    if request.method == "POST":
        course.title = request.form.get("title")
        course.short_description = request.form.get("short_description")
        course.description = request.form.get("description")
        course.cover_image_url = request.form.get("cover_image_url")
        # Note: status is managed by submit_course or admin approve/reject
        course.category_id = request.form.get("category_id")
        course.tags = request.form.get("tags", "").strip()
        course.level = request.form.get("level", "").strip()
        db.session.commit()
        flash("Đã cập nhật thông tin khóa học.", "success")
        return redirect(url_for("teacher.manage_courses"))
        
    from ..models import Category
    categories = db.session.query(Category).order_by(Category.sort_order.asc()).all()
    return render_template("edit_course.html", course=course, categories=categories)


@bp.route("/courses/<course_id>/submit", methods=["POST"])
@login_required
@role_required("teacher")
def submit_course(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        abort(403)
    
    # Validation: Ensure course has at least one lesson
    from ..models import Lesson
    lesson_count = db.session.query(Lesson).filter_by(course_id=course_id).count()
    if lesson_count == 0:
        flash("Bạn cần thêm ít nhất một bài học trước khi gửi duyệt.", "error")
        return redirect(url_for("teacher.manage_courses"))

    from ..services.course_lifecycle import transition_course, InvalidTransitionError
    try:
        transition_course(course_id, "pending_review", current_user.id)
        flash("Khóa học đã được gửi cho Học vụ duyệt.", "success")
    except InvalidTransitionError as e:
        flash(str(e), "error")
    return redirect(url_for("teacher.manage_courses"))


@bp.route("/courses/<course_id>/delete", methods=["POST"])
@login_required
@role_required("teacher")
def delete_course(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return "Unauthorized", 403
        
    course.is_deleted = True
    course.status = "archived"
    db.session.commit()
    log_action("course_soft_deleted", "Course", course_id, {"title": course.title})
    flash("Đã lưu trữ khóa học.", "info")
    return redirect(url_for("teacher.manage_courses"))


@bp.route("/courses/<course_id>/students")
@login_required
@role_required("teacher")
def course_students(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
        
    enrollments = db.session.query(Enrollment, User).join(User, User.id == Enrollment.user_id).filter(Enrollment.course_id == course_id, Enrollment.status.in_(["active", "completed"])).all()
    
    # Optimized: single GROUP BY query instead of N queries per student
    from ..models import LearningLog, Lesson
    progress_map = {}
    if course.total_lessons > 0:
        completed_counts = db.session.query(
            LearningLog.user_id, func.count(func.distinct(LearningLog.lesson_id))
        ).join(Lesson, Lesson.id == LearningLog.lesson_id).filter(
            LearningLog.action_type == "complete",
            Lesson.course_id == course_id
        ).group_by(LearningLog.user_id).all()
        counts_map = {uid: cnt for uid, cnt in completed_counts}
        for en, u in enrollments:
            progress_map[u.id] = int((counts_map.get(u.id, 0) / course.total_lessons) * 100)
    else:
        for en, u in enrollments:
            progress_map[u.id] = 0
            
    return render_template("course_students.html", course=course, enrollments=enrollments, progress_map=progress_map)


@bp.route("/courses/<course_id>/lessons")
@login_required
@role_required("teacher")
def manage_lessons(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
    lessons = db.session.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.sequence_order.asc()).all()
    return render_template("manage_lessons.html", course=course, lessons=lessons)


@bp.post("/courses/<course_id>/lessons/new")
@login_required
@role_required("teacher")
def create_lesson(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
    
    title = request.form.get("title")
    video_url = request.form.get("video_url")
    document_url = request.form.get("document_url")
    
    # Get last sequence
    last_lesson = db.session.query(Lesson).filter_by(course_id=course_id).order_by(Lesson.sequence_order.desc()).first()
    next_order = (last_lesson.sequence_order + 1) if last_lesson else 1
    
    new_lesson = Lesson(
        course_id=course_id,
        title=title,
        video_url=video_url,
        document_url=document_url,
        sequence_order=next_order
    )
    db.session.add(new_lesson)
    db.session.commit()
    recalc_total_lessons(course_id)
    flash("Đã thêm bài học mới!", "success")
    return redirect(url_for("teacher.manage_lessons", course_id=course_id))


@bp.route("/courses/<course_id>/lessons/reorder", methods=["POST"])
@login_required
@role_required("teacher")
def reorder_lessons(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        abort(403)
        
    lesson_ids = request.form.getlist("lesson_ids[]")
    for index, l_id in enumerate(lesson_ids):
        lesson = db.session.get(Lesson, l_id)
        if lesson and lesson.course_id == course_id:
            lesson.sequence_order = index + 1
            
    db.session.commit()
    return jsonify({"status": "success"})


@bp.route("/courses/<course_id>/lessons/<lesson_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def edit_lesson(course_id, lesson_id):
    course = db.session.get(Course, course_id)
    lesson = db.session.get(Lesson, lesson_id)
    if not course or not lesson or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
        
    if request.method == "POST":
        lesson.title = request.form.get("title")
        lesson.video_url = request.form.get("video_url")
        lesson.document_url = request.form.get("document_url")
        db.session.commit()
        flash("Đã cập nhật bài học.", "success")
        return redirect(url_for("teacher.manage_lessons", course_id=course_id))
        
    return render_template("edit_lesson.html", course=course, lesson=lesson)


@bp.post("/courses/<course_id>/lessons/<lesson_id>/delete")
@login_required
@role_required("teacher")
def delete_lesson(course_id, lesson_id):
    course = db.session.get(Course, course_id)
    lesson = db.session.get(Lesson, lesson_id)
    if course and lesson and course.teacher_id == current_user.id and not course.is_deleted:
        db.session.delete(lesson)
        db.session.commit()
        recalc_total_lessons(course_id)
        flash("Đã xóa bài học.", "success")
    return redirect(url_for("teacher.manage_lessons", course_id=course_id))


# --- Quiz Management ---

@bp.route("/courses/<course_id>/quizzes")
@login_required
@role_required("teacher")
def manage_quizzes(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
    quizzes = db.session.query(Quiz).filter_by(course_id=course_id).all()
    return render_template("manage_quizzes.html", course=course, quizzes=quizzes)


@bp.route("/courses/<course_id>/quizzes/new", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def create_quiz(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
        
    if request.method == "POST":
        quiz = Quiz(
            course_id=course_id,
            title=request.form.get("title"),
            pass_score=_safe_int(request.form.get("pass_score"), 80),
            max_attempts=_safe_int(request.form.get("max_attempts"), 3),
            time_limit=_safe_int(request.form.get("time_limit"), 0),
            random_question_count=_safe_int(request.form.get("random_question_count"), 0)
        )
        db.session.add(quiz)
        db.session.commit()
        return redirect(url_for("teacher.edit_quiz", course_id=course_id, quiz_id=quiz.id))
        
    return render_template("edit_quiz.html", course=course, quiz=None)


@bp.route("/courses/<course_id>/quizzes/<quiz_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def edit_quiz(course_id, quiz_id):
    course = db.session.get(Course, course_id)
    quiz = db.session.get(Quiz, quiz_id)
    if not course or not quiz or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
        
    if request.method == "POST":
        quiz.title = request.form.get("title")
        quiz.pass_score = _safe_int(request.form.get("pass_score"), 80)
        quiz.max_attempts = _safe_int(request.form.get("max_attempts"), 3)
        quiz.time_limit = _safe_int(request.form.get("time_limit"), 0)
        quiz.random_question_count = _safe_int(request.form.get("random_question_count"), 0)
        quiz.is_published = 'is_published' in request.form
        db.session.commit()
        flash("Đã cập nhật Quiz.", "success")
        return redirect(url_for("teacher.manage_quizzes", course_id=course_id))
        
    questions = db.session.query(Question).filter_by(quiz_id=quiz_id).all()
    questions_with_choices = []
    for q in questions:
        choices = db.session.query(Choice).filter_by(question_id=q.id).all()
        questions_with_choices.append({
            'id': q.id,
            'text': q.text,
            'q_type': q.q_type,
            'choices': choices
        })
        
    return render_template("edit_quiz.html", course=course, quiz=quiz, questions=questions_with_choices)


@bp.post("/quizzes/<quiz_id>/questions/add")
@login_required
@role_required("teacher")
def add_question(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        return redirect(url_for("teacher.manage_courses"))
    course = db.session.get(Course, quiz.course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return "Unauthorized", 403
    
    q_text = request.form.get("text")
    q_type = request.form.get("q_type", "mcq")
    
    question = Question(quiz_id=quiz_id, text=q_text, q_type=q_type)
    db.session.add(question)
    db.session.commit()
    
    # Add choices
    choices_texts = request.form.getlist("choice_text")
    correct_indices = request.form.getlist("correct_choices")
    
    for i, text in enumerate(choices_texts):
        if text.strip():
            is_correct = (str(i) in correct_indices) if q_type != 'fill_in_blank' else True
            db.session.add(Choice(question_id=question.id, text=text, is_correct=is_correct))
            
    db.session.commit()

    # Notify students if quiz is published
    if quiz.is_published:
        from ..services.notifications import notify
        students = db.session.query(Enrollment).filter(Enrollment.course_id == quiz.course_id, Enrollment.status.in_(["active", "completed"])).all()
        for en in students:
            notify(en.user_id, "new_quiz", f"Bài trắc nghiệm mới: {quiz.title}", url_for("student.take_quiz", course_id=quiz.course_id, quiz_id=quiz.id))

    return redirect(url_for("teacher.edit_quiz", course_id=quiz.course_id, quiz_id=quiz_id))


# --- Assignment & Grading ---

@bp.route("/courses/<course_id>/assignments")
@login_required
@role_required("teacher")
def manage_assignments(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
    assignments = db.session.query(Assignment).filter_by(course_id=course_id).all()
    return render_template("manage_assignments.html", course=course, assignments=assignments)


@bp.route("/courses/<course_id>/assignments/new", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def create_assignment(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
        
    if request.method == "POST":
        deadline_str = request.form.get("deadline")
        deadline = parse_datetime_utc(deadline_str)
        
        assign = Assignment(
            course_id=course_id,
            title=request.form.get("title"),
            description=request.form.get("description"),
            deadline=deadline,
            allow_file='allow_file' in request.form,
            allow_text='allow_text' in request.form
        )
        db.session.add(assign)
        db.session.commit()

        # Notify students
        from ..services.notifications import notify
        students = db.session.query(Enrollment).filter(Enrollment.course_id == course_id, Enrollment.status.in_(["active", "completed"])).all()
        for en in students:
            notify(en.user_id, "new_assignment", f"Bài tập mới: {assign.title}", url_for("student.submit_assignment", course_id=course_id, assignment_id=assign.id))

        flash("Đã tạo bài tập mới.", "success")
        return redirect(url_for("teacher.manage_assignments", course_id=course_id))
        
    return render_template("edit_assignment.html", course=course, assignment=None)


@bp.route("/assignments/<assignment_id>/submissions")
@login_required
@role_required("teacher")
def view_submissions(assignment_id):
    assignment = db.session.get(Assignment, assignment_id)
    if not assignment:
        return redirect(url_for("teacher.manage_courses"))
    course = db.session.get(Course, assignment.course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
        
    status_filter = request.args.get("status")
    query = db.session.query(Submission, User).join(User, User.id == Submission.user_id).filter(Submission.assignment_id == assignment_id)
    
    if status_filter:
        query = query.filter(Submission.status == status_filter)
        
    page, per_page = get_pagination(default_per_page=20, max_per_page=100)
    pagination = paginate_query(query.order_by(Submission.submitted_at.desc()), page, per_page)
    return render_template("view_submissions.html", assignment=assignment, submissions=pagination["items"], course=course, pagination=pagination)


@bp.post("/submissions/<submission_id>/grade")
@login_required
@role_required("teacher")
def grade_submission(submission_id):
    sub = db.session.get(Submission, submission_id)
    if not sub:
        return redirect(url_for("teacher.manage_courses"))
    assignment = db.session.get(Assignment, sub.assignment_id)
    if not assignment:
        return redirect(url_for("teacher.manage_courses"))
    course = db.session.get(Course, assignment.course_id)
    
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
        
    score = max(0, min(100, int(request.form.get("score", 0))))
    feedback = request.form.get("feedback")
    
    from ..services import GradingService
    GradingService.grade_assignment_submission(submission_id, score, feedback, current_user.id)

    # Audit log for grade changes
    from ..services.audit import log_action
    log_action(
        "grade_submission",
        target_type="Submission",
        target_id=str(submission_id),
        detail={
            "assignment_id": str(assignment.id),
            "assignment_title": assignment.title,
            "student_id": str(sub.user_id),
            "score": score,
        },
    )

    # Notify student
    from ..services.notifications import notify
    notify(sub.user_id, "graded", f"Bài tập '{assignment.title}' của bạn đã được chấm điểm: {score}/100", url_for("student.submit_assignment", course_id=course.id, assignment_id=assignment.id))

    flash(f"Đã chấm điểm cho học viên.", "success")
    return redirect(url_for("teacher.view_submissions", assignment_id=assignment.id))


@bp.route("/assignments/<assignment_id>/export")
@login_required
@role_required("teacher")
def export_grades(assignment_id):
    assignment = db.session.get(Assignment, assignment_id)
    if not assignment:
        return redirect(url_for("teacher.manage_courses"))
    course = db.session.get(Course, assignment.course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
    
    max_rows = _export_max_rows()
    submissions = db.session.query(Submission, User).join(User, User.id == Submission.user_id).filter(Submission.assignment_id == assignment_id).limit(max_rows).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Email', 'Submitted At', 'Score', 'Status', 'Feedback'])
    
    for sub, user in submissions:
        writer.writerow([user.email, sub.submitted_at, sub.score, sub.status, sub.feedback])
        
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=grades_{assignment_id}.csv"
    response.headers["Content-type"] = "text/csv"
    log_action("assignment_grades_exported", "Assignment", assignment_id, {"max_rows": max_rows})
    return response


# --- Gradebook & Analytics ---

@bp.route("/courses/<course_id>/gradebook")
@login_required
@role_required("teacher")
def view_gradebook(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
        
    max_rows = _export_max_rows()
    students = db.session.query(User).join(Enrollment, Enrollment.user_id == User.id).filter(Enrollment.course_id == course_id, Enrollment.status.in_(["active", "completed"])).limit(max_rows).all()
    quizzes = db.session.query(Quiz).filter_by(course_id=course_id, is_published=True).all()
    assignments = db.session.query(Assignment).filter_by(course_id=course_id).all()
    
    # Optimized: Fetch all scores in bulk to avoid N+1 queries
    quiz_attempts = db.session.query(
        QuizAttempt.user_id, QuizAttempt.quiz_id, func.max(QuizAttempt.score)
    ).filter(QuizAttempt.quiz_id.in_([q.id for q in quizzes])).group_by(QuizAttempt.user_id, QuizAttempt.quiz_id).all()
    
    submissions_list = db.session.query(
        Submission.user_id, Submission.assignment_id, Submission.score
    ).filter(Submission.assignment_id.in_([a.id for a in assignments])).all()

    scores = {s.id: {} for s in students}
    for uid, qid, score in quiz_attempts:
        if uid in scores:
            scores[uid][f"quiz_{qid}"] = score
            
    for uid, aid, score in submissions_list:
        if uid in scores:
            scores[uid][f"assign_{aid}"] = score
            
    return render_template("gradebook.html", course=course, students=students, quizzes=quizzes, assignments=assignments, scores=scores)


@bp.route("/courses/<course_id>/gradebook/export")
@login_required
@role_required("teacher")
def export_gradebook(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted: return redirect(url_for("teacher.manage_courses"))
    
    max_rows = _export_max_rows()
    students = db.session.query(User).join(Enrollment, Enrollment.user_id == User.id).filter(Enrollment.course_id == course_id, Enrollment.status.in_(["active", "completed"])).limit(max_rows).all()
    quizzes = db.session.query(Quiz).filter_by(course_id=course_id, is_published=True).all()
    assignments = db.session.query(Assignment).filter_by(course_id=course_id).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    header = ['Email', 'Name']
    for q in quizzes: header.append(f"Quiz: {q.title}")
    for a in assignments: header.append(f"Assign: {a.title}")
    writer.writerow(header)
    
    # Optimized: Bulk fetch scores
    quiz_attempts = db.session.query(
        QuizAttempt.user_id, QuizAttempt.quiz_id, func.max(QuizAttempt.score)
    ).filter(QuizAttempt.quiz_id.in_([q.id for q in quizzes])).group_by(QuizAttempt.user_id, QuizAttempt.quiz_id).all()
    
    submissions_list = db.session.query(
        Submission.user_id, Submission.assignment_id, Submission.score
    ).filter(Submission.assignment_id.in_([a.id for a in assignments])).all()

    scores_map = {s.id: {} for s in students}
    for uid, qid, score in quiz_attempts:
        if uid in scores_map: scores_map[uid][f"quiz_{qid}"] = score
    for uid, aid, score in submissions_list:
        if uid in scores_map: scores_map[uid][f"assign_{aid}"] = score

    for s in students:
        row = [s.email, s.email.split('@')[0]]
        for q in quizzes:
            score = scores_map[s.id].get(f"quiz_{q.id}")
            row.append(score if score is not None else 'N/A')
        for a in assignments:
            score = scores_map[s.id].get(f"assign_{a.id}")
            row.append(score if score is not None else 'N/A')
        writer.writerow(row)
        
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=gradebook_{course_id}.csv"
    response.headers["Content-type"] = "text/csv"
    log_action("gradebook_exported", "Course", course_id, {"max_rows": max_rows})
    return response


@bp.route("/courses/<course_id>/analytics")
@login_required
@role_required("teacher")
def course_analytics(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        return redirect(url_for("teacher.manage_courses"))
        
    from ..models import LearningLog, QuizAttempt
    lessons = db.session.query(Lesson).filter_by(course_id=course_id).order_by(Lesson.sequence_order.asc()).all()
    enrollment_count = db.session.query(Enrollment).filter(Enrollment.course_id == course_id, Enrollment.status.in_(["active", "completed"])).count()
    completed_count = db.session.query(Enrollment).filter_by(course_id=course_id, status="completed").count()
    
    # Optimized: Funnel data using GROUP BY
    completion_stats = db.session.query(
        LearningLog.lesson_id, func.count(func.distinct(LearningLog.user_id))
    ).filter(
        LearningLog.lesson_id.in_([ls.id for ls in lessons]),
        LearningLog.action_type == "complete"
    ).group_by(LearningLog.lesson_id).all()
    
    stats_map = {sid: count for sid, count in completion_stats}
    funnel_data = [{"title": ls.title, "count": stats_map.get(ls.id, 0)} for ls in lessons]
        
    # Optimized: single GROUP BY query for all quiz averages at once
    quizzes = db.session.query(Quiz).filter_by(course_id=course_id).all()
    avg_scores = db.session.query(
        QuizAttempt.quiz_id, func.avg(QuizAttempt.score)
    ).join(Quiz).filter(Quiz.course_id == course_id).group_by(QuizAttempt.quiz_id).all()
    avg_map = {qid: round(float(avg or 0), 1) for qid, avg in avg_scores}
    quiz_stats = [{"title": q.title, "avg": avg_map.get(q.id, 0)} for q in quizzes]
        
    # Score Distribution (Phổ điểm)
    score_distribution = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    attempts = db.session.query(QuizAttempt.score).join(Quiz).filter(Quiz.course_id == course_id).all()
    for (score,) in attempts:
        if score is None: continue
        if score <= 20: score_distribution["0-20"] += 1
        elif score <= 40: score_distribution["21-40"] += 1
        elif score <= 60: score_distribution["41-60"] += 1
        elif score <= 80: score_distribution["61-80"] += 1
        else: score_distribution["81-100"] += 1
        
    return render_template(
        "course_analytics.html", 
        course=course, 
        enrollment_count=enrollment_count, 
        completed_count=completed_count,
        funnel_data=funnel_data,
        quiz_stats=quiz_stats,
        score_distribution=score_distribution
    )


# recalc_total_lessons is now imported from services.course (line 14)


@bp.route("/submissions/<submission_id>/download")
@login_required
@role_required("teacher")
def download_submission_file(submission_id):
    """Secure file download — verifies teacher ownership before serving file."""
    sub = db.session.get(Submission, submission_id)
    if not sub or not sub.file_path:
        flash("File không tồn tại.", "error")
        return redirect(url_for("teacher.manage_courses"))
    
    assignment = db.session.get(Assignment, sub.assignment_id)
    if not assignment:
        flash("Bài tập không tồn tại.", "error")
        return redirect(url_for("teacher.manage_courses"))
    
    course = db.session.get(Course, assignment.course_id)
    if not course or course.teacher_id != current_user.id or course.is_deleted:
        flash("Bạn không có quyền tải file này.", "error")
        return redirect(url_for("teacher.manage_courses"))
    
    from ..services.storage import storage
    try:
        return storage.send_file_response(sub.file_path)
    except NotImplementedError:
        # S3 backend — redirect to presigned URL
        return redirect(storage.secure_get_url(sub.file_path))
