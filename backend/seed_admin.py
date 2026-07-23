"""Tạo / cập nhật tài khoản super admin trong collection Admin."""

import os
from datetime import datetime, timezone

import bcrypt
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "phong_van")

SUPER_ADMIN_ACCOUNTS = [
    {
        "email": os.getenv("ADMIN_SEED_EMAIL", "cherrythanh06@gmail.com").strip().lower(),
        "password": os.getenv("ADMIN_SEED_PASSWORD", "admin123456"),
        "full_name": os.getenv("ADMIN_SEED_NAME", "Thanh Hà"),
        "username": os.getenv("ADMIN_SEED_USERNAME", "mentor_ha"),
        "mentor_name": "Thanh Hà",
    },
]

DISABLED_SYSTEM_EMAILS = {
    email.strip().lower()
    for email in os.getenv(
        "DISABLED_SYSTEM_EMAILS",
        "mochisjtu@gmail.com",
    ).split(",")
    if email.strip()
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def upsert_super_admin(admins, account: dict):
    email = account["email"]
    existing = admins.find_one({"email": email})
    fields = {
        "status": "approved",
        "is_super_admin": True,
        "is_level1_mentor": True,
        "mentor_name": account["mentor_name"],
        "full_name": account["full_name"],
        "role": "admin",
    }

    if existing:
        admins.update_one({"_id": existing["_id"]}, {"$set": fields})
        print(f"[seed_admin] Da cap nhat super admin: {email}")
        return

    admins.insert_one({
        "username": account["username"],
        "email": email,
        "password": hash_password(account["password"]),
        "full_name": account["full_name"],
        "mentor_name": account["mentor_name"],
        "role": "admin",
        "status": "approved",
        "is_super_admin": True,
        "is_level1_mentor": True,
        "created_at": datetime.now(timezone.utc),
    })
    print(f"[seed_admin] Da tao super admin: {email}")


def disable_system_emails(admins_col, users_col):
    if not DISABLED_SYSTEM_EMAILS:
        return
    admin_result = admins_col.update_many(
        {"email": {"$in": list(DISABLED_SYSTEM_EMAILS)}},
        {
            "$set": {
                "status": "rejected",
                "is_super_admin": False,
                "is_level1_mentor": False,
                "system_disabled": True,
            }
        },
    )
    user_result = users_col.update_many(
        {"email": {"$in": list(DISABLED_SYSTEM_EMAILS)}},
        {"$set": {"system_disabled": True, "login_request_status": "rejected"}},
    )
    print(
        f"[seed_admin] Da ngat {admin_result.modified_count} admin + "
        f"{user_result.modified_count} user: {', '.join(sorted(DISABLED_SYSTEM_EMAILS))}"
    )


def main():
    if not MONGODB_URL:
        print("[seed_admin] Bo qua: chua cau hinh MONGODB_URL")
        return

    client = MongoClient(MONGODB_URL, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000)
    admins = client[DATABASE_NAME]["Admin"]
    users = client[DATABASE_NAME]["users"]
    admins.create_index("email", unique=True)

    seen = set()
    for account in SUPER_ADMIN_ACCOUNTS:
        email = account["email"]
        if email in seen:
            continue
        if email in DISABLED_SYSTEM_EMAILS:
            print(f"[seed_admin] Bo qua seed super admin bi ngat: {email}")
            continue
        seen.add(email)
        upsert_super_admin(admins, account)

    disable_system_emails(admins, users)


if __name__ == "__main__":
    main()
