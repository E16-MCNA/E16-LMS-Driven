# -*- coding: utf-8 -*-
import json
import random
from datetime import timedelta

from ..extensions import db
from ..models import AuditLog, Course, Enrollment, LearningLog, Lesson, SystemSetting, User
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
    total_seconds = max(1, int((end - start).total_seconds()))
    return start + timedelta(seconds=rng.randint(1, total_seconds))


def enrich_demo_data_once(app=None, *, force=False, rng_seed=20260521):
    """Create demo analytics data once for Vercel/prod preview databases."""
    marker = db.session.query(SystemSetting).filter_by(key=DEMO_ENRICHMENT_KEY).first()
    if marker and not force:
        return {"skipped": True, "reason": "already_enriched"}

    rng = random.Random(rng_seed)
    now = utcnow()
    ninety_days_ago = now - timedelta(days=90)

    users = db.session.query(User).all()
    teachers = [u for u in users if u.role == "teacher" and u.is_active]
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

    courses_created = 0
    lessons_created = 0
    enrollments_created = 0
    learning_logs_created = 0
    created_courses = []

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

    db.session.flush()

    active_courses = db.session.query(Course).filter(
        Course.status.in_(["published", "running"]),
        Course.is_deleted == False,
    ).all()
    if students and active_courses:
        for course in created_courses or active_courses[: min(40, len(active_courses))]:
            sample_size = min(len(students), rng.randint(8, 30))
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
                            timestamp=min(log_time + timedelta(minutes=rng.randint(10, 90)), now),
                        ))
                        learning_logs_created += 1

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

    if marker is None:
        marker = SystemSetting(
            key=DEMO_ENRICHMENT_KEY,
            value=now.isoformat(),
            description="Marks that random demo analytics data has been generated.",
        )
        db.session.add(marker)
    else:
        marker.value = now.isoformat()

    db.session.commit()

    if app:
        app.logger.info(
            "Demo data enrichment completed: users=%s login_logs=%s courses=%s lessons=%s enrollments=%s learning_logs=%s",
            user_updates,
            login_logs,
            courses_created,
            lessons_created,
            enrollments_created,
            learning_logs_created,
        )

    return {
        "skipped": False,
        "users": user_updates,
        "login_logs": login_logs,
        "courses": courses_created,
        "lessons": lessons_created,
        "enrollments": enrollments_created,
        "learning_logs": learning_logs_created,
    }
