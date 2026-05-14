import os
import random
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash

from e16_app import create_app
from e16_app.extensions import db
from e16_app.models import (
    User, Course, Lesson, Quiz, Question, Choice, 
    Enrollment, QuizAttempt, LearningLog, new_uuid
)
from supabase import create_client, Client

def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return create_client(url, key)
    return None

def run_complex_seed():
    app = create_app()
    with app.app_context():
        print("Bắt đầu tạo dữ liệu phức tạp...")
        supabase = get_supabase()
        
        students = User.query.filter_by(role="student").all()
        if not students:
            print("Không tìm thấy học sinh nào. Vui lòng chạy lại script tạo 300 users trước.")
            return

        # Dữ liệu cho Supabase
        sb_users = []
        sb_courses = []
        sb_lessons = []
        sb_quizzes = []
        sb_questions = []
        sb_choices = []
        sb_enrollments = []
        sb_quiz_attempts = []

        # 1. Tạo Teachers
        num_teachers = random.randint(15, 20)
        teachers = []
        for i in range(num_teachers):
            tid = new_uuid()
            email = f"teacher_{i+1}_{random.randint(1000, 9999)}@e16.edu.vn"
            pwd_hash = generate_password_hash("123456")
            phone = f"09{random.randint(10000000, 99999999)}"
            t = User(id=tid, email=email, password_hash=pwd_hash, role="teacher", phone=phone)
            teachers.append(t)
            
            sb_users.append({
                "id": tid, "email": email, "password_hash": pwd_hash, 
                "phone": phone, "role": "teacher", "login_count": 0, 
                "created_at": datetime.now(timezone.utc).isoformat()
            })

        db.session.add_all(teachers)

        # 2. Tạo Courses, Lessons, Quizzes
        all_courses = []
        prefixes = ["Lập trình", "Thiết kế", "Marketing", "Toán học", "Ngôn ngữ", "Kinh doanh"]
        
        for teacher in teachers:
            for c_idx in range(random.randint(3, 6)):
                cid = new_uuid()
                title = f"{random.choice(prefixes)} - Khóa học {c_idx+1} của GV {teacher.email.split('@')[0]}"
                num_lessons = random.randint(5, 10)
                
                c = Course(id=cid, title=title, description="Mô tả chi tiết khóa học...", teacher_id=teacher.id, status="published", total_lessons=num_lessons)
                db.session.add(c)
                all_courses.append(c)
                
                sb_courses.append({
                    "id": cid, "title": title, "description": "Mô tả chi tiết khóa học...", 
                    "teacher_id": teacher.id, "created_at": datetime.now(timezone.utc).isoformat(), "total_lessons": num_lessons, "cover_image_url": ""
                })
                
                for l_idx in range(num_lessons):
                    lid = new_uuid()
                    ltitle = f"Bài {l_idx+1}: Nội dung quan trọng"
                    l = Lesson(id=lid, course_id=cid, title=ltitle, sequence_order=l_idx+1)
                    db.session.add(l)
                    sb_lessons.append({"id": lid, "course_id": cid, "title": ltitle, "sequence_order": l_idx+1, "video_url": "", "document_url": "", "created_at": datetime.now(timezone.utc).isoformat()})
                
                for q_idx in range(random.randint(1, 2)):
                    qid = new_uuid()
                    qtitle = f"Bài trắc nghiệm ôn tập {q_idx+1}"
                    quiz = Quiz(id=qid, course_id=cid, title=qtitle, pass_score=50, is_published=True)
                    db.session.add(quiz)
                    sb_quizzes.append({"id": qid, "course_id": cid, "title": qtitle, "pass_score": 50, "max_attempts": 3, "is_published": True, "created_at": datetime.now(timezone.utc).isoformat()})
                    
                    for question_idx in range(3):
                        qn_id = new_uuid()
                        qtext = f"Câu hỏi số {question_idx+1} của {quiz.title}?"
                        q = Question(id=qn_id, quiz_id=qid, text=qtext, q_type="mcq")
                        db.session.add(q)
                        sb_questions.append({"id": qn_id, "quiz_id": qid, "text": qtext, "q_type": "mcq", "sequence_order": 0})
                        
                        for choice_idx in range(4):
                            ch_id = new_uuid()
                            is_correct = (choice_idx == 0)
                            ch = Choice(id=ch_id, question_id=qn_id, text=f"Đáp án {choice_idx+1}", is_correct=is_correct)
                            db.session.add(ch)
                            sb_choices.append({"id": ch_id, "question_id": qn_id, "text": f"Đáp án {choice_idx+1}", "is_correct": is_correct})
        
        # 3. Enrollments và QuizAttempts
        for student in students:
            for sc in random.sample(all_courses, random.randint(3, 8)):
                eid = new_uuid()
                status = random.choice(["active", "completed"])
                enroll = Enrollment(id=eid, user_id=student.id, course_id=sc.id, status=status)
                db.session.add(enroll)
                sb_enrollments.append({"id": eid, "user_id": student.id, "course_id": sc.id, "status": status, "enrolled_at": datetime.now(timezone.utc).isoformat()})
                
                for quiz in [q for q in sb_quizzes if q["course_id"] == sc.id]:
                    score = random.randint(40, 100)
                    passed = score >= quiz["pass_score"]
                    qa_id = new_uuid()
                    att_time = (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))).isoformat()
                    comp_time = datetime.now(timezone.utc).isoformat()
                    
                    qa = QuizAttempt(id=qa_id, quiz_id=quiz["id"], user_id=student.id, score=score, passed=passed)
                    db.session.add(qa)
                    sb_quiz_attempts.append({
                        "id": qa_id, "quiz_id": quiz["id"], "user_id": student.id, 
                        "score": score, "passed": passed, "attempted_at": att_time, "completed_at": comp_time
                    })

        db.session.commit()
        print("Đã lưu vào SQLite Local.")

        # Đẩy lên Supabase
        if supabase:
            print("Đang đẩy lên Supabase (vui lòng đợi)...")
            try:
                def push_batch(table, data, conflict_col=None):
                    for i in range(0, len(data), 100):
                        if conflict_col:
                            supabase.table(table).upsert(data[i:i+100], on_conflict=conflict_col).execute()
                        else:
                            supabase.table(table).upsert(data[i:i+100]).execute()
                
                # Gom tất cả users
                all_local_users = User.query.all()
                sb_all_users = []
                for u in all_local_users:
                    sb_all_users.append({
                        "id": u.id, "email": u.email, "password_hash": u.password_hash,
                        "phone": u.phone, "role": u.role, "login_count": u.login_count or 0,
                        "created_at": u.created_at.isoformat() if u.created_at else datetime.now(timezone.utc).isoformat()
                    })

                print("Đồng bộ TẤT CẢ Users (tránh lỗi khóa ngoại)...")
                # Xóa toàn bộ dữ liệu cũ trên Supabase theo thứ tự để không dính Foreign Key
                try:
                    supabase.table("learning_logs").delete().neq("log_id", "0").execute()
                    supabase.table("enrollments").delete().neq("id", "0").execute()
                    supabase.table("quiz_attempts").delete().neq("id", "0").execute()
                    supabase.table("choices").delete().neq("id", "0").execute()
                    supabase.table("questions").delete().neq("id", "0").execute()
                    supabase.table("quizzes").delete().neq("id", "0").execute()
                    supabase.table("lessons").delete().neq("id", "0").execute()
                    supabase.table("courses").delete().neq("id", "0").execute()
                    supabase.table("system_logs").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
                    supabase.table("users").delete().neq("id", "0").execute()
                except Exception as e:
                    print("Lưu ý khi dọn dẹp Supabase:", e)
                
                push_batch("users", sb_all_users)
                print("Đẩy Courses...")
                push_batch("courses", sb_courses)
                print("Đẩy Lessons...")
                push_batch("lessons", sb_lessons)
                print("Đẩy Quizzes...")
                push_batch("quizzes", sb_quizzes)
                print("Đẩy Questions...")
                push_batch("questions", sb_questions)
                print("Đẩy Choices...")
                push_batch("choices", sb_choices)
                print("Đẩy Enrollments...")
                push_batch("enrollments", sb_enrollments)
                print("Đẩy Quiz Attempts...")
                push_batch("quiz_attempts", sb_quiz_attempts)
                print("Đồng bộ Supabase thành công!")
            except Exception as e:
                print(f"Lỗi khi đồng bộ Supabase: {e}")

if __name__ == "__main__":
    run_complex_seed()
