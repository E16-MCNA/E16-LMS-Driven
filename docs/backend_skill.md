# SKILL: Backend — Flask Blueprints & Routes

> Layer: `e16_app/blueprints/`  
> Stack: Flask, Flask-Login, Flask-WTF, Flask-Limiter  
> Áp dụng khi: thêm route mới, sửa blueprint, thêm auth middleware, xử lý request/response

---

## 1. Nguyên tắc cốt lõi

### Blueprint chỉ làm 4 việc
1. Parse và validate request (query params, form data, JSON body)
2. Kiểm tra authentication và authorization
3. Gọi service layer để thực thi business logic
4. Trả response (render template, redirect, JSON)

**Không** để business logic, database query phức tạp, hoặc email/notification logic nằm trong blueprint.

---

## 2. Cấu trúc blueprint chuẩn

```
e16_app/blueprints/
├── auth.py          # login, logout, register, reset_password, oauth
├── admin.py         # user management, course approval, audit, metrics, seed
├── teacher.py       # course CRUD, lesson, quiz, assignment, gradebook, analytics
├── student.py       # catalog, enrollment, lesson view, quiz attempt, certificate
├── analytics.py     # dashboard data, export CSV/Excel
└── communication.py # forum, announcement, notification
```

### Đăng ký blueprint trong app factory
```python
# e16_app/__init__.py
def create_app(config_name=None):
    app = Flask(__name__)
    # ...
    from .blueprints.auth import auth_bp
    from .blueprints.admin import admin_bp
    from .blueprints.teacher import teacher_bp
    from .blueprints.student import student_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(student_bp, url_prefix='/student')
```

---

## 3. Route skeleton chuẩn

```python
# e16_app/blueprints/teacher.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from e16_app.services.course import CourseService
from e16_app.utils import require_role, paginate_query

teacher_bp = Blueprint('teacher', __name__)

@teacher_bp.route('/courses')
@login_required
@require_role('teacher', 'admin')          # ① Auth check
def course_list():
    page = request.args.get('page', 1, type=int)
    q    = request.args.get('q', '', type=str).strip()

    courses, total_pages = CourseService.list_by_teacher(  # ② Gọi service
        teacher_id=current_user.id,
        page=page,
        search=q,
    )
    return render_template(                                 # ③ Trả response
        'teacher/courses.html',
        courses=courses,
        page=page,
        total_pages=total_pages,
        q=q,
    )

@teacher_bp.route('/courses/<course_id>/edit', methods=['GET', 'POST'])
@login_required
@require_role('teacher', 'admin')
def edit_course(course_id):
    course = CourseService.get_or_404(course_id)
    _assert_owner(course)                                  # ④ Ownership check

    form = CourseForm(obj=course)
    if form.validate_on_submit():
        CourseService.update(course, form.data)
        flash("Cập nhật khóa học thành công.", "success")
        return redirect(url_for('teacher.course_list'))

    return render_template('teacher/course_edit.html', form=form, course=course)
```

---

## 4. Authorization — 3 tầng kiểm tra

### Tầng 1: Authentication — @login_required
```python
@teacher_bp.route('/courses')
@login_required                 # Redirect về login nếu chưa đăng nhập
def course_list():
    ...
```

### Tầng 2: Role check — @require_role
```python
# e16_app/utils.py
from functools import wraps
from flask import abort
from flask_login import current_user

def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
```

```python
@teacher_bp.route('/courses/new', methods=['GET', 'POST'])
@login_required
@require_role('teacher', 'admin')   # Chỉ teacher hoặc admin
def create_course():
    ...
```

### Tầng 3: Ownership/Enrollment check — trong route body
```python
def _assert_owner(course):
    """Teacher chỉ được sửa course của mình. Admin được sửa tất cả."""
    if current_user.role == 'admin':
        return
    if course.teacher_id != current_user.id:
        abort(403)

def _assert_enrolled(course_id):
    """Student chỉ được xem lesson nếu đã enroll."""
    from e16_app.models import Enrollment
    enr = Enrollment.query.filter_by(
        user_id=current_user.id,
        course_id=course_id,
    ).first()
    if not enr or enr.status not in ('active', 'completed'):
        abort(403)
```

**Mọi route student truy cập nội dung đều phải gọi `_assert_enrolled`.**

---

## 5. Request parsing chuẩn

