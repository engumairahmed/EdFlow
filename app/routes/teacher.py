
from datetime import datetime, timezone
from bson import ObjectId
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
import pandas as pd

from app.ml.predictors import predict
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
@teacher_bp.route("/update_student_data/<id>",methods=["GET","POST"])
@login_required
@role_required(["teacher","admin"])
def update_student(id):
    if request.method == "GET":
        student = db.students.find_one({"_id": ObjectId(id)})
        if student is None:
            flash("Student not found", "danger")
            return render_template("dashboard/view_all_students.html")
        if 'dateOfBirth' in student and student['dateOfBirth']:
                today = datetime.now(timezone.utc) # Use UTC for consistency
                dob = student['dateOfBirth']
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                # Add the calculated age to the ml_features sub-document
                if 'ml_features' not in student:
                    student['ml_features'] = {}
                student['ml_features']['age'] = age
        return render_template("dashboard/update_student_data.html",student=student)
    if request.method == "POST":
        studentID = request.form.get("studentID")
        studentName = request.form.get("studentName")
        age = request.form.get("age")
        gender = request.form.get("gender")
        parental_education_level = request.form.get("parental_education")
        exam_score = request.form.get("exam_score")
        netflix_hours = request.form.get("netflix_hours")
        diet_quality = request.form.get("diet_quality")
        student = db.students.find_one({"studentID": studentID})
        if student is None:
            flash("Student not found", "danger")
            return render_template("dashboard/view_all_students.html")
        db.students.update_one({"_id": ObjectId(id)}, {"$set": {
            "name": studentName,
            "ml_features.age": age,
            "ml_features.gender": gender,
            "ml_features.parental_education": parental_education_level,
            "ml_features.exam_score": exam_score,
            "ml_features.netflix_hours": netflix_hours,
            "ml_features.diet_quality": diet_quality
        }})
        flash("Student data updated successfully", "success")
        return render_template("dashboard/view_all_students.html")
  