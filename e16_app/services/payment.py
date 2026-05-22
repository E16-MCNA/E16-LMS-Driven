# -*- coding: utf-8 -*-
"""
Payment service for E16 LMS.
Handles checkout flow, QR payment simulation, IPN verification, and enrollment activation.
"""
import random
import string
from ..extensions import db
from ..models import Course, Enrollment
from ..time_utils import ensure_utc, utcnow

# Payment session timeout in seconds (10 minutes)
PAYMENT_TIMEOUT_SECONDS = 600


def get_or_create_pending_enrollment(user_id: str, course_id: str):
    """
    Find existing pending enrollment or create a new one.
    Returns (enrollment, was_expired) tuple.
    If an expired, cancelled, rejected or refunded enrollment is found, it is
    reused as a new pending payment while preserving the same business record.
    """
    from ..models import PaymentTransaction
    enrollment = db.session.query(Enrollment).filter_by(
        user_id=user_id, course_id=course_id
    ).first()

    was_expired = False
    course = db.session.get(Course, course_id)

    if enrollment:
        if enrollment.status in ("active", "completed"):
            return enrollment, False

        # If pending_payment is expired, we renew/reuse it
        if enrollment.status == "pending_payment":
            time_diff = utcnow() - ensure_utc(enrollment.enrolled_at)
            if time_diff.total_seconds() > PAYMENT_TIMEOUT_SECONDS:
                # Mark previous pending transaction as expired
                old_tx = db.session.query(PaymentTransaction).filter_by(
                    enrollment_id=enrollment.id,
                    status="pending"
                ).order_by(PaymentTransaction.created_at.desc()).first()
                if old_tx:
                    old_tx.status = "expired"
                    old_tx.processed_at = utcnow()
                    old_tx.notes = "Mã QR hết hạn thanh toán (quá 10 phút)"

                enrollment.enrolled_at = utcnow()
                enrollment.amount_paid = None
                enrollment.payment_method = None
                new_code = generate_tx_code()
                enrollment.tx_code = new_code
                enrollment.approved_by = None
                enrollment.approved_at = None
                enrollment.rejected_reason = None
                enrollment.refunded_at = None

                tx = PaymentTransaction(
                    enrollment_id=enrollment.id,
                    user_id=user_id,
                    course_id=course_id,
                    amount=course.price if course else 0,
                    payment_method="mock_qr",
                    tx_code=new_code,
                    status="pending"
                )
                db.session.add(tx)
                db.session.commit()
                was_expired = True
            return enrollment, was_expired

        # If inactive financially, transition back to pending_payment and reset current payment fields.
        if enrollment.status in ("rejected", "refunded", "expired", "cancelled"):
            enrollment.status = "pending_payment"
            enrollment.enrolled_at = utcnow()
            enrollment.amount_paid = None
            enrollment.payment_method = None
            new_code = generate_tx_code()
            enrollment.tx_code = new_code
            enrollment.approved_by = None
            enrollment.approved_at = None
            enrollment.rejected_reason = None
            enrollment.refunded_at = None
            db.session.flush()

            tx = PaymentTransaction(
                enrollment_id=enrollment.id,
                user_id=user_id,
                course_id=course_id,
                amount=course.price if course else 0,
                payment_method="mock_qr",
                tx_code=new_code,
                status="pending"
            )
            db.session.add(tx)
            db.session.commit()
            return enrollment, False

    if not enrollment:
        new_code = generate_tx_code()
        enrollment = Enrollment(
            user_id=user_id,
            course_id=course_id,
            status="pending_payment",
            enrolled_at=utcnow(),
            tx_code=new_code,
        )
        db.session.add(enrollment)
        db.session.flush()

        tx = PaymentTransaction(
            enrollment_id=enrollment.id,
            user_id=user_id,
            course_id=course_id,
            amount=course.price if course else 0,
            payment_method="mock_qr",
            tx_code=new_code,
            status="pending"
        )
        db.session.add(tx)
        db.session.commit()

    return enrollment, False


