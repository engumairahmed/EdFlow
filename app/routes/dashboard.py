
# app/routes/dashboard.py

from datetime import datetime, timezone
import logging
import os
import numpy as np
import pandas as pd
import subprocess
from config import Config
from flask import Blueprint, json, jsonify, render_template, request, session, redirect, url_for, flash
from app.ml.dataset_manager import TARGET_FEATURE, validate_columns
from app.ml.predictors import predict, predict_missing_fields
from app.ml.trainer import train_all_models_and_save
from app.ml.anomaly_detector import detect_anomalies_from_db, detect_anomalies_from_df, get_insights
from app.utils.auth_decorators import login_required
from app.utils.mongodb_utils import save_dataset_to_mongodb
from app.utils.notifications import send_role_notification
from app.utils.hdfs import hdfs_test, upload_file_to_hdfs_temp
from app.utils.role_required import role_required
from app import mongo
import plotly.express as px

MODEL_DIR = os.path.join(os.getcwd(), "app", "ml", "models")
UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
VAPID_PUBLIC_KEY = Config.VAPID_PUBLIC_KEY

dashboard_bp = Blueprint("dashboard", __name__)

db = mongo.db
saved_charts_collection = db["saved_charts"]

logger = logging.getLogger(__name__)


# ===================================
# DASHBOARD HOME ROUTE
# =================================== 

@dashboard_bp.route("", methods=["GET"], strict_slashes=False)
@login_required
def dashboard_view():
    username = session.get('username')
    role = session.get('role')
    return render_template("dashboard/home.html", username=username, role=role, VAPID_PUBLIC_KEY=VAPID_PUBLIC_KEY)

# ===================================
# DATA UPLOAD & MODEL TRAINING ROUTE
# =================================== 

@dashboard_bp.route("/upload", methods=["GET", "POST"])
@login_required
@role_required(["admin", "analyst"])
def upload_data():
    print('Route accessed')
    if request.method == "POST":
        print('Route accessed by POST')
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
            # flash(f"✅ Model '{model_name}' trained and saved!", "success")
            try:
                send_role_notification(
                    title="📢 New Model Trained",
                    body=f"The model '{model_name}' has been successfully trained.",
                    role="admin",
                    url="/my-models"
                )
                db.alerts.insert_one({
                    "title": "📢 New Model Trained",
                    "body": f"The model '{model_name}' has been successfully trained.",
                    "role": "admin",
                    "created_at": datetime.now(timezone.utc),
                    "created_by": ObjectId(session['user_id'])
                })
            except Exception as e:
                logger.exception("Error sending notifications")
                flash(f"Error: {e}", "danger")

            # return redirect(url_for("dashboard.upload_data"))
            return jsonify({"success": True, "message": f"Model '{model_name}' trained successfully."})

        except Exception as e:
            logger.exception("Error during upload:")
            flash(f"Error processing file: {e}", "danger")

        return redirect(url_for("dashboard.upload_data"))

    return render_template("dashboard/upload.html")

# ===================================
# VIEW AVAILABLE MODELS ROUTE
# =================================== 

@dashboard_bp.route("/my-models")
@login_required
@role_required(["admin", "analyst"])
def my_models():
    user = db.users.find_one({"username": session['username']})
    models_cursor = db.trained_models.find()
    models_list = []
    for model_doc in models_cursor:
        
        if '_id' in model_doc:
            model_doc['_id'] = str(model_doc['_id'])

        if 'details' in model_doc and isinstance(model_doc['details'], list):
            filtered_details = []
            regression_model_added = False
            for detail in model_doc['details']:
                if 'type' in detail:
                    detail['type'] = detail['type'].replace('_', ' ').title()
                if 'model_name' in detail:
                    detail['model_name'] = detail['model_name'].replace('_', ' ').title()
                if 'target' in detail:
                    detail['target'] = detail['target'].replace('_', ' ').title()
                if detail['type'] == 'Classification':
                    filtered_details.append(detail)
                elif detail['type'] == 'Regression' and not regression_model_added:
                    filtered_details.append(detail)
                    regression_model_added = True

            model_doc['details'] = filtered_details
        
        models_list.append(model_doc)
    return render_template("dashboard/my_models.html", models=models_list)

