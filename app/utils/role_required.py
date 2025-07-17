from functools import wraps
from flask import session, redirect, url_for, flash

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if role not in allowed_roles:
                flash("You don't have permission to access this resource.", "danger")
                return redirect(url_for('dashboard.dashboard_view'))
            return f(*args, **kwargs)
        return wrapper
    return decorator
