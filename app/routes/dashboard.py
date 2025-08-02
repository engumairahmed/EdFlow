# app/routes/dashboard.py - Final Unified Version

import os
import pandas as pd
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from app.ml.dataset_manager import merge_with_existing_dataset, process_and_store_dataset
from app.ml.model_utils import load_model
from app.ml.predictors import predict, predict_missing_fields
from app.ml.trainer import train_models_and_save_metrics
from app.utils.auth_decorators import login_required
from app import mongo
from app.utils.mongodb_utils import save_dataset_to_mongodb
from app.utils.notifications import send_role_notification
from app.utils.role_required import role_required
from app.ml.anomaly_detector import detect_student_anomalies, get_insights
from config import Config

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
                role="admin",
                url="/my-models"
            )
            return redirect(url_for("dashboard.dashboard_view"))
        except Exception as e:
            flash(f"Error processing file: {e}", "danger")

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
            return redirect(url_for("dashboard.predict_form"))
        if model_doc["is_paid"] and session.get('plan') != "premium":
            flash("This model requires a premium plan.", "danger")
            return redirect(url_for("dashboard.predict"))
        result = predict_missing_fields(input_data, model_name)
        flash(f"Prediction complete: {result}", "success")
        return render_template("dashboard/predict.html", available_models=available_models, prediction=result)

    return render_template("dashboard/predict.html", available_models=available_models)

@dashboard_bp.route('/analytics', methods=['GET'])
@login_required
@role_required(["admin", "analyst", "teacher"])
def analytics():
    return render_template("dashboard/analytics.html")

@dashboard_bp.route('/dataset')
@login_required
def dataset():
    return render_template("dashboard/dataset.html")

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

# --- Anomaly Detection Unified Route ---
@dashboard_bp.route('/anomaly-results', methods=['GET', 'POST'])
@login_required
@role_required(["admin", "analyst"])
def anomaly_results_view():
    all_files = [f for f in os.listdir(UPLOADS_DIR) if f.endswith(('.csv', '.xlsx'))]
    selected_file = None
    anomalous_students = []
    anomaly_chart_data = {'gender': {}, 'scores': {}}
    anomaly_insights = {}
    total_students = 0
    results_source = None

    if request.method == 'POST':
        if request.form.get('run_db_scan'):
            # Logic for Database Scan
            results_source = "database"
            anomalous_students, anomaly_insights, total_students = detect_anomalies_from_db()
            if not anomalous_students:
                flash("No anomalies found in the database student data.", "success")
        else:
            # Logic for File Scan
            selected_file = request.form.get("file_select")
            if not selected_file:
                flash("No file selected.", "danger")
            else:
                results_source = "file"
                file_path = os.path.join(UPLOADS_DIR, selected_file)
                try:
                    df = pd.read_csv(file_path) if selected_file.endswith('.csv') else pd.read_excel(file_path)
                    total_students = len(df)
                    anomalous_df, anomaly_insights = detect_anomalies_from_df(df)
                    anomalous_students = anomalous_df.to_dict('records')
                    if not anomalous_students:
                        flash("No anomalies found in the selected file.", "success")
                except Exception as e:
                    flash(f"Error processing the file: {e}", "danger")
                    anomalous_students = []

        if anomalous_students:
            anomalous_df = pd.DataFrame(anomalous_students)
            gender_counts = anomalous_df.get('gender', pd.Series()).value_counts().to_dict()
            score_bins = {
                '<-0.5': len(anomalous_df[anomalous_df['anomaly_score'] < -0.5]),
                '-0.5 to -0.2': len(anomalous_df[(anomalous_df['anomaly_score'] >= -0.5) & (anomalous_df['anomaly_score'] < -0.2)]),
                '-0.2 to 0': len(anomalous_df[(anomalous_df['anomaly_score'] >= -0.2) & (anomalous_df['anomaly_score'] < 0)]),
                '>0': len(anomalous_df[anomalous_df['anomaly_score'] >= 0]),
            }
            anomaly_chart_data = {'gender': gender_counts, 'scores': score_bins}
            flash(f"Anomalies detected: {len(anomalous_students)} students flagged.", "danger")
    
    # Is block ko GET request par bhi chalne ke liye move kiya gaya hai
    if not anomalous_students and request.method == 'GET':
        flash("Please select a file or run a database scan to see results.", "info")

    return render_template('dashboard/anomaly_results.html',
                           all_files=all_files,
                           selected_file=selected_file,
                           anomalous_students=anomalous_students,
                           anomaly_chart_data=anomaly_chart_data,
                           anomaly_insights=anomaly_insights,
                           total_students=total_students,
                           results_source=results_source)