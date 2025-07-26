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



# --- Existing Profile-Related Pages Ke Routes ---
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
