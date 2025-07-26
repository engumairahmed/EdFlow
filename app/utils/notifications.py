import json
from pywebpush import webpush, WebPushException
from app import mongo
from bson import ObjectId
from config import Config

VAPID_PRIVATE_KEY=Config.VAPID_PRIVATE_KEY
VAPID_CLAIMS=Config.VAPID_CLAIMS

db = mongo.db

def send_push(subscription_info, payload):
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS
        )
    except WebPushException as ex:
        print(f"Push failed: {ex}")

def send_role_notification(title, body, role, url):

    users = db.users.find({"role": role, "notifications_enabled": True, "push_subscription": {"$exists": True}})
    payload = {"title": title, "body": body, "url": url}
    print(users)
    for user in users:
        # Insert into notifications collection
        db.notifications.insert_one({
            "user_id": user["_id"],
            "title": title,
            "body": body,
            "url": url
        })
        # Send web push
        send_push(user["push_subscription"], payload)
