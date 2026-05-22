# -*- coding: utf-8 -*-
"""
Blueprint for Lễ tân (Receptionist) role.
Provides: student search, profile detail viewing (courses, progress, certificates),
direct enrollment (cash simulation), and quick student account creation.
"""
import random
import string
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from ..auth_utils import role_required
from ..extensions import db
from ..models import User, Course, Enrollment, LearningLog, Lesson, Certificate
from ..services.audit import log_action
from ..time_utils import utcnow
from ..urls import app_url_for

bp = Blueprint("le_tan", __name__, url_prefix="/le-tan")


def _gen_temp_password(length: int = 10) -> str:
    """Generate a random temporary password."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def _send_welcome_email(email: str, temp_password: str, role: str):
    """Try to send a welcome email. Falls back silently to debug logger."""
    try:
        if current_app.config.get("MAIL_USERNAME"):
            from ..services.mail import send_email
            send_email(
                to=email,
                subject="E16 LMS — Tài khoản mới tạo tại Quầy",
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
                    f"[Lễ tân Welcome Email] to={email}: temp_password={temp_password}"
                )
    except Exception as e:
        current_app.logger.error(f"Failed to send welcome email to {email}: {e}")


# ── Dashboard ────────────────────────────────────────────
@bp.route("/dashboard")
@login_required
@role_required("le_tan", "admin")
def dashboard():
    # Show active students, active courses and count of registrations
    total_students = db.session.query(User).filter_by(role="student").count()
    active_courses = db.session.query(Course).filter(
        Course.status.in_(["published", "running"]),
        Course.is_deleted == False
    ).count()
    total_enrollments = db.session.query(Enrollment).count()

    # Recent 5 students created or registered
    recent_students = (
        db.session.query(User)
        .filter_by(role="student")
        .order_by(User.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "letan_dashboard.html",
        total_students=total_students,
        active_courses=active_courses,
        total_enrollments=total_enrollments,
        recent_students=recent_students
    )


# ── Tra cứu & Quản lý Học viên ────────────────────────────
@bp.route("/students")
@login_required
@role_required("le_tan", "admin")
def list_students():
    query_str = request.args.get("q", "").strip()
    if query_str:
        students = (
            db.session.query(User)
            .filter(
                User.role == "student",
                (User.email.like(f"%{query_str}%")) | (User.phone.like(f"%{query_str}%"))
            )
            .order_by(User.created_at.desc())
            .all()
        )
    else:
        students = (
            db.session.query(User)
            .filter_by(role="student")
            .order_by(User.created_at.desc())
            .limit(50)
            .all()
        )
    return render_template("letan_students.html", students=students, query=query_str)


@bp.route("/students/<user_id>", methods=["GET", "POST"])
@login_required
@role_required("le_tan", "admin")
def student_detail(user_id):
    student = db.session.query(User).filter_by(id=user_id, role="student").first_or_404()

    if request.method == "POST":
        # Receptionist is allowed to update phone and check status
        phone = request.form.get("phone", "").strip() or None
        is_active = request.form.get("is_active") == "y"

        student.phone = phone
        student.is_active = is_active
        db.session.commit()

        log_action("student_updated_by_letan", "User", student.id, {
            "email": student.email,
            "phone": phone,
            "is_active": is_active,
            "actor": current_user.email
        })
        flash("Cập nhật thông tin học viên thành công.", "success")
        return redirect(url_for("le_tan.student_detail", user_id=student.id))

    # Get enrollments with their details and calculate progress
    enrollments_data = []
    enrollments = db.session.query(Enrollment).filter_by(user_id=student.id).all()
    for enroll in enrollments:
        course = db.session.get(Course, enroll.course_id)
        if not course:
            continue

        total_lessons = db.session.query(Lesson).filter_by(course_id=course.id).count()
        completed_lessons = 0
        if total_lessons > 0:
            lesson_ids = [l.id for l in db.session.query(Lesson.id).filter_by(course_id=course.id).all()]
            completed_lessons = db.session.query(LearningLog).filter(
                LearningLog.user_id == student.id,
                LearningLog.action_type == "complete",
                LearningLog.lesson_id.in_(lesson_ids)
            ).distinct(LearningLog.lesson_id).count()

        progress = int((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0

        cert = db.session.query(Certificate).filter_by(user_id=student.id, course_id=course.id).first()

        enrollments_data.append({
            "id": enroll.id,
            "course_title": course.title,
            "price": course.price,
            "enrolled_at": enroll.enrolled_at,
            "status": enroll.status,
            "progress": progress,
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
            "cert_code": cert.cert_code if cert else None
        })

    return render_template("letan_students.html", student=student, enrollments=enrollments_data)


# ── Đăng ký học trực tiếp tại quầy ───────────────────────────
@bp.route("/enroll", methods=["GET", "POST"])
@login_required
@role_required("le_tan", "admin")
def enroll_student():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        course_id = (request.form.get("course_id") or "").strip()

        student = db.session.query(User).filter_by(email=email, role="student").first()
        if not student:
            flash(f"Không tìm thấy học viên với email: {email}. Vui lòng tạo tài khoản trước.", "error")
            return redirect(url_for("le_tan.enroll_student", email=email))

        course = db.session.get(Course, course_id)
        if not course or course.is_deleted or course.status not in ("published", "running"):
            flash("Khóa học không khả dụng hoặc chưa được công bố.", "error")
            return redirect(url_for("le_tan.enroll_student"))

        from ..services.payment import can_enroll
        ok, msg = can_enroll(course, student)
        if not ok:
            flash(f"Không thể ghi danh vào khóa học: {msg}", "error")
            return redirect(url_for("le_tan.enroll_student"))

        existing = db.session.query(Enrollment).filter_by(
            user_id=student.id, course_id=course.id
        ).first()

        if existing:
            if existing.status in ("active", "completed"):
                flash(f"Học viên đã tham gia khóa học này (Trạng thái: {existing.status}).", "info")
            else:
                existing.status = "active"
                existing.enrolled_at = utcnow()
                existing.amount_paid = course.price if course else 0
                existing.payment_method = "cash_at_frontdesk"
                existing.approved_by = current_user.id
                existing.approved_at = utcnow()
                existing.rejected_reason = None
                existing.refunded_at = None

                # Financial Ledger entry
                from ..models import PaymentTransaction
                tx = PaymentTransaction(
                    enrollment_id=existing.id,
                    user_id=student.id,
                    course_id=course.id,
                    amount=course.price if course else 0,
                    payment_method="cash_at_frontdesk",
                    status="approved",
                    processed_by=current_user.id,
                    processed_at=utcnow(),
                    notes="Lễ tân ghi danh trực tiếp bằng tiền mặt tại quầy"
                )
                db.session.add(tx)

                db.session.commit()
                log_action("enrollment_activated_by_letan", "Enrollment", existing.id, {
                    "student_email": student.email,
                    "course_title": course.title,
                    "payment_method": "cash_at_frontdesk"
                })
                flash(f"Đã kích hoạt lại quyền tham gia khóa học '{course.title}' cho {student.email}.", "success")
        else:
            new_enroll = Enrollment(
                user_id=student.id,
                course_id=course.id,
                status="active",
                enrolled_at=utcnow(),
                amount_paid=course.price if course else 0,
                payment_method="cash_at_frontdesk",
                approved_by=current_user.id,
                approved_at=utcnow(),
            )
            db.session.add(new_enroll)
            db.session.flush()

            # Financial Ledger entry
            from ..models import PaymentTransaction
            tx = PaymentTransaction(
                enrollment_id=new_enroll.id,
                user_id=student.id,
                course_id=course.id,
                amount=course.price if course else 0,
                payment_method="cash_at_frontdesk",
                status="approved",
                processed_by=current_user.id,
                processed_at=utcnow(),
                notes="Lễ tân ghi danh trực tiếp bằng tiền mặt tại quầy"
            )
            db.session.add(tx)

            db.session.commit()
            log_action("enrollment_created_by_letan", "Enrollment", new_enroll.id, {
                "student_email": student.email,
                "course_title": course.title,
                "payment_method": "cash_at_frontdesk"
            })
            flash(f"Đăng ký trực tiếp và kích hoạt khóa học '{course.title}' cho học viên {student.email} thành công.", "success")

        return redirect(url_for("le_tan.student_detail", user_id=student.id))

    courses = (
        db.session.query(Course)
        .filter(Course.status.in_(["published", "running"]), Course.is_deleted == False)
        .order_by(Course.title)
        .all()
    )
    prefill_email = request.args.get("email", "")
    return render_template("letan_enroll.html", courses=courses, prefill_email=prefill_email)


# ── Tạo tài khoản Học viên mới ─────────────────────────────
@bp.route("/students/create", methods=["GET", "POST"])
@login_required
@role_required("le_tan", "admin")
def create_student():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip() or None

        if not email or "@" not in email:
            flash("Email không hợp lệ.", "error")
            return redirect(url_for("le_tan.create_student"))

        if db.session.query(User).filter_by(email=email).first():
            flash("Email đã tồn tại trong hệ thống.", "error")
            return redirect(url_for("le_tan.create_student"))

        temp_pass = _gen_temp_password()
        hashed = generate_password_hash(temp_pass)

        new_user = User(
            email=email,
            password_hash=hashed,
            phone=phone,
            role="student",
            must_change_password=True,
            created_by=current_user.id,
            temp_password_hash=hashed
        )
        db.session.add(new_user)
        db.session.commit()

        _send_welcome_email(email, temp_pass, "student")

        log_action("student_created_by_letan", "User", new_user.id, {
            "email": email,
            "created_by": current_user.email
        })

        flash(f"Tạo tài khoản học viên mới thành công cho {email}. Mật khẩu tạm: {temp_pass}", "success")

        # Check if receptionist wants to register this user to a course immediately
        if request.form.get("enroll_now") == "y":
            return redirect(url_for("le_tan.enroll_student", email=email))

        return redirect(url_for("le_tan.student_detail", user_id=new_user.id))

    return render_template("letan_create_student.html")


@bp.post("/students/<user_id>/reset-password")
@login_required
@role_required("le_tan", "admin")
def reset_student_password(user_id):
    student = db.session.query(User).filter_by(id=user_id, role="student").first_or_404()

    temp_pass = _gen_temp_password()
    hashed = generate_password_hash(temp_pass)

    student.password_hash = hashed
    student.temp_password_hash = hashed
    student.must_change_password = True
    student.is_active = True
    db.session.commit()

    _send_welcome_email(student.email, temp_pass, "student")

    log_action("student_password_reset_by_letan", "User", student.id, {
        "email": student.email,
        "actor": current_user.email
    })

    flash(f"Đã cấp lại mật khẩu tạm thành công cho học sinh {student.email}: {temp_pass}", "success")
    return redirect(url_for("le_tan.student_detail", user_id=student.id))
