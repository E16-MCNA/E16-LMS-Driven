import csv
import io
from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for, make_response, jsonify
from flask_login import current_user
from sqlalchemy import func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import Course, Enrollment, Lesson, Quiz, Question, Choice, Assignment, Submission, User, QuizAttempt
from ..services.audit import log_action

bp = Blueprint("teacher", __name__, url_prefix="/teacher")


@bp.route("/dashboard")
@login_required
@role_required("teacher")
def dashboard():
    courses = db.session.query(Course).filter(Course.teacher_id == current_user.id).all()
    total_courses = len(courses)
    
    course_ids = [c.id for c in courses]
    total_students = 0
    total_lessons = 0
    if course_ids:
        total_students = db.session.query(Enrollment).filter(Enrollment.course_id.in_(course_ids)).count()
        total_lessons = db.session.query(Lesson).filter(Lesson.course_id.in_(course_ids)).count()
        
    return render_template("teacher_dashboard.html", 
                           courses=courses[:5], 
                           total_courses=total_courses, 
                           total_students=total_students,
                           total_lessons=total_lessons)

@bp.route("/manage")
@login_required
@role_required("teacher")
def manage_courses():
    courses = db.session.query(Course).filter(Course.teacher_id == current_user.id).all()
    return render_template("manage_courses.html", courses=courses)


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
    if not course or course.teacher_id != current_user.id:
        flash("Không tìm thấy khóa học hoặc bạn không có quyền chỉnh sửa.", "error")
        return redirect(url_for("teacher.manage_courses"))
        
    if request.method == "POST":
        course.title = request.form.get("title")
        course.short_description = request.form.get("short_description")
        course.description = request.form.get("description")
        course.cover_image_url = request.form.get("cover_image_url")
        # Note: status is managed by submit_course or admin approve/reject
        course.category_id = request.form.get("category_id")
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
    if not course or course.teacher_id != current_user.id:
        return "Unauthorized", 403
    
    # Validation: Ensure course has at least one lesson
    from ..models import Lesson
    lesson_count = db.session.query(Lesson).filter_by(course_id=course_id).count()
    if lesson_count == 0:
        flash("Bạn cần thêm ít nhất một bài học trước khi gửi duyệt.", "error")
        return redirect(url_for("teacher.manage_courses"))
        
    course.status = "pending_review"
    course.submitted_at = datetime.utcnow()
    db.session.commit()
    
    from ..services.audit import log_action
    log_action("course_submitted", "Course", course_id)
    flash("Khóa học đã được gửi cho Admin duyệt.", "success")
    return redirect(url_for("teacher.manage_courses"))


