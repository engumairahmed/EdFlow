from flask import Flask
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from app.utils.db import Mongo, get_database

jwt = JWTManager()
mail = Mail()
mongo = Mongo()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    with app.app_context():
        db = get_database()
        if db is None:
            raise Exception("MongoDB connection failed.")

        if "users" not in db.list_collection_names():
            db.create_collection("users")

    jwt.init_app(app)
    mail.init_app(app)
    mongo.init_app(app)
    
    print(mongo.db)

    from app.routes.home import home_bp
    from app.routes.auth import auth_bp
    from app.routes.ingestion import ingestion_bp
    from app.routes.dashboard import dashboard_bp
    # from app.routes.student import student_bp
    # from app.routes.teacher import teacher_bp
    
    from app.routes.interface import interface_bp


    app.register_blueprint(home_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(ingestion_bp, url_prefix="/ingest")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    # app.register_blueprint(student_bp, url_prefix="/student")
    # app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(interface_bp) 


    return app
