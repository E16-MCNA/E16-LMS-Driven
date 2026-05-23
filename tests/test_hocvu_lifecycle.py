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

class TestHocVuAccountManagementForbidden:
    """Verify that Hoc vu is forbidden/blocked from account creation and import endpoints, which now return 404."""

    @pytest.mark.security
    def test_hocvu_cannot_access_create_user(self, client, app):
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")
        response = client.get("/hoc-vu/accounts/create")
        assert response.status_code == 404

        response = client.post("/hoc-vu/accounts/create", data={
            "email": "shouldfail@test.com",
            "role": "student",
        })
        assert response.status_code == 404

    @pytest.mark.security
    def test_hocvu_cannot_access_import_users(self, client, app):
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")
        response = client.get("/hoc-vu/accounts/import")
        assert response.status_code == 404

        response = client.post("/hoc-vu/accounts/import", data={})
        assert response.status_code == 404

    @pytest.mark.security
    def test_hocvu_cannot_access_reset_password(self, client, app):
        _mk(app, "hv@test.com", "hoc_vu")
        _login(client, "hv@test.com")
        response = client.post("/hoc-vu/accounts/1/reset-temp-password")
        assert response.status_code == 404

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
            assert course.status == "published"

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
            "/hoc-vu/courses/pending",
        ]
        for url in urls:
            response = client.get(url)
            assert response.status_code == 302, f"Student should be blocked from {url}"

        # Old account endpoints should be 404
        for url in ["/hoc-vu/accounts/create", "/hoc-vu/accounts/import"]:
            response = client.get(url)
            assert response.status_code == 404

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
            "/hoc-vu/courses/pending",
        ]
        for url in urls:
            response = client.get(url)
            assert response.status_code == 200, f"Học vụ should access {url}"

        # Old account endpoints should be 404
        for url in ["/hoc-vu/accounts/create", "/hoc-vu/accounts/import", "/hoc-vu/accounts"]:
            response = client.get(url)
            assert response.status_code == 404

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
    """E2E: Admin creates account → user forced to change password → user logs in normally."""

    @pytest.mark.integration
    def test_full_lifecycle(self, client, app):
        """Complete lifecycle: create → login → force change → login again."""
        # 1. Admin creates account
        _mk(app, "admin@test.com", "admin")
        _login(client, "admin@test.com")

        client.post("/admin/users/create", data={
            "email": "lifecycle@test.com",
            "role": "student",
        })

        # Get temp password from flash (we check via DB)
        with app.app_context():
            user = db.session.query(User).filter_by(email="lifecycle@test.com").first()
            assert user is not None
            assert user.must_change_password is True

        # 2. Logout Admin
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
