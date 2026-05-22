# BRD - E16 LMS Production

## 1. Thông tin tài liệu

| Thuộc tính | Nội dung |
| --- | --- |
| Sản phẩm | E16 LMS |
| Loại tài liệu | Business Requirements Document (BRD) |
| Phiên bản | 1.1 |
| Ngày lập | 2026-05-18 |
| Mục tiêu | Chuẩn hóa yêu cầu nghiệp vụ, phạm vi sản phẩm, tiêu chí nghiệm thu và các điều kiện bắt buộc để triển khai E16 LMS thành hệ thống production |
| Nguồn phân tích | Toàn bộ repo hiện tại: Flask app, SQLAlchemy models, blueprints, services, templates, tests, Docker, migrations, seed/export scripts |

## 2. Tóm tắt điều hành

E16 LMS là nền tảng quản lý học tập dành cho tổ chức giáo dục, trung tâm đào tạo hoặc doanh nghiệp có nhu cầu vận hành khóa học trực tuyến. Sản phẩm hiện hỗ trợ sáu vai trò gồm Admin, Học vụ, Lễ tân, Kế toán, Teacher và Student; các nghiệp vụ cốt lõi gồm cấp tài khoản, đăng nhập, quản lý khóa học, duyệt khóa học, ghi danh/thanh toán, học bài, làm quiz, nộp assignment, chấm điểm, gradebook, transcript, chứng chỉ, thông báo, forum, analytics và export dữ liệu.

Mục tiêu production của E16 LMS là chuyển sản phẩm từ trạng thái có đủ chức năng MVP/near-production sang một hệ thống ổn định, bảo mật, có thể vận hành thật với dữ liệu người dùng thật, đo lường được, kiểm thử được, khôi phục được và tuân thủ yêu cầu bảo vệ dữ liệu.

## 3. Mục tiêu kinh doanh

1. Cung cấp một LMS có thể triển khai cho trường học, trung tâm đào tạo hoặc đơn vị đào tạo nội bộ.
2. Cho phép Teacher tự tạo, quản lý và theo dõi hiệu quả khóa học.
3. Cho phép Admin kiểm soát người dùng, danh mục, cấu hình hệ thống, duyệt khóa học, audit log và dữ liệu phân tích.
4. Cho phép Học vụ duyệt khóa học trước khi phát hành theo quy trình học thuật.
5. Cho phép Lễ tân tra cứu hồ sơ học viên, tạo tài khoản học viên và ghi danh trực tiếp tại quầy.
6. Cho phép Kế toán đối soát thanh toán, duyệt giao dịch pending_payment, theo dõi doanh thu và xuất báo cáo tài chính.
7. Cho phép Student đăng nhập bằng tài khoản đã được cấp, đăng ký học, theo dõi tiến độ, làm bài kiểm tra, nộp bài, xem điểm và nhận chứng chỉ.
8. Giảm chi phí vận hành đào tạo bằng tự động hóa các quy trình: enrollment, learning log, chấm quiz, thông báo, gradebook, transcript và certificate.
9. Tạo nền tảng dữ liệu đủ tin cậy cho báo cáo học tập, phân tích hành vi và ra quyết định vận hành.

## 4. Phạm vi sản phẩm

### 4.1. Trong phạm vi production

- Xác thực người dùng bằng email/password và Google OAuth.
- Phân quyền theo vai trò Admin, Học vụ, Lễ tân, Kế toán, Teacher, Student.
- Quản lý người dùng, trạng thái tài khoản, vai trò, cấp tài khoản đơn lẻ và import người dùng bằng CSV.
- Quản lý danh mục khóa học.
- Teacher tạo khóa học, cập nhật nội dung, lessons, quizzes, assignments và gửi duyệt.
- Admin hoặc Học vụ duyệt hoặc từ chối khóa học trước khi publish.
- Lễ tân tạo tài khoản học viên, tra cứu hồ sơ học viên và ghi danh trực tiếp tại quầy.
- Kế toán đối soát thanh toán, duyệt/từ chối giao dịch chờ thanh toán, theo dõi doanh thu và xuất CSV tài chính.
- Student tìm kiếm, lọc, đăng ký khóa học và học bài.
- Ghi nhận learning logs, tính tiến độ học tập, streak và trạng thái hoàn thành.
- Quiz tự động chấm điểm với MCQ, checkbox và fill-in-blank.
- Assignment cho phép nộp văn bản/file, teacher chấm điểm và phản hồi.
- Gradebook, transcript, calendar deadline và certificate.
- Announcement, notification và course forum.
- Admin analytics, teacher course analytics và export CSV/ZIP.
- Audit log cho hành động quan trọng.
- Email reset password và thông báo qua SMTP.
- Lưu file local ở development và S3 ở production.
- Triển khai bằng Docker, PostgreSQL, Redis, Gunicorn, migration và health checks.

### 4.2. Ngoài phạm vi phiên bản production đầu tiên

- Marketplace nhiều người bán hoặc cổng thanh toán tự động hoàn chỉnh.
- Livestream/classroom realtime.
- Mobile native app.
- SCORM/xAPI đầy đủ.
- AI tutor, AI grading tự luận.
- Multi-tenant white-label phức tạp.
- Hệ thống chat realtime.
- Proctoring/chống gian lận nâng cao.

Các hạng mục ngoài phạm vi có thể được đưa vào roadmap sau khi bản production đầu tiên ổn định.

## 5. Stakeholders

| Nhóm | Mục tiêu | Trách nhiệm |
| --- | --- | --- |
| Chủ sản phẩm | Sản phẩm chạy được production, có giá trị thương mại/đào tạo | Quyết định phạm vi, ưu tiên roadmap, nghiệm thu |
| Admin hệ thống | Quản trị người dùng, khóa học, danh mục, báo cáo và vận hành | Thiết lập hệ thống, duyệt nội dung, xử lý sự cố |
| Học vụ | Kiểm soát quy trình học thuật và duyệt khóa học | Xem dashboard học vụ, duyệt/từ chối khóa học chờ review |
| Lễ tân | Hỗ trợ học viên tại quầy | Tạo tài khoản học viên, cập nhật thông tin cơ bản, ghi danh trực tiếp |
| Kế toán | Quản lý thanh toán và doanh thu | Duyệt/từ chối giao dịch chờ thanh toán, xử lý hoàn phí, xuất báo cáo doanh thu |
| Teacher | Tạo và vận hành khóa học | Soạn lesson, quiz, assignment, chấm điểm, theo dõi lớp |
| Student | Học tập và hoàn thành khóa học | Đăng ký khóa học, học bài, làm bài, xem kết quả |
| Dev/DevOps | Đưa hệ thống vào production ổn định | CI/CD, hạ tầng, bảo mật, backup, monitoring |
| Support | Hỗ trợ người dùng cuối | Xử lý ticket, hướng dẫn sử dụng, ghi nhận lỗi |

