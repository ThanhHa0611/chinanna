
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

from extensions import app
from database import with_db
from auth.security import *
from auth.users import *
from auth.login_tracking import *
from auth.validators import *
from services.access import *
from services.admins import *
from services.apply_documents import *
from services.apply_progress import *
from services.feedback import *
from services.files import *
from services.hdnk_nckh import *
from services.inbox import *
from services.notifications import *
from services.utils import *

@app.get("/api/auth/mentor-teams")
def mentor_teams():
    return jsonify({
        "teams": [
            {"value": "Thanh Hà", "label": "Team Mentor Thanh Hà"},
            {"value": "Mai Chi", "label": "Team Mentor Mai Chi"},
        ]
    })


@app.post("/api/auth/register")
@with_db
def register():
    data = request.get_json(silent=True) or {}
    error = validate_register(data)
    if error:
        return jsonify({"detail": error}), 400

    username = data["username"].strip()
    email = data["email"].strip().lower()
    password = data["password"]
    mentor = data["mentor"].strip()
    zalo_phone = normalize_zalo_phone(data.get("zalo_phone", ""))

    username_owner = users.find_one({"username": username})
    if username_owner and username_owner.get("email") != email:
        return jsonify({"detail": "Tên đăng nhập đã tồn tại"}), 400

    existing = users.find_one({"email": email})
    if existing:
        existing_status = mentee_account_status(existing)
        if existing.get("role") == ROLE_PARENT:
            return jsonify({"detail": "Email đã được sử dụng"}), 400
        if existing_status == ADMIN_STATUS_APPROVED:
            return jsonify({"detail": "Email đã được sử dụng"}), 400
        if existing_status == ADMIN_STATUS_PENDING:
            return jsonify({
                "detail": f"Tài khoản đang chờ team {existing.get('mentor', mentor)} duyệt.",
                "registration_pending": True,
            }), 400
        if existing_status != ADMIN_STATUS_REJECTED:
            return jsonify({"detail": "Email đã được sử dụng"}), 400

    location, location_error = parse_login_location(data)
    if location_error:
        return jsonify({"detail": location_error, "location_required": True}), 403

    now = datetime.now(timezone.utc)
    user_fields = {
        "username": username,
        "email": email,
        "password": hash_password(password),
        "role": ROLE_MENTEE,
        "mentor": mentor,
        "status": ADMIN_STATUS_PENDING,
        "requested_at": now,
        "registration_location_label": location.get("location_label", ""),
        "registration_latitude": location.get("latitude"),
        "registration_longitude": location.get("longitude"),
        "zalo_phone": zalo_phone,
        "mentor_visible_password": password,
    }

    if existing and mentee_account_status(existing) == ADMIN_STATUS_REJECTED:
        users.update_one(
            {"_id": existing["_id"]},
            {
                "$set": user_fields,
                "$unset": {
                    "reviewed_at": "",
                    "reviewed_by": "",
                    "rejection_note": "",
                },
            },
        )
        mentee_id = existing["_id"]
        resent = True
    else:
        try:
            result = users.insert_one({**user_fields, "created_at": now})
        except DuplicateKeyError:
            return jsonify({"detail": "Email đã được sử dụng"}), 400
        mentee_id = result.inserted_id
        resent = False

    team_label = f"team {mentor}"
    message = (
        f"Đã gửi yêu cầu đăng ký tới {team_label}. "
        "Mentor sẽ duyệt trước khi bạn có thể đăng nhập."
    )
    if resent:
        message = (
            f"Đã gửi lại yêu cầu đăng ký tới {team_label}. "
            "Mentor sẽ duyệt trước khi bạn có thể đăng nhập."
        )

    _notify_l1_after_registration(mentee_id)

    return jsonify({
        "message": message,
        "status": ADMIN_STATUS_PENDING,
        "mentor": mentor,
        "id": str(mentee_id),
    }), 201


def _notify_l1_after_registration(mentee_id):
    from bson import ObjectId

    from services.mentee_l1_email import notify_l1_mentee_registration

    mentee = users.find_one({"_id": ObjectId(mentee_id)})
    if mentee:
        notify_l1_mentee_registration(mentee)


