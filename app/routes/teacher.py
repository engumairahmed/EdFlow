
from flask import Blueprint, render_template, session

from app.utils.auth_decorators import login_required
from app.utils.role_required import role_required
from app import mongo

db = mongo.db
teacher_bp = Blueprint("teacher", __name__)

@teacher_bp.route("/view_students_data",methods=["GET"])
@login_required
@role_required(["teacher","admin"])
def students_data():
    students=db.students.find()
    return render_template("dashboard/view_all_students.html", students=students)
@teacher_bp.route("/update_student_data",methods=["GET","POST"])
@login_required
@role_required(["teacher","admin"])
def update_student():
    username = session.get('username')
    role = session.get('role')
    return render_template("dashboard/update_student_data.html")