## 6. Persona và nhu cầu

### 6.1. Admin

Admin cần một bảng điều khiển tập trung để quản trị người dùng, phân quyền, khóa/mở tài khoản, import danh sách học viên, quản lý danh mục, cấu hình tên/logo hệ thống, duyệt khóa học, xem audit log, xem analytics và export dữ liệu.

### 6.2. Teacher

Teacher cần tạo khóa học nhanh, thêm bài học bằng video/document URL, tạo quiz, tạo assignment, xem danh sách học viên, chấm bài, xuất điểm, xem gradebook và analytics để cải thiện nội dung.

### 6.3. Học vụ

Học vụ cần một màn hình tập trung để theo dõi khóa học chờ duyệt, kiểm tra thông tin khóa học và phê duyệt hoặc từ chối kèm lý do.

### 6.4. Lễ tân

Lễ tân cần tra cứu học viên nhanh, xem hồ sơ học tập cơ bản, tạo tài khoản học viên mới, cập nhật số điện thoại/trạng thái và ghi danh khóa học trực tiếp tại quầy.

### 6.5. Kế toán

Kế toán cần xem dashboard doanh thu, danh sách giao dịch chờ đối soát, phê duyệt hoặc từ chối thanh toán, xử lý hoàn phí và xuất CSV doanh thu.

### 6.6. Student

Student cần tìm khóa học, đăng ký học, xem bài học theo thứ tự, đánh dấu hoàn thành, làm quiz, nộp assignment, xem deadline, transcript, chứng chỉ và nhận thông báo khi có hoạt động mới.

## 7. Hiện trạng repo

### 7.1. Kiến trúc hiện tại

| Thành phần | Hiện trạng |
| --- | --- |
| Backend | Flask 3, Flask-SQLAlchemy, Flask-Login, Flask-Migrate |
| Frontend | Server-rendered Jinja templates, static CSS, Chart.js |
| Database | SQLite cho dev/test, PostgreSQL cho production; Supabase PostgreSQL đang là lựa chọn triển khai thật |
| Auth | Email/password, Google OAuth qua Authlib |
| Email | Flask-Mail SMTP |
| Rate limit | Flask-Limiter, memory/Redis storage |
| Security headers | Flask-Talisman với CSP |
| File storage | Local static uploads hoặc S3 |
| Logging | App log, AuditLog DB, Supabase logger optional |
| Deployment | Vercel hiện dùng cho app đã deploy; Docker/docker-compose vẫn là đường chạy production hoặc staging khi cần backend riêng |
| Tests | pytest cho auth, course enrollment, grading |

Định hướng domain production:

- `www.e16...`: landing/public marketing, ưu tiên static hoặc Next.js/Vercel, cache/CDN mạnh, SEO tốt, không phụ thuộc Flask session/auth.
- `app.e16...`: LMS login và nghiệp vụ, gồm dashboard, role, quiz, assignment, gradebook, certificate, Admin/Học vụ/Lễ tân/Kế toán.
- Flask tiếp tục là backend chính cho nghiệp vụ LMS; chưa cần rewrite sang Next.js nếu mục tiêu trước mắt là ổn định production.

### 7.2. Domain model chính

- `User`: email, password hash, phone, active status, role, login metadata, reset token.
- `Category`: danh mục khóa học.
- `Course`: nội dung khóa học, trạng thái draft/pending_review/published/rejected, teacher owner.
- `Lesson`: bài học trong khóa học.
- `Enrollment`: quan hệ Student-Course và trạng thái học.
- `LearningLog`: sự kiện start/complete lesson.
- `Quiz`, `Question`, `Choice`, `QuizAttempt`, `QuizAnswer`: ngân hàng câu hỏi, lượt làm và câu trả lời.
- `Assignment`, `Submission`: bài tập và bài nộp.
- `Notification`, `Announcement`, `ForumThread`, `ForumReply`: giao tiếp.
- `Certificate`: chứng chỉ hoàn thành.
- `SystemSetting`: cấu hình hệ thống.
- `AuditLog`: nhật ký hành động.

## 8. Quy trình nghiệp vụ cốt lõi

### 8.1. Cấp tài khoản và đăng nhập

1. Người dùng không tự đăng ký tài khoản trên production; tài khoản được cấp bởi Admin hoặc Lễ tân theo quy trình vận hành.
2. Admin có thể tạo tài khoản cho mọi role hợp lệ; Lễ tân chỉ tạo tài khoản Student.
3. Tài khoản mới nhận mật khẩu tạm, bị đánh dấu `must_change_password=True` và phải đổi mật khẩu khi đăng nhập lần đầu.
4. Người dùng đăng nhập bằng email/password hoặc Google OAuth; OAuth chỉ cho phép login với email đã được cấp tài khoản trước đó.
5. Hệ thống chặn tài khoản inactive.
6. Sau đăng nhập, hệ thống điều hướng theo role:
   - Student: `/dashboard`
   - Teacher: `/teacher/dashboard`
   - Học vụ: `/hoc-vu/dashboard`
   - Lễ tân: `/le-tan/dashboard`
   - Kế toán: `/ke-toan/dashboard`
   - Admin: `/analytics/`

### 8.2. Quản trị người dùng

1. Admin xem danh sách người dùng.
2. Admin tạo tài khoản đơn lẻ cho role hợp lệ, cấp mật khẩu tạm và có thể auto-enroll nếu tạo Student kèm course.
3. Admin đổi role giữa `student`, `teacher`, `admin`, `hoc_vu`, `le_tan`, `ke_toan`.
4. Admin khóa/mở tài khoản.
5. Admin xóa người dùng theo nghĩa soft delete/deactivate nếu không phải chính mình.
6. Admin import CSV người dùng với email và role.
7. Hệ thống ghi audit log cho thao tác quan trọng.

### 8.3. Vòng đời khóa học

1. Teacher tạo khóa học ở trạng thái `draft`.
2. Teacher cập nhật metadata: title, short description, description, cover image, category.
3. Teacher thêm ít nhất một lesson.
4. Teacher gửi duyệt, hệ thống chuyển trạng thái sang `pending_review`.
5. Admin hoặc Học vụ duyệt khóa học, hệ thống chuyển sang `published`.
6. Admin hoặc Học vụ từ chối khóa học, hệ thống chuyển sang `rejected` và lưu lý do.
7. Student chỉ nhìn thấy khóa học `published`.

