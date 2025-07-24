from flask import Blueprint, request, jsonify, session
from app.utils import notifications
from app import mongo

db = mongo.db
notifications_bp = Blueprint("notifications", __name__)

@notifications_bp.route("/subscribe", methods=["POST"])
def subscribe():
    data = request.get_json()
    saved = notifications.save_subscription(data)
    return jsonify({"status": "saved" if saved else "already exists"})

@notifications_bp.route("/notify", methods=["POST"])
def notify():
    data = request.get_json()
    title = data.get("title", "No Title")
    body = data.get("body", "No Body")
    result = notifications.send_notification(title, body)
    return jsonify(result)

@notifications_bp.route("/vapid-key", methods=["GET"])
def get_public_key():
    return jsonify({"key": notifications.get_vapid_public_key()})

@notifications_bp.route("/api/user/notifications", methods=["POST"])
def update_user_notifications():
    data = request.get_json()
    enabled = data.get("enabled", True)
    user_id = session.get("user_id")  # Or however you track users

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"notifications_enabled": enabled}}
    )
    return jsonify({"status": "updated", "enabled": enabled})