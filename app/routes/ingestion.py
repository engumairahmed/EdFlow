from flask import Blueprint, flash, render_template, request, jsonify, current_app, redirect, session, url_for
import pandas as pd
from werkzeug.utils import secure_filename
import os
from app.ml.model_utils import save_model
from app.ml.predictors import train_predictor
from app.utils.auth_decorators import login_required
import time
from datetime import datetime
from app import mongo

ingestion_bp = Blueprint("ingestion", __name__)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'csv', 'json'}

db = mongo.db

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@ingestion_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload_file():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == '':
            flash("No file selected.")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file format. Please upload CSV or JSON.")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        try:
            # Read dataset
            if filename.endswith(".csv"):
                df = pd.read_csv(filepath)
            else:
                df = pd.read_json(filepath)

            username = session.get('username')
            timestamp = int(time.time())
            base_name = os.path.splitext(filename)[0]
            unique_model_name = f"{username}_{base_name}_{timestamp}"

            # Drop irrelevant columns if they exist
            df = df.drop(columns=[col for col in ['timestamp', 'location'] if col in df.columns])

            # Train model
            model, accuracy = train_predictor(df, 'temperature')
            save_model(model, unique_model_name)

            # Store model metadata
            model_metadata = {
                "model_name": unique_model_name,
                "accuracy": round(accuracy, 4),
                "dataset": base_name,
                "trained_on": datetime.utcnow().isoformat()
            }

            db['users'].update_one(
                {"username": username},
                {"$addToSet": {"models": model_metadata}}
            )

            flash(f"Uploaded and trained on {file.filename}. Model: {unique_model_name}")
        except Exception as e:
            flash(f"Upload failed: {str(e)}")

        return redirect(url_for("ingestion.upload_file"))

    return render_template("upload.html")