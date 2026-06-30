
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import uuid
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from flask import g, jsonify, make_response, request, send_file
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.utils import secure_filename

from config import *
from database import *

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(subject_id: str, role: str = ROLE_MENTEE) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": subject_id, "role": role, "exp": expire},
        SECRET_KEY,
        algorithm="HS256",
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def require_system_super_admin(admin: dict | None):
    from services.admins import admin_is_approved, is_super_admin

    if not admin:
        return (jsonify({"detail": "Chưa đăng nhập"}), 401)
    if not is_super_admin(admin):
        return (jsonify({"detail": "Chỉ super admin hệ thống mới truy cập được"}), 403)
    if not admin_is_approved(admin):
        return (jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403)
    return None


def get_token_from_header() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def get_authenticated_user():
    token = get_token_from_header()
    if not token:
        return None, (jsonify({"detail": "Token không hợp lệ hoặc đã hết hạn"}), 401)

    payload = decode_token(token)
    if not payload:
        return None, (jsonify({"detail": "Token không hợp lệ hoặc đã hết hạn"}), 401)

    if payload.get("role") == ROLE_ADMIN:
        return None, (jsonify({"detail": "Token không hợp lệ hoặc đã hết hạn"}), 401)

    from bson import ObjectId

    user = users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        return None, (jsonify({"detail": "Người dùng không tồn tại"}), 401)

    role = user.get("role") or ROLE_MENTEE
    from auth.users import mentee_is_approved, registration_block_message

    if role == ROLE_MENTEE and not mentee_is_approved(user):
        detail, _flag = registration_block_message(user)
        return None, (jsonify({"detail": detail}), 403)

    return user, None


def require_mentee_account(user: dict):
    if (user.get("role") or ROLE_MENTEE) == ROLE_PARENT:
        return None, (jsonify({"detail": "Phụ huynh không có quyền thực hiện thao tác này"}), 403)
    return user, None


def get_authenticated_admin():
    token = get_token_from_header()
    if not token:
        return None, (jsonify({"detail": "Token admin không hợp lệ hoặc đã hết hạn"}), 401)

    payload = decode_token(token)
    if not payload or payload.get("role") != ROLE_ADMIN:
        return None, (jsonify({"detail": "Token admin không hợp lệ hoặc đã hết hạn"}), 401)

    from bson import ObjectId

    admin = admins.find_one({"_id": ObjectId(payload["sub"])})
    if not admin:
        return None, (jsonify({"detail": "Tài khoản admin không tồn tại"}), 401)

    return admin, None

