# -*- coding: utf-8 -*-
import os
from werkzeug.utils import secure_filename
from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app, session
from flask_login import current_user
from sqlalchemy import func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import Category, Course, Enrollment, LearningLog, Lesson, Quiz, Question, Choice, QuizAttempt, QuizAnswer, Assignment, Submission, Certificate, User
from ..services.logging import logger
from ..time_utils import ensure_utc, utcnow

bp = Blueprint("student", __name__)


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


@bp.route("/courses")
@login_required
def list_courses():
    query_str = request.args.get("q", "").strip()
    cat_slug = request.args.get("cat", "").strip()
    
    courses_query = db.session.query(Course).filter(Course.status == "published", Course.is_deleted == False)
    
    if query_str:
        courses_query = courses_query.filter(Course.title.ilike(f"%{query_str}%"))
    
    if cat_slug:
        courses_query = courses_query.join(Category).filter(Category.slug == cat_slug)
    
    courses = courses_query.order_by(Course.created_at.desc()).all()
    categories = db.session.query(Category).all()
    
    enrolled_course_ids = set()
    if current_user.is_authenticated:
        enrolled_course_ids = {
            en.course_id for en in db.session.query(Enrollment).filter_by(user_id=current_user.id).all()
        }
        
    return render_template(
        "course_list.html", 
        courses=courses, 
        categories=categories, 
        query=query_str, 
        cat_slug=cat_slug,
        enrolled_course_ids=enrolled_course_ids
    )


@bp.route("/dashboard")
@login_required
@role_required("student")
def dashboard():
    from sqlalchemy.orm import joinedload
    enrollments = db.session.query(Enrollment).options(joinedload(Enrollment.course)).filter(Enrollment.user_id == current_user.id).all()
    rows = []
    total_completed_lessons = 0
    
    for en in enrollments:
        course = en.course
        if not course or course.is_deleted:
            continue
            
        my_rate = student_completion_rate(current_user.id, course.id)
        
        # Find next lesson
        completed_lesson_ids = {
            log.lesson_id for log in db.session.query(LearningLog).filter_by(
                user_id=current_user.id, action_type="complete"
            ).join(Lesson).filter(Lesson.course_id == course.id).all()
        }
        total_completed_lessons += len(completed_lesson_ids)
        
        next_lesson = db.session.query(Lesson).filter(
            Lesson.course_id == course.id,
            ~Lesson.id.in_(completed_lesson_ids)
        ).order_by(Lesson.sequence_order.asc()).first()
        
        rows.append({
            "course": course,
            "enrollment": en,
            "my_rate": my_rate,
            "avg_rate": class_average_completion_rate(course.id),
            "next_lesson": next_lesson
        })
    
    # Recent activity
    recent_logs = db.session.query(LearningLog, Lesson).join(Lesson).filter(
        LearningLog.user_id == current_user.id,
        LearningLog.action_type == "complete"
    ).order_by(LearningLog.timestamp.desc()).limit(5).all()
    
    # Stats — calculate actual learning streak (consecutive days with completions)
    streak = _calc_streak(current_user.id)
    stats = {
        "total_courses": len(enrollments),
        "total_completed_lessons": total_completed_lessons,
        "streak": streak
    }
    
    return render_template(
        "student_dashboard.html",
        rows=rows,
        recent_logs=recent_logs,
        stats=stats
    )


