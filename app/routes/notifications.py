from flask import Blueprint, request, jsonify, session
from app import mongo
from bson import ObjectId

db = mongo.db

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/notifications/subscribe', methods=['POST'])
def subscribe():
    subscription = request.get_json()
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"push_subscription": subscription,"notifications_enabled": True}}
    )
    return jsonify({"message": "Subscribed successfully"}), 200
