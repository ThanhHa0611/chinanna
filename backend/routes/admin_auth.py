
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

@app.post("/api/admin/auth/login")
@with_db
def admin_login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"detail": "Email và mật khẩu là bắt buộc"}), 400

    admin = admins.find_one({"email": email})
    if not admin or not verify_password(password, admin["password"]):
        return jsonify({"detail": "Email hoặc mật khẩu admin không đúng"}), 401

    if not admin_is_approved(admin):
        status = (admin.get("status") or "").strip().lower()
        if status == ADMIN_STATUS_PENDING:
            return jsonify({
                "detail": f"Tài khoản đang chờ phê duyệt từ super admin ({ADMIN_NOTIFY_EMAIL}).",
            }), 403
        if status == ADMIN_STATUS_REJECTED:
            return jsonify({
                "detail": "Tài khoản đã bị từ chối. Vui lòng đăng ký lại tại trang Đăng ký mới.",
            }), 403
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    location, location_error = parse_login_location(data)
    if location_error:
        return jsonify({"detail": location_error, "location_required": True}), 403
    set_request_login_location(location)
    _record_admin_login_context(admin, location)

    log_mentor_activity(admin, "login", f"{admin.get('email')} đăng nhập hệ thống mentor")

    token = create_token(str(admin["_id"]), ROLE_ADMIN)
    return jsonify({
        "access_token": token,
        "token_type": "bearer",
        "admin": admin_response(admin),
    })


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return r * c


def _location_matches_reference(
    current_location: dict,
    reference_location: dict,
    tolerance_km: float,
) -> bool:
    cur_lat = _safe_float(current_location.get("latitude"))
    cur_lng = _safe_float(current_location.get("longitude"))
    ref_lat = _safe_float(reference_location.get("last_latitude"))
    ref_lng = _safe_float(reference_location.get("last_longitude"))
    if None not in (cur_lat, cur_lng, ref_lat, ref_lng):
        return _haversine_distance_km(cur_lat, cur_lng, ref_lat, ref_lng) <= tolerance_km

    cur_label = (current_location.get("location_label") or "").strip().lower()
    ref_label = (reference_location.get("last_location") or "").strip().lower()
    if cur_label and ref_label:
        return cur_label == ref_label

    return True


def _record_admin_login_context(admin: dict, location: dict) -> None:
    ip, device_id, device_label = get_login_context()
    now = datetime.now(timezone.utc)
    login_ips = list(admin.get("login_ips") or [])
    login_devices = list(admin.get("login_devices") or [])

    ip_entry = next((entry for entry in login_ips if entry.get("ip") == ip), None)
    if ip_entry:
        ip_entry["last_seen"] = now
        ip_entry["count"] = ip_entry.get("count", 0) + 1
    else:
        ip_entry = {"ip": ip, "first_seen": now, "last_seen": now, "count": 1}
        login_ips.append(ip_entry)
    apply_location_fields(ip_entry, location, now)

    device_entry = next(
        (entry for entry in login_devices if entry.get("device_id") == device_id),
        None,
    )
    if device_entry:
        device_entry["last_seen"] = now
        device_entry["count"] = device_entry.get("count", 0) + 1
        device_entry["last_ip"] = ip
        device_entry["label"] = device_label
    else:
        device_entry = {
            "device_id": device_id,
            "label": device_label,
            "first_seen": now,
            "last_seen": now,
            "count": 1,
            "last_ip": ip,
        }
        login_devices.append(device_entry)
    apply_location_fields(device_entry, location, now)

    admins.update_one(
        {"_id": admin["_id"]},
        {
            "$set": {
                "login_ips": login_ips,
                "login_devices": login_devices,
            },
        },
    )


