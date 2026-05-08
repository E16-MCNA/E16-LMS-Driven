from functools import wraps

from flask import flash, g, redirect, session, url_for

from .extensions import db
from .models import User


def load_current_user():
    uid = session.get("user_id")
    g.user = db.session.get(User, uid) if uid else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(g, "user", None):
            return redirect(url_for("auth.login"))
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not getattr(g, "user", None):
                return redirect(url_for("auth.login"))
            if g.user.role not in roles:
                flash("Bạn không có quyền truy cập.", "error")
                return redirect(url_for("auth.home"))
            return fn(*args, **kwargs)

        return wrapper

    return deco
