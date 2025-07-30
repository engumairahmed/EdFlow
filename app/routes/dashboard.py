# app/routes/dashboard.py

import os
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, flash
import pandas as pd
from app.ml.dataset_manager import merge_with_existing_dataset, process_and_store_dataset
from app.ml.model_utils import load_model
from app.ml.predictors import predict, predict_missing_fields
from app.ml.trainer import train_models_and_save_metrics
from app.utils.auth_decorators import login_required
from app import mongo
from app.utils.mongodb_utils import save_dataset_to_mongodb
from app.utils.notifications import send_role_notification
from app.utils.role_required import role_required
# Import the new anomaly detector
from app.ml.anomaly_detector import detect_student_anomalies
from config import Config

# Correctly define UPLOADS_DIR relative to the project root
# os.getcwd() is the project root if you run python run.py from there
MODEL_DIR = os.path.join(os.getcwd(), "app", "ml", "models")
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
VAPID_PUBLIC_KEY = Config.VAPID_PUBLIC_KEY

dashboard_bp = Blueprint("dashboard", __name__)

db = mongo.db

@dashboard_bp.route("")
@login_required
def dashboard_view():
    username = session.get('username')
    role = session.get('role')
    return render_template("dashboard/home.html", username=username, role=role, VAPID_PUBLIC_KEY=VAPID_PUBLIC_KEY)

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

            df = pd.read_csv(file)
            try:
                upload_path = os.path.join(UPLOADS_DIR, f"{model_name}.csv")
                df.to_csv(upload_path, index=False)
                process_and_store_dataset(df)
                train_models_and_save_metrics(df, model_name)
                save_dataset_to_mongodb(df, model_name, session['user_id'], is_paid)
                flash(f"✅ Model '{model_name}' trained and saved!", "success")
                send_role_notification(
                    title="📢 New Model Trained",
                    body=f"The model '{model_name}' has been successfully trained.",
                    role="admin",  # or send to all: loop roles if needed
                    url="/my-models"
                )
                return redirect(url_for("dashboard.dashboard_view"))
            except Exception as e:
                flash(f"Error processing file: {e}", "danger")

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
            return redirect(url_for("dashboard.predict"))

        result = predict_missing_fields(input_data, model_name)
        flash(f"Prediction complete: {result}", "success")
        return render_template("dashboard/predict.html", available_models=available_models, prediction=result)

    return render_template("dashboard/predict.html", available_models=available_models)


@dashboard_bp.route('/analytics',methods=['GET'])
@login_required
@role_required(["admin","analyst","teacher"])
def analytics():
    return render_template("dashboard/analytics.html")

@dashboard_bp.route('/dataset')
@login_required
def dataset():
    return render_template("dashboard/dataset.html")


# --- Existing Routes of Profile-Related Pages ---
@dashboard_bp.route('/my_profile')
@login_required
def my_profile():
    return render_template('dashboard/my_profile.html')

@dashboard_bp.route('/change_password')
@login_required
def change_password():
    return render_template('dashboard/change_password.html')

@dashboard_bp.route('/login_history')
@login_required
def login_history():
    return render_template('dashboard/login_history.html')

# --- Personal Information Page Ka Route ---
@dashboard_bp.route('/personal_information')
@login_required
def personal_information():
    return render_template('dashboard/personal_information.html')


# --- Notification Related Routes 
@dashboard_bp.route('/all_notifications')
@login_required
def all_notifications():
    return render_template('dashboard/all_notifications.html') 

@dashboard_bp.route('/notification_settings')
@login_required
def notification_settings():
    return render_template('dashboard/notification_settings.html') 

@dashboard_bp.route('/update_profile')
def update_profile():
    return render_template('dashboard/update_profile.html')

# =========================================================
# NEW ANOMALY DETECTION ROUTE
# =========================================================
@dashboard_bp.route('/anomaly-results', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'analyst']) # Only admins and analysts can view anomalies
def anomaly_results_view():
    all_files = []
    # Check if the uploads directory exists
    if os.path.exists(UPLOADS_DIR):
        for f in os.listdir(UPLOADS_DIR):
            if f.endswith('.csv'): # Sirf CSV files ko list karein
                all_files.append(f)
        all_files.sort() # Files ko alphabetical order mein sort karein
    
    anomalous_students = []
    anomaly_chart_data = {}
    anomaly_insights = {}
    selected_file = request.args.get('selected_file') # GET request se file name lenge
    
    if request.method == 'POST': # Agar form submit hua hai
        selected_file = request.form.get('file_select')
        
    if selected_file:
        flash(f"Running anomaly detection on: {selected_file}", "info")
        df_processed, anomalous_students = detect_student_anomalies(file_name=selected_file) # file_name pass kiya
        
        # --- Prepare data for Anomaly Overview Visualizations (Same logic as before) ---
        anomaly_chart_data = {
            'gender': {'Male': 0, 'Female': 0, 'Other': 0},
            'scores': {'bin1': 0, 'bin2': 0, 'bin3': 0, 'bin4': 0}
        }
        
        anomaly_insights = {
            'gender_insight': "Analysis of anomaly distribution by gender.",
            'score_insight': "Insights into the spread of anomaly scores."
        }

        if anomalous_students:
            for student in anomalous_students:
                gender = student.get('gender')
                if gender == 'Male':
                    anomaly_chart_data['gender']['Male'] += 1
                elif gender == 'Female':
                    anomaly_chart_data['gender']['Female'] += 1
                else:
                    anomaly_chart_data['gender']['Other'] += 1 

                try:
                    score = float(student.get('anomaly_score', 0))
                    if score < -0.5:
                        anomaly_chart_data['scores']['bin1'] += 1
                    elif -0.5 <= score < -0.2:
                        anomaly_chart_data['scores']['bin2'] += 1
                    elif -0.2 <= score < 0:
                        anomaly_chart_data['scores']['bin3'] += 1
                    else:
                        anomaly_chart_data['scores']['bin4'] += 1
                except ValueError:
                    pass 

            total_anomalies = len(anomalous_students)
            if total_anomalies > 0:
                male_anomalies = anomaly_chart_data['gender']['Male']
                female_anomalies = anomaly_chart_data['gender']['Female']
                
                if male_anomalies > female_anomalies * 1.5:
                    anomaly_insights['gender_insight'] = "Significantly more male students detected as anomalous."
                elif female_anomalies > male_anomalies * 1.5:
                    anomaly_insights['gender_insight'] = "Significantly more female students detected as anomalous."
                else:
                    anomaly_insights['gender_insight'] = "Anomalies are relatively balanced across genders."
                
                if anomaly_chart_data['scores']['bin1'] > anomaly_chart_data['scores']['bin2'] + anomaly_chart_data['scores']['bin3']:
                    anomaly_insights['score_insight'] = "Most anomalies have very low scores, indicating strong deviation from norm."
    else:
        # Initial load or no file selected
        flash("Please select a CSV file to run anomaly detection.", "warning")

    return render_template('dashboard/anomaly_results.html', 
                           all_files=all_files, # Sabhi files ki list pass ki
                           selected_file=selected_file, # Jo file select ki gai
                           anomalous_students=anomalous_students,
                           anomaly_chart_data=anomaly_chart_data,
                           anomaly_insights=anomaly_insights)