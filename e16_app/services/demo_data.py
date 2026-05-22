# -*- coding: utf-8 -*-
import json
import os
import random
from datetime import timedelta

from ..extensions import db
from ..models import AuditLog, Course, Enrollment, LearningLog, Lesson, SystemSetting, User, Quiz, Question, Choice, Assignment
from ..time_utils import utcnow


DEMO_ENRICHMENT_KEY = "demo_data_enrichment_v1"

COURSE_TOPICS = [
    ("Python ứng dụng cho người mới", "Python,Data", "Beginner"),
    ("Phân tích dữ liệu với Excel", "Excel,BI", "Beginner"),
    ("SQL thực chiến", "SQL,Database", "Intermediate"),
    ("Thiết kế UI/UX với Figma", "UI/UX,Design", "Beginner"),
    ("Marketing số đa kênh", "Marketing,Ads", "Intermediate"),
    ("Quản trị dự án Agile", "Agile,Product", "Intermediate"),
    ("Machine Learning căn bản", "AI,Machine Learning", "Advanced"),
    ("Xây dựng API với Node.js", "Node.js,Backend", "Intermediate"),
    ("DevOps và CI/CD", "DevOps,CI/CD", "Advanced"),
    ("An toàn thông tin cơ bản", "Security,Cybersecurity", "Beginner"),
    ("Kỹ năng giao tiếp chuyên nghiệp", "Communication,Soft Skills", "Beginner"),
    ("Tài chính cá nhân", "Finance,Business", "Beginner"),
]


def _random_between(start, end, rng):
    if start.tzinfo is None and end.tzinfo is not None:
        end = end.replace(tzinfo=None)
    elif start.tzinfo is not None and end.tzinfo is None:
        start = start.replace(tzinfo=None)
    total_seconds = max(1, int((end - start).total_seconds()))
    return start + timedelta(seconds=rng.randint(1, total_seconds))


def _min_compatible(left, right):
    if left.tzinfo is None and right.tzinfo is not None:
        right = right.replace(tzinfo=None)
    elif left.tzinfo is not None and right.tzinfo is None:
        left = left.replace(tzinfo=None)
    return min(left, right)


def _load_state(marker, force):
    if force or marker is None:
        return {
            "status": "running",
            "last_user_id": None,
            "last_teacher_id": None,
            "processed_users": 0,
            "processed_teachers": 0,
            "user_done": False,
            "teacher_done": False,
        }
    if marker.value and marker.value.startswith("completed:"):
        return {"status": "completed"}
    try:
        state = json.loads(marker.value or "{}")
        if state.get("status") == "completed":
            return {"status": "completed"}
        state.setdefault("status", "running")
        state.setdefault("last_user_id", None)
        state.setdefault("last_teacher_id", None)
        state.setdefault("processed_users", 0)
        state.setdefault("processed_teachers", 0)
        state.setdefault("user_done", False)
        state.setdefault("teacher_done", False)
        return state
    except Exception:
        return {
            "status": "running",
            "last_user_id": None,
            "last_teacher_id": None,
            "processed_users": 0,
            "processed_teachers": 0,
            "user_done": False,
            "teacher_done": False,
        }


def _save_state(marker, state):
    marker.value = json.dumps(state, sort_keys=True)
    db.session.commit()


