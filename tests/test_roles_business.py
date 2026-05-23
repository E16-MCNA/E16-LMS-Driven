# -*- coding: utf-8 -*-
"""
Tests for Lễ tân (Receptionist) and Kế toán (Accountant) business workflows and access control.
"""
import pytest
from werkzeug.security import generate_password_hash
from e16_app.extensions import db
from e16_app.models import User, Course, Enrollment, AuditLog, new_uuid

def _create_user(app, email, password, role, must_change_password=False):
    """Helper to provision a user in database."""
    with app.app_context():
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            must_change_password=must_change_password,
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        return user.id

def _create_course(app, title, price):
    """Helper to provision a course."""
    with app.app_context():
        # Find or create a teacher to satisfy the NOT NULL foreign key constraint
        teacher = db.session.query(User).filter_by(role="teacher").first()
        if not teacher:
            teacher = User(
                email=f"teacher_{new_uuid()[:8]}@e16.test",
                password_hash=generate_password_hash("pass123"),
                role="teacher",
                is_active=True
            )
            db.session.add(teacher)
            db.session.commit()

        course = Course(
            title=title,
            price=price,
            status="published",
            is_deleted=False,
            teacher_id=teacher.id
        )
        db.session.add(course)
        db.session.commit()
        return course.id

def _login(client, email, password):
    """Helper to login a user via form."""
    return client.post("/auth/login", data={
        "email": email,
        "password": password
    }, follow_redirects=True)

# ─────────── 1. Access Control Matrix Tests ───────────

def test_role_routing_after_login(client, app):
    """Verify le_tan and ke_toan land on correct dashboards post-login."""
    _create_user(app, "letan@e16.test", "pass123", "le_tan")
    _create_user(app, "ketoan@e16.test", "pass123", "ke_toan")

    # Log in as Lễ tân
    res = _login(client, "letan@e16.test", "pass123")
    assert res.status_code == 200
    assert res.request.path == "/le-tan/dashboard"
    client.get("/auth/logout")

    # Log in as Kế toán
    res = _login(client, "ketoan@e16.test", "pass123")
    assert res.status_code == 200
    assert res.request.path == "/ke-toan/dashboard"

def test_access_control_letan_boundaries(client, app):
    """Lễ tân should access /le-tan/* but 302 redirect on /ke-toan/* and /admin/*."""
    _create_user(app, "letan@e16.test", "pass123", "le_tan")
    _login(client, "letan@e16.test", "pass123")

    # Can access Lễ tân pages
    assert client.get("/le-tan/dashboard").status_code == 200
    assert client.get("/le-tan/students").status_code == 200
    assert client.get("/le-tan/students/create").status_code == 200

    # Forbidden from Kế toán pages (redirects to home)
    assert client.get("/ke-toan/dashboard").status_code == 302
    assert client.get("/ke-toan/reconciliation").status_code == 302
    assert client.get("/ke-toan/revenue").status_code == 302

    # Forbidden from Admin pages (redirects to home)
    assert client.get("/admin/users").status_code == 302

def test_access_control_ketoan_boundaries(client, app):
    """Kế toán should access /ke-toan/* but 302 redirect on /le-tan/* and /admin/*."""
    _create_user(app, "ketoan@e16.test", "pass123", "ke_toan")
    _login(client, "ketoan@e16.test", "pass123")

    # Can access Kế toán pages
    assert client.get("/ke-toan/dashboard").status_code == 200
    assert client.get("/ke-toan/reconciliation").status_code == 200
    assert client.get("/ke-toan/revenue").status_code == 200

    # Forbidden from Lễ tân pages (redirects to home)
    assert client.get("/le-tan/dashboard").status_code == 302
    assert client.get("/le-tan/students").status_code == 302

    # Forbidden from Admin pages (redirects to home)
    assert client.get("/admin/users").status_code == 302

def test_access_control_other_roles_on_new_blueprints(client, app):
    """Students/Teachers/Học vụ should not access Lễ tân or Kế toán pages (redirects to home)."""
    _create_user(app, "student@e16.test", "pass123", "student")
    _login(client, "student@e16.test", "pass123")

    assert client.get("/le-tan/dashboard").status_code == 302
    assert client.get("/ke-toan/dashboard").status_code == 302

# ─────────── 2. Receptionist Workflow Tests ───────────