@bp.route("/checkout/<course_id>")
@login_required
@role_required("student")
def checkout(course_id):
    from ..services.payment import get_or_create_pending_enrollment, generate_tx_code, get_seconds_remaining
    course = db.session.get(Course, course_id)
    if not course or course.status != "published" or course.is_deleted:
        flash("Khóa học không khả dụng.", "error")
        return redirect(url_for("student.list_courses"))
        
    enrollment, _ = get_or_create_pending_enrollment(current_user.id, course_id)
    
    if enrollment.status in ("active", "completed"):
        return redirect(url_for("student.learn", course_id=course_id))
    
    if enrollment.status == "pending_payment":
        from ..time_utils import utcnow, ensure_utc
        time_diff = utcnow() - ensure_utc(enrollment.enrolled_at)
        if time_diff.total_seconds() > 600:
            flash("Phiên thanh toán QR đã hết hạn (quá 10 phút). Vui lòng quét lại.", "warning")
            enrollment, _ = get_or_create_pending_enrollment(current_user.id, course_id)
    
    return render_template(
        "checkout.html",
        course=course,
        tx_code=generate_tx_code(),
        seconds_left=get_seconds_remaining(enrollment),
        payment_mode=current_app.config.get("PAYMENT_MODE", "mock"),
    )


@bp.post("/enroll/<course_id>")
@login_required
@role_required("student")
def enroll(course_id):
    from ..services.payment import activate_enrollment
    course = db.session.get(Course, course_id)
    if not course or course.status != "published" or course.is_deleted:
        flash("Khóa học không khả dụng.", "error")
        return redirect(url_for("student.list_courses"))
        
    success, message = activate_enrollment(current_user.id, course_id)
    if not success:
        flash(message, "error")
        return redirect(url_for("student.list_courses"))
    
    logger.log("pay_course", user_id=current_user.id, user_email=current_user.email, resource_type="course", resource_id=course_id, metadata={"course_title": course.title, "amount": course.price})
    flash(f"Thanh toán và đăng ký thành công khóa học {course.title}!", "success")
    return redirect(url_for("student.learn", course_id=course_id))


@bp.post("/checkout/simulate-ipn/<course_id>")
@login_required
@role_required("student")
def simulate_ipn(course_id):
    if current_app.config.get("PAYMENT_MODE", "mock") == "real":
        return {"status": "error", "message": "Tính năng thanh toán thực chưa được triển khai. Vui lòng liên hệ admin."}, 501

    from ..services.payment import activate_enrollment
    success, message = activate_enrollment(current_user.id, course_id)
    if not success:
        return {"status": "error", "message": message}, 400
    
    course = db.session.get(Course, course_id)
    logger.log("pay_course", user_id=current_user.id, user_email=current_user.email, resource_type="course", resource_id=course_id, metadata={"course_title": course.title if course else "", "amount": course.price if course else 0})
    return {"status": "success", "message": "Thanh toán thành công qua cổng MB Bank IPN!"}


@bp.post("/checkout/cancel/<course_id>")
@login_required
@role_required("student")
def cancel_checkout(course_id):
    from ..services.payment import cancel_pending_enrollment
    if cancel_pending_enrollment(current_user.id, course_id):
        flash("Đã hủy giao dịch thanh toán QR.", "info")
    return redirect(url_for("student.list_courses"))


@bp.route("/learn/<course_id>")
@login_required
@role_required("student")
def learn(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.is_deleted:
        return redirect(url_for("student.dashboard"))
        
    enrollment = db.session.query(Enrollment).filter(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id).first()
    if not enrollment:
        flash("Bạn chưa đăng ký khóa học này.", "error")
        return redirect(url_for("student.list_courses"))
        
    if enrollment.status == "pending_payment":
        flash("Vui lòng hoàn tất thanh toán chuyển khoản QR để tham gia khóa học.", "warning")
        return redirect(url_for("student.checkout", course_id=course_id))
        
    if enrollment.status not in ("active", "completed"):
        flash("Đăng ký khóa học của bạn không còn hoạt động.", "error")
        return redirect(url_for("student.list_courses"))
        
    lessons = db.session.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.sequence_order.asc()).all()
    quizzes = db.session.query(Quiz).filter_by(course_id=course_id, is_published=True).all()
    assignments = db.session.query(Assignment).filter_by(course_id=course_id).all()
    
    if not lessons:
        return redirect(url_for("student.dashboard"))

    selected_id = request.args.get("lesson") or lessons[0].id
    selected_lesson = next((ls for ls in lessons if ls.id == selected_id), lessons[0])
    
    db.session.add(LearningLog(user_id=current_user.id, lesson_id=selected_lesson.id, action_type="start", timestamp=utcnow()))
    db.session.commit()
    
    # Track lesson open timestamp for minimum-time enforcement (90 seconds)
    session[f"lesson_start_{selected_lesson.id}"] = utcnow().isoformat()
    logger.log("view_lesson", user_id=current_user.id, user_email=current_user.email, resource_type="lesson", resource_id=selected_lesson.id, metadata={"course_id": course_id, "lesson_title": selected_lesson.title})

    completed_ids = {
        row[0]
        for row in db.session.query(func.distinct(LearningLog.lesson_id))
        .join(Lesson, Lesson.id == LearningLog.lesson_id)
        .filter(LearningLog.user_id == current_user.id, Lesson.course_id == course_id, LearningLog.action_type == "complete")
        .all()
    }
    
    progress = (len(completed_ids) / len(lessons) * 100) if lessons else 0
    
    return render_template(
        "learning_page.html",
        course=course,
        lessons=lessons,
        quizzes=quizzes,
        assignments=assignments,
        selected_lesson=selected_lesson,
        completed_ids=completed_ids,
        progress=progress
    )