### 8.4. Học tập và tiến độ

1. Student xem danh sách khóa học published.
2. Student tìm kiếm theo keyword và lọc theo category.
3. Student enroll vào khóa học.
4. Khi Student mở lesson, hệ thống ghi log `start`.
5. Khi Student đánh dấu hoàn thành, hệ thống ghi log `complete`.
6. Hệ thống tính completion rate dựa trên số lesson complete trên tổng lessons.
7. Khi completion rate đạt 100%, enrollment chuyển `completed` và hệ thống cấp certificate nếu chưa có.

### 8.5. Quiz

1. Teacher tạo quiz trong khóa học.
2. Teacher cấu hình pass score, max attempts, time limit, random question count và publish.
3. Teacher thêm câu hỏi và choices.
4. Student làm quiz nếu còn attempt.
5. Hệ thống chấm điểm tự động theo số câu đúng/tổng câu.
6. Hệ thống lưu QuizAttempt và QuizAnswer.
7. Student xem kết quả sau khi submit.
8. Teacher/Admin dùng dữ liệu quiz cho gradebook và analytics.

### 8.6. Assignment

1. Teacher tạo assignment, deadline, cho phép text/file.
2. Student nộp text, file hoặc cả hai trước deadline.
3. Student có thể cập nhật bài nộp trước deadline.
4. Teacher xem submissions, lọc theo status.
5. Teacher nhập score và feedback.
6. Hệ thống cập nhật trạng thái, thời gian chấm, người chấm và gửi notification.

### 8.7. Giao tiếp

1. Teacher tạo announcement cho course.
2. Hệ thống gửi notification đến học viên đã enroll.
3. Người dùng đã đăng nhập xem forum của khóa học nếu có quyền.
4. Người dùng tạo thread và reply.
5. Teacher pin/unpin thread.
6. Tác giả thread nhận notification khi có reply mới.

### 8.8. Báo cáo và phân tích

1. Admin xem dashboard tổng quan: users, teachers, students, published courses, enrollments, activity logs hôm nay.
2. Admin xem tăng trưởng người dùng, xu hướng enrollment và top courses.
3. Admin export dữ liệu dạng CSV hoặc ZIP.
4. Teacher xem analytics theo course: enrollment, completion, funnel lesson, quiz average, score distribution.
5. Teacher export gradebook và assignment grades.

### 8.9. Xác thực chứng chỉ

1. Khi Student hoàn thành 100% lessons của course, hệ thống cấp một Certificate duy nhất cho cặp Student-Course.
2. Student xem chứng chỉ trong trang cá nhân và có thể chia sẻ URL public dạng `/certificates/<cert_code>`.
3. Người ngoài truy cập URL public chỉ thấy trạng thái xác thực, tên khóa học, ngày cấp, mã chứng chỉ và tên hiển thị tối thiểu của học viên theo cấu hình privacy.
4. Production phải có lựa chọn ẩn hoặc rút gọn PII của học viên trên trang public, ví dụ chỉ hiển thị tên đã mask hoặc email đã mask.
5. Nếu certificate bị thu hồi hoặc course/user bị soft delete theo chính sách, URL public phải hiển thị trạng thái không còn hiệu lực thay vì trả dữ liệu cũ.
6. Trang public không được hiển thị điểm số, transcript, email đầy đủ, phone, submission hoặc learning logs.

### 8.10. Ghi danh và thanh toán

1. Student chọn khóa học published và đi qua trang checkout để tạo enrollment `pending_payment`.
2. Nếu `PAYMENT_MODE=mock`, luồng simulate IPN chỉ dùng cho development/staging và không được xem là thanh toán production.
3. Nếu `PAYMENT_MODE=real`, hệ thống phải tích hợp provider/webhook thật hoặc quy trình đối soát thủ công rõ ràng trước khi cấp quyền học.
4. Kế toán duyệt giao dịch `pending_payment` sau đối soát; enrollment chỉ chuyển sang quyền học active khi thanh toán được approve.
5. Kế toán có thể reject/refund nhưng phải giữ lịch sử tài chính, audit log và không xóa dữ liệu học tập ngoài chính sách retention.

## 9. Yêu cầu chức năng

### 9.1. Authentication & Authorization

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| AUTH-001 | Tài khoản người dùng được cấp bởi Admin hoặc Lễ tân | Must | Không có self-registration production; email không trùng; tài khoản mới có mật khẩu tạm và `must_change_password=True` |
| AUTH-002 | Người dùng đăng nhập bằng email/password | Must | Đúng credential thì login, sai thì báo lỗi chung |
| AUTH-003 | Hệ thống chặn tài khoản inactive | Must | User inactive không thể login |
| AUTH-004 | Hệ thống hỗ trợ reset password qua email | Must | Token có hạn 1 giờ, dùng xong bị xóa |
| AUTH-005 | Hệ thống hỗ trợ Google OAuth login-only | Should | Email đã được cấp tài khoản có thể đăng nhập OAuth; email chưa được cấp bị từ chối bằng thông báo chung/liên hệ Học vụ |
| AUTH-006 | Route phải được bảo vệ theo role | Must | Student, Teacher, Học vụ, Lễ tân, Kế toán và Admin chỉ truy cập được vùng chức năng đúng quyền |
| AUTH-007 | Admin không thể tự xóa/tự đổi role/tự deactivate chính mình | Must | Các hành động này bị chặn |

### 9.2. Admin

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| ADM-001 | Admin xem danh sách users | Must | Danh sách sắp xếp mới nhất trước |
| ADM-002 | Admin đổi role user | Must | Chỉ nhận role hợp lệ: `student`, `teacher`, `admin`, `hoc_vu`, `le_tan`, `ke_toan`; Admin không tự đổi role chính mình |
| ADM-003 | Admin khóa/mở tài khoản | Must | is_active thay đổi và audit log được ghi |
| ADM-004 | Admin import users bằng CSV | Must | CSV tuân thủ format ở mục 10.5; trả kết quả thành công/lỗi từng dòng; không tạo dữ liệu lỗi một phần ngoài chính sách batch |
| ADM-005 | Admin quản lý category | Must | Tạo/sửa/xóa category; không xóa category đang có course |
| ADM-006 | Admin cập nhật system settings | Should | Cache settings được flush sau cập nhật |
| ADM-007 | Admin xem audit log | Must | Hiển thị 200 log mới nhất kèm actor nếu có |
| ADM-008 | Admin duyệt/từ chối course | Must | Course chuyển đúng trạng thái và Teacher nhận notification |
| ADM-009 | Admin chạy seed chỉ trong development | Must | Production trả 403 |
| ADM-010 | Admin tạo tài khoản đơn lẻ | Must | Tạo user với email/role/phone, mật khẩu tạm, `must_change_password=True`; nếu role Student và có course thì có thể auto-enroll |

