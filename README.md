# E16 LMS

E16 LMS là ứng dụng quản lý học tập viết bằng Flask. Repo hiện có các luồng chính cho Admin, Teacher và Student: xác thực, quản lý khóa học, duyệt khóa học, học bài, quiz, assignment, gradebook, transcript, certificate, notification, forum, analytics, import/export CSV, Docker và migration database.

Tài liệu phân tích production chi tiết hơn nằm ở [docs/BRD_PRODUCTION.md](docs/BRD_PRODUCTION.md).

## Stack hiện tại

- Backend: Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF CSRF, Flask-Limiter, Flask-Talisman.
- Frontend: Jinja templates, static CSS, vanilla JavaScript, Chart.js.
- Database: SQLite cho local/test, PostgreSQL cho production.
- Storage: local `static/uploads` hoặc S3-compatible backend.
- Email/OAuth: Flask-Mail SMTP, Google OAuth qua Authlib.
- Deploy: Dockerfile, docker-compose với web, PostgreSQL và Redis.
- Tests: pytest cho auth, admin, course, grading, communication và storage.

## Cấu trúc repo

```text
e16_app/
  blueprints/       Routes theo domain: auth, admin, teacher, student, analytics, communication
  services/         Business helpers: audit, course, grading, storage, mail, settings, notifications
  models.py         SQLAlchemy domain models
  config.py         Config theo APP_ENV
templates/          Jinja templates
static/             CSS và uploads local
migrations/         Alembic migrations
tests/              Test suite pytest
docs/               Tài liệu sản phẩm/production readiness
scripts/            Script kiểm tra, export, vận hành phụ trợ
```

## Chạy local

Yêu cầu khuyến nghị: Python 3.11 hoặc 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask db upgrade
flask run --debug
```

Trên Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
flask db upgrade
flask run --debug
```

Seed dữ liệu demo chỉ nên chạy trong development:

```bash
flask seed
```

Hoặc đăng nhập Admin và vào `/admin/seed` khi `APP_ENV=development`.

## Chạy bằng Docker

```bash
cp .env.example .env
# Cập nhật SECRET_KEY, POSTGRES_PASSWORD và các biến cần thiết trong .env
docker compose up --build
```

Docker Compose chạy:

- `web`: Flask/Gunicorn app.
- `db`: PostgreSQL 15.
- `redis`: rate-limit storage.

## Tài khoản demo

Sau khi seed:

| Role | Email | Mật khẩu |
| --- | --- | --- |
| Admin | `admin@e16.local` | `admine16` |
| Teacher | `teacher@e16.local` | `teachere16` |
| Student | `student@e16.local` | `studente16` |
| Student demo | `student1@e16.local` đến `student5@e16.local` | `E16_SEED_PASSWORD` hoặc `demo-password` |

Không dùng các tài khoản/mật khẩu demo trong production.

## Kiểm thử

```bash
pytest
```

Các nhóm test hiện có:

- Auth: đăng ký, đăng nhập, logout, inactive account, security headers.
- Admin: seed protection, import CSV, soft delete user, pagination, audit log, metrics, export.
- Courses/communication/storage/grading: enrollment, forum/notification, upload backend, quiz/assignment grading.

## Hiện trạng đã đọc từ repo

- App factory đã tách extension, config theo môi trường và blueprint theo domain.
- Production có fail-fast cho `SECRET_KEY`, CSP/Talisman, CSRF, rate limit, health checks `/healthz`, readiness `/readyz`, metrics `/metricsz`.
- Admin đã có pagination cho users/audit logs, CSV import, course approval, audit logging.
- Teacher đã có quản lý course, lesson, quiz, assignment, gradebook, analytics và export.
- Student đã có catalog, checkout mô phỏng, enrollment, learning page, completion tracking, quiz, assignment, transcript, calendar và certificate.
- Storage service đã validate extension cơ bản và hỗ trợ local/S3.
- BRD production đã có checklist khá đầy đủ, nhưng README cũ bị dài và khó dùng làm entry point.

## Điểm cần cải thiện

### P0 - Chặn lỗi production và bảo mật

- Rà soát và chuẩn hóa UTF-8 cho README, `.env.example`, flash messages, seed data và các string tiếng Việt trong source để tránh mojibake giữa Windows/Linux/CI.
- Rà lại authorization theo owner/enrollment cho mọi route nested: quiz, assignment, announcement, forum, submission, certificate và file download.
- File bài nộp hiện có thể được render qua static path; production nên dùng private object storage, signed URL và kiểm tra quyền trước khi tải.
- Luồng thanh toán hiện là mô phỏng QR/IPN trong route student; cần tách rõ mock/dev và tích hợp payment thật nếu đưa vào production.
- Chuẩn hóa CSRF cho mọi state-changing route và kiểm tra các endpoint JSON/POST.
- Bỏ hoặc khóa tuyệt đối seed/demo credentials ở production; giữ `/admin/seed` chỉ cho development/staging có kiểm soát.
- Loại bỏ dần `unsafe-inline` trong CSP bằng nonce hoặc file script/style riêng.
- Bổ sung secret scanning và dependency/security scan trong CI.