@bp.post("/learn/<course_id>/complete/<lesson_id>")
@login_required
@role_required("student")
def mark_complete(course_id, lesson_id):
    lesson = db.session.get(Lesson, lesson_id)
    enrollment = db.session.query(Enrollment).filter_by(user_id=current_user.id, course_id=course_id).first()
    if not lesson or lesson.course_id != course_id or not enrollment or enrollment.status not in ("active", "completed"):
        flash("Bạn không có quyền cập nhật bài học này.", "error")
        return redirect(url_for("student.dashboard"))

    # Enforce minimum 90-second time on lesson page
    from datetime import datetime
    lesson_start_key = f"lesson_start_{lesson_id}"
    lesson_start_iso = session.get(lesson_start_key)
    if lesson_start_iso:
        try:
            lesson_start_time = datetime.fromisoformat(lesson_start_iso)
            elapsed = (utcnow() - lesson_start_time).total_seconds()
            if elapsed < 90:
                remaining = int(90 - elapsed)
                flash(f"Bạn cần ở trong bài học ít nhất 1 phút 30 giây trước khi đánh dấu hoàn thành. Còn {remaining} giây nữa.", "warning")
                return redirect(url_for("student.learn", course_id=course_id, lesson=lesson_id))
        except (ValueError, TypeError):
            pass
    else:
        flash("Vui lòng mở bài học trước khi đánh dấu hoàn thành.", "warning")
        return redirect(url_for("student.learn", course_id=course_id, lesson=lesson_id))

    exists = db.session.query(LearningLog).filter_by(
        user_id=current_user.id, lesson_id=lesson_id, action_type="complete"
    ).first()
    
    if not exists:
        db.session.add(LearningLog(user_id=current_user.id, lesson_id=lesson_id, action_type="complete", timestamp=utcnow()))
        db.session.commit()
        logger.log("complete_lesson", user_id=current_user.id, user_email=current_user.email, resource_type="lesson", resource_id=lesson_id, metadata={"course_id": course_id})
        update_enrollment_if_completed(current_user.id, course_id)
        # Clear the lesson start timestamp from session
        session.pop(lesson_start_key, None)
        
    return redirect(url_for("student.learn", course_id=course_id, lesson=lesson_id))


# --- Quiz & Assignment Routes for Students ---

