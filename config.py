from datetime import timedelta
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGO_URI = os.getenv("MONGO_URI")
    DB_NAME = os.getenv("DB_NAME")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "secret")
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-flask-secret-key')

    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True

    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('EMAIL_APP_PASS')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER_EMAIL')
    
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY')
    VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY')
    VAPID_CLAIMS = {
    "sub": f"mailto:{MAIL_DEFAULT_SENDER}"
    }

    HDFS_URL = os.getenv("HDFS_URL")
    HDFS_USER = os.getenv("HDFS_USER")