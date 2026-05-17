import csv
import io
import json
import re
import random
import string
import os
from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for, make_response, current_app
from flask_login import current_user
from sqlalchemy import func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import User, Category, Course, SystemSetting, AuditLog, Enrollment
from ..services.audit import log_action
from ..services.settings import flush_settings_cache

bp = Blueprint("admin", __name__, url_prefix="/admin")

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text

# --- User Management ---

@bp.route("/users")
@login_required
@role_required("admin")
def list_users():
    users = db.session.query(User).order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=users)

@bp.post("/users/<user_id>/update_role")
@login_required
@role_required("admin")
def update_user_role(user_id):
    if user_id == current_user.id:
        flash("Bạn không thể tự thay đổi role của chính mình.", "error")
        return redirect(url_for("admin.list_users"))
    user = db.session.get(User, user_id)
    new_role = request.form.get("role")
    if user and new_role in ["student", "teacher", "admin"]:
        old_role = user.role
        user.role = new_role
        db.session.commit()
        log_action("user_role_changed", "User", user_id, {"old": old_role, "new": new_role})
        flash(f"Đã cập nhật role cho {user.email}.", "success")
    return redirect(url_for("admin.list_users"))

@bp.post("/users/<user_id>/delete")
@login_required
@role_required("admin")
def delete_user(user_id):
    if user_id == current_user.id:
        flash("Bạn không thể tự xóa tài khoản của chính mình.", "error")
        return redirect(url_for("admin.list_users"))
    user = db.session.get(User, user_id)
    if user:
        email = user.email
        db.session.delete(user)
        db.session.commit()
        log_action("user_deleted", "User", user_id, {"email": email})
        flash(f"Đã xóa người dùng {email}.", "success")
    return redirect(url_for("admin.list_users"))

@bp.post("/users/<user_id>/toggle_status")
@login_required
@role_required("admin")
def toggle_user_status(user_id):
    if user_id == current_user.id:
        flash("Bạn không thể tự vô hiệu hóa tài khoản của chính mình.", "error")
        return redirect(url_for("admin.list_users"))
        
    user = db.session.get(User, user_id)
    if user:
        user.is_active = not user.is_active
        db.session.commit()
        status_str = "kích hoạt" if user.is_active else "vô hiệu hóa"
        flash(f"Đã {status_str} tài khoản {user.email}.", "success")
        log_action("user_status_changed", "User", user_id, {"new_status": user.is_active})
    return redirect(url_for("admin.list_users"))

# --- Category Management ---

@bp.route("/categories")
@login_required
@role_required("admin")
def list_categories():
    categories = db.session.query(Category).order_by(Category.sort_order.asc()).all()
    return render_template("admin_categories.html", categories=categories)

@bp.post("/categories/new")
@login_required
@role_required("admin")
def create_category():
    name = request.form.get("name")
    icon = request.form.get("icon", "📚")
    description = request.form.get("description", "")
    slug = slugify(name)
    
    # Ensure unique slug
    base_slug = slug
    counter = 1
    while db.session.query(Category).filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
        
    cat = Category(name=name, slug=slug, icon=icon, description=description)
    db.session.add(cat)
    db.session.commit()
    log_action("category_created", "Category", cat.id, {"name": name})
    flash("Đã tạo danh mục mới.", "success")
    return redirect(url_for("admin.list_categories"))

@bp.post("/categories/<cat_id>/edit")
@login_required
@role_required("admin")
def edit_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if cat:
        cat.name = request.form.get("name")
        cat.icon = request.form.get("icon")
        cat.description = request.form.get("description")
        cat.sort_order = int(request.form.get("sort_order", 0))
        db.session.commit()
        flash("Đã cập nhật danh mục.", "success")
    return redirect(url_for("admin.list_categories"))

