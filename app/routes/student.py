
from flask import Blueprint, render_template, session


student_bp = Blueprint("student", __name__)

@student_bp.route("/")
def student_data():
    username = session.get('username')
    role = session.get('role')
    return render_template("dashboard.html", username=username, role=role)