# ===================================
# PREDICTION ROUTE
# =================================== 

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

@dashboard_bp.route('/dataset')
@login_required
def dataset():
    # user = db.users.find_one({"_id": session["user_id"]})
    userId = session["user_id"]
    return render_template("dashboard/dataset.html",user_id=userId)

@dashboard_bp.route('/personal_information')
@login_required
def personal_information():
    user_id = session['user_id']
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})

    if not user:
        flash("User not found", "danger")
        return redirect(url_for('dashboard.update_profile'))

    return render_template('dashboard/personal_information.html', user=user)

@dashboard_bp.route('/change_password')
@login_required
def change_password():
    return render_template('dashboard/change_password.html')


@dashboard_bp.route('/login-history')
@login_required
def login_history():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    logs = mongo.db.login_logs.find({'user_id': user_id}).sort('timestamp', -1)

    formatted_logs = []
    for log in logs:
        dt = log['timestamp']
        formatted_logs.append({
            'date': dt.strftime('%Y-%m-%d'),
            'day': dt.strftime('%A'),
            'time': dt.strftime('%I:%M %p'),
            'username': log.get('username', 'N/A'),
            'role': log.get('role', 'N/A')
        })

    return render_template('dashboard/login_history.html', login_logs=formatted_logs)
   
@dashboard_bp.route('/my_profile')
@login_required
def my_profile():
    user_id = session['user_id']
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})

    if not user:
        flash("User not found", "danger")
        return redirect(url_for('dashboard.update_profile'))

    return render_template('dashboard/my_profile.html', user=user)


@dashboard_bp.route('/all_notifications')
@login_required
def all_notifications():
    notifications=[]

    user_notifications = db.notifications.find({"user_id": ObjectId(session["user_id"])})
    notifications.extend(user_notifications)


    role = session.get("role")
    if role:
        role_alerts = db.alerts.find({"targetEntityType": {"$in": [role]}})
        notifications.extend(role_alerts)
    
    return render_template('dashboard/all_notifications.html', notifications=notifications) 

@dashboard_bp.route('/notification_settings')
@login_required
def notification_settings():
    return render_template('dashboard/notification_settings.html') 

@dashboard_bp.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    if 'role' not in session:
        return redirect(url_for('auth.login'))

    role = session['role']
    user_id = session['user_id']
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        dob = request.form.get('dob')
        gender = request.form.get('gender'),
        address = request.form.get('address')
        phone = request.form.get('phone')

        data = {
            "full_name": full_name,
            "dob": dob,
            "gender": request.form.get('gender'),  
            "address": address,
            "phone": phone,
            "role": role
        }

        if role == 'student':
            data["grade"] = request.form.get('grade')
            data["roll_number"] = request.form.get('roll_number')

        elif role == 'teacher':
            data["department"] = request.form.get('department')
            data["qualification"] = request.form.get('qualification')

        elif role == 'admin':
            data["designation"] = request.form.get('designation')
            data["admin_code"] = request.form.get('admin_code')

        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": data},
            upsert=True 
        )

        flash("Profile updated successfully", "success")
        return redirect(url_for('dashboard.my_profile'))

    return render_template('dashboard/update_profile.html', role=role, user=user)


       
# ===================================
# ANOMALY DETECTION ROUTE
# ===================================