@bp.post("/categories/<cat_id>/delete")
@login_required
@role_required("admin")
def delete_category(cat_id):
    # Check if any course is using it
    course_count = db.session.query(Course).filter_by(category_id=cat_id).count()
    if course_count > 0:
        flash(f"Không thể xóa danh mục này vì đang có {course_count} khóa học sử dụng.", "error")
        return redirect(url_for("admin.list_categories"))
        
    cat = db.session.get(Category, cat_id)
    if cat:
        db.session.delete(cat)
        db.session.commit()
        flash("Đã xóa danh mục.", "success")
    return redirect(url_for("admin.list_categories"))

# --- System Settings ---

@bp.route("/settings")
@login_required
@role_required("admin")
def view_settings():
    settings = db.session.query(SystemSetting).all()
    return render_template("admin_settings.html", settings=settings)

@bp.post("/settings/update")
@login_required
@role_required("admin")
def update_settings():
    for key, value in request.form.items():
        setting = db.session.query(SystemSetting).filter_by(key=key).first()
        if setting:
            setting.value = value
            
    db.session.commit()
    flush_settings_cache()
    log_action("settings_updated")
    flash("Đã cập nhật cấu hình hệ thống.", "success")
    return redirect(url_for("admin.view_settings"))

# --- Audit Logs ---

@bp.route("/audit-log")
@login_required
@role_required("admin")
def view_audit_log():
    logs = db.session.query(AuditLog, User).outerjoin(User, User.id == AuditLog.actor_id).order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin_audit_log.html", logs=logs)

# --- User Import (Phase 2) ---

@bp.route("/users/import")
@login_required
@role_required("admin")
def import_users_view():
    return render_template("admin_import_users.html")

@bp.post("/users/import")
@login_required
@role_required("admin")
def import_users():
    file = request.files.get("file")
    if not file or not file.filename.endswith('.csv'):
        flash("Vui lòng tải lên file CSV hợp lệ.", "error")
        return redirect(url_for("admin.import_users_view"))
        
    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    csv_input = csv.DictReader(stream)
    
    success_count = 0
    error_count = 0
    results = []
    
    from werkzeug.security import generate_password_hash
    
    for row in csv_input:
        email = row.get("email")
        role = row.get("role", "student")
        
        if not email or "@" not in email:
            error_count += 1
            results.append({"email": email, "status": "Lỗi", "reason": "Email không hợp lệ"})
            continue
            
        exists = db.session.query(User).filter_by(email=email).first()
        if exists:
            error_count += 1
            results.append({"email": email, "status": "Bỏ qua", "reason": "Email đã tồn tại"})
            continue
            
        # Generate random password
        temp_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        user = User(
            email=email,
            password_hash=generate_password_hash(temp_pass),
            role=role
        )
        db.session.add(user)
        success_count += 1
        results.append({"email": email, "temp_pass": temp_pass, "status": "Thành công"})
        
    db.session.commit()
    log_action("bulk_import", detail={"success": success_count, "errors": error_count})
    
    flash(f"Import hoàn tất: {success_count} thành công, {error_count} lỗi/bỏ qua.", "success")
    return render_template("admin_import_results.html", results=results)

# --- Course Approval (Phase 2) ---

@bp.route("/courses/pending")
@login_required
@role_required("admin")
def pending_courses():
    courses = db.session.query(Course, User).join(User, User.id == Course.teacher_id).filter(Course.status == "pending_review").all()
    return render_template("admin_pending_courses.html", courses=courses)

@bp.post("/courses/<course_id>/approve")
@login_required
@role_required("admin")
def approve_course(course_id):
    course = db.session.get(Course, course_id)
    if course:
        course.status = "published"
        course.published_at = datetime.utcnow()
        db.session.commit()
        
        from ..services.notifications import notify
        notify(course.teacher_id, "announcement", f"Khóa học của bạn '{course.title}' đã được duyệt và xuất bản!", url_for("teacher.manage_courses"))
        log_action("course_approved", "Course", course_id)
        flash("Đã duyệt khóa học.", "success")
    return redirect(url_for("admin.pending_courses"))