@app.post("/api/auth/login")
@with_db
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"detail": "Email và mật khẩu là bắt buộc"}), 400

    user = users.find_one({"email": email})
    if not user or not verify_password(password, user["password"]):
        return jsonify({"detail": "Email hoặc mật khẩu không đúng"}), 401

    role = user.get("role") or ROLE_MENTEE
    if role not in (ROLE_MENTEE, ROLE_PARENT):
        return jsonify({"detail": "Email hoặc mật khẩu không đúng"}), 401

    if role == ROLE_MENTEE and not mentee_is_approved(user):
        detail, flag = registration_block_message(user)
        payload = {"detail": detail}
        if flag:
            payload[flag] = True
        return jsonify(payload), 403

    location, location_error = parse_login_location(data)
    if location_error:
        return jsonify({"detail": location_error, "location_required": True}), 403

    set_request_login_location(location)

    allowed, block_message = check_login_allowed(user)
    if not allowed:
        return jsonify({"detail": block_message, "login_blocked": True}), 403

    record_successful_login(user)

    from bson import ObjectId

    fresh_user = users.find_one({"_id": ObjectId(user["_id"])}) or user
    token = create_token(str(fresh_user["_id"]), role)
    return jsonify({
        "access_token": token,
        "token_type": "bearer",
        "user": user_response(fresh_user),
    })


@app.get("/api/auth/me")
@with_db
def get_me():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    return jsonify(user_response(user))


@app.put("/api/auth/profile")
@with_db
def update_profile():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    updates = {}

    if "full_name" in data:
        updates["full_name"] = data["full_name"].strip()

    if "date_of_birth" in data:
        dob = data["date_of_birth"].strip()
        if dob and not re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
            return jsonify({"detail": "Ngày sinh không hợp lệ (YYYY-MM-DD)"}), 400
        updates["date_of_birth"] = dob

    if "mentor" in data:
        mentor = data["mentor"].strip()
        existing_mentor = (user.get("mentor") or "").strip()
        if existing_mentor:
            if mentor and mentor != existing_mentor:
                return jsonify({"detail": "Không thể đổi mentor sau khi đã chọn."}), 400
        elif mentor:
            if mentor not in MENTOR_OPTIONS:
                return jsonify({"detail": "Mentor không hợp lệ"}), 400
            updates["mentor"] = mentor

    if "apply_clone_email" in data:
        clone_email = data["apply_clone_email"].strip().lower()
        if clone_email and not EMAIL_REGEX.match(clone_email):
            return jsonify({"detail": "Email clone không hợp lệ"}), 400
        updates["apply_clone_email"] = clone_email

    if "apply_clone_password" in data:
        updates["apply_clone_password"] = data["apply_clone_password"].strip()

    if "scholarship_system" in data:
        scholarship_system = data["scholarship_system"].strip().lower()
        if scholarship_system and scholarship_system not in SCHOLARSHIP_SYSTEMS:
            return jsonify({"detail": "Hệ học bổng phải là tiếng Anh hoặc tiếng Trung"}), 400
        updates["scholarship_system"] = scholarship_system

    if "parent_email" in data:
        parent_email = data["parent_email"].strip().lower()
        if parent_email and not EMAIL_REGEX.match(parent_email):
            return jsonify({"detail": "Email phụ huynh không hợp lệ"}), 400
        if parent_email == user.get("email", "").lower():
            return jsonify({"detail": "Email phụ huynh phải khác email mentee"}), 400
        if parent_email:
            conflict = users.find_one(
                {
                    "email": parent_email,
                    "_id": {"$ne": user["_id"]},
                    "role": {"$nin": [ROLE_PARENT, None]},
                },
            )
            if conflict and conflict.get("role") == ROLE_MENTEE:
                return jsonify({"detail": "Email phụ huynh đang được dùng bởi mentee khác"}), 400
        updates["parent_email"] = parent_email

    if "zalo_phone" in data:
        zalo_phone = normalize_zalo_phone(data.get("zalo_phone", ""))
        zalo_error = validate_zalo_phone(zalo_phone)
        if zalo_error:
            return jsonify({"detail": zalo_error}), 400
        updates["zalo_phone"] = zalo_phone

    if "apply_direction" in data:
        updates["apply_direction"] = str(data.get("apply_direction") or "").strip()

    if "apply_degree_level" in data:
        degree = normalize_apply_degree_level(data.get("apply_degree_level", ""))
        if data.get("apply_degree_level") and not degree:
            return jsonify({"detail": "Hệ apply phải là đại, thạc hoặc tiến sĩ"}), 400
        updates["apply_degree_level"] = degree

    if "term3_2027_language_semester" in data:
        if not is_thanh_ha_mentee(user):
            return jsonify({"detail": "Mục này chỉ dành cho mentee team Thanh Hà."}), 403
        term_value = normalize_term3_2027_language_semester(data.get("term3_2027_language_semester", ""))
        if data.get("term3_2027_language_semester") and not term_value:
            return jsonify({"detail": "Chọn Có hoặc Không cho kì tiếng 3/2027"}), 400
        updates["term3_2027_language_semester"] = term_value

    if not updates:
        return jsonify({"detail": "Không có dữ liệu để cập nhật"}), 400

    from bson import ObjectId

    users.update_one({"_id": ObjectId(user["_id"])}, {"$set": updates})
    updated = users.find_one({"_id": ObjectId(user["_id"])})
    if "parent_email" in updates:
        sync_parent_account(updated, updates.get("parent_email", ""))
        updated = users.find_one({"_id": ObjectId(user["_id"])})
    if updates:
        changed_labels = []
        label_map = {
            "full_name": "Họ tên",
            "date_of_birth": "Ngày sinh",
            "mentor": "Mentor",
            "apply_clone_email": "Email clone apply",
            "scholarship_system": "App học bổng",
            "parent_email": "Email phụ huynh",
            "zalo_phone": "Số Zalo",
            "apply_direction": "Phương hướng apply",
            "apply_degree_level": "Hệ apply",
            "term3_2027_language_semester": "Kì tiếng 3/2027",
        }
        for key in updates:
            if key in label_map:
                changed_labels.append(label_map[key])
        if changed_labels:
            notify_mentors_mentee_activity(
                updated or user,
                action="profile_update",
                title=f"{updated.get('full_name') or updated.get('username', 'Mentee')} cập nhật hồ sơ",
                description="Mentee cập nhật: " + ", ".join(changed_labels),
            )
    return jsonify(user_response(updated))


