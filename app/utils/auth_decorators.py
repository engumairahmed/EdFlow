from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            flash("Please login to access this page", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated