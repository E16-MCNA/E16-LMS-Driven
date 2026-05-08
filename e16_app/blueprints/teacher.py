from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import Course, Enrollment, LearningLog, Lesson
from ..services import recalc_total_lessons

bp = Blueprint("teacher", __name__, url_prefix="/manage")


@bp.route("")
@login_required
@role_required("teacher")
def manage_courses():
    courses = db.session.query(Course).filter(Course.teacher_id == g.user.id).order_by(Course.created_at.desc()).all()
    return render_template("manage_courses.html", courses=courses, user=g.user)


@bp.post("/course/create")
@login_required
@role_required("teacher")
def create_course():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    cover_image_url = request.form.get("cover_image_url", "").strip()
    if not title:
        flash("Title không được để trống.", "error")
        return redirect(url_for("teacher.manage_courses"))
    course = Course(title=title, description=description, cover_image_url=cover_image_url, teacher_id=g.user.id)
    db.session.add(course)
    db.session.commit()
    return redirect(url_for("teacher.manage_courses"))


@bp.post("/course/<course_id>/delete")
@login_required
@role_required("teacher")
def delete_course(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != g.user.id:
        flash("Không tìm thấy khóa học.", "error")
        return redirect(url_for("teacher.manage_courses"))
    lessons = db.session.query(Lesson).filter(Lesson.course_id == course.id).all()
    lesson_ids = [ls.id for ls in lessons]
    if lesson_ids:
        db.session.query(LearningLog).filter(LearningLog.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)
    db.session.query(Lesson).filter(Lesson.course_id == course.id).delete(synchronize_session=False)
    db.session.query(Enrollment).filter(Enrollment.course_id == course.id).delete(synchronize_session=False)
    db.session.delete(course)
    db.session.commit()
    return redirect(url_for("teacher.manage_courses"))


@bp.route("/course/<course_id>")
@login_required
@role_required("teacher")
def manage_lessons(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != g.user.id:
        flash("Không tìm thấy khóa học.", "error")
        return redirect(url_for("teacher.manage_courses"))
    lessons = db.session.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.sequence_order.asc()).all()
    return render_template("manage_lessons.html", course=course, lessons=lessons, user=g.user)


@bp.post("/course/<course_id>/lesson/create")
@login_required
@role_required("teacher")
def create_lesson(course_id):
    title = request.form.get("title", "").strip()
    video_url = request.form.get("video_url", "").strip()
    document_url = request.form.get("document_url", "").strip()
    if not title:
        flash("Tên bài học là bắt buộc.", "error")
        return redirect(url_for("teacher.manage_lessons", course_id=course_id))
    max_order = db.session.query(func.max(Lesson.sequence_order)).filter(Lesson.course_id == course_id).scalar() or 0
    lesson = Lesson(
        course_id=course_id,
        title=title,
        video_url=video_url,
        document_url=document_url,
        sequence_order=max_order + 1,
    )
    db.session.add(lesson)
    db.session.commit()
    recalc_total_lessons(course_id)
    return redirect(url_for("teacher.manage_lessons", course_id=course_id))


@bp.post("/course/<course_id>/lesson/<lesson_id>/delete")
@login_required
@role_required("teacher")
def delete_lesson(course_id, lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    if lesson and lesson.course_id == course_id:
        db.session.query(LearningLog).filter(LearningLog.lesson_id == lesson.id).delete(synchronize_session=False)
        db.session.delete(lesson)
        db.session.commit()
        lessons = db.session.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.sequence_order.asc()).all()
        for idx, ls in enumerate(lessons, 1):
            ls.sequence_order = idx
        db.session.commit()
    recalc_total_lessons(course_id)
    return redirect(url_for("teacher.manage_lessons", course_id=course_id))


@bp.post("/course/<course_id>/lesson/reorder")
@login_required
@role_required("teacher")
def reorder_lessons(course_id):
    lesson_ids = request.form.getlist("lesson_ids")
    lessons = {ls.id: ls for ls in db.session.query(Lesson).filter(Lesson.course_id == course_id).all()}
    order = 1
    for lid in lesson_ids:
        if lid in lessons:
            lessons[lid].sequence_order = order
            order += 1
    db.session.commit()
    return redirect(url_for("teacher.manage_lessons", course_id=course_id))