@dashboard_bp.route('/anomaly-results', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'analyst'])
def anomaly_results_view():
    all_files = []
    if os.path.exists(UPLOADS_DIR):
        for f in os.listdir(UPLOADS_DIR):
            if f.endswith('.csv') or f.endswith('.xlsx'):
                all_files.append(f)
        all_files.sort()
    
    anomalous_students = []
    anomaly_insights = {}
    total_students = 0
    selected_file = request.args.get('selected_file')
    results_source = "file"

    if request.method == 'POST':
        if request.form.get('run_db_scan'):
            results_source = "database"
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
                    anomalous_df, anomaly_insights, total_students = detect_anomalies_from_df(selected_file)
                    anomalous_students = anomalous_df.to_dict('records')
                except FileNotFoundError:
                    logger.error(f"Error: The file '{selected_file}' was not found.")
                    flash(f"Error in dashboard: The file '{selected_file}' was not found.", "danger")
                except KeyError as e:
                    logger.error(f"Error: Missing columns in the uploaded file: {e}")
                    flash(f"Error in dashboard: Missing columns in the uploaded file: {e}. Please ensure the file has columns like 'age', 'total_score', or 'attendance'.", "danger")
                except Exception as e:
                    logger.error(f"An unexpected error occurred: {e}", exc_info=True)
                    flash(f"An unexpected Error in dashboard: {e}", "danger")
            else:
                flash("Please select a file or choose to run a database scan.", "warning")



    chart_data = {
                            'student_ids': [],
                            'anomaly_scores': [],
                            'feature_counts': {}
                    }

    if anomalous_students:  # Ensure it's not empty or None
        for student in anomalous_students:
              student_id = student.get('studentID') or student.get('student_id') or "Unknown"
        chart_data['student_ids'].append(student_id)
        chart_data['anomaly_scores'].append(student.get('anomaly_score', 0))

        # Count extreme features only if source is file
        if results_source == "file":
            extreme_features = student.get('extreme_features', {})
            for feature in extreme_features:
                chart_data['feature_counts'][feature] = chart_data['feature_counts'].get(feature, 0) + 1

    return render_template(
    'dashboard/anomaly_results.html',
    all_files=all_files,
    selected_file=selected_file,
    anomalous_students=anomalous_students,
    anomaly_insights=anomaly_insights,
    total_students=total_students,
    results_source=results_source,
    chart_data=chart_data  # Pass chart data to HTML
    )