def test_letan_create_student_account(client, app):
    """Lễ tân provisions student directly. Verifies temp password & forced pw change."""
    _create_user(app, "letan@e16.test", "pass123", "le_tan")
    _login(client, "letan@e16.test", "pass123")

    # Submit the student creation form
    response = client.post("/le-tan/students/create", data={
        "email": "newstudent@e16.test",
        "phone": "0987654321",
        "enroll_now": "n"
    }, follow_redirects=True)

    assert response.status_code == 200

    with app.app_context():
        student = db.session.query(User).filter_by(email="newstudent@e16.test").first()
        assert student is not None
        assert student.role == "student"
        assert student.phone == "0987654321"
        assert student.must_change_password is True
        assert student.temp_password_hash is not None

        # Verify audit logging
        audit = db.session.query(AuditLog).filter_by(action="student_created_by_letan").first()
        assert audit is not None
        assert audit.metadata_json["email"] == "newstudent@e16.test"

def test_letan_enroll_student_direct_cash(client, app):
    """Lễ tân registers a student directly bypassing standard QR checkout."""
    _create_user(app, "letan@e16.test", "pass123", "le_tan")
    student_id = _create_user(app, "student@e16.test", "pass123", "student")
    course_id = _create_course(app, "Lập trình Python Cơ Bản", 300000)

    _login(client, "letan@e16.test", "pass123")

    # Enroll the student
    response = client.post("/le-tan/enroll", data={
        "email": "student@e16.test",
        "course_id": course_id
    }, follow_redirects=True)

    assert response.status_code == 200

    with app.app_context():
        # Verifies enrollment is immediately created as 'active' (bypassing pending)
        enrollment = db.session.query(Enrollment).filter_by(user_id=student_id, course_id=course_id).first()
        assert enrollment is not None
        assert enrollment.status == "active"

        # Verifies audit logging
        audit = db.session.query(AuditLog).filter_by(action="enrollment_created_by_letan").first()
        assert audit is not None
        assert audit.metadata_json["course_title"] == "Lập trình Python Cơ Bản"

# ─────────── 3. Accountant Workflow Tests ───────────

def test_ketoan_payment_reconciliation_flow(client, app):
    """Kế toán processes payment reconciliation: approving and rejecting."""
    _create_user(app, "ketoan@e16.test", "pass123", "ke_toan")
    student_id = _create_user(app, "student@e16.test", "pass123", "student")
    course_1_id = _create_course(app, "SQL Bootcamp", 150000)
    course_2_id = _create_course(app, "Docker Mastery", 200000)

    # 1. Simulate two pending payment checkouts
    with app.app_context():
        e1 = Enrollment(user_id=student_id, course_id=course_1_id, status="pending_payment")
        e2 = Enrollment(user_id=student_id, course_id=course_2_id, status="pending_payment")
        db.session.add_all([e1, e2])
        db.session.commit()
        e1_id = e1.id
        e2_id = e2.id

    _login(client, "ketoan@e16.test", "pass123")

    # 2. Approve e1
    res_approve = client.post(f"/ke-toan/reconciliation/approve/{e1_id}", follow_redirects=True)
    assert res_approve.status_code == 200

    with app.app_context():
        enroll_1 = db.session.get(Enrollment, e1_id)
        assert enroll_1 is not None
        assert enroll_1.status == "active" # transitions to active

        # Verify Audit Log
        audit = db.session.query(AuditLog).filter_by(action="payment_approved_by_ketoan").first()
        assert audit is not None
        assert audit.metadata_json["amount"] == 150000

    # 3. Reject e2
    res_reject = client.post(f"/ke-toan/reconciliation/reject/{e2_id}", follow_redirects=True)
    assert res_reject.status_code == 200

    with app.app_context():
        enroll_2 = db.session.get(Enrollment, e2_id)
        assert enroll_2 is not None
        assert enroll_2.status == "rejected"

        # Verify Audit Log
        audit = db.session.query(AuditLog).filter_by(action="payment_rejected_by_ketoan").first()
        assert audit is not None
        assert audit.metadata_json["course_title"] == "Docker Mastery"

