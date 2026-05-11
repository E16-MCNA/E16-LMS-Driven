import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user
from sqlalchemy import func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import Category, Course, Enrollment, LearningLog, Lesson, Quiz, Question, Choice, QuizAttempt, QuizAnswer, Assignment, Submission, Certificate
from ..services.logging import logger

bp = Blueprint("student", __name__)



@bp.route("/courses")
@login_required
def list_courses():
    query_str = request.args.get("q", "").strip()
    cat_slug = request.args.get("cat", "").strip()
    
    courses_query = db.session.query(Course).filter(Course.status == "published")
    
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
    enrollments = db.session.query(Enrollment).filter(Enrollment.user_id == current_user.id).all()
    rows = []
    total_completed_lessons = 0
    
    for en in enrollments:
        course = db.session.get(Course, en.course_id)
        if not course:
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


@bp.post("/enroll/<course_id>")
@login_required
@role_required("student")
def enroll(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.status != "published":
        flash("Khóa học không khả dụng.", "error")
        return redirect(url_for("student.list_courses"))
        
    exists = db.session.query(Enrollment).filter(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id).first()
    if not exists:
        db.session.add(Enrollment(user_id=current_user.id, course_id=course_id, status="active"))
        db.session.commit()
        logger.log("enroll_course", user_id=current_user.id, user_email=current_user.email, resource_type="course", resource_id=course_id, metadata={"course_title": course.title})
        flash(f"Đăng ký thành công khóa học {course.title}!", "success")
    
    return redirect(url_for("student.learn", course_id=course_id))


@bp.route("/learn/<course_id>")
@login_required
@role_required("student")
def learn(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return redirect(url_for("student.dashboard"))
        
    enrollment = db.session.query(Enrollment).filter(Enrollment.user_id == current_user.id, Enrollment.course_id == course_id).first()
    if not enrollment:
        return redirect(url_for("student.list_courses"))
        
    lessons = db.session.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.sequence_order.asc()).all()
    quizzes = db.session.query(Quiz).filter_by(course_id=course_id, is_published=True).all()
    assignments = db.session.query(Assignment).filter_by(course_id=course_id).all()
    
    if not lessons:
        return redirect(url_for("student.dashboard"))

    selected_id = request.args.get("lesson") or lessons[0].id
    selected_lesson = next((ls for ls in lessons if ls.id == selected_id), lessons[0])
    
    db.session.add(LearningLog(user_id=current_user.id, lesson_id=selected_lesson.id, action_type="start", timestamp=datetime.utcnow()))
    db.session.commit()
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
    exists = db.session.query(LearningLog).filter_by(
        user_id=current_user.id, lesson_id=lesson_id, action_type="complete"
    ).first()
    
    if not exists:
        db.session.add(LearningLog(user_id=current_user.id, lesson_id=lesson_id, action_type="complete", timestamp=datetime.utcnow()))
        db.session.commit()
        logger.log("complete_lesson", user_id=current_user.id, user_email=current_user.email, resource_type="lesson", resource_id=lesson_id, metadata={"course_id": course_id})
        update_enrollment_if_completed(current_user.id, course_id)
        
    return redirect(url_for("student.learn", course_id=course_id, lesson=lesson_id))


# --- Quiz & Assignment Routes for Students ---

@bp.route("/learn/<course_id>/quiz/<quiz_id>", methods=["GET", "POST"])
@login_required
@role_required("student")
def take_quiz(course_id, quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or not quiz.is_published: return redirect(url_for("student.dashboard"))
    
    # Check attempts
    attempts = db.session.query(QuizAttempt).filter_by(user_id=current_user.id, quiz_id=quiz_id).count()
    if attempts >= quiz.max_attempts:
        flash("Bạn đã hết lượt làm bài trắc nghiệm này.", "warning")
        return redirect(url_for("student.learn", course_id=course_id))
        
    if request.method == "POST":
        from ..services import GradingService
        attempt = GradingService.grade_quiz_attempt(current_user.id, quiz_id, request.form.to_dict())
        
        if not attempt:
            flash("Có lỗi xảy ra khi chấm điểm.", "error")
            return redirect(url_for("student.learn", course_id=course_id))

        logger.log("complete_quiz", user_id=current_user.id, user_email=current_user.email, resource_type="quiz", resource_id=quiz_id, metadata={"score": attempt.score, "course_id": course_id})
        return render_template("quiz_result.html", quiz=quiz, attempt=attempt, course_id=course_id)
        
    questions = db.session.query(Question).filter_by(quiz_id=quiz_id).all()
    return render_template("take_quiz.html", quiz=quiz, questions=questions, course_id=course_id)


@bp.route("/learn/<course_id>/assignment/<assignment_id>", methods=["GET", "POST"])
@login_required
@role_required("student")
def submit_assignment(course_id, assignment_id):
    assignment = db.session.get(Assignment, assignment_id)
    if not assignment: return redirect(url_for("student.dashboard"))
    
    existing_sub = db.session.query(Submission).filter_by(user_id=current_user.id, assignment_id=assignment_id).first()
    
    if request.method == "POST":
        if assignment.deadline and datetime.utcnow() > assignment.deadline:
            flash("Đã hết hạn nộp bài.", "error")
            return redirect(url_for("student.learn", course_id=course_id))
            
        from ..services import StorageService
        text_content = request.form.get("text_content")
        file = request.files.get("file")
        file_path = StorageService.save_file(file, "assignments") if file and assignment.allow_file else None
            
        if existing_sub:
            existing_sub.text_content = text_content
            if file_path: existing_sub.file_path = file_path
            existing_sub.submitted_at = datetime.utcnow()
            existing_sub.status = "pending"
        else:
            sub = Submission(
                assignment_id=assignment_id,
                user_id=current_user.id,
                text_content=text_content,
                file_path=file_path
            )
            db.session.add(sub)
        
        db.session.commit()
        flash("Đã nộp bài thành công!", "success")
        return redirect(url_for("student.learn", course_id=course_id))
        
    return render_template("submit_assignment.html", assignment=assignment, submission=existing_sub, course_id=course_id)


@bp.route("/transcript")
@login_required
@role_required("student")
def view_transcript():
    enrollments = db.session.query(Enrollment).filter_by(user_id=current_user.id).all()
    transcript_data = []
    
    for en in enrollments:
        course = db.session.get(Course, en.course_id)
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
        Assignment.deadline != None
    ).all()
    
    # Deadlines from Quizzes
    quiz_deadlines = db.session.query(Quiz, Course).join(Course).filter(
        Quiz.course_id.in_(course_ids),
        Quiz.due_date != None
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
        
    # Sort by deadline
    deadlines.sort(key=lambda x: x["deadline"])
    
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


def student_completion_rate(user_id, course_id):
    total = db.session.query(Lesson).filter_by(course_id=course_id).count()
    if total == 0: return 0
    completed = db.session.query(func.distinct(LearningLog.lesson_id)).join(Lesson).filter(
        LearningLog.user_id == user_id, 
        Lesson.course_id == course_id, 
        LearningLog.action_type == "complete"
    ).count()
    return (completed / total) * 100

def class_average_completion_rate(course_id):
    students = db.session.query(Enrollment.user_id).filter_by(course_id=course_id, status="active").all()
    if not students: return 0
    total_rate = sum(student_completion_rate(s.user_id, course_id) for s in students)
    return total_rate / len(students)

def update_enrollment_if_completed(user_id, course_id):
    rate = student_completion_rate(user_id, course_id)
    if rate >= 100:
        en = db.session.query(Enrollment).filter_by(user_id=user_id, course_id=course_id).first()
        if en and en.status != "completed":
            en.status = "completed"
            
            # Issue Certificate
            exists = db.session.query(Certificate).filter_by(user_id=user_id, course_id=course_id).first()
            if not exists:
                cert = Certificate(user_id=user_id, course_id=course_id)
                db.session.add(cert)
                
                # Notify student
                from ..services.notifications import notify
                notify(user_id, "announcement", f"Chúc mừng! Bạn đã nhận được chứng chỉ hoàn thành khóa học {db.session.get(Course, course_id).title}", url_for("student.view_certificates"))
                
            db.session.commit()


@bp.route("/certificates")
@login_required
@role_required("student")
def view_certificates():
    certs = db.session.query(Certificate, Course).join(Course).filter(Certificate.user_id == current_user.id).all()
    return render_template("student_certificates.html", certs=certs)


@bp.route("/certificates/<cert_code>")
def public_certificate(cert_code):
    cert = db.session.query(Certificate, Course, User).join(Course).join(User, User.id == Certificate.user_id).filter(Certificate.cert_code == cert_code).first()
    if not cert:
        return "Chứng chỉ không tồn tại hoặc mã xác thực không đúng.", 404
    return render_template("certificate_view.html", cert=cert[0], course=cert[1], user=cert[2])
