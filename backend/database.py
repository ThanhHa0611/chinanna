
import certifi
from functools import wraps
from flask import jsonify
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config import DATABASE_NAME, MONGODB_URL

_db_initialized = False

client = MongoClient(
    MONGODB_URL,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000,
)
db = client[DATABASE_NAME]
users = db.users
admins = db["Admin"]
mentor_activities = db["Mentor"]
mentor_inbox = db["mentor_inbox"]
feedback_app = db["feedback app"]
password_reset_otps = db["password_reset_otps"]
def ensure_db():
    global _db_initialized
    if not _db_initialized:
        users.create_index("email", unique=True)
        admins.create_index("email", unique=True)
        mentor_activities.create_index([("mentor_name", 1), ("created_at", -1)])
        mentor_activities.create_index([("admin_id", 1), ("created_at", -1)])
        feedback_app.create_index([("user_id", 1), ("created_at", -1)])
        mentor_inbox.create_index([("audience", 1), ("mentor_name", 1), ("created_at", -1)])
        mentor_inbox.create_index("view_token")
        mentor_inbox.create_index("confirm_token")
        mentor_inbox.create_index([("status", 1), ("next_reminder_at", 1)])
        password_reset_otps.create_index([("email", 1), ("account_type", 1)], unique=True)
        password_reset_otps.create_index("expires_at", expireAfterSeconds=0)
        _db_initialized = True

def with_db(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            ensure_db()
            return func(*args, **kwargs)
        except PyMongoError:
            return jsonify({
                "detail": "Không thể kết nối MongoDB. Kiểm tra Network Access trên MongoDB Atlas.",
            }), 503

    return wrapper

