# -*- coding: utf-8 -*-
from datetime import timedelta
import os
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from sqlalchemy import func

from ..auth_utils import role_required
from ..extensions import db
from ..models import User, Course, Enrollment, LearningLog
from ..services.audit import log_action
from ..time_utils import utcnow

bp = Blueprint("analytics", __name__, url_prefix="/analytics")


def _export_max_rows() -> int:
    return max(1, int(os.getenv("EXPORT_MAX_ROWS", "50000")))


@bp.route("/")
@login_required
@role_required("admin")
def dashboard():
    days = int(request.args.get("range", 30))
    now = utcnow()
    start_date = now - timedelta(days=days)
    
    # Summary Stats
    total_users = db.session.query(User).count()
    total_teachers = db.session.query(User).filter_by(role="teacher").count()
    total_students = db.session.query(User).filter_by(role="student").count()
    total_courses = db.session.query(Course).filter_by(status="published", is_deleted=False).count()
    total_enrollments = db.session.query(Enrollment).count()
    today_logs = db.session.query(LearningLog).filter(LearningLog.timestamp >= now.replace(hour=0, minute=0, second=0, microsecond=0)).count()
    
    # Growth Data (Line Chart)
    user_growth = db.session.query(
        func.date(User.created_at).label('date'),
        func.count(User.id).label('count')
    ).filter(User.created_at >= start_date).group_by('date').all()
    
    # Enrollment Trend (Bar Chart)
    enroll_trend = db.session.query(
        func.date(Enrollment.enrolled_at).label('date'),
        func.count(Enrollment.id).label('count')
    ).filter(Enrollment.enrolled_at >= start_date).group_by('date').all()
    
    # Top 5 Courses (Horizontal Bar)
    top_courses = db.session.query(
        Course.title,
        func.count(Enrollment.id).label('enroll_count')
    ).join(Enrollment).filter(Course.is_deleted == False).group_by(Course.id).order_by(func.count(Enrollment.id).desc()).limit(5).all()
    
    return render_template(
        "admin_analytics.html",
        range=days,
        total_users=total_users,
        total_teachers=total_teachers,
        total_students=total_students,
        total_courses=total_courses,
        total_enrollments=total_enrollments,
        today_logs=today_logs,
        user_growth=user_growth,
        enroll_trend=enroll_trend,
        top_courses=top_courses
    )

