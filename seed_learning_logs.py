import os
import random
from datetime import datetime, timedelta, timezone

from e16_app import create_app
from e16_app.extensions import db
from e16_app.models import User, Lesson, LearningLog, new_uuid
from supabase import create_client

def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return create_client(url, key)
    return None

def run_seed_learning_logs():
    app = create_app()
    with app.app_context():
        print("Bắt đầu tạo dữ liệu learning_logs...")
        supabase = get_supabase()
        
        students = User.query.filter_by(role="student").all()
        lessons = Lesson.query.all()
        
        if supabase:
            print("Đang đồng bộ ID từ Supabase để tránh lỗi Foreign Key...")
            try:
                # Lấy danh sách ID hợp lệ từ Supabase
                sb_users = supabase.table("users").select("id").execute()
                valid_user_ids = {u["id"] for u in sb_users.data}
                
                sb_lessons = supabase.table("lessons").select("id").execute()
                valid_lesson_ids = {l["id"] for l in sb_lessons.data}
                
                # Lọc lại dữ liệu local
                students = [s for s in students if s.id in valid_user_ids]
                lessons = [l for l in lessons if l.id in valid_lesson_ids]
            except Exception as e:
                print(f"Lỗi khi lấy ID từ Supabase: {e}")

        if not students:
            print("Không tìm thấy học sinh nào hợp lệ.")
            return
            
        if not lessons:
            print("Không tìm thấy lesson nào hợp lệ.")
            return

        action_types = ["view_video", "view_document", "start_lesson", "complete_lesson"]
        
        logs_to_add = []
        sb_logs = []
        
        for student in students:
            # Randomly select a few lessons for each student
            num_lessons = random.randint(1, min(10, len(lessons)))
            sampled_lessons = random.sample(lessons, num_lessons)
            
            for lesson in sampled_lessons:
                num_logs = random.randint(1, 5)
                for _ in range(num_logs):
                    action = random.choice(action_types)
                    log_time = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
                    
                    log = LearningLog(
                        log_id=new_uuid(),
                        user_id=student.id,
                        lesson_id=lesson.id,
                        action_type=action,
                        timestamp=log_time
                    )
                    logs_to_add.append(log)
                    
                    sb_logs.append({
                        "log_id": log.log_id,
                        "user_id": student.id,
                        "lesson_id": lesson.id,
                        "action_type": action,
                        "timestamp": log_time.isoformat()
                    })

        print(f"Sẽ tạo {len(logs_to_add)} learning_logs.")
        db.session.add_all(logs_to_add)
        db.session.commit()
        print("Đã lưu vào SQLite Local.")
        
        if supabase:
            print("Đang đẩy lên Supabase (vui lòng đợi)...")
            try:
                for i in range(0, len(sb_logs), 100):
                    supabase.table("learning_logs").upsert(sb_logs[i:i+100]).execute()
                print("Đồng bộ Supabase thành công!")
            except Exception as e:
                print(f"Lỗi khi đồng bộ Supabase: {e}")

if __name__ == "__main__":
    run_seed_learning_logs()
