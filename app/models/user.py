# MongoDB schema (for reference, not enforced unless using ODM like MongoEngine)

# user_schema = {
#     "username": "string",
#     "password": "hashed string",
#     "role": "string"  # Either 'admin' or 'analyst'
# }

from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from app.models import get_users_collection

class User:
    def __init__(self, data):
        self.id = str(data.get("_id"))
        self.username = data.get("username")
        self.email = data.get("email")
        self.password_hash = data.get("password")
        self.role = data.get("role", "analyst")

    @staticmethod
    def create_user(username, email, password, role="analyst"):
        users = get_users_collection()
        if users.find_one({"email": email}):
            return None  # User already exists
        hashed_password = generate_password_hash(password)
        user_id = users.insert_one({
            "username": username,
            "email": email,
            "password": hashed_password,
            "role": role
        }).inserted_id
        return str(user_id)

    @staticmethod
    def find_by_email(email):
        users = get_users_collection()
        user_data = users.find_one({"email": email})
        return User(user_data) if user_data else None

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
