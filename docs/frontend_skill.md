# SKILL: Frontend — Jinja Templates, CSS, JavaScript

> Layer: `templates/`, `static/css/`, `static/js/`  
> Stack: Jinja2, vanilla JS, Chart.js, Bootstrap-like custom CSS  
> Áp dụng khi: tạo template mới, sửa UI, thêm component, viết JS behavior

---

## 1. Nguyên tắc cốt lõi

### 1.1 Template inheritance — luôn extend base
Mọi template đều phải extend `templates/base.html`. Không viết HTML boilerplate lại.

```html
{% extends "base.html" %}

{% block title %}Tên trang — E16 LMS{% endblock %}

{% block content %}
{# nội dung trang #}
{% endblock %}
```

**Các block có sẵn trong base.html:**
| Block | Dùng cho |
|---|---|
| `title` | `<title>` tag |
| `content` | Nội dung chính |
| `extra_css` | CSS riêng của trang (đặt trong `<head>`) |
| `extra_js` | JS riêng của trang (đặt cuối `<body>`) |

### 1.2 Không dùng inline style
```html
<!-- ❌ Sai -->
<div style="color: red; margin-top: 10px;">

<!-- ✅ Đúng — dùng class từ components.css -->
<div class="text-danger mt-2">
```

Nếu class chưa có → thêm vào `static/css/components.css`, không inline.

### 1.3 Dùng Jinja macro cho component lặp lại
```html
{# Import macro ở đầu template nếu cần #}
{% from "macros/ui.html" import form_field, alert, pagination, badge %}

{# Dùng #}
{{ form_field(form.email, label="Email") }}
{{ badge("Đã hoàn thành", type="success") }}
{{ pagination(page, total_pages, endpoint="student.catalog") }}
```

---

## 2. Cấu trúc thư mục templates

```
templates/
├── base.html                  # Layout chính, nav, flash messages
├── macros/
│   └── ui.html                # Macro: form_field, alert, badge, pagination, card
├── auth/
│   ├── login.html
│   ├── register.html
│   └── reset_password.html
├── admin/
│   ├── dashboard.html
│   ├── users.html             # Có pagination, search
│   └── courses.html
├── teacher/
│   ├── dashboard.html
│   ├── course_detail.html
│   └── gradebook.html
├── student/
│   ├── catalog.html
│   ├── lesson.html
│   └── quiz.html
└── shared/
    ├── pagination.html        # Reusable pagination block
    ├── empty_state.html       # Khi list rỗng
    └── error.html             # 403, 404, 500
```

---

## 3. Macro chuẩn — `templates/macros/ui.html`

### form_field
```jinja
{% macro form_field(field, label=None, hint=None) %}
<div class="form-group {% if field.errors %}has-error{% endif %}">
  <label for="{{ field.id }}" class="form-label">
    {{ label or field.label.text }}
    {% if field.flags.required %}<span class="text-danger">*</span>{% endif %}
  </label>
  {{ field(class="form-control" + (" is-invalid" if field.errors else "")) }}
  {% if hint %}<small class="form-hint">{{ hint }}</small>{% endif %}
  {% for error in field.errors %}
    <div class="form-error">{{ error }}</div>
  {% endfor %}
</div>
{% endmacro %}
```

### badge
```jinja
{% macro badge(text, type="default") %}
{# type: success | warning | danger | info | default #}
<span class="badge badge-{{ type }}">{{ text }}</span>
{% endmacro %}
```

### pagination
```jinja
{% macro pagination(page, total_pages, endpoint, **kwargs) %}
{% if total_pages > 1 %}
<nav class="pagination-nav" aria-label="Phân trang">
  {% if page > 1 %}
    <a href="{{ url_for(endpoint, page=page-1, **kwargs) }}" class="pagination-btn">‹ Trước</a>
  {% endif %}
  <span class="pagination-info">{{ page }} / {{ total_pages }}</span>
  {% if page < total_pages %}
    <a href="{{ url_for(endpoint, page=page+1, **kwargs) }}" class="pagination-btn">Sau ›</a>
  {% endif %}
</nav>
{% endif %}
{% endmacro %}
```

### alert (flash message)
```jinja
{% macro alert(message, category="info") %}
<div class="alert alert-{{ category }}" role="alert">
  <span class="alert-icon">
    {% if category == "success" %}✓{% elif category == "error" or category == "danger" %}✕{% else %}ℹ{% endif %}
  </span>
  {{ message }}
</div>
{% endmacro %}
```

---

## 4. Flash messages — render trong base.html

```html
{# Trong base.html — render tất cả flash messages #}
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <div class="flash-container">
      {% for category, message in messages %}
        {{ alert(message, category) }}
      {% endfor %}
    </div>
  {% endif %}
{% endwith %}
```

**Quy tắc category trong Python:**
```python
# ✅ Dùng đúng category
flash("Lưu thành công.", "success")
flash("Không có quyền truy cập.", "error")
flash("Deadline sắp đến.", "warning")
flash("Cập nhật thông tin tài khoản.", "info")

# ❌ Không dùng string tùy ý
flash("Xong rồi.", "ok")  # class alert-ok không tồn tại
```