def test_ketoan_refund_revocation(client, app):
    """Kế toán processes a refund: revokes access and logs action."""
    _create_user(app, "ketoan@e16.test", "pass123", "ke_toan")
    student_id = _create_user(app, "student@e16.test", "pass123", "student")
    course_id = _create_course(app, "Fullstack Web Dev", 500000)

    # Provision an active enrollment
    with app.app_context():
        e = Enrollment(user_id=student_id, course_id=course_id, status="active")
        db.session.add(e)
        db.session.commit()
        enroll_id = e.id

    _login(client, "ketoan@e16.test", "pass123")

    # Request refund
    res = client.post(f"/ke-toan/refund/{enroll_id}", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        enroll = db.session.get(Enrollment, enroll_id)
        assert enroll is not None
        assert enroll.status == "refunded"

        # Verify audit log
        audit = db.session.query(AuditLog).filter_by(action="refund_processed_by_ketoan").first()
        assert audit is not None
        assert audit.metadata_json["refund_amount"] == 500000

def test_ketoan_export_revenue_csv(client, app):
    """Kế toán exports financial data to CSV."""
    _create_user(app, "ketoan@e16.test", "pass123", "ke_toan")
    _login(client, "ketoan@e16.test", "pass123")

    res = client.get("/ke-toan/export-revenue")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    assert "bao_cao_doanh_thu.csv" in res.headers.get("Content-Disposition", "")
    csv_data = res.data.decode("utf-8")
    assert "Mã Ghi Danh" in csv_data
    assert "Email Học Viên" in csv_data
    assert "Học Phí (VND)" in csv_data


def test_payment_ledger_and_transactions(client, app):
    """Verify that every creation, approval, rejection, and refund of an enrollment automatically records correctly in PaymentTransaction table."""
    from e16_app.models import PaymentTransaction, Enrollment
    from e16_app.services.payment import get_or_create_pending_enrollment

    # Create users and course
    _create_user(app, "letan@e16.test", "pass123", "le_tan")
    _create_user(app, "ketoan@e16.test", "pass123", "ke_toan")
    student_id = _create_user(app, "student@e16.test", "pass123", "student")
    course_id = _create_course(app, "Ledger Course", 200000)

    # 1. Test get_or_create_pending_enrollment creates a pending transaction
    with app.app_context():
        enrollment, was_expired = get_or_create_pending_enrollment(student_id, course_id)
        assert enrollment.status == "pending_payment"
        tx = db.session.query(PaymentTransaction).filter_by(enrollment_id=enrollment.id).first()
        assert tx is not None
        assert tx.status == "pending"
        assert tx.amount == 200000
        assert tx.payment_method == "mock_qr"
        enroll_id = enrollment.id

    # 2. Test Accountant approves payment updates transaction to approved
    _login(client, "ketoan@e16.test", "pass123")
    res = client.post(f"/ke-toan/reconciliation/approve/{enroll_id}", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        enroll = db.session.get(Enrollment, enroll_id)
        assert enroll.status == "active"
        tx = db.session.query(PaymentTransaction).filter_by(enrollment_id=enroll_id, status="approved").first()
        assert tx is not None
        assert tx.payment_method == "bank_transfer"

    # 3. Test Accountant refunds, creating a negative amount refunded transaction
    res = client.post(f"/ke-toan/refund/{enroll_id}", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        enroll = db.session.get(Enrollment, enroll_id)
        assert enroll.status == "refunded"
        tx_refund = db.session.query(PaymentTransaction).filter_by(enrollment_id=enroll_id, status="refunded").first()
        assert tx_refund is not None
        assert tx_refund.amount == -200000

    # 4. Test Lễ tân counter enrollment creates an approved cash_at_frontdesk transaction
    client.get("/auth/logout")
    _login(client, "letan@e16.test", "pass123")

    # Enroll student in a different course
    course2_id = _create_course(app, "Frontdesk Course", 120000)
    res = client.post("/le-tan/enroll", data={
        "email": "student@e16.test",
        "course_id": course2_id
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        enroll2 = db.session.query(Enrollment).filter_by(user_id=student_id, course_id=course2_id).first()
        assert enroll2 is not None
        assert enroll2.status == "active"
        tx = db.session.query(PaymentTransaction).filter_by(enrollment_id=enroll2.id).first()
        assert tx is not None
        assert tx.status == "approved"
        assert tx.payment_method == "cash_at_frontdesk"
        assert tx.amount == 120000

    # 5. Test Accountant rejects payment, updating transaction to rejected
    course3_id = _create_course(app, "Rejected Course", 180000)
    with app.app_context():
        enroll3, _ = get_or_create_pending_enrollment(student_id, course3_id)
        enroll3_id = enroll3.id

    client.get("/auth/logout")
    _login(client, "ketoan@e16.test", "pass123")
    res = client.post(f"/ke-toan/reconciliation/reject/{enroll3_id}", data={
        "rejected_reason": "Wrong amount sent"
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        enroll = db.session.get(Enrollment, enroll3_id)
        assert enroll.status == "rejected"
        tx = db.session.query(PaymentTransaction).filter_by(enrollment_id=enroll3_id, status="rejected").first()
        assert tx is not None
        assert tx.notes == "Wrong amount sent"
