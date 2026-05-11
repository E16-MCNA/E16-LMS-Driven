# E16 LMS - Premium Learning Management System

E16 LMS là một nền tảng quản lý học tập hiện đại, được thiết kế với trải nghiệm người dùng cao cấp (Premium UI/UX) và các tính năng vận hành mạnh mẽ dành cho doanh nghiệp và trường học.

![Dashboard Preview](https://images.unsplash.com/photo-1501504905252-473c47e087f8?q=80&w=1974&auto=format&fit=crop)

## ✨ Tính năng nổi bật

- **Premium Interface**: Giao diện Glassmorphism hiện đại, hỗ trợ Dark/Light mode linh hoạt.
- **Role-based Access**: Phân quyền chi tiết cho Admin, Teacher và Student.
- **Interactive Learning**: Bài học Video/Document, Quiz trắc nghiệm, Nộp bài tập (Assignment).
- **Academic Records**: Sổ điểm (Gradebook), Học bạ điện tử (Transcript), Chứng chỉ hoàn thành tự động.
- **Communication**: Diễn đàn thảo luận (Forum), Thông báo (Notification), Email Alert.
- **Admin Tools**: Phân tích dữ liệu (Analytics), Import người dùng hàng loạt, Nhật ký hệ thống (Audit Log).

## 🚀 Cài đặt nhanh (Onboarding)

### 1. Chuẩn bị môi trường
Yêu cầu Python 3.11+.

```bash
# Clone repository
git clone https://github.com/nssiwi19/E16-LMS-Driven.git
cd E16-LMS-Driven

# Cấu hình biến môi trường
cp .env.example .env
# Chỉnh sửa .env với các thông số của bạn (SECRET_KEY, MAIL, GOOGLE_OAUTH...)
```

### 2. Cài đặt tự động với Makefile
```bash
# Cài đặt thư viện
make install

# Khởi tạo Database (SQLite mặc định)
make migrate

# Chạy ứng dụng Development
make dev
```

### 3. Khởi tạo dữ liệu mẫu (Seed)
1. Đăng nhập với tài khoản Admin mặc định (nếu đã seed qua script) hoặc tạo mới.
2. Truy cập `/auth/seed?key=<E16_SEED_PASSWORD>` để khởi tạo Danh mục, Khóa học mẫu và Dữ liệu demo.

## 🛠️ Công nghệ sử dụng
- **Backend**: Flask, SQLAlchemy, Flask-Migrate, Flask-Login.
- **Frontend**: Vanilla HTML/CSS/JS (Modern CSS Grid & Flexbox).
- **Database**: SQLite (Dev) / PostgreSQL (Prod).
- **Communication**: Flask-Mail (SMTP), Chart.js (Analytics).

## 🔑 Tài khoản mặc định (Test Data)
- **Admin**: `admin@e16.local` / `<E16_SEED_PASSWORD>`
- **Teacher**: `teacher@e16.local` / `<E16_SEED_PASSWORD>`
- **Student**: `student1@e16.local` ~ `student5@e16.local` / `<E16_SEED_PASSWORD>`

> **Lưu ý**: Mật khẩu mặc định là giá trị biến môi trường `E16_SEED_PASSWORD` (mặc định: `demo-password`).

---

© 2024 E16 Education Team. All rights reserved.