def _trusted_admin_context_matches(admin: dict, location: dict | None) -> bool:
    ip, device_id, _device_label = get_login_context()
    current_location = location or {}
    if not current_location:
        return False

    login_ips = list(admin.get("login_ips") or [])
    login_devices = list(admin.get("login_devices") or [])
    ip_entry = next((entry for entry in login_ips if entry.get("ip") == ip), None)
    device_entry = next((entry for entry in login_devices if entry.get("device_id") == device_id), None)
    if not ip_entry or not device_entry:
        return False

    tolerance_km = _safe_float(os.getenv("TRUSTED_LOGIN_LOCATION_TOLERANCE_KM", "10")) or 10.0
    return _location_matches_reference(current_location, ip_entry, tolerance_km) or _location_matches_reference(
        current_location,
        device_entry,
        tolerance_km,
    )


@app.post("/api/admin/auth/auto-login")
@with_db
def admin_auto_login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"detail": "Email là bắt buộc"}), 400

    location, location_error = parse_login_location(data)
    if location_error:
        return jsonify({"detail": location_error, "location_required": True}), 403
    set_request_login_location(location)

    # Không phân biệt "email không tồn tại" / "chưa duyệt" / "chưa tin cậy" để
    # tránh dò email (account enumeration). Mọi trường hợp không đủ điều kiện
    # auto-login đều trả về cùng một phản hồi chung; người dùng hợp lệ vẫn có
    # thể đăng nhập bằng mật khẩu để nhận thông báo chi tiết.
    untrusted_response = jsonify(
        {
            "detail": "Thiết bị/IP/vị trí chưa khớp với lần đăng nhập trước. Vui lòng đăng nhập bằng mật khẩu.",
        },
    ), 403

    admin = admins.find_one({"email": email})
    if not admin:
        return untrusted_response
    if not admin_is_approved(admin):
        return untrusted_response
    if not _trusted_admin_context_matches(admin, location):
        return untrusted_response

    _record_admin_login_context(admin, location)
    fresh_admin = admins.find_one({"_id": admin["_id"]}) or admin
    token = create_token(str(fresh_admin["_id"]), ROLE_ADMIN)
    return jsonify(
        {
            "access_token": token,
            "token_type": "bearer",
            "admin": admin_response(fresh_admin),
            "auto_login": True,
        },
    )


