import os
import random
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash

from e16_app import create_app
from e16_app.extensions import db
from e16_app.models import (
    User, Category, Course, SystemSetting, Lesson,
    Enrollment, LearningLog, Quiz, Question, Choice,
    QuizAttempt, QuizAnswer, Assignment, Submission,
    Notification, Announcement, ForumThread, ForumReply,
    Certificate, AuditLog, new_uuid
)
from supabase import create_client

def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return create_client(url, key)
    return None

def run_comprehensive_seed():
    app = create_app()
    with app.app_context():
        print("🚀 BẮT ĐẦU QUÁ TRÌNH SEED DỮ LIỆU TOÀN DIỆN 🚀")

        # 1. Đảm bảo các bảng tồn tại (tự động tạo bảng thiếu)
        db.create_all()

        # 2. SEED SYSTEM SETTINGS & CATEGORIES
        print("1️⃣ Khởi tạo Cấu hình hệ thống & Danh mục...")
        settings_data = [
            {"key": "site_name", "value": "E16 LMS Pro", "description": "Tên hệ thống"},
            {"key": "site_logo_url", "value": "https://images.unsplash.com/photo-1614850523296-d8c1af93d400", "description": "Logo"},
            {"key": "allow_registration", "value": "True", "description": "Cho phép đăng ký"}
        ]
        for s in settings_data:
            if not db.session.query(SystemSetting).filter_by(key=s["key"]).first():
                db.session.add(SystemSetting(**s))

        categories_data = [
            {"name": "Công nghệ thông tin", "slug": "it", "icon": "💻", "sort_order": 1},
            {"name": "Kinh doanh & Khởi nghiệp", "slug": "business", "icon": "📈", "sort_order": 2},
            {"name": "Thiết kế đồ họa", "slug": "design", "icon": "🎨", "sort_order": 3}
        ]
        categories = {}
        for c in categories_data:
            cat = db.session.query(Category).filter_by(slug=c["slug"]).first()
            if not cat:
                cat = Category(**c)
                db.session.add(cat)
            categories[cat.slug] = cat
        db.session.commit()

        # 3. SEED CORE USERS (Admin, Core Teacher, Core Student)
        print("2️⃣ Khởi tạo Tài khoản Core (Admin/Teacher/Student)...")
        app_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "production")).lower()
        is_local = not os.environ.get("VERCEL") and app_env in ("development", "testing")

        if is_local:
            core_users = [
                ("admin_local@e16.local", "admin_local_pass", "admin"),
                ("teacher_local@e16.local", "teacher_local_pass", "teacher"),
                ("student_local@e16.local", "student_local_pass", "student"),
                ("hocvu_local@e16.local", "hocvu_local_pass", "hoc_vu")
            ]
        else:
            core_users = [
                ("admin@e16.local", "admine16", "admin"),
                ("teacher@e16.local", "teachere16", "teacher"),
                ("student@e16.local", "studente16", "student"),
                ("hocvu@e16.local", "hocvue16", "hoc_vu")
            ]

        core_objects = {}
        for email, pwd, role in core_users:
            u = db.session.query(User).filter_by(email=email).first()
            last_login_time = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24))
            created_time = last_login_time - timedelta(days=random.randint(30, 60))
            if not u:
                u = User(
                    email=email,
                    password_hash=generate_password_hash(pwd),
                    role=role,
                    is_active=True,
                    phone="0988123456",
                    created_at=created_time,
                    last_login=last_login_time,
                    login_count=random.randint(5, 50)
                )
                db.session.add(u)
            else:
                u.password_hash = generate_password_hash(pwd) # Đảm bảo pass chuẩn
                u.phone = "0988123456"
                u.created_at = created_time
                u.last_login = last_login_time
                u.login_count = random.randint(5, 50)
            core_objects[role] = u
        db.session.commit()

        # 4. SEED RANDOM USERS
        print("3️⃣ Khởi tạo thêm Giảng viên và Học viên ngẫu nhiên...")
        batch_id = random.randint(1000, 9999)
        teachers = [core_objects["teacher"]]
        for i in range(3):
            phone_num = f"09{random.randint(10000000, 99999999)}"
            last_login_time = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 15), hours=random.randint(0, 23))
            created_time = last_login_time - timedelta(days=random.randint(10, 50))
            t = User(
                email=f"teacher_gen_{batch_id}_{i}@e16.local",
                password_hash=generate_password_hash("123456"),
                role="teacher",
                phone=phone_num,
                created_at=created_time,
                last_login=last_login_time,
                login_count=random.randint(2, 20)
            )
            db.session.add(t)
            teachers.append(t)

        students = [core_objects["student"]]
        for i in range(20): # Seed 20 học viên test
            phone_num = f"09{random.randint(10000000, 99999999)}"
            last_login_time = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 20), hours=random.randint(0, 23))
            created_time = last_login_time - timedelta(days=random.randint(5, 40))
            s = User(
                email=f"student_gen_{batch_id}_{i}@e16.local",
                password_hash=generate_password_hash("123456"),
                role="student",
                phone=phone_num,
                created_at=created_time,
                last_login=last_login_time,
                login_count=random.randint(1, 15)
            )
            db.session.add(s)
            students.append(s)
        db.session.commit()

        # 4.5 SEED LOGIN AUDIT LOGS
        print("💡 Khởi tạo lịch sử Audit Log đăng nhập...")
        all_created_users = teachers + students
        for u in all_created_users:
            if u.last_login:
                for log_idx in range(random.randint(1, 5)):
                    log_time = u.last_login - timedelta(days=log_idx, hours=random.randint(0, 12))
                    audit = AuditLog(
                        actor_id=u.id,
                        action="login_success",
                        target_type="User",
                        target_id=u.id,
                        ip_address=f"192.168.1.{random.randint(2, 254)}",
                        created_at=log_time
                    )
                    db.session.add(audit)
        db.session.commit()

        # 4.7 UPDATE ALL EXISTING USERS IN THE DATABASE (CLEANUP & FILL PHONES/TIMELINES)
        print("🔧 Cập nhật số điện thoại và sửa mâu thuẫn thời gian cho TOÀN BỘ User cũ...")
        all_users = User.query.all()
        updated_count = 0
        for u in all_users:
            needs_update = False

            # 1. Điền số điện thoại nếu trống
            if not u.phone or len(u.phone.strip()) < 8:
                u.phone = f"09{random.randint(10000000, 99999999)}"
                needs_update = True

            # 2. Xử lý mâu thuẫn ngày tham gia và lần đăng nhập cuối
            # Chuyển all datetimes sang naive để so sánh an toàn
            current_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            user_created_str = u.created_at.strftime("%Y-%m-%d") if u.created_at else current_date_str

            if not u.created_at or user_created_str == current_date_str:
                # Gán ngày tham gia ngẫu nhiên trong vòng 1-6 tháng qua
                u.created_at = (datetime.now(timezone.utc) - timedelta(days=random.randint(30, 180), hours=random.randint(0, 23))).replace(tzinfo=None)
                needs_update = True

            if u.last_login:
                last_login_naive = u.last_login.replace(tzinfo=None)
                created_at_naive = u.created_at.replace(tzinfo=None)
                if last_login_naive <= created_at_naive:
                    u.last_login = (u.created_at.replace(tzinfo=None) + timedelta(days=random.randint(1, 10), hours=random.randint(1, 23)))
                    needs_update = True
            else:
                if (u.login_count and u.login_count > 0) or random.random() > 0.3:
                    u.last_login = (u.created_at.replace(tzinfo=None) + timedelta(days=random.randint(1, 15), hours=random.randint(1, 23)))
                    u.login_count = u.login_count or random.randint(1, 25)
                    needs_update = True

            if needs_update:
                updated_count += 1

        db.session.commit()
        print(f"✅ Đã dọn dẹp và cập nhật thành công {updated_count} user có sẵn trong database!")

        # 5. SEED COURSES, LESSONS, QUIZZES & ASSIGNMENTS
        print("4️⃣ Khởi tạo Khóa học, Bài giảng, Quiz, Bài tập, Thông báo...")
        all_courses = []
        for teacher in teachers:
            for c_idx in range(2):
                cat = random.choice(list(categories.values()))
                course = Course(
                    title=f"Khóa học {cat.name} - Lớp {batch_id}_{c_idx}",
                    short_description="Khóa học tổng hợp kiến thức từ cơ bản đến nâng cao.",
                    description="Mô tả chi tiết khóa học, lộ trình học tập và kết quả đạt được.",
                    category_id=cat.id,
                    teacher_id=teacher.id,
                    status="published",
                    published_at=datetime.now(timezone.utc),
                    total_lessons=5
                )
                db.session.add(course)
                all_courses.append(course)
                db.session.commit()

                # Announcement
                db.session.add(Announcement(course_id=course.id, author_id=teacher.id, title="Chào mừng khóa học", body="Chúc các bạn học tốt!"))

                # Forum Thread
                thread = ForumThread(course_id=course.id, author_id=teacher.id, title="Hỏi đáp chung", body="Đặt câu hỏi tại đây.")
                db.session.add(thread)
                db.session.commit()
                db.session.add(ForumReply(thread_id=thread.id, author_id=students[0].id, body="Em chào thầy ạ!"))

                # Lessons
                course_lessons = []
                for l_idx in range(5):
                    l = Lesson(course_id=course.id, title=f"Bài {l_idx + 1}: Lý thuyết cốt lõi", sequence_order=l_idx + 1)
                    db.session.add(l)
                    course_lessons.append(l)

                # Quiz
                quiz = Quiz(course_id=course.id, title="Kiểm tra trắc nghiệm cuối khóa", pass_score=60, max_attempts=3, is_published=True)
                db.session.add(quiz)
                db.session.commit()

                for q_idx in range(3):
                    q = Question(quiz_id=quiz.id, text=f"Câu hỏi số {q_idx + 1} có nội dung là gì?", q_type="mcq")
                    db.session.add(q)
                    db.session.commit()
                    db.session.add(Choice(question_id=q.id, text="Đáp án Đúng", is_correct=True))
                    db.session.add(Choice(question_id=q.id, text="Đáp án Sai 1", is_correct=False))
                    db.session.add(Choice(question_id=q.id, text="Đáp án Sai 2", is_correct=False))

                # Assignment
                assign = Assignment(course_id=course.id, title="Bài tập thực hành", description="Nộp file word hoặc pdf.", deadline=datetime.now(timezone.utc) + timedelta(days=7))
                db.session.add(assign)

        db.session.commit()

        # 6. SEED ENROLLMENTS, LOGS, SUBMISSIONS & CERTIFICATES
        print("5️⃣ Khởi tạo Quá trình học tập (Enrollments, Logs, Submissions, Chứng chỉ)...")
        for student in students:
            # Chọn 3 khóa học ngẫu nhiên
            for course in random.sample(all_courses, min(3, len(all_courses))):
                enroll = Enrollment(user_id=student.id, course_id=course.id, status="active", enrolled_at=datetime.now(timezone.utc) - timedelta(days=10))
                db.session.add(enroll)

                # Learning logs
                lessons = Lesson.query.filter_by(course_id=course.id).all()
                completed_lessons = random.randint(1, len(lessons))
                for i in range(completed_lessons):
                    db.session.add(LearningLog(user_id=student.id, lesson_id=lessons[i].id, action_type="start"))
                    db.session.add(LearningLog(user_id=student.id, lesson_id=lessons[i].id, action_type="complete"))

                # Nếu hoàn thành 100% lessons -> Cấp chứng chỉ
                if completed_lessons == len(lessons):
                    enroll.status = "completed"
                    db.session.add(Certificate(user_id=student.id, course_id=course.id))

                # Quiz Attempts
                quiz = Quiz.query.filter_by(course_id=course.id).first()
                if quiz and random.random() > 0.5:
                    score = random.randint(40, 100)
                    db.session.add(QuizAttempt(quiz_id=quiz.id, user_id=student.id, score=score, passed=(score >= quiz.pass_score), completed_at=datetime.now(timezone.utc)))

                # Submissions
                assign = Assignment.query.filter_by(course_id=course.id).first()
                if assign and random.random() > 0.5:
                    sub = Submission(assignment_id=assign.id, user_id=student.id, text_content="Em nộp bài ạ.", status="graded", score=random.randint(60, 100), graded_at=datetime.now(timezone.utc), graded_by=course.teacher_id)
                    db.session.add(sub)
                    db.session.add(Notification(user_id=student.id, type="graded", message=f"Bài tập '{assign.title}' đã được chấm điểm!"))

        db.session.commit()
        print("✅ Dữ liệu Local SQLite đã được Seed đầy đủ!")

        # 7. SUPABASE SYNC (Optional)
        supabase = get_supabase()
        if supabase:
            print("6️⃣ Đang đồng bộ lên Supabase...")
            try:
                # Chỉ sync Users (lõi quan trọng nhất để login đa nền tảng nếu cần)
                # Vì các bảng khác có cấu trúc FK phức tạp, nếu Push toàn bộ sẽ tốn thời gian và dễ lỗi FK.
                # Ở script này ta sẽ Upsert toàn bộ User.
                all_users = User.query.all()
                sb_users = []
                for u in all_users:
                    sb_users.append({
                        "id": u.id, "email": u.email, "password_hash": u.password_hash,
                        "phone": u.phone, "role": u.role, "is_active": u.is_active,
                        "login_count": u.login_count or 0,
                        "created_at": u.created_at.isoformat() if u.created_at else datetime.now(timezone.utc).isoformat()
                    })

                # Batch upsert with schema-mismatch self-healing fallback
                try:
                    for i in range(0, len(sb_users), 100):
                        supabase.table("users").upsert(sb_users[i:i+100]).execute()
                except Exception as e:
                    err_msg = str(e)
                    if "is_active" in err_msg or "phone" in err_msg:
                        print("⚠️ Supabase schema mismatch detected. Retrying with basic fields...")
                        for u_data in sb_users:
                            if "is_active" in err_msg:
                                u_data.pop("is_active", None)
                            if "phone" in err_msg:
                                u_data.pop("phone", None)
                        for i in range(0, len(sb_users), 100):
                            supabase.table("users").upsert(sb_users[i:i+100]).execute()
                    else:
                        raise e
                print("✅ Đồng bộ Users lên Supabase thành công!")

            except Exception as e:
                print(f"❌ Lỗi khi đồng bộ Supabase: {e}")
        else:
            print("⚠️ Bỏ qua bước đồng bộ Supabase (chưa cấu hình trong .env).")

        print("🎉 HOÀN TẤT! Dữ liệu đã sẵn sàng để demo/test toàn diện.")

if __name__ == "__main__":
    run_comprehensive_seed()
