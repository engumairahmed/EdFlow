import os
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, flash
import pandas as pd
from app.ml.dataset_manager import merge_with_existing_dataset, process_and_store_dataset
from app.ml.model_utils import load_model
from app.ml.predictors import predict, predict_missing_fields
from app.ml.trainer import train_models_and_save_metrics
from app.utils.auth_decorators import login_required
from app.utils.db import get_database, get_mongo_client
from app.utils.mongodb_utils import save_dataset_to_mongodb
from app.utils.role_required import role_required

MODEL_DIR = os.path.join(os.getcwd(), "app", "ml", "models")
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")

dashboard_bp = Blueprint("dashboard", __name__)

db = get_database()

print(db)

@dashboard_bp.route("")
@login_required
def dashboard_view():
    username = session.get('username')
    role = session.get('role')
    print()
    return render_template("dashboard/home.html", username=username, role=role)

@dashboard_bp.route("/upload", methods=["GET", "POST"])
@login_required
@role_required(["admin", "analyst"])
def upload_data():
        if request.method == "POST":
            file = request.files.get("dataset")
            model_name = request.form.get("model_name").strip()
            is_paid = True if request.form.get("is_paid") == "on" else False

            if not file or not model_name:
                flash("Please provide a file and model name.", "danger")
                return redirect(url_for("data.upload_data"))

            df = pd.read_csv(file)
            try:
                print("Step.0: Read data")
                upload_path = os.path.join(UPLOADS_DIR, f"{model_name}.csv")
                df.to_csv(upload_path, index=False)
                print("Step.1: Uploaded data")
                process_and_store_dataset(df)
                print("Step.1: Proccessed data")
                train_models_and_save_metrics(df, model_name)
                print("Step.2: Trained models")
                save_dataset_to_mongodb(df, model_name, session['user_id'], is_paid)
                print("Step.3: Saved to MongoDB")
                flash(f"✅ Model '{model_name}' trained and saved!", "success")
                return redirect(url_for("dashboard.dashboard_view"))
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
                print(f"Error: {str(e)}")
                return redirect(url_for("dashboard.upload_data"))

        return render_template("dashboard/upload.html")

@dashboard_bp.route("/dataset")
@login_required
@role_required(["admin", "analyst"])
def dataset():
    return render_template("dashboard/dataset.html")

@dashboard_bp.route("/data-summary")
@login_required
@role_required(["admin"])
def data_summary():
    try:
        summary = {
            "total_records": db.count_documents({}),
            "latest_entry": db.find_one(sort=[("timestamp", -1)])
        }
        return render_template("summary.html", summary=summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@dashboard_bp.route("/my-models")
@login_required
@role_required(["admin"])
def my_models():
    if 'username' not in session:
        flash("Please login to access this page", "warning")
        return redirect(url_for('auth.login'))

    user = db.users.find_one({"username": session['username']})
    model_names = user.get("models", [])

    return render_template("my_models.html", models=model_names)

@dashboard_bp.route("/predict", methods=["GET", "POST"])
@login_required
@role_required(["admin"])
def predict_form():
    db = get_mongo_client()
    available_models = list(db.trained_models.find())

    if request.method == "POST":
        model_name = request.form.get("model_name")
        input_data = {
            k: float(v) if v else None for k, v in request.form.items() if k != "model_name"
        }

        model_doc = db.trained_models.find_one({"name": model_name})
        if not model_doc:
            flash("Model not found.", "danger")
            return redirect(url_for("dashboard.predict"))

        # Access control: is model paid & does user have plan?
        if model_doc["is_paid"] and session['plan'] != "premium":
            flash("This model requires a premium plan.", "danger")
            return redirect(url_for("dashboard.predict"))

        result = predict_missing_fields(input_data, model_name)
        flash(f"Prediction complete: {result}", "success")
        return render_template("predict.html", available_models=available_models, prediction=result)

    return render_template("dashboard/predict.html", available_models=available_models)


@dashboard_bp.route('/analytics',methods=['GET'])
@login_required
@role_required(["analyst","teacher"])
def analytics():
    return render_template("dashboard/analytics.html")