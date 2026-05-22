# -*- coding: utf-8 -*-
"""
Blueprint for Kế toán (Accountant) role.
Provides: financial dashboard (revenue summary, chart stats), bank transfer
reconciliation (confirming pending_payment), revenue logs, refunds, and CSV export.
"""
import csv
from io import StringIO
from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from sqlalchemy import func
from ..auth_utils import role_required
from ..extensions import db
from ..models import User, Course, Enrollment
from ..services.audit import log_action
from ..time_utils import utcnow

bp = Blueprint("ke_toan", __name__, url_prefix="/ke-toan")


# ── Financial Dashboard ──────────────────────────────────
@bp.route("/dashboard")
@login_required
@role_required("ke_toan", "admin")
def dashboard():
    # Total Revenue (sum of Course.price for active/completed enrollments)
    total_rev = db.session.query(func.sum(Course.price)).select_from(Enrollment).join(
        Course, Enrollment.course_id == Course.id
    ).filter(
        Enrollment.status.in_(["active", "completed"]),
        Course.is_deleted == False
    ).scalar() or 0
    
    # Count of pending_payment transactions waiting for accountant approval
    pending_count = db.session.query(Enrollment).filter_by(status="pending_payment").count()
    
    # Revenue by Course (grouped by Course Title)
    course_rev_rows = db.session.query(
        Course.title,
        func.count(Enrollment.id).label("sales_count"),
        func.sum(Course.price).label("course_revenue")
    ).select_from(Enrollment).join(
        Course, Enrollment.course_id == Course.id
    ).filter(
        Enrollment.status.in_(["active", "completed"]),
        Course.is_deleted == False
    ).group_by(Course.id, Course.title).order_by(func.sum(Course.price).desc()).all()
    
    # Recent 5 approved enrollments
    recent_transactions = (
        db.session.query(Enrollment)
        .filter(Enrollment.status.in_(["active", "completed"]))
        .order_by(Enrollment.enrolled_at.desc())
        .limit(5)
        .all()
    )
    
    # Get revenue growth data over last 30 days for Chart.js
    now = utcnow()
    start_date = now - timedelta(days=30)
    growth_rows = db.session.query(
        func.date(Enrollment.enrolled_at).label("date"),
        func.sum(Course.price).label("daily_revenue")
    ).select_from(Enrollment).join(
        Course, Enrollment.course_id == Course.id
    ).filter(
        Enrollment.status.in_(["active", "completed"]),
        Enrollment.enrolled_at >= start_date,
        Course.is_deleted == False
    ).group_by(func.date(Enrollment.enrolled_at)).all()
    
    revenue_growth = []
    for r in growth_rows:
        d = r[0]
        d_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
        revenue_growth.append({"date": d_str, "amount": int(r[1])})
        
    return render_template(
        "ketoan_dashboard.html",
        total_revenue=int(total_rev),
        pending_count=pending_count,
        course_revenue=course_rev_rows,
        recent_transactions=recent_transactions,
        revenue_growth=revenue_growth
    )