### P1 - Data integrity và lỗi runtime

- Sửa bug trong `teacher.export_gradebook`: biến `max_rows` được log nhưng chưa khai báo trong hàm.
- Chuẩn hóa timezone: code đang dùng cả `utcnow()` timezone-aware và `datetime.utcnow()` naive trong checkout/enrollment.
- Chuẩn hóa enum/constant cho `role`, `course.status`, `enrollment.status`, `submission.status`, `notification.type`.
- Thêm/rà lại database constraints và migration cho các quan hệ quan trọng: enrollment, certificate, quiz answers, submissions.
- Hoàn thiện cascade/soft-delete policy cho user, course, lesson, quiz, assignment để tránh orphan data.
- Validate input form chặt hơn: score, pass_score, max_attempts, time_limit, deadline, URL video/document, category, text length.
- Bổ sung transaction boundary cho các flow nhiều bước như grade + notify, complete lesson + issue certificate, import CSV.

### P2 - Test coverage và CI

- Thêm test ma trận role/owner/enrollment cho tất cả route nhạy cảm.
- Thêm test cho checkout timeout, pending payment, simulated IPN và trạng thái enrollment.
- Thêm test cho quiz random question, checkbox/fill-in-blank review, attempt limit và due date.
- Thêm test cho assignment deadline, upload invalid MIME/extension/size và private file access.
- Thêm test cho certificate public privacy, revoked/deleted course và incomplete completion rate.
- Thêm CI chạy `pytest`, migration check, Docker build và dependency scan.
- Đo coverage, đặt ngưỡng tối thiểu cho route/service core.

### P3 - Vận hành production

- Bổ sung tài liệu biến môi trường production: Redis rate limiter, SMTP, S3, OAuth, metrics token, export/import limits.
- Thiết lập backup/restore PostgreSQL và diễn tập restore định kỳ.
- Thiết lập log aggregation, alerting, uptime check, error-rate/latency alerts.
- Chuyển email batch, export lớn và analytics aggregation sang background jobs.
- Tối ưu query dashboard/analytics/gradebook để tránh N+1 ở dữ liệu lớn.
- Chuẩn hóa Docker startup: migration fail-fast, non-root user, writable upload path và healthcheck.

### P4 - UX và maintainability

- Giảm inline style trong templates, gom component/style lặp lại vào CSS hoặc macro Jinja.
- Thêm pagination/search/filter nhất quán cho bảng lớn: course list, submissions, gradebook, notifications, pending courses.
- Tách business logic khỏi route vào service layer để dễ test và giảm file blueprint quá dài.
- Chuẩn hóa thông báo lỗi/thành công và form validation trên UI.
- Bổ sung accessibility smoke test cho các trang chính.
- Tạo route inventory hoặc OpenAPI/internal QA checklist tự động từ Flask routes.

## Roadmap đề xuất

1. Hardening nhanh: chuẩn hóa encoding, sửa bug export gradebook, timezone checkout, route authorization và file access.
2. Test nền: thêm test cho role/owner/enrollment, payment mock, assignment upload và certificate privacy.
3. Production infra: CI, Docker build check, Redis limiter, PostgreSQL backup/restore, S3 private uploads, monitoring.
4. Refactor vừa đủ: tách service layer cho grading/course/payment/notification, chuẩn hóa enum và validation.
5. UX/data scale: pagination/filter, background jobs, analytics performance và admin health dashboard.

## Checklist trước production

- [x] `pytest` pass 100% với 47/47 test cases.
- [x] Migration chạy thành công trên database sạch và có script dọn dẹp trùng lặp.
- [x] Docker image build và app chạy non-root (`e16user`).
- [x] UI/tài liệu hiển thị tiếng Việt đúng trên Windows, Linux và CI.
- [x] Bền vững hóa Quiz Review lưu trữ hoàn toàn qua Database (loại bỏ session).
- [x] Refactor toàn bộ route lớn: tách Payment, Submission, Quiz, Course vào Service Layer chuẩn.
- [x] Route nhạy cảm có test unauthorized/forbidden chặt chẽ (`test_role_matrix.py`).
- [x] Redis rate limiter được cấu hình và bật bằng `RATELIMIT_STORAGE_URI`.
- [ ] Upload production dùng S3-compatible private storage hoặc endpoint kiểm quyền.
- [ ] `/healthz`, `/readyz`, `/metricsz` được kiểm tra tích hợp trong staging.
- [ ] Backup/restore được kiểm chứng định kỳ.
