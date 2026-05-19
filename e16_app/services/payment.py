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
    If an expired pending enrollment is found, it is deleted and a fresh one is created.
    """
    enrollment = db.session.query(Enrollment).filter_by(
        user_id=user_id, course_id=course_id
    ).first()

    if enrollment:
        if enrollment.status in ("active", "completed"):
            return enrollment, False
        if enrollment.status == "pending_payment":
            time_diff = utcnow() - ensure_utc(enrollment.enrolled_at)
            if time_diff.total_seconds() > PAYMENT_TIMEOUT_SECONDS:
                db.session.delete(enrollment)
                db.session.commit()
                enrollment = None

    if not enrollment:
        enrollment = Enrollment(
            user_id=user_id,
            course_id=course_id,
            status="pending_payment",
            enrolled_at=utcnow(),
        )
        db.session.add(enrollment)
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
    enrollment = db.session.query(Enrollment).filter_by(
        user_id=user_id, course_id=course_id
    ).first()

    if not enrollment:
        return False, "Không tìm thấy thông tin đăng ký."

    if enrollment.status in ("active", "completed"):
        return True, "Đã đăng ký trước đó."

    # Verify expiration
    time_diff = utcnow() - ensure_utc(enrollment.enrolled_at)
    if time_diff.total_seconds() > PAYMENT_TIMEOUT_SECONDS:
        db.session.delete(enrollment)
        db.session.commit()
        return False, "Giao dịch thất bại: Mã QR đã hết hạn thanh toán (quá 10 phút)!"

    enrollment.status = "active"
    db.session.commit()
    return True, "Thanh toán thành công."


def cancel_pending_enrollment(user_id: str, course_id: str) -> bool:
    """Cancel a pending payment enrollment. Returns True if one was found and deleted."""
    enrollment = db.session.query(Enrollment).filter_by(
        user_id=user_id, course_id=course_id, status="pending_payment"
    ).first()
    if enrollment:
        db.session.delete(enrollment)
        db.session.commit()
        return True
    return False
