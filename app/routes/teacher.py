
from flask import Blueprint, render_template, session


teacher_bp = Blueprint("teacher", __name__)

@teacher_bp.route("/")
def teacher_data():
    username = session.get('username')
    role = session.get('role')
    return render_template("dashboard.html", username=username, role=role)