### 9.3. Học vụ

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| HOC-001 | Học vụ xem dashboard riêng | Must | Hiển thị số khóa học chờ duyệt và liên kết đến hàng đợi review |
| HOC-002 | Học vụ xem danh sách course pending_review | Must | Chỉ hiển thị course cần duyệt, có thông tin teacher/category/lesson |
| HOC-003 | Học vụ duyệt hoặc từ chối course | Must | Course chuyển sang `published` hoặc `rejected`; lý do từ chối được lưu; Teacher nhận notification |

### 9.4. Lễ tân

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| LET-001 | Lễ tân xem dashboard riêng | Must | Hiển thị số học viên, enrollment gần đây và hành động nhanh |
| LET-002 | Lễ tân tra cứu danh sách học viên | Must | Tìm theo email/điện thoại/trạng thái; chỉ hiển thị user role Student |
| LET-003 | Lễ tân xem và cập nhật hồ sơ học viên | Must | Cập nhật phone/is_active trong phạm vi được phép; không đổi role hoặc quyền hệ thống |
| LET-004 | Lễ tân tạo tài khoản Student | Must | Tạo email Student duy nhất, mật khẩu tạm, `must_change_password=True` |
| LET-005 | Lễ tân ghi danh trực tiếp tại quầy | Must | Tạo enrollment cho Student vào course published, ghi trạng thái thanh toán theo quy trình frontdesk |

### 9.5. Kế toán

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| KTO-001 | Kế toán xem dashboard doanh thu | Must | Hiển thị paid/pending/refunded và tổng doanh thu theo dữ liệu enrollment |
| KTO-002 | Kế toán xem hàng đợi đối soát | Must | Danh sách enrollment `pending_payment` có thông tin student/course/amount/source |
| KTO-003 | Kế toán duyệt hoặc từ chối thanh toán | Must | Approve chuyển enrollment sang paid/active; reject giữ lịch sử và không cấp quyền học sai trạng thái |
| KTO-004 | Kế toán xử lý hoàn phí | Must | Refund cập nhật trạng thái tài chính, giữ audit và không xóa dữ liệu học tập ngoài chính sách |
| KTO-005 | Kế toán xuất CSV doanh thu | Must | CSV tải được, có mã enrollment, student, course, amount, status, timestamps |

### 9.6. Teacher

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| TCH-001 | Teacher xem dashboard riêng | Must | Hiển thị tổng courses, students, lessons |
| TCH-002 | Teacher tạo course draft | Must | Course gắn teacher_id hiện tại |
| TCH-003 | Teacher sửa course của mình | Must | Không sửa được course của teacher khác |
| TCH-004 | Teacher submit course để duyệt | Must | Course phải có ít nhất 1 lesson |
| TCH-005 | Teacher xóa course của mình | Should | Không xóa được course người khác |
| TCH-006 | Teacher quản lý lesson | Must | Tạo/sửa/xóa lesson và cập nhật total_lessons |
| TCH-007 | Teacher quản lý quiz | Must | Tạo/sửa/publish quiz, cấu hình score/attempt/time/random |
| TCH-008 | Teacher thêm câu hỏi quiz | Must | Hỗ trợ MCQ, checkbox, fill-in-blank theo service chấm điểm |
| TCH-009 | Teacher quản lý assignment | Must | Tạo assignment, deadline, allow text/file |
| TCH-010 | Teacher chấm submission | Must | Score, feedback, graded_at, graded_by được lưu |
| TCH-011 | Teacher xem/export gradebook | Must | CSV chứa student và điểm quiz/assignment |
| TCH-012 | Teacher xem course analytics | Should | Có funnel lesson, quiz avg, score distribution |

### 9.7. Student

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| STU-001 | Student xem catalog courses | Must | Chỉ hiển thị course published |
| STU-002 | Student tìm kiếm/lọc courses | Should | Lọc theo keyword và category |
| STU-003 | Student enroll course | Must | Không tạo duplicate enrollment |
| STU-004 | Student học lesson | Must | Mở lesson ghi learning log start |
| STU-005 | Student đánh dấu hoàn thành lesson | Must | Ghi log complete, cập nhật completion |
| STU-006 | Student làm quiz | Must | Chặn khi vượt max attempts |
| STU-007 | Student nộp assignment | Must | Chặn nộp sau deadline |
| STU-008 | Student xem transcript | Must | Hiển thị điểm quiz, assignment và completion |
| STU-009 | Student xem calendar deadline | Should | Hiển thị quiz/assignment deadline theo enrollment |
| STU-010 | Student nhận certificate khi hoàn thành | Must | Certificate có cert_code public, trang xác thực chỉ hiển thị dữ liệu tối thiểu theo chính sách privacy ở mục 8.9 |
| STU-011 | Student xem notifications | Must | Có thể mark read từng notification hoặc tất cả |

### 9.8. Communication

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| COM-001 | Teacher tạo announcement trong course của mình | Must | Enrolled students nhận notification |
| COM-002 | Người dùng xem announcements của course | Should | Sắp xếp pinned trước, mới trước |
| COM-003 | Người dùng tạo forum thread | Should | Thread gắn đúng course và author |
| COM-004 | Người dùng reply thread | Should | Tác giả thread nhận notification nếu người reply khác tác giả |
| COM-005 | Teacher pin/unpin thread | Should | Chỉ teacher owner của course được pin |
| COM-006 | Teacher/Admin kiểm duyệt forum | Must | Teacher owner và Admin có thể ẩn/xóa thread/reply vi phạm; hành động được ghi audit log |
| COM-007 | Người dùng report nội dung forum | Should | Report tạo queue kiểm duyệt cho Teacher/Admin và không hiển thị thông tin reporter cho học viên khác |

### 9.9. Analytics & Export

| ID | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
| --- | --- | --- | --- |
| ANL-001 | Admin xem analytics tổng quan | Must | Các KPI tính từ DB hiện tại |
| ANL-002 | Admin export general report | Must | CSV tải được |
| ANL-003 | Admin export raw learning logs | Should | CSV chứa log_id/user_id/lesson_id/action/timestamp |
| ANL-004 | Admin export quiz attempts | Should | CSV chứa attempt data |
| ANL-005 | Admin export all data dạng ZIP | Should | ZIP chứa users/courses/enrollments/logs/quiz/datastudio |
| ANL-006 | Teacher export assignment grades | Must | CSV tải được |
| ANL-007 | Teacher export course gradebook | Must | CSV tải được |

## 10. Yêu cầu dữ liệu

### 10.1. Quy tắc dữ liệu

- Email người dùng phải duy nhất, lowercase khi nhập từ form.
- Role hợp lệ: `student`, `teacher`, `admin`, `hoc_vu`, `le_tan`, `ke_toan`.
- User có `is_active=False` không được đăng nhập.
- Course status hợp lệ: `draft`, `pending_review`, `published`, `rejected`.
- Student chỉ enroll được course `published`.
- Mỗi user-course không nên có hơn một enrollment active.
- Learning completion được xác định bằng distinct lesson complete logs.
- Certificate chỉ cấp một lần cho mỗi user-course.
- Quiz score tính theo phần trăm câu đúng.
- Assignment score production nên chuẩn hóa trong khoảng 0-100.
- File upload production phải dùng object storage, không phụ thuộc local filesystem container.

### 10.2. Migration và seed

- Production bắt buộc dùng Alembic migration, không dùng `db.create_all()` để tạo schema chính.
- Seed demo chỉ dùng development/staging.
- Không đưa tài khoản demo/password mặc định vào production.
- Dữ liệu import CSV phải có log, kết quả lỗi rõ ràng và cơ chế rollback/batch nếu có lỗi nghiêm trọng.

### 10.3. Retention

| Dữ liệu | Chính sách đề xuất |
| --- | --- |
| User/account | Mặc định soft delete/deactivate; hard delete chỉ thực hiện theo quy trình yêu cầu xóa dữ liệu có kiểm soát |
| Learning logs | Tối thiểu 24 tháng hoặc theo hợp đồng |
| Audit logs | Tối thiểu 12 tháng |
| Submission files | Theo vòng đời course hoặc yêu cầu tổ chức |
| Reset tokens | Hết hạn sau 1 giờ; xóa sau sử dụng |
| Exports | Không lưu lâu trên server; tải trực tiếp theo request |

### 10.4. Chính sách delete và privacy

- Hành động "delete user" trong UI production phải được định nghĩa là soft delete/deactivate mặc định: user không đăng nhập được, không xuất hiện trong danh sách active, nhưng dữ liệu học tập vẫn được giữ để bảo toàn gradebook, audit và báo cáo.
- Hard delete chỉ được thực hiện qua quy trình admin cấp cao hoặc job vận hành có kiểm soát, sau khi đánh giá ràng buộc pháp lý/hợp đồng và tác động đến transcript, certificate, audit log.
- Khi user bị soft delete, analytics tổng hợp có thể giữ dữ liệu dạng ẩn danh; các màn hình có PII phải mask hoặc ẩn user tùy cấu hình.
- Khi course bị soft delete, course không còn hiển thị trong catalog; dữ liệu lịch sử phục vụ transcript/certificate chỉ hiển thị cho người có quyền.
- Learning logs và audit logs không được hard delete tự động nếu còn nằm trong thời hạn retention.
- Certificate public của user/course đã bị soft delete phải chuyển sang trạng thái "revoked" hoặc "not publicly available" nếu chính sách privacy yêu cầu.

### 10.5. CSV import specification

| Thuộc tính | Yêu cầu |
| --- | --- |
| Encoding | UTF-8; chấp nhận UTF-8 BOM |
| Delimiter | Comma `,`; phase sau có thể hỗ trợ semicolon bằng auto-detect |
| Header row | Bắt buộc |
| Required columns | `email`, `role` |
| Optional columns | `phone`, `is_active`, `course_id`; phase sau có thể thêm `display_name` nếu model hỗ trợ |
| Role values | `student`, `teacher`, `admin`, `hoc_vu`, `le_tan`, `ke_toan`; giá trị khác bị reject từng dòng |
| Email handling | Trim, lowercase, validate có `@`; email trùng mặc định bị skip và ghi kết quả "exists" |
| Update existing | Không update user đã tồn tại trong bản production đầu tiên, trừ khi có option explicit `update_existing=true` ở phase sau |
| Max file size | Theo `MAX_CONTENT_LENGTH`; khuyến nghị giới hạn CSV import riêng tối đa 5 MB |
| Max rows | 5.000 dòng/file cho phase 1 |
| Error policy | Lỗi từng dòng không rollback toàn bộ batch; lỗi parse/header làm fail cả file |
| Output | Trang kết quả phải liệt kê email, status, reason, temp password nếu tạo mới |

## 11. Yêu cầu phi chức năng

### 11.1. Bảo mật

- Production bắt buộc có `SECRET_KEY` mạnh, không dùng default.
- Bật HTTPS và secure cookie.
- CSRF phải bật cho tất cả form thay đổi dữ liệu.
- Rate limit phải dùng Redis, không dùng memory backend trong production.
- Password phải hash bằng Werkzeug hoặc thuật toán tương đương; không log password/token.
- Reset password không được tiết lộ email có tồn tại hay không.
- CSP phải được kiểm tra để không mở quá rộng `unsafe-inline` trong dài hạn.
- File upload phải giới hạn size, extension, MIME type và scan malware nếu dùng thật.
- OAuth redirect URI phải whitelist theo domain production.
- Admin routes, Teacher owner checks và Student enrollment checks phải được test đầy đủ.
- Audit log phải ghi actor, action, target, IP và timestamp cho hành động nhạy cảm.

### 11.2. Hiệu năng

- P95 response time cho trang HTML chính: dưới 800ms trong load profile phase 1.
- P95 response time cho export nhỏ/trung bình: dưới 5s với file dưới 10.000 rows.
- Hỗ trợ tối thiểu production phase 1: 5.000 users, 500 concurrent active users, 1.000 courses, 100.000 learning logs.
- Load profile phase 1 để nghiệm thu: 500 concurrent users, 50 RPS duy trì trong 15 phút, 70% read requests, 20% write requests, 10% export/report requests.
- Baseline hạ tầng để đo phase 1: web container Gunicorn 4 workers, PostgreSQL trên tối thiểu 2 vCPU/4 GB RAM, Redis riêng, static assets qua CDN hoặc reverse proxy cache.
- Kịch bản đo phải bao gồm login, course catalog, student dashboard, learning page, quiz submit, assignment submit, teacher gradebook và admin analytics.
- Các truy vấn dashboard, gradebook, analytics phải tránh N+1 query.
- Các bảng lớn cần index theo foreign key, role/status/timestamp.
- Export lớn nên chuyển sang background job ở phase sau.

### 11.3. Khả dụng và vận hành

