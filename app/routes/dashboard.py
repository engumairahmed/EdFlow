
# app/routes/dashboard.py

import logging
import os
from flask import Blueprint, json, jsonify, render_template, request, session, redirect, url_for, flash
import numpy as np
import pandas as pd
from app.ml.dataset_manager import TARGET_FEATURE, validate_columns
from app.ml.predictors import predict, predict_missing_fields
from app.ml.trainer import train_all_models_and_save
from app.utils.auth_decorators import login_required
from app import mongo
from app.utils.mongodb_utils import save_dataset_to_mongodb
from app.utils.notifications import send_role_notification
from app.utils.role_required import role_required
from app.ml.anomaly_detector import detect_anomalies_from_db, detect_anomalies_from_df, get_insights
from config import Config

MODEL_DIR = os.path.join(os.getcwd(), "app", "ml", "models")
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
VAPID_PUBLIC_KEY = Config.VAPID_PUBLIC_KEY

dashboard_bp = Blueprint("dashboard", __name__)

db = mongo.db

logger = logging.getLogger(__name__)

@dashboard_bp.route("", methods=["GET"], strict_slashes=False)
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

        try:
            df = pd.read_csv(file)
            missing = validate_columns(df)
            if missing:
                flash(f"Dataset is missing required columns: {', '.join(missing)}", "danger")
                return redirect(request.url)

            upload_path = os.path.join(UPLOADS_DIR, f"{model_name}.csv")
            df.to_csv(upload_path, index=False)

            df['dropout'] = df['dropout'].values

            train_all_models_and_save(df, dataset_name=model_name, is_paid=is_paid)

            save_dataset_to_mongodb(df, model_name, session['user_id'], is_paid)
            flash(f"✅ Model '{model_name}' trained and saved!", "success")
            try:
                send_role_notification(
                    title="📢 New Model Trained",
                    body=f"The model '{model_name}' has been successfully trained.",
                    role="admin",
                    url="/my-models"
                )
            except Exception as e:
                logger.exception("Error sending notifications")
                flash(f"Error: {e}", "danger")

            return redirect(url_for("dashboard.dashboard_view"))

        except Exception as e:
            logger.exception("Error during upload:")
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
    user = db.users.find_one({"_id": session["user_id"]})
    user_plan = user.get("plan", "free") if user else "free"

    if user_plan == "premium":
        available_models = list(db.trained_models.find())
    else:
        available_models = list(db.trained_models.find({"is_paid": False}))

    if request.method == "POST":
        try:
            data = request.get_json()
            if not data or "model" not in data:
                logger.warning("Prediction request missing model field.")
                return jsonify({"error": "Invalid input. Model not specified."}), 400

            model_path = data["model"]

            numeric_fields = ['age', 'currentGPA', 'attendance', 'study_hours',
                              'sleep_hours', 'social_media_hours',
                              'netflix_hours', 'mental_health_score', 'exam_score']

            input_data = {}
            for k, v in data.items():
                if k == "model":
                    continue
                if k in numeric_fields:
                    try:
                        input_data[k] = float(v) if v is not None and str(v).strip() != '' else None
                    except ValueError:
                        logger.warning(f"Invalid numeric input for field '{k}': {v}")
                        input_data[k] = None
                else:
                    input_data[k] = v if v is not None and str(v).strip() != '' else None

            model_doc = db.trained_models.find_one({
                "details.model_path": model_path
            })

            if not model_doc:
                logger.error(f"Model not found for path: {model_path}")
                return jsonify({"error": "Model not found."}), 404

            if model_doc.get("is_paid") and user_plan != "premium":
                logger.info(f"User with free plan tried accessing paid model: {model_path}")
                return jsonify({"error": "This model requires a premium plan."}), 403

            dataset_name_for_imputation = model_doc.get("dataset")
            if not dataset_name_for_imputation:
                logger.error("Dataset name for imputation missing in model document.")
                return jsonify({"error": "Model dataset not specified for imputation."}), 400

            imputed_input_data_dict = predict_missing_fields(input_data, dataset_name_for_imputation)
            df_data = pd.DataFrame([imputed_input_data_dict])

            prediction_class, probabilities, recommendations = predict(data=df_data, model_name=model_path)

            logger.info(f"Prediction successful using model: {model_path}")
            return jsonify({
                "prediction_class": int(prediction_class),
                "prediction_probability": float(probabilities[1]) if probabilities is not None else None,
                "recommendations": recommendations
            })

        except Exception as e:
            logger.exception("Unexpected error during prediction.")
            return jsonify({"error": f"An unexpected error occurred. Please try again later."}), 500

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
            if f.endswith('.csv') or f.endswith('.xlsx'): # CSV aur XLSX files ko list karein
                all_files.append(f)
        all_files.sort() # Files ko alphabetical order mein sort karein
    
    anomalous_students = []
    anomaly_insights = {}
    total_students = 0
    selected_file = request.args.get('selected_file')
    results_source = "file" # Default source file hai

    if request.method == 'POST':
        if request.form.get('run_db_scan'):
            results_source = "database"
            # Ab 3 values ko sahi se unpack kiya ja raha hai
            anomalous_students, anomaly_insights, total_students = detect_anomalies_from_db()
            if not anomalous_students:
                flash("No anomalies found in the database.", "info")
            else:
                flash(f"Successfully ran anomaly detection on database. Found {len(anomalous_students)} anomalies.", "success")
        else:
            selected_file = request.form.get('file_select')
            if selected_file:
                flash(f"Running anomaly detection on: {selected_file}", "info")
                try:
                    # Ab 3 values ko sahi se unpack kiya ja raha hai
                    anomalous_df, anomaly_insights, total_students = detect_anomalies_from_df(selected_file)
                    anomalous_students = anomalous_df.to_dict('records')
                except FileNotFoundError:
                    flash(f"Error: The file '{selected_file}' was not found.", "danger")
                except KeyError as e:
                    # Agar file mein koi column missing ho to is error ko catch karein
                    flash(f"Error: Missing columns in the uploaded file: {e}. Please ensure the file has columns like 'age', 'total_score', or 'attendance'.", "danger")
                except Exception as e:
                    flash(f"An unexpected error occurred: {e}", "danger")
            else:
                flash("Please select a file or choose to run a database scan.", "warning")

    # Chart data JSON ke liye prepare karna
    gender_anomaly_data = {}
    score_distribution_data = {}

    if anomalous_students:
        # Gender Chart data
        genders = [s.get('gender') for s in anomalous_students if s.get('gender') is not None]
        if genders:
            gender_counts = pd.Series(genders).value_counts().to_dict()
            gender_anomaly_data = {
                'data': [{'labels': list(gender_counts.keys()), 'values': list(gender_counts.values()), 'type': 'pie'}],
                'layout': {'title': 'Anomalies by Gender'}
            }
        
        # Anomaly Score Chart data
        scores = pd.Series([s.get('anomaly_score') for s in anomalous_students if s.get('anomaly_score') is not None])
        if not scores.empty:
            bins = [-float('inf'), -0.2, 0, float('inf')] # You can adjust these bins
            labels = ['<-0.2', '-0.2 to 0', '>0']
            score_bins = pd.cut(scores, bins=bins, labels=labels)
            score_counts = score_bins.value_counts().sort_index().to_dict()
            score_distribution_data = {
                'data': [{'x': list(score_counts.keys()), 'y': list(score_counts.values()), 'type': 'bar'}],
                'layout': {'title': 'Anomaly Score Distribution'}
            }

    return render_template(
        'dashboard/anomaly_results.html',
        all_files=all_files,
        selected_file=selected_file,
        anomalous_students=anomalous_students,
        anomaly_insights=anomaly_insights, # Naya 'insights' variable pass kiya gaya hai
        total_students=total_students, # Total students ki sankhya pass ki gai hai
        results_source=results_source,
        gender_chart_json=json.dumps(gender_anomaly_data),
        score_chart_json=json.dumps(score_distribution_data)
    )