@bp.route("/learn/<course_id>/quiz/<quiz_id>", methods=["GET", "POST"])
@login_required
@role_required("student")
def take_quiz(course_id, quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    enrollment = db.session.query(Enrollment).filter_by(user_id=current_user.id, course_id=course_id).first()
    if not quiz or quiz.course_id != course_id or not quiz.is_published or not enrollment or enrollment.status not in ("active", "completed"):
        flash("Bạn không có quyền làm bài trắc nghiệm này.", "error")
        return redirect(url_for("student.dashboard"))
    
    from ..services import QuizService
    attempts = QuizService.get_attempt_count(current_user.id, quiz_id)
    if attempts >= quiz.max_attempts:
        flash("Bạn đã hết lượt làm bài trắc nghiệm này.", "warning")
        return redirect(url_for("student.learn", course_id=course_id))
        
    if request.method == "POST":
        from ..services import GradingService
        served_q_ids = request.form.getlist("served_questions")
        attempt = GradingService.grade_quiz_attempt(current_user.id, quiz_id, request.form.to_dict(flat=False), served_q_ids)
        
        if not attempt:
            flash("Có lỗi xảy ra khi chấm điểm.", "error")
            return redirect(url_for("student.learn", course_id=course_id))

        logger.log("complete_quiz", user_id=current_user.id, user_email=current_user.email, resource_type="quiz", resource_id=quiz_id, metadata={"score": attempt.score, "course_id": course_id})
        return redirect(url_for("student.review_quiz", course_id=course_id, quiz_id=quiz_id, attempt_id=attempt.id))
        
    questions = QuizService.prepare_shuffled_questions(quiz_id)
    return render_template("take_quiz.html", quiz=quiz, questions=questions, course_id=course_id)


@bp.route("/learn/<course_id>/assignment/<assignment_id>", methods=["GET", "POST"])
@login_required
@role_required("student")
def submit_assignment(course_id, assignment_id):
    assignment = db.session.get(Assignment, assignment_id)
    enrollment = db.session.query(Enrollment).filter_by(user_id=current_user.id, course_id=course_id).first()
    if not assignment or assignment.course_id != course_id or not enrollment or enrollment.status not in ("active", "completed"):
        flash("Bạn không có quyền nộp bài tập này.", "error")
        return redirect(url_for("student.dashboard"))
    
    existing_sub = db.session.query(Submission).filter_by(user_id=current_user.id, assignment_id=assignment_id).first()
    
    if request.method == "POST":
        if assignment.deadline and utcnow() > ensure_utc(assignment.deadline):
            flash("Đã hết hạn nộp bài.", "error")
            return redirect(url_for("student.learn", course_id=course_id))
            
        from ..services.storage import storage
        file = request.files.get("file")
        try:
            file_path = storage.save_file(file, "assignments") if file and assignment.allow_file else None
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("student.submit_assignment", course_id=course_id, assignment_id=assignment_id))
        
        from ..services.submission import submit_or_update
        submit_or_update(
            user_id=current_user.id,
            assignment_id=assignment_id,
            text_content=request.form.get("text_content"),
            file_path=file_path,
        )
        flash("Đã nộp bài thành công!", "success")
        return redirect(url_for("student.learn", course_id=course_id))
        
    return render_template("submit_assignment.html", assignment=assignment, submission=existing_sub, course_id=course_id)


