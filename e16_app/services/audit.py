import json
from flask import request
from flask_login import current_user
from ..extensions import db
from ..models import AuditLog
from .logging import logger

def log_action(action, target_type=None, target_id=None, detail=None):
    """
    Logs an administrative or significant user action.
    """
    actor_id = current_user.id if current_user.is_authenticated else None
    
    # Try to get IP address
    ip_address = request.remote_addr if request else "Unknown"
    
    # Detail can be a dict, convert to JSON
    detail_str = json.dumps(detail) if detail else None
    
    log = None
    try:
        log = AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail_str,
            ip_address=ip_address
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        from flask import current_app
        current_app.logger.error(f"Failed to write audit log to database: {str(e)}")
    
    # Push to Supabase
    try:
        user_email = current_user.email if current_user.is_authenticated else "Anonymous"
        logger.log(
            action_type=action,
            user_id=actor_id,
            user_email=user_email,
            resource_type=target_type,
            resource_id=target_id,
            metadata=detail,
            status="success"
        )
    except Exception:
        pass

    return log
