import re
from bson.objectid import ObjectId
from app.models import get_contact_collection

class ContactMessage:
    def __init__(self, data):
        self.id = str(data.get("_id"))
        self.fullname = data.get("fullname")
        self.email = data.get("email")
        self.subject = data.get("subject")
        self.message = data.get("message")

    @staticmethod
    def create(fullname, email, subject, message):
        contacts = get_contact_collection()
        contact_id = contacts.insert_one({
            "fullname": fullname,
            "email": email,
            "subject": subject,
            "message": message
        }).inserted_id
        return str(contact_id)
    
    @staticmethod
    def validate(fullname, email, subject, message):
        errors = {}

        if not fullname.strip():
            errors['fullname'] = "Full name is required."

        if not email.strip():
            errors['email'] = "Email is required."
        else:
            email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if not re.match(email_pattern, email):
                errors['email'] = "Invalid email format."

        if not subject.strip():
            errors['subject'] = "Subject is required."

        if not message.strip():
            errors['message'] = "Message is required."

        return errors
    
    