@bp.route("/learn/<course_id>/quiz/<quiz_id>/review/<attempt_id>")
@login_required
@role_required("student")
def review_quiz(course_id, quiz_id, attempt_id):
    """Show detailed quiz result with correct/incorrect answers for review."""
    quiz = db.session.get(Quiz, quiz_id)
    attempt = db.session.get(QuizAttempt, attempt_id)
    enrollment = db.session.query(Enrollment).filter_by(user_id=current_user.id, course_id=course_id).first()
    if (
        not quiz
        or quiz.course_id != course_id
        or not enrollment
        or not attempt
        or attempt.user_id != current_user.id
        or attempt.quiz_id != quiz_id
    ):
        flash("Không tìm thấy kết quả bài làm.", "error")
        return redirect(url_for("student.learn", course_id=course_id))
    
    # Fetch the questions that were served in this attempt via quiz_answers
    answer_records = db.session.query(QuizAnswer).filter_by(attempt_id=attempt_id).all()
    review_question_ids = {a.question_id for a in answer_records}
    
    # Build a lookup: question_id -> list of selected choice_ids
    user_choices_map = {}
    for a in answer_records:
        user_choices_map.setdefault(a.question_id, []).append(a.choice_id)
        
    # Build a lookup: question_id -> fill_in_blank text answer
    user_text_map = {}
    for a in answer_records:
        if a.text_answer is not None:
            user_text_map[a.question_id] = a.text_answer
    
    # Fetch all questions that were in this attempt
    questions = db.session.query(Question).filter(Question.id.in_(review_question_ids)).all() if review_question_ids else []
    
    # Build review data for each question
    review_items = []
    for q in questions:
        choices = db.session.query(Choice).filter_by(question_id=q.id).all()
        correct_choice_ids = {str(c.id) for c in choices if c.is_correct}
        selected_choice_ids = {str(cid) for cid in user_choices_map.get(q.id, []) if cid is not None}
        
        if q.q_type == "fill_in_blank":
            normalized_answers = {c.text.strip().lower() for c in choices}
            submitted_text = user_text_map.get(q.id, "").strip()
            is_correct = submitted_text.lower() in normalized_answers if submitted_text else False
        else:
            submitted_text = ""
            is_correct = selected_choice_ids == correct_choice_ids and len(selected_choice_ids) > 0
        
        review_items.append({
            "question": q,
            "choices": choices,
            "correct_choice_ids": correct_choice_ids,
            "selected_choice_ids": selected_choice_ids,
            "submitted_text": submitted_text,
            "is_correct": is_correct
        })
    
    # Check remaining attempts
    total_attempts = db.session.query(QuizAttempt).filter_by(user_id=current_user.id, quiz_id=quiz_id).count()
    can_retry = total_attempts < quiz.max_attempts
    
    return render_template(
        "quiz_result.html",
        quiz=quiz,
        attempt=attempt,
        course_id=course_id,
        review_items=review_items,
        can_retry=can_retry
    )


@bp.route("/transcript")
@login_required
@role_required("student")
def view_transcript():
    enrollments = db.session.query(Enrollment).filter_by(user_id=current_user.id).all()
    transcript_data = []
    
    for en in enrollments:
        course = db.session.get(Course, en.course_id)
        if not course or course.is_deleted:
            continue
        quizzes = db.session.query(Quiz).filter_by(course_id=course.id, is_published=True).all()
        assignments = db.session.query(Assignment).filter_by(course_id=course.id).all()
        
        course_scores = []
        for q in quizzes:
            best = db.session.query(func.max(QuizAttempt.score)).filter_by(user_id=current_user.id, quiz_id=q.id).scalar()
            course_scores.append({"title": q.title, "score": best, "type": "Quiz", "pass_score": q.pass_score})
            
        for a in assignments:
            sub = db.session.query(Submission).filter_by(user_id=current_user.id, assignment_id=a.id).first()
            course_scores.append({"title": a.title, "score": sub.score if sub else None, "type": "Assignment", "status": sub.status if sub else "missing"})
            
        transcript_data.append({
            "course": course,
            "items": course_scores,
            "completion_rate": student_completion_rate(current_user.id, course.id)
        })
        
    return render_template("transcript.html", transcript_data=transcript_data)


@bp.route("/calendar")
@login_required
@role_required("student")
def view_calendar():
    enrollments = db.session.query(Enrollment.course_id).filter_by(user_id=current_user.id).all()
    course_ids = [en.course_id for en in enrollments]
    
    # Deadlines from Assignments
    assign_deadlines = db.session.query(Assignment, Course).join(Course).filter(
        Assignment.course_id.in_(course_ids),
        Assignment.deadline != None,
        Course.is_deleted == False
    ).all()
    
    # Deadlines from Quizzes
    quiz_deadlines = db.session.query(Quiz, Course).join(Course).filter(
        Quiz.course_id.in_(course_ids),
        Quiz.due_date != None,
        Course.is_deleted == False
    ).all()
    
    deadlines = []
    for a, c in assign_deadlines:
        sub = db.session.query(Submission).filter_by(user_id=current_user.id, assignment_id=a.id).first()
        deadlines.append({
            "title": a.title,
            "course": c.title,
            "deadline": a.deadline,
            "type": "Assignment",
            "status": sub.status if sub else "Chưa nộp"
        })
        
    for q, c in quiz_deadlines:
        attempt = db.session.query(QuizAttempt).filter_by(user_id=current_user.id, quiz_id=q.id).first()
        deadlines.append({
            "title": q.title,
            "course": c.title,
            "deadline": q.due_date,
            "type": "Quiz",
            "status": "Đã làm" if attempt else "Chưa làm"
        })
        
    # Sort by deadline safely (handling potential NoneType values)
    from datetime import datetime
    max_datetime = datetime.max
    deadlines.sort(key=lambda x: x["deadline"] if x["deadline"] is not None else max_datetime)
    
    return render_template("calendar.html", deadlines=deadlines)


