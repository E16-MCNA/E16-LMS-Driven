# -*- coding: utf-8 -*-
"""
Comprehensive tests for the new Role System, Học vụ workflow,
Force Password Change, and Course Lifecycle.
"""
import csv
import io
import pytest
from werkzeug.security import generate_password_hash, check_password_hash

from e16_app import create_app, db
from e16_app.models import (
    VALID_ROLES, COURSE_STATUSES, COURSE_TRANSITIONS,
    User, Course, Enrollment, Lesson, Certificate,
)

# ═══════════════════════════════════════════════════════════
#                        FIXTURES
# ═══════════════════════════════════════════════════════════

def _mk(app, email, role, password="testpass1", must_change=False):
    """Create a user and return the id."""
    with app.app_context():
        u = User(
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            must_change_password=must_change,
        )
        db.session.add(u)
        db.session.commit()
        return u.id

def _login(client, email, password="testpass1"):
    """Login helper."""
    return client.post("/auth/login", data={
        "email": email,
        "password": password,
    })

def _mk_course(app, teacher_id, title="Test Course", status="draft"):
    """Create a course and return the id."""
    with app.app_context():
        c = Course(title=title, teacher_id=teacher_id, status=status)
        db.session.add(c)
        db.session.commit()
        return c.id

# ═══════════════════════════════════════════════════════════
#           1. MODEL CONSTANTS & TRANSITIONS
# ═══════════════════════════════════════════════════════════

class TestModelConstants:
    """Verify model constants are correctly defined."""

    @pytest.mark.unit
    def test_valid_roles_contains_all_six(self):
        assert VALID_ROLES == {"admin", "teacher", "student", "hoc_vu", "le_tan", "ke_toan"}

    @pytest.mark.unit
    def test_course_statuses_complete(self):
        expected = {"draft", "pending_review", "approved", "published",
                    "running", "closed", "archived", "suspended", "rejected"}
        assert COURSE_STATUSES == expected

    @pytest.mark.unit
    def test_draft_can_only_go_to_pending_review(self):
        assert COURSE_TRANSITIONS["draft"] == ["pending_review"]

    @pytest.mark.unit
    def test_archived_has_no_transitions(self):
        assert COURSE_TRANSITIONS["archived"] == []

    @pytest.mark.unit
    def test_all_statuses_have_transition_entry(self):
        for status in COURSE_STATUSES:
            assert status in COURSE_TRANSITIONS

# ═══════════════════════════════════════════════════════════
#           2. FORCE PASSWORD CHANGE MIDDLEWARE
# ═══════════════════════════════════════════════════════════