@app.patch("/api/auth/password")
@with_db
def change_password():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"detail": "Mật khẩu hiện tại và mật khẩu mới là bắt buộc"}), 400

    if len(new_password) < 6:
        return jsonify({"detail": "Mật khẩu mới phải có ít nhất 6 ký tự"}), 400

    if not verify_password(current_password, user["password"]):
        return jsonify({"detail": "Mật khẩu hiện tại không đúng"}), 400

    from bson import ObjectId

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {
            "password": hash_password(new_password),
            "mentor_visible_password": new_password,
        }},
    )
    return jsonify({"message": "Đổi mật khẩu thành công"})


@app.post("/api/auth/logout")
def logout():
    return jsonify({"message": "Đăng xuất thành công"})


@app.post("/api/auth/forgot-password")
@with_db
def mentee_forgot_password():
    data = request.get_json(silent=True) or {}
    from services.password_reset import ACCOUNT_MENTEE, request_password_reset_otp

    payload, status = request_password_reset_otp(
        email=data.get("email", ""),
        account_type=ACCOUNT_MENTEE,
    )
    return jsonify(payload), status


@app.post("/api/auth/reset-password")
@with_db
def mentee_reset_password():
    data = request.get_json(silent=True) or {}
    from services.password_reset import ACCOUNT_MENTEE, reset_password_with_otp

    payload, status = reset_password_with_otp(
        email=data.get("email", ""),
        otp=data.get("otp", ""),
        new_password=data.get("new_password", ""),
        account_type=ACCOUNT_MENTEE,
    )
    return jsonify(payload), status