### Query parameters
```python
page     = request.args.get('page', 1, type=int)          # có default, có type
per_page = request.args.get('per_page', 20, type=int)
q        = request.args.get('q', '', type=str).strip()
status   = request.args.get('status', 'all', type=str)
```

### Form data (WTForms)
```python
form = QuizForm()
if form.validate_on_submit():          # validate + CSRF check tự động
    # form.title.data, form.pass_score.data đã được validate
    ...
```

### JSON body (API endpoint)
```python
@teacher_bp.route('/api/lessons/reorder', methods=['POST'])
@login_required
@require_role('teacher', 'admin')
def reorder_lessons():
    data = request.get_json(silent=True)
    if not data or 'order' not in data:
        return {'error': 'Invalid payload'}, 400
    lesson_ids = data['order']
    if not isinstance(lesson_ids, list):
        return {'error': 'order must be a list'}, 400
    # ...
    return {'ok': True}, 200
```

---

## 6. Response patterns

### Render template
```python
return render_template('teacher/course_detail.html',
    course=course,
    lessons=lessons,
    page=page,
    total_pages=total_pages,
)
```

### Redirect sau POST (PRG pattern — luôn dùng sau state-changing action)
```python
flash("Lưu thành công.", "success")
return redirect(url_for('teacher.course_list'))
```

### JSON response
```python
return {'ok': True, 'data': result}, 200
return {'error': 'Not found'}, 404
```

### File download
```python
from flask import send_file
import io

def download_csv():
    buf = io.BytesIO()
    # ... ghi dữ liệu vào buf
    buf.seek(0)
    return send_file(
        buf,
        mimetype='text/csv; charset=utf-8-sig',    # utf-8-sig cho Excel mở đúng tiếng Việt
        as_attachment=True,
        download_name='gradebook.csv',
    )
```

---

## 7. Error handling chuẩn

### abort() vs raise
```python
# Dùng abort() cho HTTP error
abort(403)    # Forbidden
abort(404)    # Not found — thay vì if not x: return 404

# Dùng raise cho exception nghiệp vụ (bắt trong service)
raise ValueError("Score must be between 0 and 100")
```

### Error handler trong app factory
```python
# e16_app/__init__.py
@app.errorhandler(403)
def forbidden(e):
    return render_template('shared/error.html', code=403,
                           message="Bạn không có quyền truy cập trang này."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('shared/error.html', code=404,
                           message="Trang không tồn tại."), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('shared/error.html', code=500,
                           message="Lỗi hệ thống, vui lòng thử lại."), 500
```

---

## 8. Rate limiting — @limiter.limit

```python
from e16_app import limiter

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")         # Chống brute-force
def login():
    ...

@auth_bp.route('/register', methods=['POST'])
@limiter.limit("3 per hour")
def register():
    ...
```

Rate limit chỉ áp dụng POST/state-changing routes. GET routes không cần trừ khi expensive.

---

## 9. Pagination helper

```python
# e16_app/utils.py
def paginate_query(query, page: int, per_page: int = 20):
    """
    Trả về (items, total_pages).
    Tự động clamp page về range hợp lệ.
    """
    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total_pages
```

```python
# Trong route:
from e16_app.utils import paginate_query

@admin_bp.route('/users')
@login_required
@require_role('admin')
def user_list():
    page = request.args.get('page', 1, type=int)
    q    = request.args.get('q', '')
    query = User.query.filter(User.email.ilike(f'%{q}%')).order_by(User.created_at.desc())
    users, total_pages = paginate_query(query, page)
    return render_template('admin/users.html', users=users, page=page, total_pages=total_pages, q=q)
```

---

## 10. Checklist khi thêm route mới

```
[ ] Có @login_required
[ ] Có @require_role nếu chỉ một số role được dùng
[ ] Có ownership/enrollment check trong body nếu truy cập resource của người khác
[ ] GET params có type= và default=
[ ] Form POST đã qua WTForms validate_on_submit (tự động check CSRF)
[ ] JSON POST check Content-Type và key existence
[ ] Dùng abort(403/404) thay vì return tuple thủ công
[ ] Redirect sau POST thành công (PRG pattern)
[ ] flash() dùng đúng category: success / error / warning / info
[ ] Business logic nằm trong service, không trong route
[ ] Route có test: anonymous → 302, wrong role → 403, happy path → 200/302
```