# ===================================
# ANALYTICS/VISUALIZATION ROUTE
# ===================================
@dashboard_bp.route('/analytics', methods=['GET', 'POST']) 
@login_required
@role_required(["admin", "analyst", "teacher"])
def analytics():
    collections = db.list_collection_names()
    selected_data = {}
    fields = []
    chart_html = None
    form_data = None
    rendered_charts = []

    if request.method == "POST":
        collection_name = request.form.get("collection")
        selected_data["collection"] = collection_name
        collection = db[collection_name]
        sample_doc = collection.find_one()

        if sample_doc:
            fields = [key for key in sample_doc.keys() if key != "_id"]

        # Chart generate logic
        if "x_axis" in request.form and "y_axis" in request.form and "chart_type" in request.form:
            x_axis = request.form["x_axis"]
            y_axis = request.form["y_axis"]
            chart_type = request.form["chart_type"]
            limit = int(request.form.get("limit", 10))
            color = request.form.get("color", "#636EFA")

            data = list(collection.find({}, {"_id": 0}))
            df = pd.DataFrame(data).head(limit)
            
            # Check if columns exist
            if x_axis in df.columns and y_axis in df.columns:
                df = df[[x_axis, y_axis]].dropna()

                # Pie chart validation
                if chart_type == "pie":
                    if not pd.api.types.is_numeric_dtype(df[y_axis]):
                        flash("The Y-axis must be numeric for a pie chart.", "danger")
                        return redirect(url_for("dashboard.analytics"))

                # Generate chart
                fig = None
                if chart_type == "bar":
                    fig = px.bar(df, x=x_axis, y=y_axis, title="Bar Chart", color_discrete_sequence=[color])
                elif chart_type == "line":
                    fig = px.line(df, x=x_axis, y=y_axis, title="Line Chart", color_discrete_sequence=[color])
                elif chart_type == "pie":
                    fig = px.pie(df, names=x_axis, values=y_axis, title="Pie Chart", color_discrete_sequence=[color])
                else:
                    chart_html = "Invalid chart type selected."

                if fig:
                    fig.update_layout(template="plotly_white")  # Important!
                    chart_html = fig.to_html(full_html=False)

                form_data = {
                    "collection": collection_name,
                    "x_axis": x_axis,
                    "y_axis": y_axis,
                    "chart_type": chart_type,
                    "limit": limit,
                    "color": color
                }
            else:
                flash("The selected fields are not found in the data.", "danger")
                return redirect(url_for("dashboard.analytics"))

        # Render saved charts
        saved_charts_collection = db["saved_charts"]
        charts = list(saved_charts_collection.find({"collection": selected_data.get("collection")}))
        for chart in charts:
            try:
                c = db[chart["collection"]]
                d = list(c.find({}, {"_id": 0}))
                df = pd.DataFrame(d).head(chart["limit"])
                df = df[[chart["x_axis"], chart["y_axis"]]].dropna()

                f = None
                if chart["chart_type"] == "bar":
                    f = px.bar(df, x=chart["x_axis"], y=chart["y_axis"], color_discrete_sequence=[chart["color"]])
                elif chart["chart_type"] == "line":
                    f = px.line(df, x=chart["x_axis"], y=chart["y_axis"], color_discrete_sequence=[chart["color"]])
                elif chart["chart_type"] == "pie":
                    f = px.pie(df, names=chart["x_axis"], values=chart["y_axis"], color_discrete_sequence=[chart["color"]])

                if f:
                    f.update_layout(template="plotly_white")
                    rendered_charts.append({
                        "collection": chart["collection"],
                        "x_axis": chart["x_axis"],
                        "y_axis": chart["y_axis"],
                        "chart_type": chart["chart_type"],
                        "limit": chart["limit"],
                        "color": chart["color"],
                        "chart_html": f.to_html(full_html=False)
                    })

            except Exception as e:
                logger.info("Error rendering saved chart:", e)

    return render_template("dashboard/analytics.html",
        collections=collections,
        fields=fields,
        selected_data=selected_data,
        chart=chart_html,
        form_data=form_data,
        saved_charts=rendered_charts
    )
