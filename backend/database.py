
import certifi
from functools import wraps
from flask import jsonify
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError, ServerSelectionTimeoutError

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

def _mongo_error_detail(exc: PyMongoError) -> str:
    msg = str(exc).lower()
    if isinstance(exc, OperationFailure) or "authentication failed" in msg or "bad auth" in msg:
        return (
            "Không thể xác thực MongoDB (sai username/password). "
            "Kiểm tra MONGODB_URL trong backend/.env; mã hóa ký tự đặc biệt trong password (@ → %40, : → %3A, . → %2E)."
        )
    if isinstance(exc, ServerSelectionTimeoutError) or "timed out" in msg:
        return "Không thể kết nối MongoDB (timeout). Kiểm tra Network Access trên MongoDB Atlas."
    if "network" in msg or "connection refused" in msg or "getaddrinfo" in msg:
        return "Không thể kết nối MongoDB (lỗi mạng). Kiểm tra internet và Network Access trên MongoDB Atlas."
    return f"Không thể kết nối MongoDB ({type(exc).__name__})."


def with_db(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            ensure_db()
            return func(*args, **kwargs)
        except PyMongoError as exc:
            return jsonify({"detail": _mongo_error_detail(exc)}), 503

    return wrapper