def enrich_demo_data_once(app=None, *, force=False, rng_seed=20260521):
    """Create demo analytics data across all users/teachers in small batches."""
    marker = db.session.query(SystemSetting).filter_by(key=DEMO_ENRICHMENT_KEY).first()
    state = _load_state(marker, force)
    if state.get("status") == "completed" and not force:
        try:
            ensure_courses_have_quizzes_and_assignments()
        except Exception:
            pass
        return {"skipped": True, "reason": "already_enriched"}

    rng = random.Random(rng_seed)
    now = utcnow()
    ninety_days_ago = now - timedelta(days=90)

    if marker is None:
        marker = SystemSetting(
            key=DEMO_ENRICHMENT_KEY,
            value="{}",
            description="Marks that random demo analytics data has been generated.",
        )
        db.session.add(marker)
        db.session.commit()

    user_batch_size = max(1, int(os.getenv("E16_DEMO_USER_BATCH_SIZE", os.getenv("E16_DEMO_USER_LIMIT", "120"))))
    teacher_batch_size = max(1, int(os.getenv("E16_DEMO_TEACHER_BATCH_SIZE", "30")))

    _save_state(marker, {**state, "status": "running", "started_at": now.isoformat()})

    user_query = db.session.query(User).order_by(User.id.asc())
    if state.get("last_user_id"):
        user_query = user_query.filter(User.id > state["last_user_id"])
    users = [] if state.get("user_done") else user_query.limit(user_batch_size).all()
    students = [u for u in users if u.role == "student" and u.is_active]

    user_updates = 0
    login_logs = 0
    for user in users:
        created_at = now - timedelta(
            days=rng.randint(1, 90),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        if created_at < ninety_days_ago:
            created_at = ninety_days_ago + timedelta(minutes=rng.randint(1, 240))

        last_login = _random_between(created_at + timedelta(hours=1), now, rng)
        user.created_at = created_at
        user.last_login = last_login
        user.login_count = rng.randint(2, 45)
        user_updates += 1

        log_count = rng.randint(1, min(8, user.login_count))
        for idx in range(log_count):
            log_time = last_login if idx == 0 else _random_between(created_at, last_login, rng)
            db.session.add(AuditLog(
                actor_id=user.id,
                action="login_success",
                target_type="User",
                target_id=user.id,
                detail=json.dumps({"email": user.email, "method": "demo_seed"}),
                ip_address=f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
                created_at=log_time,
            ))
            login_logs += 1

    db.session.commit()
    if users:
        state["last_user_id"] = users[-1].id
        state["processed_users"] = int(state.get("processed_users", 0)) + len(users)
        if len(users) < user_batch_size:
            state["user_done"] = True
    else:
        state["user_done"] = True

    courses_created = 0
    lessons_created = 0
    enrollments_created = 0
    learning_logs_created = 0
    created_courses = []

    teacher_query = db.session.query(User).filter_by(role="teacher", is_active=True).order_by(User.id.asc())
    if state.get("last_teacher_id"):
        teacher_query = teacher_query.filter(User.id > state["last_teacher_id"])
    teachers = [] if state.get("teacher_done") else teacher_query.limit(teacher_batch_size).all()

    for teacher_index, teacher in enumerate(teachers):
        existing_count = db.session.query(Course).filter_by(teacher_id=teacher.id, is_deleted=False).count()
        target_count = rng.randint(1, 3)
        missing_count = max(0, target_count - existing_count)

        for offset in range(missing_count):
            topic, tags, level = COURSE_TOPICS[(teacher_index + offset) % len(COURSE_TOPICS)]
            created_at = now - timedelta(days=rng.randint(10, 85), hours=rng.randint(0, 23))
            lesson_count = rng.randint(4, 8)
            status = "published" if rng.random() < 0.85 else "running"
            course = Course(
                title=f"{topic} - {teacher.email.split('@')[0]}",
                short_description=f"Khóa học thực hành: {topic}.",
                description=f"Chương trình demo giúp học viên luyện tập {topic.lower()} qua bài học và bài tập ngắn.",
                cover_image_url="https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=1200&auto=format&fit=crop",
                teacher_id=teacher.id,
                total_lessons=lesson_count,
                status=status,
                is_deleted=False,
                tags=tags,
                level=level,
                price=rng.choice([0, 199000, 250000, 399000]),
                created_at=created_at,
                published_at=created_at + timedelta(days=1),
            )
            db.session.add(course)
            db.session.flush()
            courses_created += 1
            created_courses.append(course)

            for seq in range(1, lesson_count + 1):
                db.session.add(Lesson(
                    course_id=course.id,
                    title=f"Bài {seq}: {topic}",
                    video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    document_url="",
                    sequence_order=seq,
                    created_at=created_at + timedelta(days=seq),
                ))
                lessons_created += 1

            # Seed a Quiz for this course
            quiz = Quiz(
                course_id=course.id,
                title=f"Trắc nghiệm cuối khóa: {topic}",
                pass_score=80,
                max_attempts=3,
                is_published=True,
                created_at=created_at + timedelta(days=1),
            )
            db.session.add(quiz)
            db.session.flush()

            # Seed Questions and Choices
            q1 = Question(
                quiz_id=quiz.id,
                text=f"HTML là viết tắt của từ nào sau đây khi thiết kế web và {topic}?",
                q_type="mcq",
                sequence_order=1
            )
            db.session.add(q1)
            db.session.flush()
            db.session.add(Choice(question_id=q1.id, text="Hyper Text Markup Language", is_correct=True))
            db.session.add(Choice(question_id=q1.id, text="Hyperlinks and Text Markup Language", is_correct=False))
            db.session.add(Choice(question_id=q1.id, text="Home Technology Modern Language", is_correct=False))

            q2 = Question(
                quiz_id=quiz.id,
                text=f"Đâu là yếu tố cốt lõi nhất cần chú ý khi tối ưu trải nghiệm người dùng?",
                q_type="mcq",
                sequence_order=2
            )
            db.session.add(q2)
            db.session.flush()
            db.session.add(Choice(question_id=q2.id, text="Sự đơn giản, rõ ràng và phản hồi nhanh chóng", is_correct=True))
            db.session.add(Choice(question_id=q2.id, text="Sử dụng càng nhiều màu sắc sặc sỡ càng tốt", is_correct=False))

            # Seed an Assignment for this course
            assignment = Assignment(
                course_id=course.id,
                title=f"Bài tập thực hành: Thực chiến {topic}",
                description=f"Hãy áp dụng các kỹ năng và kiến thức đã học trong khóa học {topic} để hoàn thành một bài thực hành thực tế ngắn và nộp báo cáo (hoặc nhập nội dung trả lời tại đây).",
                allow_file=True,
                allow_text=True,
                created_at=created_at + timedelta(days=1),
            )
            db.session.add(assignment)

    db.session.commit()
    if teachers:
        state["last_teacher_id"] = teachers[-1].id
        state["processed_teachers"] = int(state.get("processed_teachers", 0)) + len(teachers)
        if len(teachers) < teacher_batch_size:
            state["teacher_done"] = True
    else:
        state["teacher_done"] = True

    active_courses = db.session.query(Course).filter(
        Course.status.in_(["published", "running"]),
        Course.is_deleted == False,
    ).all()
    if not students:
        students = db.session.query(User).filter_by(role="student", is_active=True).order_by(User.created_at.desc()).limit(100).all()
    if students and active_courses:
        for course in (created_courses or active_courses[: min(12, len(active_courses))]):
            sample_size = min(len(students), rng.randint(4, 12))
            for student in rng.sample(students, sample_size):
                existing = db.session.query(Enrollment).filter_by(user_id=student.id, course_id=course.id).first()
                if existing:
                    continue
                enrolled_at = _random_between(max(student.created_at, course.created_at), now, rng)
                status = rng.choices(["active", "completed"], weights=[75, 25], k=1)[0]
                db.session.add(Enrollment(
                    user_id=student.id,
                    course_id=course.id,
                    enrolled_at=enrolled_at,
                    status=status,
                ))
                enrollments_created += 1

                lessons = db.session.query(Lesson).filter_by(course_id=course.id).order_by(Lesson.sequence_order).all()
                for lesson in lessons[: rng.randint(1, min(3, len(lessons)))]:
                    log_time = _random_between(enrolled_at, now, rng)
                    db.session.add(LearningLog(
                        user_id=student.id,
                        lesson_id=lesson.id,
                        action_type="start",
                        timestamp=log_time,
                    ))
                    learning_logs_created += 1
                    if rng.random() < 0.65:
                        db.session.add(LearningLog(
                            user_id=student.id,
                            lesson_id=lesson.id,
                            action_type="complete",
                            timestamp=_min_compatible(log_time + timedelta(minutes=rng.randint(10, 90)), now),
                        ))
                        learning_logs_created += 1

            db.session.commit()

    today_lessons = db.session.query(Lesson).limit(50).all()
    if students and today_lessons:
        for student in rng.sample(students, min(50, len(students))):
            lesson = rng.choice(today_lessons)
            db.session.add(LearningLog(
                user_id=student.id,
                lesson_id=lesson.id,
                action_type=rng.choice(["start", "complete"]),
                timestamp=now - timedelta(minutes=rng.randint(0, 720)),
            ))
            learning_logs_created += 1

    if state.get("user_done") and state.get("teacher_done"):
        state["status"] = "completed"
        state["completed_at"] = now.isoformat()
    else:
        state["status"] = "running"
        state["updated_at"] = now.isoformat()
    _save_state(marker, state)

    if app:
        app.logger.info(
            "Demo data enrichment batch: status=%s processed_users=%s processed_teachers=%s users=%s login_logs=%s courses=%s lessons=%s enrollments=%s learning_logs=%s",
            state["status"],
            state.get("processed_users", 0),
            state.get("processed_teachers", 0),
            user_updates,
            login_logs,
            courses_created,
            lessons_created,
            enrollments_created,
            learning_logs_created,
        )

    # Tự động đồng bộ các khóa học đang thiếu Quiz/Assignment
    try:
        ensure_courses_have_quizzes_and_assignments()
    except Exception as e:
        if app:
            app.logger.warning(f"ensure_courses_have_quizzes_and_assignments failed in enrich_demo_data_once: {str(e)}")

    return {
        "skipped": False,
        "users": user_updates,
        "login_logs": login_logs,
        "courses": courses_created,
        "lessons": lessons_created,
        "enrollments": enrollments_created,
        "learning_logs": learning_logs_created,
        "status": state["status"],
        "processed_users": state.get("processed_users", 0),
        "processed_teachers": state.get("processed_teachers", 0),
    }


def ensure_courses_have_quizzes_and_assignments():
    """Ensure all existing courses in the database have at least one Quiz and one Assignment."""
    courses = db.session.query(Course).filter(Course.is_deleted == False).all()
    mutated = False
    now = utcnow()

    for course in courses:
        # Check quiz
        has_quiz = db.session.query(Quiz).filter_by(course_id=course.id).first()
        if not has_quiz:
            # Lấy tên chủ đề
            topic = course.title.split(" - ")[0]
            quiz = Quiz(
                course_id=course.id,
                title=f"Trắc nghiệm cuối khóa: {topic}",
                pass_score=80,
                max_attempts=3,
                is_published=True,
                created_at=course.created_at + timedelta(days=1) if course.created_at else now,
            )
            db.session.add(quiz)
            db.session.flush()

            # Tạo câu hỏi và lựa chọn mẫu
            q1 = Question(
                quiz_id=quiz.id,
                text=f"HTML là viết tắt của từ nào sau đây khi thiết kế web và {topic}?",
                q_type="mcq",
                sequence_order=1
            )
            db.session.add(q1)
            db.session.flush()
            db.session.add(Choice(question_id=q1.id, text="Hyper Text Markup Language", is_correct=True))
            db.session.add(Choice(question_id=q1.id, text="Hyperlinks and Text Markup Language", is_correct=False))
            db.session.add(Choice(question_id=q1.id, text="Home Technology Modern Language", is_correct=False))

            q2 = Question(
                quiz_id=quiz.id,
                text=f"Đâu là yếu tố cốt lõi nhất cần chú ý khi tối ưu trải nghiệm người dùng?",
                q_type="mcq",
                sequence_order=2
            )
            db.session.add(q2)
            db.session.flush()
            db.session.add(Choice(question_id=q2.id, text="Sự đơn giản, rõ ràng và phản hồi nhanh chóng", is_correct=True))
            db.session.add(Choice(question_id=q2.id, text="Sử dụng càng nhiều màu sắc sặc sỡ càng tốt", is_correct=False))

            mutated = True

        # Check assignment
        has_assignment = db.session.query(Assignment).filter_by(course_id=course.id).first()
        if not has_assignment:
            topic = course.title.split(" - ")[0]
            assignment = Assignment(
                course_id=course.id,
                title=f"Bài tập thực hành: Thực chiến {topic}",
                description=f"Hãy áp dụng các kỹ năng và kiến thức đã học trong khóa học để hoàn thành một bài thực hành thực tế ngắn và nộp báo cáo (hoặc nhập nội dung trả lời tại đây).",
                allow_file=True,
                allow_text=True,
                created_at=course.created_at + timedelta(days=1) if course.created_at else now,
            )
            db.session.add(assignment)
            mutated = True

    if mutated:
        db.session.commit()