@dashboard_bp.route('/generate_chart', methods=['POST'])
@login_required
@role_required(["admin", "analyst", "teacher"])
def generate_chart():
    try:
        collection_name = request.form["collection"]
        x_axis = request.form["x_axis"]
        y_axis = request.form["y_axis"]
        chart_type = request.form["chart_type"]
        limit = int(request.form["limit"])
        color = request.form["color"]

        chart_data = {
            "collection": collection_name,
            "x_axis": x_axis,
            "y_axis": y_axis,
            "chart_type": chart_type,
            "limit": limit,
            "color": color
        }

        collection = mongo.db[collection_name]
        data = list(collection.find({}, {"_id": 0}))
        df = pd.DataFrame(data).head(limit)
        

        if x_axis in df.columns and y_axis in df.columns:
            df = df[[x_axis, y_axis]].dropna()

            # Pie chart validation
            if chart_type == "pie":
                if not pd.api.types.is_numeric_dtype(df[y_axis]):
                    flash( "Y-axis must be numeric for a pie chart.", "danger")
                    return redirect(url_for("dashboard.analytics"))

            # Generate chart
            fig = None
            if chart_type == "bar":
                fig = px.bar(df, x=x_axis, y=y_axis, color_discrete_sequence=[color])
            elif chart_type == "line":
                fig = px.line(df, x=x_axis, y=y_axis, color_discrete_sequence=[color])
            elif chart_type == "pie":
                fig = px.pie(df, names=x_axis, values=y_axis, color_discrete_sequence=[color])

            if fig:
                fig.update_layout(template="plotly_white")
                chart_html = fig.to_html(full_html=False)
            else:
                chart_html = None

            # Render saved charts
            saved_charts_collection = mongo.db.saved_charts
            charts = list(saved_charts_collection.find({"collection": collection_name}))
            rendered_charts = []

            for chart in charts:
                try:
                    chart["_id"] = str(chart["_id"])
                    c = mongo.db[chart["collection"]]
                    d = list(c.find({}, {"_id": 0}))
                    df = pd.DataFrame(d).head(chart["limit"])
                    df = df[[chart["x_axis"], chart["y_axis"]]].dropna()

                    f = None
                    if chart["chart_type"] == "bar":
                        f = px.bar(df, x=chart["x_axis"], y=chart["y_axis"], color_discrete_sequence=[chart["color"]])
                    elif chart["chart_type"] == "line":
                        f = px.line(df, x=chart["x_axis"], y=chart["y_axis"], color_discrete_sequence=[chart["color"]])
                    elif chart["chart_type"] == "pie":
                        f = px.pie(df, names=chart["x_axis"], values=chart["y_axis"], color_discrete_sequence=[chart["color"]])

                    if f:
                        f.update_layout(template="plotly_white")
                        rendered_charts.append({
                            "_id": chart["_id"],
                            "collection": chart["collection"],
                            "x_axis": chart["x_axis"],
                            "y_axis": chart["y_axis"],
                            "chart_type": chart["chart_type"],
                            "limit": chart["limit"],
                            "color": chart["color"],
                            "chart_html": f.to_html(full_html=False)
                        })

                except Exception as e:
                    logger.info("Error rendering saved chart:", e)

            sample_doc = collection.find_one()
            fields = [key for key in sample_doc.keys() if key != "_id"] if sample_doc else []

            return render_template("dashboard/analytics.html",
                fields=fields,
                selected_data={"collection": collection_name},
                chart=chart_html,
                form_data=chart_data,
                saved_charts=rendered_charts
            )

        else:
            flash( "The fields you selected are not present in the data.", "danger")
            return redirect(url_for("dashboard.analytics"))

    except Exception as e:
        logger.info("Error generating chart:", e)
        flash("The chart could not be generated.", "danger")
        return redirect(url_for("dashboard.analytics"))

@dashboard_bp.route('/save_chart', methods=['POST'])
@login_required
@role_required(["admin", "analyst", "teacher"])
def save_chart():
    try:
        collection = request.form.get("collection")
        x_axis = request.form.get("x_axis")
        y_axis = request.form.get("y_axis")
        chart_type = request.form.get("chart_type")
        limit = request.form.get("limit")
        color = request.form.get("color")

        if not all([collection, x_axis, y_axis, chart_type, limit, color]):
            flash("Some fields are missing. The chart was not saved.", "warning")
            return redirect(url_for("dashboard.analytics"))

        chart_data = {
            "collection": collection,
            "x_axis": x_axis,
            "y_axis": y_axis,
            "chart_type": chart_type,
            "limit": int(limit),
            "color": color
        }

        saved_charts_collection = mongo.db.saved_charts
        saved_charts_collection.insert_one(chart_data)

        logger.info("Chart saved successfully:", chart_data)
        flash("Chart has been saved!", "success")
        return redirect(url_for("dashboard.analytics"))

    except Exception as e:
        logger.info("Error saving chart:", e)
        flash("Chart has not been saved.", "danger")
        return redirect(url_for("dashboard.analytics"))


from bson.objectid import ObjectId
from bson.objectid import ObjectId
@dashboard_bp.route("/delete_chart", methods=["POST"])
@login_required
@role_required(["admin", "analyst", "teacher"])
def delete_chart():
    try:
        collection = request.form.get("collection")
        x_axis = request.form.get("x_axis")
        y_axis = request.form.get("y_axis")
        chart_type = request.form.get("chart_type")

        deleted = saved_charts_collection.delete_one({
            "collection": collection,
            "x_axis": x_axis,
            "y_axis": y_axis,
            "chart_type": chart_type
        })

        if deleted.deleted_count:
            flash("Chart deleted successfully!", "success")
        else:
            flash("Chart not found or already deleted.", "warning")

        return redirect(url_for("dashboard.analytics"))

    except Exception as e:
        flash(f"Error deleting chart: {str(e)}", "danger")
        return redirect(url_for("dashboard.analytics"))