@bp.route("/courses/<course_id>/delete", methods=["POST"])
@login_required
@role_required("teacher")
def delete_course(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
        return "Unauthorized", 403
        
    db.session.delete(course)
    db.session.commit()
    flash("Đã xóa khóa học.", "info")
    return redirect(url_for("teacher.manage_courses"))


@bp.route("/courses/<course_id>/students")
@login_required
@role_required("teacher")
def course_students(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
        
    enrollments = db.session.query(Enrollment, User).join(User, User.id == Enrollment.user_id).filter(Enrollment.course_id == course_id).all()
    
    # Tính toán tiến độ từng học viên
    from ..models import LearningLog, Lesson
    progress_map = {}
    if course.total_lessons > 0:
        for en, u in enrollments:
            completed = db.session.query(LearningLog).join(Lesson, Lesson.id == LearningLog.lesson_id).filter(
                LearningLog.user_id == u.id,
                LearningLog.action_type == "complete",
                Lesson.course_id == course_id
            ).count()
            progress_map[u.id] = int((completed / course.total_lessons) * 100)
    else:
        for en, u in enrollments:
            progress_map[u.id] = 0
            
    return render_template("course_students.html", course=course, enrollments=enrollments, progress_map=progress_map)


@bp.route("/courses/<course_id>/lessons")
@login_required
@role_required("teacher")
def manage_lessons(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
    lessons = db.session.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.sequence_order.asc()).all()
    return render_template("manage_lessons.html", course=course, lessons=lessons)


@bp.post("/courses/<course_id>/lessons/new")
@login_required
@role_required("teacher")
def create_lesson(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
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
    if not course or course.teacher_id != current_user.id:
        return "Unauthorized", 403
        
    lesson_ids = request.form.getlist("lesson_ids[]")
    for index, l_id in enumerate(lesson_ids):
        lesson = db.session.get(Lesson, l_id)
        if lesson and lesson.course_id == course_id:
            lesson.order = index + 1
            
    db.session.commit()
    return jsonify({"status": "success"})


@bp.route("/courses/<course_id>/lessons/<lesson_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def edit_lesson(course_id, lesson_id):
    course = db.session.get(Course, course_id)
    lesson = db.session.get(Lesson, lesson_id)
    if not course or not lesson or course.teacher_id != current_user.id:
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
    if course and lesson and course.teacher_id == current_user.id:
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
    if not course or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
    quizzes = db.session.query(Quiz).filter_by(course_id=course_id).all()
    return render_template("manage_quizzes.html", course=course, quizzes=quizzes)


@bp.route("/courses/<course_id>/quizzes/new", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def create_quiz(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
        
    if request.method == "POST":
        quiz = Quiz(
            course_id=course_id,
            title=request.form.get("title"),
            pass_score=int(request.form.get("pass_score", 80)),
            max_attempts=int(request.form.get("max_attempts", 3)),
            time_limit=int(request.form.get("time_limit", 0)),
            random_question_count=int(request.form.get("random_question_count", 0))
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
    if not course or not quiz or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
        
    if request.method == "POST":
        quiz.title = request.form.get("title")
        quiz.pass_score = int(request.form.get("pass_score"))
        quiz.max_attempts = int(request.form.get("max_attempts"))
        quiz.time_limit = int(request.form.get("time_limit", 0))
        quiz.random_question_count = int(request.form.get("random_question_count", 0))
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
    if not quiz: return redirect(url_for("teacher.manage_courses"))
    
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
        students = db.session.query(Enrollment).filter_by(course_id=quiz.course_id).all()
        for en in students:
            notify(en.user_id, "new_quiz", f"Bài trắc nghiệm mới: {quiz.title}", url_for("student.take_quiz", course_id=quiz.course_id, quiz_id=quiz.id))

    return redirect(url_for("teacher.edit_quiz", course_id=quiz.course_id, quiz_id=quiz_id))


# --- Assignment & Grading ---

@bp.route("/courses/<course_id>/assignments")
@login_required
@role_required("teacher")
def manage_assignments(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
    assignments = db.session.query(Assignment).filter_by(course_id=course_id).all()
    return render_template("manage_assignments.html", course=course, assignments=assignments)


@bp.route("/courses/<course_id>/assignments/new", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def create_assignment(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
        
    if request.method == "POST":
        deadline_str = request.form.get("deadline")
        deadline = datetime.fromisoformat(deadline_str) if deadline_str else None
        
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
        students = db.session.query(Enrollment).filter_by(course_id=course_id).all()
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
    course = db.session.get(Course, assignment.course_id)
    if not assignment or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
        
    status_filter = request.args.get("status")
    query = db.session.query(Submission, User).join(User, User.id == Submission.user_id).filter(Submission.assignment_id == assignment_id)
    
    if status_filter:
        query = query.filter(Submission.status == status_filter)
        
    submissions = query.all()
    return render_template("view_submissions.html", assignment=assignment, submissions=submissions, course=course)


@bp.post("/submissions/<submission_id>/grade")
@login_required
@role_required("teacher")
def grade_submission(submission_id):
    sub = db.session.get(Submission, submission_id)
    assignment = db.session.get(Assignment, sub.assignment_id)
    course = db.session.get(Course, assignment.course_id)
    
    if not sub or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
        
    score = int(request.form.get("score", 0))
    feedback = request.form.get("feedback")
    
    from ..services import GradingService
    GradingService.grade_assignment_submission(submission_id, score, feedback, current_user.id)

    # Notify student
    from ..services.notifications import notify
    notify(sub.user_id, "graded", f"Bài tập '{assignment.title}' của bạn đã được chấm điểm: {sub.score}/100", url_for("student.submit_assignment", course_id=course.id, assignment_id=assignment.id))

    flash(f"Đã chấm điểm cho học viên.", "success")
    return redirect(url_for("teacher.view_submissions", assignment_id=assignment.id))


@bp.route("/assignments/<assignment_id>/export")
@login_required
@role_required("teacher")
def export_grades(assignment_id):
    assignment = db.session.get(Assignment, assignment_id)
    if not assignment: return redirect(url_for("teacher.manage_courses"))
    
    submissions = db.session.query(Submission, User).join(User, User.id == Submission.user_id).filter(Submission.assignment_id == assignment_id).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Email', 'Submitted At', 'Score', 'Status', 'Feedback'])
    
    for sub, user in submissions:
        writer.writerow([user.email, sub.submitted_at, sub.score, sub.status, sub.feedback])
        
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=grades_{assignment_id}.csv"
    response.headers["Content-type"] = "text/csv"
    return response


# --- Gradebook & Analytics ---

@bp.route("/courses/<course_id>/gradebook")
@login_required
@role_required("teacher")
def view_gradebook(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
        
    students = db.session.query(User).join(Enrollment, Enrollment.user_id == User.id).filter(Enrollment.course_id == course_id).all()
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
    if not course or course.teacher_id != current_user.id: return redirect(url_for("teacher.manage_courses"))
    
    students = db.session.query(User).join(Enrollment, Enrollment.user_id == User.id).filter(Enrollment.course_id == course_id).all()
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
    return response


@bp.route("/courses/<course_id>/analytics")
@login_required
@role_required("teacher")
def course_analytics(course_id):
    course = db.session.get(Course, course_id)
    if not course or course.teacher_id != current_user.id:
        return redirect(url_for("teacher.manage_courses"))
        
    from ..models import LearningLog, QuizAttempt
    lessons = db.session.query(Lesson).filter_by(course_id=course_id).order_by(Lesson.sequence_order.asc()).all()
    enrollment_count = db.session.query(Enrollment).filter_by(course_id=course_id).count()
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
        
    # Quiz averages
    quizzes = db.session.query(Quiz).filter_by(course_id=course_id).all()
    quiz_stats = []
    for q in quizzes:
        avg = db.session.query(func.avg(QuizAttempt.score)).filter_by(quiz_id=q.id).scalar() or 0
        quiz_stats.append({"title": q.title, "avg": round(float(avg), 1)})
        
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


def recalc_total_lessons(course_id):
    count = db.session.query(Lesson).filter_by(course_id=course_id).count()
    course = db.session.get(Course, course_id)
    if course:
        course.total_lessons = count
        db.session.commit()