def generate_tx_code() -> str:
    """Generate a unique transaction reference code."""
    random_str = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"E16PAY{random_str}"


def get_seconds_remaining(enrollment) -> int:
    """Calculate seconds left in the payment window."""
    time_diff = utcnow() - ensure_utc(enrollment.enrolled_at)
    return max(0, int(PAYMENT_TIMEOUT_SECONDS - time_diff.total_seconds()))


def activate_enrollment(user_id: str, course_id: str):
    """
    Activate a pending enrollment after successful payment.
    Returns (success: bool, message: str).
    """
    from ..models import PaymentTransaction
    enrollment = db.session.query(Enrollment).filter_by(
        user_id=user_id, course_id=course_id
    ).first()

    if not enrollment:
        return False, "Không tìm thấy thông tin đăng ký."

    if enrollment.status in ("active", "completed"):
        return True, "Đã đăng ký trước đó."

    if enrollment.status != "pending_payment":
        return False, "Trạng thái thanh toán không hợp lệ. Vui lòng tạo lại yêu cầu thanh toán."

    course = db.session.get(Course, course_id)
    ok, message = can_enroll(course, None)
    if not ok:
        return False, message

    tx = db.session.query(PaymentTransaction).filter_by(
        enrollment_id=enrollment.id,
        status="pending"
    ).order_by(PaymentTransaction.created_at.desc()).first()

    # Verify expiration
    time_diff = utcnow() - ensure_utc(enrollment.enrolled_at)
    if time_diff.total_seconds() > PAYMENT_TIMEOUT_SECONDS:
        enrollment.status = "expired"
        enrollment.rejected_reason = "Mã QR hết hạn thanh toán"
        if tx:
            tx.status = "expired"
            tx.processed_at = utcnow()
            tx.notes = "Mã QR hết hạn thanh toán (quá 10 phút)"
        db.session.commit()
        return False, "Giao dịch thất bại: Mã QR đã hết hạn thanh toán (quá 10 phút)!"

    enrollment.status = "active"
    enrollment.amount_paid = course.price if course else 0
    enrollment.payment_method = "mock_qr"
    enrollment.approved_at = utcnow()
    if tx:
        tx.status = "approved"
        tx.processed_at = utcnow()
        tx.tx_code = enrollment.tx_code
    db.session.commit()
    return True, "Thanh toán thành công."


def cancel_pending_enrollment(user_id: str, course_id: str) -> bool:
    """Cancel a pending payment enrollment without deleting the financial trail."""
    from ..models import PaymentTransaction
    enrollment = db.session.query(Enrollment).filter_by(
        user_id=user_id, course_id=course_id, status="pending_payment"
    ).first()
    if enrollment:
        enrollment.status = "cancelled"
        enrollment.rejected_reason = "Học viên hủy checkout"
        tx = db.session.query(PaymentTransaction).filter_by(
            enrollment_id=enrollment.id,
            status="pending"
        ).order_by(PaymentTransaction.created_at.desc()).first()
        if tx:
            tx.status = "cancelled"
            tx.processed_at = utcnow()
            tx.notes = "Học viên hủy checkout"
        db.session.commit()
        return True
    return False



def can_enroll(course, user) -> tuple[bool, str]:
    """
    Check if a user can enroll in a course based on deadline and capacity constraints.
    Returns (can_enroll: bool, message: str).
    """
    if not course:
        return False, "Khóa học không tồn tại."
    if course.is_deleted:
        return False, "Khóa học đã bị xóa."

    # Check enrollment deadline
    if course.enrollment_deadline:
        from ..time_utils import ensure_utc, utcnow
        if utcnow() > ensure_utc(course.enrollment_deadline):
            return False, "Đã quá hạn đăng ký khóa học này."

    # Check capacity limit
    if course.max_students is not None:
        active_count = db.session.query(Enrollment).filter(
            Enrollment.course_id == course.id,
            Enrollment.status.in_(["active", "completed"])
        ).count()
        if active_count >= course.max_students:
            return False, "Khóa học đã đầy sĩ số tối đa."

    return True, ""
