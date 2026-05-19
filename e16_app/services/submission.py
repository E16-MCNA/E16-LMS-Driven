# -*- coding: utf-8 -*-
"""
Submission service for E16 LMS.
Handles student assignment submission creation and updates.
"""
from ..extensions import db
from ..models import Submission
from ..time_utils import utcnow


def submit_or_update(user_id: str, assignment_id: str, text_content: str = None, file_path: str = None):
    """
    Create or update a student's submission for an assignment.
    Returns the Submission object.
    """
    existing = db.session.query(Submission).filter_by(
        user_id=user_id, assignment_id=assignment_id
    ).first()

    if existing:
        existing.text_content = text_content
        if file_path:
            existing.file_path = file_path
        existing.submitted_at = utcnow()
        existing.status = "pending"
        db.session.commit()
        return existing

    sub = Submission(
        assignment_id=assignment_id,
        user_id=user_id,
        text_content=text_content,
        file_path=file_path,
    )
    db.session.add(sub)
    db.session.commit()
    return sub