@bp.post("/courses/<course_id>/reject")
@login_required
@role_required("admin")
def reject_course(course_id):
    course = db.session.get(Course, course_id)
    note = request.form.get("rejection_note")
    if course:
        course.status = "rejected"
        course.rejection_note = note
        db.session.commit()
        
        from ..services.notifications import notify
        notify(course.teacher_id, "announcement", f"Khóa học '{course.title}' bị từ chối duyệt. Lý do: {note}", url_for("teacher.manage_courses"))
        log_action("course_rejected", "Course", course_id, {"reason": note})
        flash("Đã từ chối khóa học.", "info")
    return redirect(url_for("admin.pending_courses"))

@bp.route("/seed")
def seed_system():
    # Allow seeding without login ONLY if no users exist in the DB
    user_count = db.session.query(User).count()
    if user_count > 0:
        # If users exist, require admin role
        from flask_login import current_user
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Bạn cần quyền Admin để chạy lại lệnh Seed.", "error")
            return redirect(url_for("auth.login"))

    # Security: Only allow seeding in development
    app_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "production")).lower()
    if app_env != "development":
        flash("Tính năng khởi tạo dữ liệu chỉ khả dụng trong môi trường Development.", "error")
        return "Forbidden: This action is only allowed in development environment.", 403
        
    # Seed Categories
    cats = [
        {"name": "Công nghệ thông tin", "slug": "it", "icon": "💻", "sort_order": 1},
        {"name": "Kinh doanh & Khởi nghiệp", "slug": "business", "icon": "📈", "sort_order": 2},
        {"name": "Ngoại ngữ", "slug": "languages", "icon": "🌍", "sort_order": 3},
        {"name": "Thiết kế đồ họa", "slug": "design", "icon": "🎨", "sort_order": 4}
    ]
    for c_data in cats:
        if not db.session.query(Category).filter_by(slug=c_data["slug"]).first():
            db.session.add(Category(**c_data))
            
    # Seed Settings
    settings = [
        {"key": "site_name", "value": "E16 LMS", "description": "Tên nền tảng hiển thị trên tiêu đề và sidebar."},
        {"key": "site_logo_url", "value": "https://images.unsplash.com/photo-1614850523296-d8c1af93d400?q=80&w=2070&auto=format&fit=crop", "description": "URL ảnh logo của hệ thống."},
        {"key": "allow_registration", "value": "True", "description": "Cho phép người dùng tự đăng ký tài khoản."},
        {"key": "require_course_approval", "value": "True", "description": "Yêu cầu admin duyệt khóa học trước khi xuất bản."}
    ]
    for s_data in settings:
        if not db.session.query(SystemSetting).filter_by(key=s_data["key"]).first():
            db.session.add(SystemSetting(**s_data))

    # Seed Users
    from werkzeug.security import generate_password_hash
    users = [
        {"email": "admin@e16.local", "password_hash": generate_password_hash("admine16"), "role": "admin"},
        {"email": "teacher@e16.local", "password_hash": generate_password_hash("teachere16"), "role": "teacher"},
        {"email": "student@e16.local", "password_hash": generate_password_hash("studente16"), "role": "student"}
    ]
    for u_data in users:
        if not db.session.query(User).filter_by(email=u_data["email"]).first():
            db.session.add(User(**u_data))
            
    seed_password = os.getenv("E16_SEED_PASSWORD", "demo-password")
    for i in range(1, 6):
        email = f"student{i}@e16.local"
        if not db.session.query(User).filter_by(email=email).first():
            db.session.add(User(email=email, password_hash=generate_password_hash(seed_password), role="student"))

    db.session.commit()
    flush_settings_cache()
    flash("Đã khởi tạo dữ liệu mẫu hệ thống thành công.", "success")
    return redirect(url_for("admin.view_settings"))
