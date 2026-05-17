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
2. Truy cập `/admin/seed` để khởi tạo Danh mục, Khóa học mẫu và Dữ liệu demo hệ thống (hoặc dùng CLI lệnh `flask seed`).

## 🛠️ Công nghệ sử dụng
- **Backend**: Flask, SQLAlchemy, Flask-Migrate, Flask-Login.
- **Frontend**: Vanilla HTML/CSS/JS (Modern CSS Grid & Flexbox).
- **Database**: SQLite (Dev) / PostgreSQL (Prod).
- **Communication**: Flask-Mail (SMTP), Chart.js (Analytics).

## 🔑 Tài khoản mặc định (Core & Demo Seed Users)
Hệ thống hỗ trợ các tài khoản mặc định sau sau khi chạy seed hệ thống:

| Vai trò | Email | Mật khẩu mặc định | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@e16.local` | `admine16` | Tài khoản quản trị tối cao |
| **Teacher** | `teacher@e16.local` | `teachere16` | Giáo viên quản lý khóa học/bài tập |
| **Student** | `student@e16.local` | `studente16` | Học viên cốt lõi |
| **Student 1-5** | `student1@e16.local` ~ `student5@e16.local` | `<E16_SEED_PASSWORD>` (Mặc định: `demo-password`) | Nhóm học viên bổ trợ chạy thử nghiệm |

---

## 📊 Bảng so sánh Script Seed Dữ liệu mẫu

Hệ thống có nhiều script seed khác nhau phục vụ các kịch bản kiểm thử hiệu năng và giao diện riêng biệt:

| Script / Lệnh | Dữ liệu khởi tạo | Danh sách người dùng tạo ra | Mật khẩu mặc định | Mục đích sử dụng |
| :--- | :--- | :--- | :--- | :--- |
| **`flask seed`** hoặc **`/admin/seed`** | Danh mục, 4 khóa học mẫu, lessons, enrollments, logs cơ bản | `admin@e16.local`, `teacher@e16.local`, `student@e16.local`, `student1@e16.local` ~ `student5@e16.local` | `admine16` (Admin), `teachere16` (Teacher), `studente16` (Student), `demo-password` (Student 1-5) | Khởi tạo onboarding nhanh và cơ bản để trải nghiệm giao diện. |
| **`seed_100.py`** | 1 khóa học mẫu, 10 bài học, 100 học viên, logs học tập ngẫu nhiên | `teacher_demo@e16.edu.vn` và `student_demo_1@e16.edu.vn` ~ `student_demo_100@e16.edu.vn` | `123456` | Thử nghiệm hiển thị phân trang và hiệu suất mức trung bình. |
| **`seed_300_users.py`** | 300 tài khoản học sinh (đồng bộ SQLite & Supabase) | `student_300_1@e16.edu.vn` ~ `student_300_300@e16.edu.vn` | `123456` | Kiểm thử chịu tải số lượng lớn người dùng. |
| **`seed_complex_data.py`** | 15-20 giáo viên, nhiều khóa học/bài học/quizzes phức tạp | `teacher_1_[random]@e16.edu.vn` ~ `teacher_N_[random]@e16.edu.vn` (Yêu cầu có sẵn học sinh từ script 300) | `123456` | Kiểm thử dữ liệu phân tích Analytics phức tạp đa cấp độ. |
| **`seed_quizzes_assignments.py`** | 1 Quiz trắc nghiệm, 1 Assignment tự luận, giả lập điểm số | Không tạo thêm (Sử dụng nhóm học sinh `student_demo_*` có sẵn) | N/A | Kiểm thử luồng Sổ điểm (Gradebook) và nộp bài (Submission). |
| **`seed_learning_logs.py`** | Logs hoạt động học tập ngẫu nhiên (SQLite & Supabase) | Không tạo thêm (Sử dụng học sinh & bài học có sẵn) | N/A | Mô phỏng dòng thời gian học tập cho các biểu đồ Analytics. |

---

© 2024 E16 Education Team. All rights reserved.
