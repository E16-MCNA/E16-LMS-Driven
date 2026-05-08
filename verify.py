from e16_app import create_app
from e16_app.models import Course, Lesson

app = create_app()


def run():
    with app.app_context():
        client = app.test_client()

        seed_res = client.get("/seed")
        print("seed:", seed_res.status_code)

        res = client.post(
            "/login",
            data={"email": "student@e16.local", "password": "123456"},
            follow_redirects=False,
        )
        print("student_login:", res.status_code, res.headers.get("Location"))

        course = Course.query.first()
        print("course_exists:", bool(course))
        if not course:
            return

        res = client.get(f"/learn/{course.id}", follow_redirects=True)
        print("learn_page:", res.status_code)

        first_lesson = (
            Lesson.query.filter_by(course_id=course.id).order_by(Lesson.sequence_order.asc()).first()
        )
        if first_lesson:
            res = client.post(f"/learn/{course.id}/complete/{first_lesson.id}", follow_redirects=True)
            print("mark_complete:", res.status_code)

        admin_client = app.test_client()
        res = admin_client.post(
            "/login",
            data={"email": "admin@e16.local", "password": "123456"},
            follow_redirects=False,
        )
        print("admin_login:", res.status_code, res.headers.get("Location"))

        res = admin_client.get("/analytics")
        print("analytics:", res.status_code)

        res = admin_client.get("/analytics/export.csv")
        print("csv:", res.status_code, "bytes:", len(res.data))


if __name__ == "__main__":
    run()