- Uptime mục tiêu phase 1: 99.5%.
- Email reset password phải được gửi thành công tới SMTP provider trong vòng 60 giây ở P95; email announcement/notification batch phải được enqueue hoặc gửi trong vòng 5 phút ở P95.
- Khi SMTP provider lỗi, hệ thống phải log lỗi có request_id, không làm lộ reset token ở production logs, và hiển thị thông báo chung cho người dùng.
- Có `/healthz` cho liveness và `/readyz` cho readiness.
- Có structured JSON logs trong production.
- Có request ID trên response header.
- Có backup database tự động hằng ngày.
- Có khả năng restore backup định kỳ để kiểm chứng.
- Có rollback deployment.
- Không chạy Flask dev server ở production; dùng Gunicorn.
- Alerting tối thiểu:
  - Error rate HTTP 5xx > 2% trong 5 phút.
  - P95 latency trang HTML > 1.500ms trong 10 phút.
  - `/readyz` fail liên tục 3 lần.
  - Database connection pool saturation > 80% trong 5 phút.
  - Disk/storage usage > 80%.
  - Failed login rate > 50 lần/phút hoặc tăng đột biến theo baseline.
  - Email send failure rate > 5% trong 10 phút.
  - Background job queue age > 10 phút nếu đã có queue.

### 11.4. Khả năng mở rộng

- Web app phải stateless ngoài database, Redis và object storage.
- Upload file production dùng S3-compatible storage.
- Flask session mặc định là client-side signed cookie; multi-instance production không cần server-side session store nếu mọi instance dùng cùng `SECRET_KEY` và cookie config giống nhau.
- Nếu sau này cần revoke session tức thời hoặc lưu session lớn, bổ sung Flask-Session với Redis và đưa vào scope riêng.
- Rate limit storage dùng Redis chung.
- Background jobs có thể bổ sung cho email batch, export lớn, analytics aggregation.

### 11.5. Khả dụng giao diện

- Các trang chính phải responsive cho desktop/tablet/mobile.
- Form phải có validation lỗi rõ ràng.
- Bảng lớn cần pagination/search/filter.
- Các action nguy hiểm cần confirm.
- Thông báo lỗi/thành công phải nhất quán.
- Không để text mojibake/encoding lỗi trên UI production.

## 12. Production readiness checklist

### 12.1. Critical security trước production

1. Bổ sung owner/enrollment authorization cho forum, announcements, quiz, assignment và public course resources.
2. Chặn Student truy cập quiz/assignment nếu chưa enroll course.
3. Chặn Teacher thao tác question/assignment/submission không thuộc course của mình.
4. Validate file upload: extension, MIME type, size, filename, private/public access.
5. Không expose file submission nhạy cảm qua static public path nếu bài nộp cần riêng tư.
6. Xóa route seed khỏi production build hoặc giữ route nhưng production luôn trả 404/403, không expose demo credentials, không cho seed qua UI production.
7. Bật Redis rate limiter trong production và kiểm tra cấu hình `RATELIMIT_STORAGE_URI`.
8. Đảm bảo production fail-fast nếu thiếu `SECRET_KEY`, cấu hình OAuth/SMTP/S3 sai hoặc migration lỗi.
9. CSRF phải bật cho mọi POST/PUT/DELETE state-changing route.
10. Audit log phải ghi grade changes, import, export, role changes, permission denied và moderation actions.

### 12.2. High data integrity trước production

1. Chuẩn hóa timezone: dùng timezone-aware UTC nhất quán thay vì trộn `datetime.utcnow()` và timezone-aware datetime.
2. Thêm unique constraint hoặc logic chắc chắn cho enrollment `user_id + course_id`.
3. Thêm unique constraint cho certificate `user_id + course_id`.
4. Sửa logic reorder lesson đang gán `lesson.order` trong khi model dùng `sequence_order`.
5. Validate score assignment trong khoảng 0-100.
6. Bổ sung database cascade hoặc service delete an toàn cho user/course/lesson/quiz/assignment để tránh orphan data hoặc lỗi FK.
7. Thay hard delete user/course bằng soft delete mặc định và hard delete có quy trình kiểm soát.
8. Hoàn thiện test suite cho role access, course approval, quiz attempts, assignment deadline, certificate, import CSV, exports.
9. Đảm bảo migration chạy trước app start và fail-fast nếu migration lỗi.
10. Kiểm tra Dockerfile: `chmod +x entrypoint.sh` sau `USER e16user` có thể lỗi build nếu user không có quyền thay đổi mode; nên chmod trước khi switch user.

### 12.3. Medium operational readiness

1. Sửa lỗi encoding tiếng Việt/mojibake trong README, flash messages, templates và seed data.
2. Bổ sung pagination cho users, courses, audit logs, notifications, submissions, gradebook.
3. Thiết lập backup/restore, monitoring, alerting và log aggregation.
4. Hoàn thiện email SLA, retry/fallback và logging.
5. Chạy load test theo baseline ở mục 11.2.
6. Hoàn thiện certificate verification privacy flow.
7. Hoàn thiện moderation UI cho forum/report content.

### 12.4. Should fix cho production chất lượng cao

1. Tách business logic khỏi route để dễ test.
2. Chuẩn hóa notification type bằng enum/constant.
3. Chuẩn hóa trạng thái submission/enrollment/course bằng enum/constant.
4. Dùng form validation library hoặc WTForms đầy đủ.
5. Thêm audit log cho login failure, import, export, grade changes và permission denied.
6. Thêm email templates cho announcement/assignment/graded nếu cần.
7. Thêm background queue cho email hàng loạt và export lớn.
8. Thêm OpenAPI/internal route inventory cho QA.
9. Thêm data anonymization cho export nếu chia sẻ cho bên thứ ba.
10. Thêm admin dashboard kiểm tra storage/mail/oauth/db/redis.

## 13. Tiêu chí nghiệm thu production

### 13.1. Functional acceptance

- Admin có thể tạo/import/quản lý user và category.
- Teacher có thể tạo course, lesson, quiz, assignment và gửi duyệt.
- Admin có thể duyệt course.
- Student có thể tìm course, enroll, học lesson, complete lesson.
- Student có thể làm quiz và nhận điểm.
- Student có thể nộp assignment, Teacher chấm điểm, Student nhận notification.
- Student hoàn thành toàn bộ lessons nhận certificate.
- Admin và Teacher export được báo cáo tương ứng.
- Role unauthorized bị chặn đúng.

### 13.2. Security acceptance

- Không route nhạy cảm nào truy cập được khi chưa login.
- Không role nào truy cập vượt quyền.
- Không Teacher nào sửa được dữ liệu course của Teacher khác.
- Không Student nào truy cập được course private/chưa enroll cho hoạt động học.
- CSRF hoạt động trên các POST form.
- Rate limit hoạt động với Redis.
- Production không chạy nếu thiếu SECRET_KEY.
- Reset password token hết hạn đúng và không tái sử dụng được.

