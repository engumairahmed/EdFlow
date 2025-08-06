
from datetime import datetime, timezone
import logging
from bson import ObjectId
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
import pandas as pd

from app.ml.model_utils import get_classification_models_summary  
from app.ml.predictors import predict
from app.utils.auth_decorators import login_required
from app.utils.role_required import role_required
from app import mongo

db = mongo.db
teacher_bp = Blueprint("teacher", __name__)

logger = logging.getLogger(__name__)

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
    
# @teacher_bp.route('/predict-all-students')
# @login_required
# @role_required('teacher')
# def predict_all_students():
#     try:
#         # get_all_student_predictions ek helper function hai
#         # jo database se saare students ka data laega aur prediction run karega
#         students_with_predictions = get_all_student_predictions()
        
#         # Calculate dropout rate for visualization
#         total_students = len(students_with_predictions)
#         dropout_count = sum(1 for s in students_with_predictions if s.get('dropout_prediction_class') == 1)
#         dropout_rate = (dropout_count / total_students) * 100 if total_students > 0 else 0

#         # Template render karein jahan data aur dropout rate pass kiya jaega
#         return render_template(
#             'teacher/all_student_predictions.html',
#             students=students_with_predictions,
#             dropout_rate=dropout_rate,
#             dropout_count=dropout_count,
#             total_students=total_students
#         )
#     except Exception as e:
#         flash(f"Error predicting for all students: {e}", "danger")
#         return redirect(url_for('teacher.dashboard'))

# @teacher_bp.route('/predict-all-students', methods=['GET'])
# # @login_required # Add your decorators here
# # @role_required('teacher')
# def predict_all_students():
#     try:
#         # URL se 'model_name' query parameter get karen. Default value 'random_forest' hai.
#         selected_model = request.args.get('model_name', 'random_forest')
        
#         # 'selected_model' ko prediction service function mein pass karen
#         students_with_predictions = get_all_student_predictions(model_name=selected_model)
        
#         # Dropout rate calculate karen
#         total_students = len(students_with_predictions)
#         dropout_count = sum(1 for s in students_with_predictions if s.get('dropout_prediction_class') == 1)
#         dropout_rate = (dropout_count / total_students) * 100 if total_students > 0 else 0

#         # Template render karen aur 'selected_model' ko bhi pass karen taaki drop-down updated rahe
#         return render_template(
#             'teacher/all_student_predictions.html',
#             students=students_with_predictions,
#             dropout_rate=dropout_rate,
#             dropout_count=dropout_count,
#             total_students=total_students,
#             selected_model=selected_model
#         )
#     except Exception as e:
#         flash(f"Error predicting for all students: {e}", "danger")
#         return redirect(url_for('teacher.dashboard'))


@teacher_bp.route("/students-prediction-dashboard")
@login_required
@role_required(["admin", "analyst", "teacher"])
def students_prediction_dashboard():
    models = get_classification_models_summary()
    return render_template("dashboard/students_prediction.html", models=models)


# @teacher_bp.route("/predict-all-students", methods=["POST"])
# @login_required
# @role_required(["admin", "analyst"])
# def predict_all_students():
#     """
#     Triggers a bulk prediction for all students using the selected model.
#     """
#     try:
#         data = request.get_json()
#         selected_model_name = data.get('model_name')
#         model_path = selected_model_name
#         all_students = list(db.students.find({}))
        
#         for student_data in all_students:
#             df_data = pd.DataFrame([student_data.ml_features])
            
#             prediction_class, probabilities, recommendations = predict(
#                 data=df_data,
#                 model_name=model_path
#             )
            
#             # db.students.update_one(
#             #     {"_id": student_data["_id"]},
#             #     {"$set": {
#             #         "prediction": { # Using a nested document for better organization
#             #             "class": int(prediction_class),
#             #             "probability": float(probabilities[1]),
#             #             "recommendations": recommendations,
#             #             "model_used": selected_model_name,
#             #             "timestamp": datetime.now()
#             #         }
#             #     }}
#             # )

#         return jsonify({"status": "success", "message": f"Predictions updated using {selected_model_name}."}), 200

#     except Exception as e:
#         # A more robust logging mechanism is recommended here
#         print(f"Error during bulk prediction: {e}")
#         return jsonify({"status": "error", "message": str(e)}), 500

@teacher_bp.route("/predict-all-students", methods=["POST"])
@login_required
@role_required(["admin", "analyst"])
def predict_all_students():
    try:
        data = request.get_json()
        model_path = data.get('model_path')
        if not model_path:
            return jsonify({"status": "error", "message": "No model path provided."}), 400

        model_document = db.trained_models.find_one({'details.model_path': model_path})

        print(model_document)
        
        if not model_document:
            logger.error(f"Model path not found in trained_models: {model_path}")
            return jsonify({"status": "error", "message": "Selected model not found."}), 404

        model_name = model_document.get('dataset', 'Unknown Dataset')

        all_students = list(db.students.find({}))
        
        for student_data in all_students:

            if 'ml_features' not in student_data or not student_data['ml_features']:
                logger.warning(f"Skipping student {student_data.get('studentID')} due to missing ml_features.")
                continue

            dob = student_data.get('dateOfBirth')
            age = None
            if dob and isinstance(dob, datetime):
                today = datetime.now(timezone.utc)
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

            ml_features = student_data['ml_features'].copy()
            if age is not None:
                ml_features['age'] = age
            
            df_data = pd.DataFrame([ml_features])
            
            prediction_class, probabilities, recommendations = predict(
                data=df_data,
                model_name=model_path
            )

            db.students.update_one(
                {"_id": student_data["_id"]},
                {"$set": {
                    "prediction": { 
                        "class": int(prediction_class),
                        "probability": float(probabilities[1]),
                        "recommendations": recommendations,
                        "model_used": model_name,
                        "timestamp": datetime.now(timezone.utc)
                    }
                }}
            )

        logger.info(f"Predictions updated for all students using {model_name}.")

        return jsonify({"status": "success", "message": f"Predictions updated for all students using {model_name}."}), 200

    except Exception as e:
        logger.error(f"Error during bulk prediction: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An internal server error occurred."}), 500

@teacher_bp.route("/api/get-all-predictions", methods=["GET"])
@login_required
@role_required(["admin", "analyst"])
def get_all_predictions():
    """
    Fetches all student predictions to be displayed on the frontend.
    """
    try:
        # Fetch students who have a prediction stored
        all_students = list(db.students.find({
            "prediction.class": {"$exists": True}
        }))
        
        # Prepare data for JSON response
        predictions = []
        for student in all_students:
            student['_id'] = str(student['_id'])
            
            # Ensure the structure is what the frontend expects
            predictions.append({
                "student_name": student.get("student_name", "N/A"),
                "prediction_class": student["prediction"]["class"],
                "prediction_probability": student["prediction"]["probability"],
                "recommendations": student["prediction"]["recommendations"],
                "prediction_timestamp": student["prediction"]["timestamp"].isoformat(), # Convert to string
                "model_used": student["prediction"]["model_used"]
            })

        return jsonify({"status": "success", "predictions": predictions}), 200

    except Exception as e:
        print(f"Error fetching all predictions: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500