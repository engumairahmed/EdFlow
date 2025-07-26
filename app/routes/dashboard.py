# app/routes/dashboard.py

import os
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, flash
import pandas as pd
from app.ml.dataset_manager import merge_with_existing_dataset, process_and_store_dataset
from app.ml.model_utils import load_model
from app.ml.predictors import predict, predict_missing_fields
from app.ml.trainer import train_models_and_save_metrics
from app.utils.auth_decorators import login_required
from app.utils.db import get_database, get_mongo_client
from app.utils.role_required import role_required
# Import the new anomaly detector
from app.ml.anomaly_detector import detect_student_anomalies

# Correctly define UPLOADS_DIR relative to the project root
# os.getcwd() is the project root if you run python run.py from there
MODEL_DIR = os.path.join(os.getcwd(), "app", "ml", "models")
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads") # Ensure this points to your uploads folder

dashboard_bp = Blueprint("dashboard", __name__)

# It's better to get db inside routes if using Flask app context correctly,
# or ensure it's initialized globally in __init__.py and imported.
# For simplicity, keeping it here for now if get_database() works globally.
db = get_database()


@dashboard_bp.route("")
@login_required
def dashboard_view():
    username = session.get('username')
    role = session.get('role')
    return render_template("dashboard/home.html", username=username, role=role)

@dashboard_bp.route("/upload", methods=["GET", "POST"])
@login_required
@role_required(["admin", "analyst"])
def upload_data():
        if request.method == "POST":
            file = request.files.get("dataset")
            model_name = request.form.get("model_name").strip()
            is_paid = True if request.form.get("is_paid") == "on" else False

            if not file or file.filename == "":
                flash("No file selected.", "danger")
                return redirect(request.url)

            # Ensure UPLOADS_DIR exists
            os.makedirs(UPLOADS_DIR, exist_ok=True)

            # Save the uploaded file temporarily to process
            filepath = os.path.join(UPLOADS_DIR, file.filename)
            file.save(filepath)

            try:
                if file.filename.endswith('.csv'):
                    new_df = pd.read_csv(filepath)
                elif file.filename.endswith('.xlsx'):
                    new_df = pd.read_excel(filepath)
                else:
                    flash("Invalid file format. Please upload CSV or XLSX.", "danger")
                    # os.remove(filepath) # Clean up
                    return redirect(request.url)
                
                # Process and store the dataset (this also handles merging if similar dataset exists)
                # This function now also inserts data into MongoDB
                # Note: process_and_store_dataset might need to be updated to handle the 'merged_dataset_2.csv' naming
                # if you intend to use this route for that specific file.
                message = process_and_store_dataset(new_df)
                flash(message, "success")

                # If you want to train a model immediately after upload, uncomment below
                # train_models_and_save_metrics(new_df, model_name, is_paid, session.get('username'))
                # flash(f"Dataset uploaded and processed successfully. Model '{model_name}' trained.", "success")

            except Exception as e:
                flash(f"Error processing file: {e}", "danger")
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath) # Clean up the uploaded file

            return redirect(url_for("dashboard.upload_data"))
        
        return render_template("dashboard/upload.html")

@dashboard_bp.route("/my-models")
@login_required
@role_required(["admin", "analyst"])
def my_models():
    user = db.users.find_one({"username": session['username']})
    model_names = user.get("models", [])

    return render_template("dashboard/my_models.html", models=model_names)

@dashboard_bp.route("/predict", methods=["GET", "POST"])
@login_required
@role_required(["admin"])
def predict_form():
    available_models = list(db.trained_models.find())

    if request.method == "POST":
        model_name = request.form.get("model_name")
        input_data = {
            k: float(v) if v else None for k, v in request.form.items() if k != "model_name"
        }

        model_doc = db.trained_models.find_one({"name": model_name})
        if not model_doc:
            flash("Model not found.", "danger")
            return redirect(url_for("dashboard.predict_form")) # Changed to predict_form

        # Access control: is model paid & does user have plan?
        if model_doc["is_paid"] and session.get('plan') != "premium": # Assuming 'plan' in session for user
            flash("This model requires a premium plan.", "danger")
            return redirect(url_for("dashboard.predict_form")) 

        result = predict_missing_fields(input_data, model_name) # Assuming predict_missing_fields handles data properly
        
        # Flash message for prediction result
        if result and isinstance(result, dict) and 'prediction' in result:
            flash(f"Prediction complete: {result['prediction']}", "success")
        elif result:
            flash(f"Prediction complete: {result}", "success")
        else:
            flash("Prediction failed.", "danger")

        return render_template("dashboard/predict.html", available_models=available_models, prediction=result)

    return render_template("dashboard/predict.html", available_models=available_models)


@dashboard_bp.route('/analytics',methods=['GET'])
@login_required
@role_required(['admin', 'analyst'])
def analytics(): # Renamed from analytics_view to analytics for endpoint consistency as per error
    return render_template('dashboard/analytics.html')

@dashboard_bp.route('/dataset',methods=['GET'])
@login_required
@role_required(['admin', 'analyst'])
def dataset(): # Renamed from dataset_view to dataset for endpoint consistency as per error
    return render_template('dashboard/dataSet.html')

# =========================================================
# NEW ANOMALY DETECTION ROUTE
# =========================================================
@dashboard_bp.route('/anomaly-results', methods=['GET'])
@login_required
@role_required(['admin', 'analyst']) # Only admins and analysts can view anomalies
def anomaly_results_view():
    # Adjust contamination based on your dataset; 0.03 means expecting 3% outliers
    # If you see too many or too few anomalies, adjust this value (e.g., 0.01 to 0.1)
    full_df, anomalous_students = detect_student_anomalies(contamination=0.03) 
    
    if anomalous_students: # Check if the list of anomalies is not empty
        # Prepare data for display, ensuring all relevant columns are passed
        display_anomalies = []
        for student in anomalous_students:
            display_anomalies.append({
                'student_id': student.get('student_id', 'N/A'),
                'age': student.get('age', 'N/A'),
                'gender': student.get('gender', 'N/A'),
                'attendance_percentage': student.get('attendance_percentage', 'N/A'),
                'study_hours_per_day': student.get('study_hours_per_day', 'N/A'),
                'exam_score': student.get('exam_score', 'N/A'),
                'social_media_hours': student.get('social_media_hours', 'N/A'),
                'sleep_hours': student.get('sleep_hours', 'N/A'),
                'mental_health_rating': student.get('mental_health_rating', 'N/A'),
                'extracurricular_participation': student.get('extracurricular_participation', 'N/A'),
                'anomaly_score': f"{student.get('anomaly_score', 0):.4f}" # Format score for display
            })
        
        return render_template('dashboard/anomaly_results.html', anomalies=display_anomalies)
    else:
        # If no anomalies or data loading failed
        flash("Could not load student data for anomaly detection or no anomalies found.", "info")
        return render_template('dashboard/anomaly_results.html', anomalies=[])