### 13.3. Operational acceptance

- Docker image build thành công.
- Container web chạy non-root.
- `flask db upgrade` chạy thành công trên database sạch.
- `/healthz` trả 200.
- `/readyz` trả 200 khi database sẵn sàng và 503 khi database lỗi.
- Logs có JSON format và request_id trong production.
- Backup database chạy tự động và restore test thành công.
- Deploy rollback được về version trước.

### 13.4. Quality acceptance

- Test suite pass trên CI.
- Coverage tối thiểu đề xuất: 70% line coverage cho service và route core.
- Không có lỗi critical/high từ dependency scanning.
- Không có secret trong repo.
- Không còn mojibake ở UI/tài liệu.
- Lighthouse/accessibility smoke test cho các trang chính đạt ngưỡng nội bộ.

## 14. Rủi ro và phương án giảm thiểu

| Rủi ro | Tác động | Giảm thiểu |
| --- | --- | --- |
| Lỗi phân quyền route nested | Lộ dữ liệu course/submission | Thêm test matrix role/owner/enrollment cho tất cả routes |
| Xóa dữ liệu gây orphan hoặc mất lịch sử | Mất dữ liệu học tập | Soft delete, cascade rõ ràng, backup |
| File upload public | Lộ bài nộp học viên | S3 private bucket, signed URL, kiểm soát quyền |
| Export lớn gây timeout | Ảnh hưởng hiệu năng | Background job, streaming, giới hạn date range |
| Encoding lỗi tiếng Việt | Sản phẩm thiếu chuyên nghiệp | Chuẩn hóa UTF-8 toàn repo |
| Trộn timezone | Sai deadline, logs, reports | Dùng timezone-aware UTC và convert ở UI |
| Memory rate limiter ở multi-instance | Rate limit không chính xác | Bắt buộc Redis production |
| Seed/demo credentials xuất hiện ở prod | Rủi ro bảo mật | Seed chỉ dev/staging, secret scanning |
| CSP còn `unsafe-inline` | Rủi ro XSS | Refactor inline script/style, nonce/hashing |

## 15. Roadmap triển khai production

### Phase 0 - Hardening bắt buộc

- Sửa encoding tiếng Việt.
- Sửa authorization gaps.
- Sửa reorder lesson.
- Chuẩn hóa datetime/timezone.
- Thêm constraints DB quan trọng.
- Bổ sung validation form và upload.
- Tăng coverage test cho nghiệp vụ lõi.

### Phase 1 - Production infrastructure

- Hoàn thiện Docker build/startup.
- PostgreSQL managed hoặc HA-ready.
- Redis cho rate limit.
- S3-compatible storage cho uploads.
- SMTP production.
- CI/CD với test, migration check, image scan.
- Backup/restore và monitoring.

### Phase 2 - Operational UX

- Pagination/filter/search cho admin tables và gradebook.
- Bulk actions an toàn.
- Better analytics performance.
- Background jobs cho export/email.
- Admin health dashboard.

### Phase 3 - Product expansion

- Multi-tenant/basic organization.
- SCORM/xAPI hoặc LTI.
- Payment provider nâng cao hoặc course marketplace nếu cần thương mại hóa.
- Advanced reporting.
- Mobile responsive polish hoặc PWA.

## 16. Yêu cầu môi trường production

| Hạng mục | Cấu hình đề xuất |
| --- | --- |
| Runtime | Python 3.12 |
| App server | Gunicorn |
| Database | PostgreSQL 15+ |
| Cache/rate limit | Redis 7+ |
| Object storage | AWS S3 hoặc S3-compatible |
| Email | SMTP provider production |
| Reverse proxy | Nginx/Cloudflare/Load Balancer |
| TLS | Bắt buộc HTTPS |
| Secrets | Secret manager hoặc env injected an toàn |
| Observability | Log aggregation, metrics, uptime checks, alerts |
| Backup | Daily full backup, PITR nếu có thể |

## 17. Biến môi trường bắt buộc/khuyến nghị

| Biến | Bắt buộc production | Ghi chú |
| --- | --- | --- |
| `APP_ENV=production` | Có | Chọn production config |
| `SECRET_KEY` | Có | Secret mạnh, không commit |
| `DATABASE_URL` | Có | PostgreSQL URL |
| `APP_BASE_URL` | Có | Domain app LMS dùng cho OAuth redirect, reset password và link hệ thống |
| `PUBLIC_SITE_URL` | Khuyến nghị | Domain landing/public marketing, ví dụ `www.e16...` |
| `PAYMENT_MODE` | Có | `mock` chỉ dùng dev/staging; production dùng provider thật hoặc quy trình đối soát thủ công có audit |
| `RATELIMIT_STORAGE_URI` | Có | Redis URL |
| `SESSION_COOKIE_SECURE=True` | Có | Khi chạy HTTPS |
| `MAIL_SERVER` | Có nếu bật email | SMTP |
| `MAIL_PORT` | Có nếu bật email | SMTP |
| `MAIL_USERNAME` | Có nếu bật email | SMTP |
| `MAIL_PASSWORD` | Có nếu bật email | SMTP |
| `MAIL_DEFAULT_SENDER` | Có nếu bật email | Sender |
| `GOOGLE_CLIENT_ID` | Có nếu bật OAuth | Google OAuth |
| `GOOGLE_CLIENT_SECRET` | Có nếu bật OAuth | Google OAuth |
| `STORAGE_BACKEND=s3` | Khuyến nghị | Production upload |
| `AWS_S3_BUCKET` | Có nếu S3 | Bucket |
| `AWS_S3_REGION` | Có nếu S3 | Region |
| `AWS_ACCESS_KEY_ID` | Có nếu S3 | Credential |
| `AWS_SECRET_ACCESS_KEY` | Có nếu S3 | Credential |
| `SUPABASE_URL` | Tùy chọn | External logging |
| `SUPABASE_KEY` | Tùy chọn | External logging |

## 18. Test strategy

### 18.1. Unit tests

- GradingService: MCQ, checkbox, fill-in-blank, zero question, random served questions.
- Course service: completion rate, certificate issuance, duplicate prevention.
- Settings cache: get/flush.
- Storage service: local và mocked S3.

### 18.2. Integration tests

- Auth login/logout/reset password, cấp tài khoản và OAuth login-only.
- Role access matrix cho Admin, Học vụ, Lễ tân, Kế toán, Teacher và Student.
- Course lifecycle draft -> pending_review -> published/rejected.
- Student enroll -> learn -> complete -> certificate.
- Assignment submit -> grade -> notification.
- Quiz publish -> attempt limit -> gradebook.
- CSV import/export.