def _calc_streak(user_id):
    """Calculate consecutive days with at least one lesson completion, counting back from today."""
    from datetime import date, timedelta as td
    rows = db.session.query(
        func.date(LearningLog.timestamp)
    ).filter(
        LearningLog.user_id == user_id,
        LearningLog.action_type == "complete"
    ).distinct().order_by(func.date(LearningLog.timestamp).desc()).all()

    if not rows:
        return 0

    from datetime import datetime
    dates = sorted({r[0] if isinstance(r[0], date) else datetime.strptime(str(r[0]), "%Y-%m-%d").date() for r in rows}, reverse=True)
    streak = 0
    expected = date.today()
    for d in dates:
        if d == expected:
            streak += 1
            expected -= td(days=1)
        elif d < expected:
            break
    return max(streak, 1) if dates else 0


# Import progress calculation helpers from the centralized service layer
from ..services import (
    student_completion_rate,
    class_average_completion_rate,
    update_enrollment_if_completed
)


@bp.route("/certificates")
@login_required
@role_required("student")
def view_certificates():
    certs = db.session.query(Certificate, Course).join(Course).filter(Certificate.user_id == current_user.id).all()
    return render_template("student_certificates.html", certs=certs)


@bp.route("/submissions/<submission_id>/download")
@login_required
@role_required("student")
def download_own_submission_file(submission_id):
    sub = db.session.get(Submission, submission_id)
    if not sub or sub.user_id != current_user.id or not sub.file_path:
        flash("File không tồn tại hoặc bạn không có quyền truy cập.", "error")
        return redirect(url_for("student.dashboard"))

    assignment = db.session.get(Assignment, sub.assignment_id)
    if not assignment:
        flash("Bài tập không tồn tại.", "error")
        return redirect(url_for("student.dashboard"))

    enrollment = db.session.query(Enrollment).filter_by(user_id=current_user.id, course_id=assignment.course_id).first()
    if not enrollment:
        flash("Bạn không có quyền truy cập file này.", "error")
        return redirect(url_for("student.dashboard"))

    from ..services.storage import storage
    try:
        return storage.send_file_response(sub.file_path)
    except NotImplementedError:
        return redirect(storage.secure_get_url(sub.file_path))


@bp.route("/certificates/<cert_code>")
def public_certificate(cert_code):
    cert = (
        db.session.query(Certificate, Course, User)
        .join(Course, Course.id == Certificate.course_id)
        .join(User, User.id == Certificate.user_id)
        .filter(Certificate.cert_code == cert_code)
        .first()
    )
    if not cert:
        return "Chứng chỉ không tồn tại hoặc mã xác thực không đúng.", 404
    if cert[1].is_deleted:
        return "Chứng chỉ không còn khả dụng công khai.", 404
    
    user = cert[2]
    course = cert[1]
    # Strictly verify the student has reached 100% completion rate
    rate = student_completion_rate(user.id, course.id)
    if rate < 100:
        return "Chứng chỉ chưa hợp lệ do khóa học chưa hoàn thành 100%.", 403
        
    return render_template(
        "certificate_view.html",
        cert=cert[0],
        course=course,
        recipient_name=_mask_email(user.email),
    )
