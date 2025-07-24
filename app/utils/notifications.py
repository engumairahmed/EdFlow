from pywebpush import webpush, WebPushException
from flask import json, jsonify
from app import mongo
from config import Config

VAPID_PRIVATE_KEY = Config.VAPID_PRIVATE_KEY
VAPID_PUBLIC_KEY = Config.VAPID_PUBLIC_KEY

db = mongo.db
subscriptions_collection = db.subscriptions

def notify(title, body, subscriptions):
    payload = {"title": "New Message!", "body": "This is a test notification."}

    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": "mailto:your-email@example.com"
                }
            )
        except WebPushException as ex:
            print(f"WebPush failed: {repr(ex)}")

    return jsonify({'status': 'sent'})

def save_subscription(subscription, user_id):
    """Save browser subscription to MongoDB and link to user."""
    subscription['user_id'] = user_id
    existing = subscriptions_collection.find_one({"endpoint": subscription.get("endpoint")})
    
    if not existing:
        subscriptions_collection.insert_one(subscription)
        db.users.update_one(
            {"_id": user_id},
            {"$set": {"notifications_enabled": True}}
        )
        return True
    return False

def send_notification(title, body):
    """Send a notification to all saved subscriptions."""
    payload = json.dumps({"title": title, "body": body})
    failed = 0
    for sub in subscriptions_collection.find():
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": "mailto:admin@example.com"}
            )
        except WebPushException as e:
            print(f"❌ Failed to push to {sub['endpoint']}: {e}")
            failed += 1
            # Optionally delete expired/invalid subscriptions
            # subscriptions_collection.delete_one({"endpoint": sub["endpoint"]})
    return {"status": "sent", "failed": failed}

def send_notification_by_role(role, title, body):
    """Send push notifications only to users with matching role & enabled."""
    users = list(db.users.find({
        "role": role,
        "notifications_enabled": True
    }))
    
    user_ids = [u["_id"] for u in users]

    subscriptions = list(subscriptions_collection.find({
        "user_id": {"$in": user_ids}
    }))

    payload = json.dumps({"title": title, "body": body})
    failed = 0

    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": "mailto:admin@example.com"}
            )
        except WebPushException as e:
            print(f"❌ Push failed for {sub.get('endpoint')}: {e}")
            failed += 1

    return {"status": "sent", "target_role": role, "failed": failed}


def get_vapid_public_key():
    return VAPID_PUBLIC_KEY