@app.post("/api/admin/auth/register")
@with_db
def admin_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    full_name = data.get("full_name", "").strip()
    mentor_name = data.get("mentor_name", "").strip()

    if len(username) < 3:
        return jsonify({"detail": "Tên đăng nhập phải có ít nhất 3 ký tự"}), 400
    if not EMAIL_REGEX.match(email):
        return jsonify({"detail": "Email không hợp lệ"}), 400
    if len(password) < 6:
        return jsonify({"detail": "Mật khẩu phải có ít nhất 6 ký tự"}), 400
    if mentor_name not in MENTOR_OPTIONS:
        return jsonify({"detail": "Chọn mentor cấp 1: Thanh Hà hoặc Mai Chi"}), 400

    existing = admins.find_one({"email": email})
    if existing:
        existing_status = (existing.get("status") or "").strip().lower()
        if existing.get("is_super_admin") or existing_status == ADMIN_STATUS_APPROVED:
            return jsonify({"detail": "Email đã được đăng ký"}), 400
        if existing_status not in {ADMIN_STATUS_PENDING, ADMIN_STATUS_REJECTED}:
            return jsonify({"detail": "Email đã được đăng ký"}), 400

    username_owner = admins.find_one({"username": username})
    if username_owner and username_owner.get("email") != email:
        return jsonify({"detail": "Tên đăng nhập đã tồn tại"}), 400

    now = datetime.now(timezone.utc)
    admin_fields = {
        "username": username,
        "password": hash_password(password),
        "full_name": full_name or mentor_name,
        "mentor_name": mentor_name,
        "is_level1_mentor": False,
        "role": ROLE_ADMIN,
        "status": ADMIN_STATUS_PENDING,
        "requested_at": now,
        "is_super_admin": False,
    }
    resent = bool(existing)

    if existing:
        admins.update_one(
            {"_id": existing["_id"]},
            {
                "$set": admin_fields,
                "$unset": {
                    "reviewed_at": "",
                    "reviewed_by": "",
                    "email_action_tokens": "",
                },
            },
        )
        admin_doc = {**existing, **admin_fields, "_id": existing["_id"], "email": email}
    else:
        admin_doc = {**admin_fields, "email": email, "created_at": now}
        try:
            result = admins.insert_one(admin_doc)
        except DuplicateKeyError:
            return jsonify({"detail": "Email đã được đăng ký"}), 400
        admin_doc["_id"] = result.inserted_id

    email_tokens = create_email_action_tokens(admin_doc["_id"])
    action_urls = email_action_urls(email_tokens)

    log_mentor_activity(
        admin_doc,
        "access_request",
        f"{'Gửi lại' if resent else 'Yêu cầu'} cấp quyền admin: {email} — Mentor {mentor_name}",
    )

    super_admin = admins.find_one({"email": ADMIN_NOTIFY_EMAIL}) or admins.find_one(
        {"email": {"$in": SUPER_ADMIN_EMAILS}}
    ) or {"email": ADMIN_NOTIFY_EMAIL, "mentor_name": ""}
    log_mentor_activity(
        super_admin if super_admin.get("_id") else admin_doc,
        "access_request_notify",
        f"Cần phê duyệt tài khoản {email} (Mentor {mentor_name}) — gửi tới {ADMIN_NOTIFY_EMAIL}",
        target_email=email,
    )

    email_sent = False
    try:
        from email_notify import send_admin_access_request_email

        email_sent = send_admin_access_request_email(
            applicant_email=email,
            applicant_username=username,
            applicant_name=full_name or mentor_name,
            mentor_name=mentor_name,
            requested_at=now.strftime("%d/%m/%Y %H:%M UTC"),
            approve_url=action_urls["approve"],
            reject_url=action_urls["reject"],
            admin_page_url=action_urls["admin_page"],
        )
    except Exception:
        pass

    message = (
        f"Đã {'gửi lại' if resent else 'gửi'} yêu cầu cấp quyền. "
        f"Vui lòng chờ super admin ({ADMIN_NOTIFY_EMAIL}) phê duyệt."
    )
    if email_sent:
        message += f" Đã gửi email thông báo tới {ADMIN_NOTIFY_EMAIL}."
    else:
        message += (
            f" Super admin có thể duyệt tại http://localhost:5174/access-requests "
            f"(cấu hình SMTP trong backend/.env để tự gửi email)."
        )

    return jsonify({"message": message, "email_sent": email_sent}), 201


@app.get("/api/admin/auth/me")
@with_db
def admin_me():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    return jsonify(admin_response(admin))


@app.post("/api/admin/auth/logout")
def admin_logout():
    return jsonify({"message": "Đăng xuất admin thành công"})


@app.patch("/api/admin/auth/password")
@with_db
def admin_change_password():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"detail": "Mật khẩu hiện tại và mật khẩu mới là bắt buộc"}), 400

    if len(new_password) < 6:
        return jsonify({"detail": "Mật khẩu mới phải có ít nhất 6 ký tự"}), 400

    if not verify_password(current_password, admin["password"]):
        return jsonify({"detail": "Mật khẩu hiện tại không đúng"}), 400

    from bson import ObjectId

    admins.update_one(
        {"_id": ObjectId(admin["_id"])},
        {"$set": {"password": hash_password(new_password)}},
    )
    return jsonify({"message": "Đổi mật khẩu thành công"})


@app.post("/api/admin/auth/forgot-password")
@with_db
def admin_forgot_password():
    data = request.get_json(silent=True) or {}
    from services.password_reset import ACCOUNT_MENTOR, request_password_reset_otp

    payload, status = request_password_reset_otp(
        email=data.get("email", ""),
        account_type=ACCOUNT_MENTOR,
    )
    return jsonify(payload), status


@app.post("/api/admin/auth/reset-password")
@with_db
def admin_reset_password():
    data = request.get_json(silent=True) or {}
    from services.password_reset import ACCOUNT_MENTOR, reset_password_with_otp

    payload, status = reset_password_with_otp(
        email=data.get("email", ""),
        otp=data.get("otp", ""),
        new_password=data.get("new_password", ""),
        account_type=ACCOUNT_MENTOR,
    )
    return jsonify(payload), status

