from celery import Celery
from flask import Flask, current_app, render_template, request
from flask_mail import Mail
import os

import logging
from logging.handlers import RotatingFileHandler

from app.utils.db import Mongo
from app.utils.dummy_data import create_dummy_data

mail = Mail()
mongo = Mongo()
celery_app = Celery('edflow_tasks')

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    mail.init_app(app)
    mongo.init_app(app)
    celery_app.conf.update(app.config)

    # --- Logging Setup ---
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False 

     # --- Celery Task Context Handling ---
    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            # 'with app.app_context():' sets up the context for the duration of the task.
            with app.app_context():
                return self.run(*args, **kwargs)
    celery_app.Task = ContextTask
    # --- End Celery Task Context Handling ---

    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.mkdir(logs_dir)

    file_handler = RotatingFileHandler(os.path.join(logs_dir, 'edflow_logs.txt'),
                                       maxBytes=10240,
                                       backupCount=10,
                                       encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    app.logger.info('EdFlow application startup')


    with app.app_context():
        db = current_app.db
        if db is None:
            app.logger.critical("MongoDB database object is not available after initialization.")
            raise Exception("MongoDB database object is not available.")

        required_collections = [
            "users", "students", "teachers", "courses", "alerts",
            "feedbacks", "contacts", "otp_codes", "lms_logs"
        ]
        existing_collections = db.list_collection_names()
        for col_name in required_collections:
            if col_name not in existing_collections:
                db.create_collection(col_name)
                app.logger.info(f"Created MongoDB collection: {col_name}")
            else:
                app.logger.debug(f"MongoDB collection '{col_name}' already exists.")

        if "otp_codes" in existing_collections:
            try:
                indexes = list(db.otp_codes.list_indexes())
                if not any(idx['name'] == 'expires_at_1' for idx in indexes):
                    db.otp_codes.create_index("expires_at", expireAfterSeconds=0)
                    app.logger.info("Created TTL index on 'otp_codes.expires_at'")
                else:
                    app.logger.debug("TTL index on 'otp_codes.expires_at' already exists.")
            except Exception as e:
                app.logger.error(f"Failed to ensure TTL index on otp_codes: {e}")

        create_dummy_data(db)
    #-------------------------
    # Importing Blueprints -
    #-------------------------
    from app.routes.home import home_bp
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    # from app.routes.student import student_bp
    # from app.routes.teacher import teacher_bp
    
    from app.routes.interface import interface_bp
    from app.routes.notifications import notifications_bp
    #-------------------------
    # Registering Blueprints -
    #-------------------------
    app.register_blueprint(home_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    # app.register_blueprint(student_bp, url_prefix="/student")
    # app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(interface_bp) 
    app.register_blueprint(notifications_bp)

    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith("/dashboard"):
            return render_template("dashboard/error_404.html"), 404
        else:
            return render_template("Interface/error_404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith("/dashboard"):
            return render_template("dashboard/error_500.html"), 500
        else:
            return render_template("Interface/error_500.html"), 500
        
    return app