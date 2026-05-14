import os
import random
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash

from e16_app import create_app
from e16_app.extensions import db
from e16_app.models import User, new_uuid
from supabase import create_client, Client

def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return create_client(url, key)
    return None

def run_seed():
    app = create_app()
    with app.app_context():
        # Ensure 'phone' column is there (already there but just in case)
        try:
            db.session.execute(db.text("ALTER TABLE users ADD COLUMN phone VARCHAR(20)"))
            db.session.commit()
            print("Đã thêm cột 'phone' vào bảng users SQLite.")
        except Exception as e:
            db.session.rollback()
            print("Cột 'phone' đã tồn tại (bỏ qua).")

        supabase = get_supabase()
        if not supabase:
            print("Chưa cấu hình Supabase (thiếu URL/Key).")
        
        print("Bắt đầu tạo 300 users mẫu...")
        users_to_add = []
        supabase_data = []

        start_index = User.query.filter(User.email.like("student_300_%")).count() + 1

        for i in range(start_index, start_index + 300):
            user_id = new_uuid()
            email = f"student_300_{i}@e16.edu.vn"
            phone_num = f"09{random.randint(10000000, 99999999)}"
            pwd_hash = generate_password_hash("123456")
            
            # Local db
            student = User(
                id=user_id,
                email=email,
                password_hash=pwd_hash,
                role="student",
                phone=phone_num
            )
            users_to_add.append(student)

            # Supabase
            if supabase:
                supabase_data.append({
                    "id": user_id,
                    "email": email,
                    "password_hash": pwd_hash,
                    "phone": phone_num,
                    "role": "student",
                    "login_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })

        # Add to SQLite
        try:
            db.session.add_all(users_to_add)
            db.session.commit()
            print(f"Đã thêm {len(users_to_add)} users vào SQLite thành công.")
        except Exception as e:
            db.session.rollback()
            print(f"Lỗi khi lưu vào SQLite: {e}")
            return

        # Add to Supabase
        if supabase:
            print(f"Đang đẩy {len(supabase_data)} users lên Supabase...")
            success_count = 0
            for i in range(0, len(supabase_data), 100):
                batch = supabase_data[i:i+100]
                try:
                    supabase.table("users").insert(batch).execute()
                    success_count += len(batch)
                except Exception as e:
                    print(f"Lỗi khi thêm lô {i} vào Supabase: {e}")
            print(f"Đã thêm {success_count} users vào Supabase.")

if __name__ == "__main__":
    run_seed()