# ── Đối soát & Duyệt Thanh toán ───────────────────────────
@bp.route("/reconciliation")
@login_required
@role_required("ke_toan", "admin")
def reconciliation():
    # List all enrollments with status 'pending_payment'
    pending_list = (
        db.session.query(Enrollment)
        .filter_by(status="pending_payment")
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    return render_template("ketoan_reconciliation.html", pending_list=pending_list)


@bp.route("/reconciliation/approve/<enroll_id>", methods=["POST"])
@login_required
@role_required("ke_toan", "admin")
def approve_payment(enroll_id):
    enrollment = db.session.get(Enrollment, enroll_id)
    if not enrollment:
        flash("Không tìm thấy thông tin đăng ký khóa học.", "error")
        return redirect(url_for("ke_toan.reconciliation"))
        
    if enrollment.status in ("active", "completed"):
        flash("Đăng ký này đã được xác nhận thanh toán trước đó.", "info")
        return redirect(url_for("ke_toan.reconciliation"))
        
    course = db.session.get(Course, enrollment.course_id)
    student = db.session.get(User, enrollment.user_id)
    
    # Transition to active
    enrollment.status = "active"
    enrollment.enrolled_at = utcnow()  # reset purchase/activation date to now
    db.session.commit()
    
    log_action("payment_approved_by_ketoan", "Enrollment", enrollment.id, {
        "student_email": student.email if student else "",
        "course_title": course.title if course else "",
        "amount": course.price if course else 0,
        "actor": current_user.email
    })
    
    flash(f"Đã duyệt thành công giao dịch đóng tiền cho học viên {student.email if student else ''} học khóa {course.title if course else ''}.", "success")
    return redirect(url_for("ke_toan.reconciliation"))


@bp.route("/reconciliation/reject/<enroll_id>", methods=["POST"])
@login_required
@role_required("ke_toan", "admin")
def reject_payment(enroll_id):
    enrollment = db.session.get(Enrollment, enroll_id)
    if not enrollment:
        flash("Không tìm thấy thông tin đăng ký khóa học.", "error")
        return redirect(url_for("ke_toan.reconciliation"))
        
    course = db.session.get(Course, enrollment.course_id)
    student = db.session.get(User, enrollment.user_id)
    
    # Delete the pending enrollment to release the lock
    db.session.delete(enrollment)
    db.session.commit()
    
    log_action("payment_rejected_by_ketoan", "Enrollment", enroll_id, {
        "student_email": student.email if student else "",
        "course_title": course.title if course else "",
        "actor": current_user.email
    })
    
    flash(f"Đã xóa yêu cầu ghi danh chưa đóng tiền của học viên {student.email if student else ''} đối với khóa {course.title if course else ''}.", "info")
    return redirect(url_for("ke_toan.reconciliation"))


# ── Sổ Thu Chi (Lịch sử thanh toán) ───────────────────────
@bp.route("/revenue")
@login_required
@role_required("ke_toan", "admin")
def revenue():
    # List all successful payments (active/completed enrollments)
    sales = (
        db.session.query(Enrollment)
        .filter(Enrollment.status.in_(["active", "completed"]))
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    return render_template("ketoan_revenue.html", sales=sales)


@bp.route("/refund/<enroll_id>", methods=["POST"])
@login_required
@role_required("ke_toan", "admin")
def refund_enrollment(enroll_id):
    enrollment = db.session.get(Enrollment, enroll_id)
    if not enrollment:
        flash("Không tìm thấy thông tin ghi danh.", "error")
        return redirect(url_for("ke_toan.revenue"))
        
    course = db.session.get(Course, enrollment.course_id)
    student = db.session.get(User, enrollment.user_id)
    
    # Hard refund: delete the enrollment to revoke course access and subtract from revenue
    db.session.delete(enrollment)
    db.session.commit()
    
    log_action("refund_processed_by_ketoan", "Enrollment", enroll_id, {
        "student_email": student.email if student else "",
        "course_title": course.title if course else "",
        "refund_amount": course.price if course else 0,
        "actor": current_user.email
    })
    
    flash(f"Đã hoàn trả học phí thành công cho {student.email if student else ''} và thu hồi quyền truy cập khóa học {course.title if course else ''}.", "success")
    return redirect(url_for("ke_toan.revenue"))


# ── Xuất Báo cáo CSV Tài chính ───────────────────────────
@bp.route("/export-revenue")
@login_required
@role_required("ke_toan", "admin")
def export_revenue():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow([
        "Mã Ghi Danh", "Email Học Viên", "Khóa Học", 
        "Học Phí (VND)", "Trạng Thái", "Ngày Thanh Toán"
    ])
    
    sales = (
        db.session.query(Enrollment)
        .filter(Enrollment.status.in_(["active", "completed"]))
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    
    for s in sales:
        course = db.session.get(Course, s.course_id)
        student = db.session.get(User, s.user_id)
        cw.writerow([
            s.id,
            student.email if student else "N/A",
            course.title if course else "N/A",
            course.price if course else 0,
            "Đã thanh toán" if s.status == "active" else "Hoàn thành khóa học",
            s.enrolled_at.strftime("%d/%m/%Y %H:%M:%S") if s.enrolled_at else ""
        ])
        
    output = si.getvalue()
    log_action("financial_report_exported", "Revenue", "CSV", {"actor": current_user.email})
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=bao_cao_doanh_thu.csv"}
    )