@dashboard_bp.route('/delete-data/',methods=['POST'])
@login_required
@role_required(["admin"])
def delete_data(item_id):
    user_id = item_id
    admin_user=db.users.find_one({
        "_id": ObjectId(user_id),
        "role": "admin"
        })   
    if admin_user is None:
        flash('You are not authorized to delete data.', 'danger')
        return redirect(url_for('dashboard.dataset'))
    try:
        # db.drop_collection('dataset')
        flash('Data deleted successfully.', 'success')
        return redirect(url_for('dashboard.upload_data'))
    except Exception as e:
        flash(f'Error deleting data: {str(e)}', 'danger')
        return redirect(url_for('dashboard.dataset'))

# # ==========================
# # HDFS functions
# # ==========================
@dashboard_bp.route('/upload-data', methods=['GET', 'POST'])
@login_required
@role_required(["admin", "analyst"])
def upload_data_hdfs():
    if request.method == 'POST':
        status=hdfs_test()
        if status['status'] == 'error':
            flash('Failed to connect HDFS please configure HDFS connection', 'error')
            return redirect(url_for('dashboard.upload_data_hdfs'))
        file = request.files.get('dataset')
        if not file or file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if file and file.filename.endswith('.csv'):
            local_filepath = os.path.join(UPLOADS_DIR, file.filename)
            file.save(local_filepath)

            hdfs_temp_path = f'/user/hdfs/temp/{file.filename}'
            hdfs_final_path = f'/user/hdfs/student_data.csv'

            try:
                # Step 1: Upload to HDFS
                upload_file_to_hdfs_temp(local_filepath, hdfs_temp_path)

                # Uncomment below code is spark is installed in local machine or docker 
                # else move spark_deduplication.py file to spark VM

                # Step 2: Trigger Spark Job
                # spark_script_path = os.path.join(os.getcwd(), 'spark_deduplicate.py')
                # spark_submit_command = [
                #     'spark-submit',
                #     '--master', 'local[*]',  # or 'yarn'
                #     spark_script_path,
                #     hdfs_temp_path,
                #     hdfs_final_path
                # ]

                # result = subprocess.run(
                #     spark_submit_command,
                #     check=True,
                #     capture_output=True,
                #     text=True
                # )

                # logger.info(result.stdout)
                logger.info('File uploaded successfully!')
                flash(f'File uploaded successfully!', 'success')
            except Exception as e:
                logger.error(f'Error during Spark processing: {e}')
                flash(f'Error during Spark processing: {e}', 'danger')
            finally:
                if os.path.exists(local_filepath):
                    os.remove(local_filepath)

            return redirect(url_for('dashboard.analytics'))

    return render_template('dashboard/upload-hdfs.html')

@dashboard_bp.route('/contact-queries', methods=['GET', 'POST'])
@login_required
@role_required(["admin", "analyst"])
def contact_queries():
    contacts = list(db.contacts.find())

    total_contacts = len(contacts)
    read_count = db.contacts.count_documents({'is_read': True})
    unread_count = db.contacts.count_documents({'is_read': False})
    unread_percentage = (unread_count / total_contacts) * 100 if total_contacts else 0

    # Get most recent contact (based on creation time)
    last_contact = db.contacts.find_one({}, sort=[('created_at', -1)])
    last_created_at = last_contact.get('created_at').strftime('%Y-%m-%d') if last_contact and last_contact.get('created_at') else None
    return render_template(
        'dashboard/contact-queries.html',
        queries=contacts,
        total_contacts=total_contacts,
        read_count=read_count,
        unread_count=unread_percentage,
        last_created_at=last_created_at
    )
