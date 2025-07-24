import re
from app.models import get_feedbacks_collection

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app

class Feedback:
    def __init__(self, data):
        self.id = str(data.get('_id'))
        self.name = data.get('name')
        self.email = data.get('email')
        self.message = data.get('message')
        self.rating = data.get('rating')

    @staticmethod
    def create_feedback(name, email, message, rating):
        feedbacks = get_feedbacks_collection()

       
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps(email, salt='feedback-verify')

        feedback_id = feedbacks.insert_one({
            "name": name,
            "email": email,
            "message": message,
            "rating": int(rating),
            "verified": False, 
            "verify_token": token
        }).inserted_id

        return str(feedback_id), token
    
    @staticmethod
    def verify_feedback(token):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt='feedback-verify', max_age=3600)
        except:
            return False

        feedbacks = get_feedbacks_collection()
        result = feedbacks.update_one(
            {"email": email, "verified": False},
            {"$set": {"verified": True}}
        )
        return result.modified_count > 0
    @staticmethod
    def validate(name, email, message, rating):
        errors = {}

        if not name.strip():
            errors['name'] = "Name is required."

        if not email.strip():
            errors['email'] = "Email is required."
        else:
            email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if not re.match(email_pattern, email):
                errors['email'] = "Invalid email format."

        if not message.strip():
            errors['message'] = "Message is required."
        
        if not rating or int(rating) < 1 or int(rating) > 5:
         errors['rating'] = "Please select a rating."

        return errors

    @staticmethod
    def get_all_feedbacks(limit=None):
     feedbacks = get_feedbacks_collection()
     result = feedbacks.find().sort('_id', -1)
     if limit:
        result = result.limit(limit)
     return [Feedback(f) for f in result]
 