### 18.3. Security tests

- CSRF enforced.
- Unauthorized POST blocked.
- Teacher cannot access other teacher resources.
- Student cannot access non-enrolled learning resources.
- Inactive account blocked.
- Rate limit triggered.
- Upload file restrictions.

### 18.4. Smoke tests

- App boots with production config.
- DB migration applies.
- Health/readiness endpoints.
- Main pages render for each role.
- Static assets load.
- Email send can be mocked/sandboxed.

## 19. Release plan

1. Tạo staging environment giống production.
2. Chạy migration trên staging database sạch.
3. Seed dữ liệu staging.
4. Chạy automated tests và manual UAT theo checklist.
5. Chạy security scan và dependency scan.
6. Kiểm tra backup/restore staging.
7. Chạy load smoke test theo các route chính.
8. Freeze release candidate.
9. Deploy production ngoài giờ cao điểm.
10. Theo dõi logs, metrics, errors trong 24-48 giờ đầu.

## 20. Definition of Done cho production

E16 LMS được xem là sẵn sàng production khi:

- Toàn bộ Must requirements trong BRD được đáp ứng.
- Không còn issue critical/high về security hoặc data integrity.
- Các route chính có test pass trên CI.
- Test coverage tối thiểu 70% line coverage cho service và route core; riêng auth, authorization, grading, enrollment, assignment và certificate phải có positive/negative tests.
- Docker image build và chạy ổn định với PostgreSQL/Redis.
- Migration và rollback được kiểm chứng.
- Backup/restore được kiểm chứng.
- Monitoring/alerting hoạt động.
- Email reset password đạt SLA P95 60 giây trong staging test hoặc provider sandbox test.
- Load test phase 1 đạt baseline ở mục 11.2.
- Admin, Học vụ, Lễ tân, Kế toán, Teacher và Student UAT pass.
- Tài liệu vận hành và biến môi trường production đầy đủ.

## 21. Phụ lục - Route inventory nghiệp vụ

### Auth

- `/auth/register` (development/staging hoặc luồng nội bộ; production public không dùng self-registration)
- `/auth/login`
- `/auth/logout`
- `/auth/forgot-password`
- `/auth/reset-password/<token>`
- `/auth/login/<name>`
- `/auth/authorize/<name>`

### Student

- `/courses`
- `/dashboard`
- `/checkout/<course_id>`
- `/checkout/simulate-ipn/<course_id>` (development/staging only khi `PAYMENT_MODE=mock`)
- `/checkout/cancel/<course_id>`
- `/enroll/<course_id>`
- `/learn/<course_id>`
- `/learn/<course_id>/complete/<lesson_id>`
- `/learn/<course_id>/quiz/<quiz_id>`
- `/learn/<course_id>/quiz/<quiz_id>/review/<attempt_id>`
- `/learn/<course_id>/assignment/<assignment_id>`
- `/transcript`
- `/calendar`
- `/certificates`
- `/submissions/<submission_id>/download`
- `/certificates/<cert_code>`

### Teacher

- `/teacher/dashboard`
- `/teacher/manage`
- `/teacher/courses/new`
- `/teacher/courses/<course_id>/edit`
- `/teacher/courses/<course_id>/submit`
- `/teacher/courses/<course_id>/delete`
- `/teacher/courses/<course_id>/students`
- `/teacher/courses/<course_id>/lessons`
- `/teacher/courses/<course_id>/lessons/new`
- `/teacher/courses/<course_id>/lessons/reorder`
- `/teacher/courses/<course_id>/lessons/<lesson_id>/edit`
- `/teacher/courses/<course_id>/lessons/<lesson_id>/delete`
- `/teacher/courses/<course_id>/quizzes`
- `/teacher/courses/<course_id>/quizzes/new`
- `/teacher/courses/<course_id>/quizzes/<quiz_id>/edit`
- `/teacher/quizzes/<quiz_id>/questions/add`
- `/teacher/courses/<course_id>/assignments`
- `/teacher/courses/<course_id>/assignments/new`
- `/teacher/assignments/<assignment_id>/submissions`
- `/teacher/submissions/<submission_id>/grade`
- `/teacher/assignments/<assignment_id>/export`
- `/teacher/courses/<course_id>/gradebook`
- `/teacher/courses/<course_id>/gradebook/export`
- `/teacher/courses/<course_id>/analytics`

### Admin

Ghi chú production: `/admin/seed` chỉ được phép tồn tại ở development/staging. Trong production, route này phải bị xóa khỏi route table hoặc luôn trả 404/403 trước khi thực hiện bất kỳ logic seed nào.

- `/admin/users`
- `/admin/users/create`
- `/admin/users/<user_id>/update_role`
- `/admin/users/<user_id>/delete`
- `/admin/users/<user_id>/toggle_status`
- `/admin/users/import`
- `/admin/categories`
- `/admin/categories/new`
- `/admin/categories/<cat_id>/edit`
- `/admin/categories/<cat_id>/delete`
- `/admin/settings`
- `/admin/settings/update`
- `/admin/audit-log`
- `/admin/courses/pending`
- `/admin/courses/<course_id>/approve`
- `/admin/courses/<course_id>/reject`
- `/admin/seed` (development/staging only; forbidden in production)

### Học vụ

- `/hoc-vu/dashboard`
- `/hoc-vu/courses/pending`
- `/hoc-vu/courses/<course_id>/review`

### Lễ tân

- `/le-tan/dashboard`
- `/le-tan/students`
- `/le-tan/students/<user_id>`
- `/le-tan/students/<user_id>/reset-password`
- `/le-tan/students/create`
- `/le-tan/enroll`

### Kế toán

- `/ke-toan/dashboard`
- `/ke-toan/reconciliation`
- `/ke-toan/reconciliation/approve/<enroll_id>`
- `/ke-toan/reconciliation/reject/<enroll_id>`
- `/ke-toan/revenue`
- `/ke-toan/refund/<enroll_id>`
- `/ke-toan/export-revenue`

### Communication

- `/notifications`
- `/notifications/<notif_id>/read`
- `/notifications/read-all`
- `/courses/<course_id>/announcements`
- `/teacher/courses/<course_id>/announcements/new`
- `/courses/<course_id>/forum`
- `/courses/<course_id>/forum/new`
- `/courses/<course_id>/forum/<thread_id>`
- `/courses/<course_id>/forum/<thread_id>/reply`
- `/teacher/forum/<thread_id>/pin`

### Analytics và health

- `/analytics/`
- `/analytics/export`
- `/healthz`
- `/readyz`