---

## 5. CSRF token — bắt buộc với mọi form POST

```html
<!-- Form HTML thuần -->
<form method="POST" action="{{ url_for('teacher.save_lesson', id=lesson.id) }}">
  {{ csrf_token() }}   {# LUÔN có dòng này #}
  <!-- ... fields ... -->
</form>

<!-- WTForms form object -->
<form method="POST">
  {{ form.hidden_tag() }}  {# bao gồm CSRF token #}
  {{ form_field(form.title) }}
</form>
```

**CSRF trong fetch/AJAX:**
```javascript
// Lấy token từ meta tag (thêm vào base.html)
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

fetch('/api/endpoint', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken,   // LUÔN gửi header này
  },
  body: JSON.stringify(data),
});
```

Thêm vào `base.html` trong `<head>`:
```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

---

## 6. JavaScript — quy tắc viết

### 6.1 Truyền dữ liệu từ Python → JS qua data-* attribute
```html
<!-- ❌ Sai — inline script với biến Python nhúng trực tiếp -->
<script>
  const courseId = "{{ course.id }}";  // vi phạm CSP unsafe-inline
</script>

<!-- ✅ Đúng — dùng data attribute -->
<div id="course-chart"
     data-course-id="{{ course.id }}"
     data-labels="{{ labels | tojson }}"
     data-values="{{ values | tojson }}">
</div>
```

```javascript
// Trong file static/js/course-chart.js
document.addEventListener('DOMContentLoaded', () => {
  const el = document.getElementById('course-chart');
  if (!el) return;                              // guard — trang khác không có element này
  const courseId = el.dataset.courseId;
  const labels = JSON.parse(el.dataset.labels);
  const values = JSON.parse(el.dataset.values);
  // render chart...
});
```

### 6.2 Cấu trúc file JS

```
static/js/
├── base.js              # Chạy trên mọi trang: flash auto-dismiss, nav toggle
├── form-validation.js   # Client-side validation helper
├── course-chart.js      # Chart.js cho analytics
├── quiz.js              # Quiz timer, answer selection
├── lesson.js            # Video progress tracking
└── admin-table.js       # Sort, search, select-all cho bảng admin
```

### 6.3 Không dùng jQuery (project đang dùng vanilla JS)
```javascript
// ❌
$('#btn').click(handler);

// ✅
document.getElementById('btn').addEventListener('click', handler);
```

---

## 7. Chart.js — pattern chuẩn

```javascript
// static/js/course-chart.js
document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('completion-chart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: JSON.parse(canvas.dataset.labels),
      datasets: [{
        label: 'Tỷ lệ hoàn thành (%)',
        data: JSON.parse(canvas.dataset.values),
        backgroundColor: '#378ADD',
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, ticks: { callback: v => v + '%' } },
      },
    },
  });
});
```

```html
<!-- Template -->
<div style="height: 260px;">
  <canvas id="completion-chart"
          data-labels="{{ course_titles | tojson }}"
          data-values="{{ completion_rates | tojson }}">
  </canvas>
</div>

{% block extra_js %}
<script src="{{ url_for('static', filename='js/course-chart.js') }}"></script>
{% endblock %}
```

---

## 8. Responsive & accessibility checklist

Trước khi commit template mới, kiểm tra:

- [ ] Có `alt` text cho mọi `<img>`
- [ ] Mọi `<input>` có `<label>` liên kết (qua `for` or `aria-label`)
- [ ] Button không dùng `<div>` giả làm button
- [ ] Table có `<thead>` với `scope="col"` trên `<th>`
- [ ] Color contrast đủ (text trên background đạt AA)
- [ ] Tab order hợp lý (không dùng `tabindex` số dương)
- [ ] Flash message có `role="alert"` để screen reader đọc

---

## 9. Anti-pattern cần tránh

| ❌ Không làm | ✅ Thay bằng |
|---|---|
| Inline style `style="..."` | CSS class từ `components.css` |
| Logic phức tạp trong template | Xử lý trong route, truyền biến đã sẵn sàng |
| Hardcode string tiếng Việt lẫn lộn encoding | UTF-8 everywhere, dùng `# -*- coding: utf-8 -*-` |
| `<script>` inline trong template | File `.js` riêng trong `static/js/` |
| Biến Python nhúng trực tiếp vào JS | `data-*` attribute + `JSON.parse` |
| Tạo form không có CSRF token | Luôn có `{{ csrf_token() }}` hoặc `{{ form.hidden_tag() }}` |
| Copy-paste HTML block giống nhau | Tạo Jinja macro |

---

## 10. Checklist khi tạo template mới

```
[ ] Extend base.html
[ ] Đặt title trong {% block title %}
[ ] Render flash messages (base.html đã xử lý — không cần làm lại)
[ ] Mọi form có CSRF token
[ ] Không có inline style
[ ] Dữ liệu Python → JS qua data-* attribute
[ ] JS trong file riêng, load qua {% block extra_js %}
[ ] Table có pagination nếu list có thể > 20 item
[ ] Empty state khi list rỗng: {% include "shared/empty_state.html" %}
[ ] Accessibility: alt, label, role
```