class TestForcePasswordChange:
    """Verify must_change_password middleware blocks all routes."""

    @pytest.mark.auth
    def test_user_with_must_change_redirected(self, client, app):
        """User with must_change_password=True should be redirected to change-password."""
        _mk(app, "newuser@test.com", "student", must_change=True)
        _login(client, "newuser@test.com")

        response = client.get("/dashboard")
        assert response.status_code == 302
        assert "/auth/change-password" in response.headers.get("Location", "")

    @pytest.mark.auth
    def test_change_password_page_loads(self, client, app):
        """Change password page should be accessible for users needing to change."""
        _mk(app, "newuser@test.com", "student", must_change=True)
        _login(client, "newuser@test.com")

        response = client.get("/auth/change-password")
        assert response.status_code == 200

    @pytest.mark.auth
    def test_change_password_success(self, client, app):
        """Changing password should clear must_change_password flag."""
        _mk(app, "newuser@test.com", "student", must_change=True)
        _login(client, "newuser@test.com")

        response = client.post("/auth/change-password", data={
            "new_password": "newpassword123",
            "confirm_password": "newpassword123",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.query(User).filter_by(email="newuser@test.com").first()
            assert user.must_change_password is False
            assert user.temp_password_hash is None
            assert check_password_hash(user.password_hash, "newpassword123")

    @pytest.mark.auth
    def test_change_password_mismatch(self, client, app):
        """Mismatched passwords should fail."""
        _mk(app, "newuser@test.com", "student", must_change=True)
        _login(client, "newuser@test.com")

        response = client.post("/auth/change-password", data={
            "new_password": "newpassword123",
            "confirm_password": "different123",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.query(User).filter_by(email="newuser@test.com").first()
            assert user.must_change_password is True

    @pytest.mark.auth
    def test_change_password_too_short(self, client, app):
        """Password under 8 chars should fail."""
        _mk(app, "newuser@test.com", "student", must_change=True)
        _login(client, "newuser@test.com")

        response = client.post("/auth/change-password", data={
            "new_password": "short",
            "confirm_password": "short",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.query(User).filter_by(email="newuser@test.com").first()
            assert user.must_change_password is True

    @pytest.mark.auth
    def test_logout_exempt_from_middleware(self, client, app):
        """Logout should work even when must_change_password is True."""
        _mk(app, "newuser@test.com", "student", must_change=True)
        _login(client, "newuser@test.com")

        response = client.get("/auth/logout")
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("Location", "")

    @pytest.mark.auth
    def test_normal_user_not_redirected(self, client, app):
        """User with must_change_password=False should NOT be redirected."""
        _mk(app, "normal@test.com", "student", must_change=False)
        _login(client, "normal@test.com")

        response = client.get("/dashboard")
        assert response.status_code == 200

# ═══════════════════════════════════════════════════════════
#           3. HỌC VỤ — SINGLE ACCOUNT CREATION
# ═══════════════════════════════════════════════════════════

class TestHocVuAccountCreation:
    """Test Học vụ single account creation flow."""

    @pytest.mark.integration
    def test_create_student_account(self, client, app):
        """Học vụ can create a student account."""
        hv_id = _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        response = client.post("/hoc-vu/accounts/create", data={
            "email": "newstudent@test.com",
            "role": "student",
            "full_name": "Student Test",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.query(User).filter_by(email="newstudent@test.com").first()
            assert user is not None
            assert user.role == "student"
            assert user.must_change_password is True
            assert user.created_by == hv_id

    @pytest.mark.integration
    def test_create_teacher_account(self, client, app):
        """Học vụ can create a teacher account."""
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        response = client.post("/hoc-vu/accounts/create", data={
            "email": "newteacher@test.com",
            "role": "teacher",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.query(User).filter_by(email="newteacher@test.com").first()
            assert user is not None
            assert user.role == "teacher"

    @pytest.mark.integration
    def test_reset_temp_password_for_created_account(self, client, app, monkeypatch):
        """Hoc vu can issue a new temporary password when the first one is lost."""
        hv_id = _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        with app.app_context():
            user = User(
                email="frontdesk@test.com",
                password_hash=generate_password_hash("oldtemp123"),
                role="le_tan",
                must_change_password=True,
                created_by=hv_id,
                temp_password_hash=generate_password_hash("oldtemp123"),
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        monkeypatch.setattr("e16_app.blueprints.hoc_vu._gen_temp_password", lambda length=10: "newtemp123")
        response = client.post(f"/hoc-vu/accounts/{user_id}/reset-temp-password", follow_redirects=True)

        assert response.status_code == 200
        assert b"newtemp123" in response.data
        with app.app_context():
            user = db.session.get(User, user_id)
            assert user.must_change_password is True
            assert user.is_active is True
            assert check_password_hash(user.password_hash, "newtemp123")
            assert check_password_hash(user.temp_password_hash, "newtemp123")

    @pytest.mark.integration
    def test_cannot_create_admin_account(self, client, app):
        """Học vụ should NOT be able to create admin accounts."""
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        response = client.post("/hoc-vu/accounts/create", data={
            "email": "newadmin@test.com",
            "role": "admin",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.query(User).filter_by(email="newadmin@test.com").first()
            assert user is None

    @pytest.mark.integration
    def test_cannot_create_hocvu_account(self, client, app):
        """Học vụ should NOT be able to create another hoc_vu account."""
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        response = client.post("/hoc-vu/accounts/create", data={
            "email": "hv2@test.com",
            "role": "hoc_vu",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.query(User).filter_by(email="hv2@test.com").first()
            assert user is None

    @pytest.mark.integration
    def test_duplicate_email_rejected(self, client, app):
        """Creating account with existing email should fail."""
        _mk(app, "hv@test.com", "hoc_vu")
        _mk(app, "exists@test.com", "student")
        _login(client, "hv@test.com")

        response = client.post("/hoc-vu/accounts/create", data={
            "email": "exists@test.com",
            "role": "student",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            count = db.session.query(User).filter_by(email="exists@test.com").count()
            assert count == 1  # No duplicate created

    @pytest.mark.integration
    def test_create_with_course_enrollment(self, client, app):
        """Creating student with course_id should auto-enroll."""
        hv_id = _mk(app, "hv@test.com", "hoc_vu")
        teacher_id = _mk(app, "teacher@test.com", "teacher")
        course_id = _mk_course(app, teacher_id, status="published")
        _login(client, "hv@test.com")

        response = client.post("/hoc-vu/accounts/create", data={
            "email": "enrolled@test.com",
            "role": "student",
            "course_id": course_id,
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            user = db.session.query(User).filter_by(email="enrolled@test.com").first()
            enrollment = db.session.query(Enrollment).filter_by(
                user_id=user.id, course_id=course_id
            ).first()
            assert enrollment is not None
            assert enrollment.status == "active"

# ═══════════════════════════════════════════════════════════
#           4. HỌC VỤ — CSV IMPORT
# ═══════════════════════════════════════════════════════════

class TestHocVuCSVImport:
    """Test CSV bulk import functionality."""

    def _make_csv(self, rows):
        """Build an in-memory CSV file from list of dicts."""
        si = io.StringIO()
        writer = csv.DictWriter(si, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        si.seek(0)
        return (io.BytesIO(si.getvalue().encode("utf-8")), "import.csv")

    @pytest.mark.integration
    def test_csv_import_success(self, client, app):
        """Valid CSV should create users."""
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        csv_data, filename = self._make_csv([
            {"email": "csv1@test.com", "role": "student"},
            {"email": "csv2@test.com", "role": "teacher"},
        ])

        response = client.post("/hoc-vu/accounts/import", data={
            "file": (csv_data, filename),
        }, content_type="multipart/form-data", follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            u1 = db.session.query(User).filter_by(email="csv1@test.com").first()
            u2 = db.session.query(User).filter_by(email="csv2@test.com").first()
            assert u1 is not None and u1.role == "student"
            assert u2 is not None and u2.role == "teacher"
            assert u1.must_change_password is True
            assert u2.must_change_password is True

    @pytest.mark.integration
    def test_csv_import_duplicate_skipped(self, client, app):
        """Existing emails in CSV should be skipped, not cause errors."""
        _mk(app, "hv@test.com", "hoc_vu")
        _mk(app, "exists@test.com", "student")
        _login(client, "hv@test.com")

        csv_data, filename = self._make_csv([
            {"email": "exists@test.com", "role": "student"},
            {"email": "new@test.com", "role": "student"},
        ])

        response = client.post("/hoc-vu/accounts/import", data={
            "file": (csv_data, filename),
        }, content_type="multipart/form-data", follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            assert db.session.query(User).filter_by(email="exists@test.com").count() == 1
            assert db.session.query(User).filter_by(email="new@test.com").first() is not None

    @pytest.mark.integration
    def test_csv_import_invalid_role(self, client, app):
        """Invalid roles in CSV should be rejected per-row."""
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        csv_data, filename = self._make_csv([
            {"email": "bad@test.com", "role": "superuser"},
            {"email": "good@test.com", "role": "student"},
        ])

        response = client.post("/hoc-vu/accounts/import", data={
            "file": (csv_data, filename),
        }, content_type="multipart/form-data", follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            assert db.session.query(User).filter_by(email="bad@test.com").first() is None
            assert db.session.query(User).filter_by(email="good@test.com").first() is not None

    @pytest.mark.integration
    def test_csv_import_no_file(self, client, app):
        """Import without file should redirect back."""
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        response = client.post("/hoc-vu/accounts/import", data={},
                               follow_redirects=True)
        assert response.status_code == 200

# ═══════════════════════════════════════════════════════════
#           5. COURSE LIFECYCLE STATE MACHINE
# ═══════════════════════════════════════════════════════════

class TestCourseLifecycle:
    """Test course status transitions via the lifecycle service."""

    def _login_user(self, app, user_id):
        """Push a request context with a logged-in user for audit log."""
        from flask_login import login_user as fl_login
        user = db.session.get(User, user_id)
        fl_login(user)

    @pytest.mark.unit
    def test_valid_transition_draft_to_pending(self, app):
        """draft → pending_review should succeed."""
        from e16_app.services.course_lifecycle import transition_course

        teacher_id = _mk(app, "t@test.com", "teacher")
        course_id = _mk_course(app, teacher_id, status="draft")

        with app.test_request_context():
            self._login_user(app, teacher_id)
            course = transition_course(course_id, "pending_review", teacher_id)
            assert course.status == "pending_review"

    @pytest.mark.unit
    def test_valid_transition_pending_to_approved(self, app):
        """pending_review → approved should succeed."""
        from e16_app.services.course_lifecycle import transition_course

        teacher_id = _mk(app, "t@test.com", "teacher")
        hv_id = _mk(app, "hv@test.com", "hoc_vu")
        course_id = _mk_course(app, teacher_id, status="pending_review")

        with app.test_request_context():
            self._login_user(app, hv_id)
            course = transition_course(course_id, "approved", hv_id, "Looks good")
            assert course.status == "approved"
            assert course.reviewed_by == hv_id
            assert course.reviewed_at is not None
            assert course.review_note == "Looks good"

    @pytest.mark.unit
    def test_valid_transition_pending_to_rejected(self, app):
        """pending_review → rejected should succeed with note."""
        from e16_app.services.course_lifecycle import transition_course

        teacher_id = _mk(app, "t@test.com", "teacher")
        hv_id = _mk(app, "hv@test.com", "hoc_vu")
        course_id = _mk_course(app, teacher_id, status="pending_review")

        with app.test_request_context():
            self._login_user(app, hv_id)
            course = transition_course(course_id, "rejected", hv_id, "Needs work")
            assert course.status == "rejected"
            assert course.rejection_note == "Needs work"

    @pytest.mark.unit
    def test_invalid_transition_raises_error(self, app):
        """draft → published should raise InvalidTransitionError."""
        from e16_app.services.course_lifecycle import transition_course, InvalidTransitionError

        teacher_id = _mk(app, "t@test.com", "teacher")
        course_id = _mk_course(app, teacher_id, status="draft")

        with app.test_request_context():
            self._login_user(app, teacher_id)
            with pytest.raises(InvalidTransitionError):
                transition_course(course_id, "published", teacher_id)

    @pytest.mark.unit
    def test_invalid_transition_archived_to_anything(self, app):
        """archived → any status should raise error."""
        from e16_app.services.course_lifecycle import transition_course, InvalidTransitionError

        teacher_id = _mk(app, "t@test.com", "teacher")
        course_id = _mk_course(app, teacher_id, status="archived")

        with app.test_request_context():
            self._login_user(app, teacher_id)
            with pytest.raises(InvalidTransitionError):
                transition_course(course_id, "draft", teacher_id)

    @pytest.mark.unit
    def test_full_lifecycle_chain(self, app):
        """Test complete lifecycle: draft → pending → approved → published."""
        from e16_app.services.course_lifecycle import transition_course

        teacher_id = _mk(app, "t@test.com", "teacher")
        hv_id = _mk(app, "hv@test.com", "hoc_vu")
        course_id = _mk_course(app, teacher_id, status="draft")

        with app.test_request_context():
            self._login_user(app, teacher_id)
            transition_course(course_id, "pending_review", teacher_id)

            self._login_user(app, hv_id)
            transition_course(course_id, "approved", hv_id, "OK")
            course = transition_course(course_id, "published", hv_id)
            assert course.status == "published"
            assert course.published_at is not None

    @pytest.mark.unit
    def test_rejected_can_go_back_to_draft(self, app):
        """rejected → draft should work (teacher can resubmit)."""
        from e16_app.services.course_lifecycle import transition_course

        teacher_id = _mk(app, "t@test.com", "teacher")
        course_id = _mk_course(app, teacher_id, status="rejected")

        with app.test_request_context():
            self._login_user(app, teacher_id)
            course = transition_course(course_id, "draft", teacher_id)
            assert course.status == "draft"

# ═══════════════════════════════════════════════════════════
#           6. COURSE APPROVAL VIA HỌC VỤ ROUTES
# ═══════════════════════════════════════════════════════════

class TestHocVuCourseApproval:
    """Test course approval via Học vụ blueprint routes."""

    @pytest.mark.integration
    def test_approve_course(self, client, app):
        """Học vụ can approve a pending course."""
        _mk(app, "hv@test.com", "hoc_vu")
        teacher_id = _mk(app, "t@test.com", "teacher")
        course_id = _mk_course(app, teacher_id, status="pending_review")
        _login(client, "hv@test.com")

        response = client.post(f"/hoc-vu/courses/{course_id}/review", data={
            "action": "approve",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            course = db.session.get(Course, course_id)
            assert course.status == "approved"

    @pytest.mark.integration
    def test_reject_course_with_note(self, client, app):
        """Học vụ can reject a pending course with a note."""
        _mk(app, "hv@test.com", "hoc_vu")
        teacher_id = _mk(app, "t@test.com", "teacher")
        course_id = _mk_course(app, teacher_id, status="pending_review")
        _login(client, "hv@test.com")

        response = client.post(f"/hoc-vu/courses/{course_id}/review", data={
            "action": "reject",
            "review_note": "Video quality too low",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            course = db.session.get(Course, course_id)
            assert course.status == "rejected"
            assert course.rejection_note == "Video quality too low"

    @pytest.mark.integration
    def test_reject_without_note_fails(self, client, app):
        """Rejection without a note should fail."""
        _mk(app, "hv@test.com", "hoc_vu")
        teacher_id = _mk(app, "t@test.com", "teacher")
        course_id = _mk_course(app, teacher_id, status="pending_review")
        _login(client, "hv@test.com")

        response = client.post(f"/hoc-vu/courses/{course_id}/review", data={
            "action": "reject",
            "review_note": "",
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            course = db.session.get(Course, course_id)
            assert course.status == "pending_review"  # not changed

# ═══════════════════════════════════════════════════════════
#           7. ROLE-BASED ACCESS CONTROL (NEW ROLES)
# ═══════════════════════════════════════════════════════════

class TestNewRoleAccess:
    """Verify access boundaries for hoc_vu, le_tan, ke_toan."""

    @pytest.mark.security
    def test_student_cannot_access_hocvu_routes(self, client, app):
        """Students should be blocked from Học vụ endpoints."""
        _mk(app, "s@test.com", "student")
        _login(client, "s@test.com")

        urls = [
            "/hoc-vu/dashboard",
            "/hoc-vu/accounts/create",
            "/hoc-vu/accounts/import",
            "/hoc-vu/courses/pending",
        ]
        for url in urls:
            response = client.get(url)
            assert response.status_code == 302, f"Student should be blocked from {url}"

    @pytest.mark.security
    def test_teacher_cannot_access_hocvu_routes(self, client, app):
        """Teachers should be blocked from Học vụ endpoints."""
        _mk(app, "t@test.com", "teacher")
        _login(client, "t@test.com")

        response = client.get("/hoc-vu/dashboard")
        assert response.status_code == 302

    @pytest.mark.security
    def test_hocvu_can_access_own_routes(self, client, app):
        """Học vụ should access all hoc_vu endpoints."""
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        urls = [
            "/hoc-vu/dashboard",
            "/hoc-vu/accounts/create",
            "/hoc-vu/accounts/import",
            "/hoc-vu/courses/pending",
            "/hoc-vu/accounts",
        ]
        for url in urls:
            response = client.get(url)
            assert response.status_code == 200, f"Học vụ should access {url}"

    @pytest.mark.security
    def test_admin_can_access_hocvu_routes(self, client, app):
        """Admin should also access Học vụ endpoints."""
        _mk(app, "admin@test.com", "admin")
        _login(client, "admin@test.com")

        response = client.get("/hoc-vu/dashboard")
        assert response.status_code == 200

    @pytest.mark.security
    def test_hocvu_cannot_access_admin_settings(self, client, app):
        """Học vụ should NOT access admin-only routes like settings."""
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        response = client.get("/admin/settings")
        assert response.status_code == 302

    @pytest.mark.security
    def test_le_tan_can_access_analytics(self, client, app):
        """Lễ tân should access analytics dashboard."""
        _mk(app, "lt@test.com", "le_tan")
        _login(client, "lt@test.com")

        response = client.get("/analytics/")
        assert response.status_code == 200

    @pytest.mark.security
    def test_ke_toan_can_access_analytics(self, client, app):
        """Kế toán should access analytics dashboard."""
        _mk(app, "kt@test.com", "ke_toan")
        _login(client, "kt@test.com")

        response = client.get("/analytics/")
        assert response.status_code == 200

    @pytest.mark.security
    def test_unauthenticated_cannot_access_hocvu(self, client):
        """Anonymous visitors should be blocked from Học vụ routes."""
        response = client.get("/hoc-vu/dashboard")
        assert response.status_code == 302
        assert "login" in response.headers.get("Location", "").lower()

# ═══════════════════════════════════════════════════════════
#           8. HỌC VỤ DASHBOARD
# ═══════════════════════════════════════════════════════════

class TestHocVuDashboard:
    """Test Học vụ dashboard data."""

    @pytest.mark.integration
    def test_dashboard_loads(self, client, app):
        """Dashboard should load with stats."""
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        response = client.get("/hoc-vu/dashboard")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_pending_courses_page(self, client, app):
        """Pending courses page should display courses."""
        _mk(app, "hv@test.com", "hoc_vu")
        teacher_id = _mk(app, "t@test.com", "teacher")
        _mk_course(app, teacher_id, title="Pending Course", status="pending_review")
        _login(client, "hv@test.com")

        response = client.get("/hoc-vu/courses/pending")
        assert response.status_code == 200
        assert b"Pending Course" in response.data

# ═══════════════════════════════════════════════════════════
#           9. END-TO-END: FULL ACCOUNT LIFECYCLE
# ═══════════════════════════════════════════════════════════

class TestEndToEndAccountLifecycle:
    """E2E: Học vụ creates account → user forced to change password → user logs in normally."""

    @pytest.mark.integration
    def test_full_lifecycle(self, client, app):
        """Complete lifecycle: create → login → force change → login again."""
        # 1. Học vụ creates account
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")

        client.post("/hoc-vu/accounts/create", data={
            "email": "lifecycle@test.com",
            "role": "student",
        })

        # Get temp password from flash (we check via DB)
        with app.app_context():
            user = db.session.query(User).filter_by(email="lifecycle@test.com").first()
            assert user is not None
            assert user.must_change_password is True

        # 2. Logout Học vụ
        client.get("/auth/logout")

        # 3. Login as new user (we need to know the temp password - check DB password_hash)
        # Since we can't easily extract temp password, create user manually for this part
        with app.app_context():
            u = db.session.query(User).filter_by(email="lifecycle@test.com").first()
            u.password_hash = generate_password_hash("temppass123")
            db.session.commit()

        _login(client, "lifecycle@test.com", "temppass123")

        # 4. Should be redirected to change password
        response = client.get("/dashboard")
        assert response.status_code == 302
        assert "/auth/change-password" in response.headers.get("Location", "")

        # 5. Change password
        response = client.post("/auth/change-password", data={
            "new_password": "mynewpass123",
            "confirm_password": "mynewpass123",
        }, follow_redirects=True)

        assert response.status_code == 200

        # 6. Now dashboard should work
        response = client.get("/dashboard")
        assert response.status_code == 200

        # 7. Logout and login with new password
        client.get("/auth/logout")
        response = _login(client, "lifecycle@test.com", "mynewpass123")
        assert response.status_code == 302  # redirect to home

        response = client.get("/dashboard")
        assert response.status_code == 200