@bp.route("/export")
@login_required
@role_required("admin")
def export_csv():
    import csv
    import zipfile
    from io import StringIO, BytesIO
    from flask import Response, request
    from ..models import QuizAttempt, Lesson

    export_type = request.args.get("type", "general").lower()
    max_rows = _export_max_rows()
    log_action("admin_export", "Analytics", export_type, {"max_rows": max_rows})

    if export_type == "general":
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(["Type", "ID", "Title/Email", "Date", "Detail"])
        
        users = db.session.query(User).limit(max_rows).all()
        for u in users:
            cw.writerow(["User", u.id, u.email, u.created_at.strftime("%Y-%m-%d") if u.created_at else "", u.role])
            
        courses = db.session.query(Course).limit(max_rows).all()
        for c in courses:
            cw.writerow(["Course", c.id, c.title, c.created_at.strftime("%Y-%m-%d") if c.created_at else "", c.status])
            
        enrollments = db.session.query(Enrollment).limit(max_rows).all()
        for e in enrollments:
            cw.writerow(["Enrollment", e.id, f"User {e.user_id} - Course {e.course_id}", e.enrolled_at.strftime("%Y-%m-%d") if e.enrolled_at else "", e.status])
            
        output = si.getvalue()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=admin_report.csv"}
        )

    elif export_type == "learning_logs":
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(["log_id", "user_id", "lesson_id", "action_type", "timestamp"])
        
        logs = db.session.query(LearningLog).limit(max_rows).all()
        for l in logs:
            cw.writerow([l.log_id, l.user_id, l.lesson_id, l.action_type, l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else ""])
            
        output = si.getvalue()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=learning_logs_raw.csv"}
        )

    elif export_type == "quiz_attempts":
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(["id", "quiz_id", "user_id", "score", "passed", "attempted_at"])
        
        attempts = db.session.query(QuizAttempt).limit(max_rows).all()
        for a in attempts:
            cw.writerow([a.id, a.quiz_id, a.user_id, a.score, int(a.passed) if a.passed is not None else "", a.attempted_at.strftime("%Y-%m-%d %H:%M:%S") if a.attempted_at else ""])
            
        output = si.getvalue()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=quiz_attempts_raw.csv"}
        )

    elif export_type == "datastudio":
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow([
            'user_id', 'course_title', 'enroll_date', 
            'is_enrolled', 'is_started', 'is_completed', 
            'avg_quiz_score', 'tốc độ học'
        ])
        
        enrollments = db.session.query(Enrollment).limit(max_rows).all()
        for e in enrollments:
            course = db.session.get(Course, e.course_id)
            if not course:
                continue
            
            is_enrolled = 1
            is_completed = 1 if e.status == 'completed' else 0
            
            lesson_ids = [l.id for l in db.session.query(Lesson.id).filter_by(course_id=e.course_id).all()]
            has_logs = False
            if lesson_ids:
                has_logs = db.session.query(LearningLog).filter(
                    LearningLog.user_id == e.user_id,
                    LearningLog.lesson_id.in_(lesson_ids)
                ).first() is not None
                
            is_started = 1 if (has_logs or is_completed == 1) else 0
            
            sql_query = """
                SELECT AVG(qa.score) 
                FROM quiz_attempts qa
                JOIN quizzes q ON qa.quiz_id = q.id
                WHERE qa.user_id = :uid AND q.course_id = :cid
            """
            result = db.session.execute(db.text(sql_query), {"uid": e.user_id, "cid": e.course_id}).scalar()
            avg_quiz_score = round(float(result), 2) if result else 0
            
            toc_do_hoc = "Đang học"
            if is_completed == 1:
                toc_do_hoc = "Bình thường"
            
            enroll_date = e.enrolled_at.strftime("%Y-%m-%d") if e.enrolled_at else ""
            
            cw.writerow([
                e.user_id,
                course.title,
                enroll_date,
                is_enrolled,
                is_started,
                is_completed,
                avg_quiz_score,
                toc_do_hoc
            ])
            
        output = si.getvalue()
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=datastudio_obt.csv"}
        )

    elif export_type == "all":
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. users.csv
            users_si = StringIO()
            users_cw = csv.writer(users_si)
            users_cw.writerow(["id", "email", "role", "is_active", "created_at", "last_login", "login_count"])
            for u in db.session.query(User).limit(max_rows).all():
                users_cw.writerow([
                    u.id, u.email, u.role, int(u.is_active),
                    u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "",
                    u.last_login.strftime("%Y-%m-%d %H:%M:%S") if u.last_login else "",
                    u.login_count or 0
                ])
            zf.writestr("users.csv", users_si.getvalue())

            # 2. courses.csv
            courses_si = StringIO()
            courses_cw = csv.writer(courses_si)
            courses_cw.writerow(["id", "title", "short_description", "status", "category_id", "teacher_id", "created_at"])
            for c in db.session.query(Course).limit(max_rows).all():
                courses_cw.writerow([
                    c.id, c.title, c.short_description, c.status, c.category_id or "", c.teacher_id,
                    c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else ""
                ])
            zf.writestr("courses.csv", courses_si.getvalue())

            # 3. enrollments.csv
            enroll_si = StringIO()
            enroll_cw = csv.writer(enroll_si)
            enroll_cw.writerow(["id", "user_id", "course_id", "enrolled_at", "status"])
            for e in db.session.query(Enrollment).limit(max_rows).all():
                enroll_cw.writerow([
                    e.id, e.user_id, e.course_id,
                    e.enrolled_at.strftime("%Y-%m-%d %H:%M:%S") if e.enrolled_at else "",
                    e.status
                ])
            zf.writestr("enrollments.csv", enroll_si.getvalue())

            # 4. learning_logs.csv
            logs_si = StringIO()
            logs_cw = csv.writer(logs_si)
            logs_cw.writerow(["log_id", "user_id", "lesson_id", "action_type", "timestamp"])
            for l in db.session.query(LearningLog).limit(max_rows).all():
                logs_cw.writerow([
                    l.log_id, l.user_id, l.lesson_id, l.action_type,
                    l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else ""
                ])
            zf.writestr("learning_logs.csv", logs_si.getvalue())

            # 5. quiz_attempts.csv
            quiz_si = StringIO()
            quiz_cw = csv.writer(quiz_si)
            quiz_cw.writerow(["id", "quiz_id", "user_id", "score", "passed", "attempted_at"])
            for a in db.session.query(QuizAttempt).limit(max_rows).all():
                quiz_cw.writerow([
                    a.id, a.quiz_id, a.user_id, a.score,
                    int(a.passed) if a.passed is not None else "",
                    a.attempted_at.strftime("%Y-%m-%d %H:%M:%S") if a.attempted_at else ""
                ])
            zf.writestr("quiz_attempts.csv", quiz_si.getvalue())

            # 6. datastudio_obt.csv
            ds_si = StringIO()
            ds_cw = csv.writer(ds_si)
            ds_cw.writerow([
                'user_id', 'course_title', 'enroll_date', 
                'is_enrolled', 'is_started', 'is_completed', 
                'avg_quiz_score', 'tốc độ học'
            ])
            for e in db.session.query(Enrollment).limit(max_rows).all():
                course = db.session.get(Course, e.course_id)
                if not course:
                    continue
                is_enrolled = 1
                is_completed = 1 if e.status == 'completed' else 0
                lesson_ids = [l.id for l in db.session.query(Lesson.id).filter_by(course_id=e.course_id).all()]
                has_logs = False
                if lesson_ids:
                    has_logs = db.session.query(LearningLog).filter(
                        LearningLog.user_id == e.user_id,
                        LearningLog.lesson_id.in_(lesson_ids)
                    ).first() is not None
                is_started = 1 if (has_logs or is_completed == 1) else 0
                sql_query = """
                    SELECT AVG(qa.score) 
                    FROM quiz_attempts qa
                    JOIN quizzes q ON qa.quiz_id = q.id
                    WHERE qa.user_id = :uid AND q.course_id = :cid
                """
                result = db.session.execute(db.text(sql_query), {"uid": e.user_id, "cid": e.course_id}).scalar()
                avg_quiz_score = round(float(result), 2) if result else 0
                toc_do_hoc = "Đang học"
                if is_completed == 1:
                    toc_do_hoc = "Bình thường"
                enroll_date = e.enrolled_at.strftime("%Y-%m-%d") if e.enrolled_at else ""
                ds_cw.writerow([e.user_id, course.title, enroll_date, is_enrolled, is_started, is_completed, avg_quiz_score, toc_do_hoc])
            zf.writestr("datastudio_obt.csv", ds_si.getvalue())

        memory_file.seek(0)
        return Response(
            memory_file.getvalue(),
            mimetype="application/zip",
            headers={"Content-Disposition": "attachment;filename=e16_analyst_data.zip"}
        )
