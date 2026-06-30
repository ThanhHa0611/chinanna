
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
from auth.login_tracking import (
    apply_location_fields,
    get_login_context,
    get_request_login_location,
    notify_login_security_event,
    upsert_pending_login_request,
)

def user_response(user: dict) -> dict:
    from services.admins import is_thanh_ha_mentee
    from services.apply_documents import apply_degree_level_label, term3_2027_language_semester_label
    from services.profile_info import profile_info_reminder_unread, serialize_profile_info_reminder

    role = user.get("role") or ROLE_MENTEE
    payload = {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "role": role,
        "full_name": user.get("full_name", ""),
        "date_of_birth": user.get("date_of_birth", ""),
        "mentor": user.get("mentor", ""),
        "apply_clone_email": user.get("apply_clone_email", ""),
        "apply_clone_password": user.get("apply_clone_password", ""),
        "apply_clone_forward_installed": bool(user.get("apply_clone_forward_installed")),
        "scholarship_system": user.get("scholarship_system", ""),
        "parent_email": user.get("parent_email", ""),
        "zalo_phone": user.get("zalo_phone", ""),
        "apply_direction": user.get("apply_direction", ""),
        "apply_degree_level": user.get("apply_degree_level", ""),
        "apply_degree_level_label": apply_degree_level_label(user.get("apply_degree_level", "")),
    }
    if is_thanh_ha_mentee(user):
        payload["term3_2027_language_semester"] = user.get("term3_2027_language_semester", "")
        payload["term3_2027_language_semester_label"] = term3_2027_language_semester_label(
            user.get("term3_2027_language_semester", ""),
        )
    if role == ROLE_PARENT:
        payload["linked_mentee_id"] = str(user.get("linked_mentee_id", ""))
        payload["linked_mentee_name"] = user.get("linked_mentee_name", "")
    if role == ROLE_MENTEE:
        payload["profile_info_reminder"] = serialize_profile_info_reminder(user)
        payload["profile_info_reminder_unread"] = profile_info_reminder_unread(user)
    return payload


def check_login_allowed(user: dict) -> tuple[bool, str]:
    ip, device_id, device_label = get_login_context()
    approved_ips = set(user.get("approved_login_ips") or [])
    approved_devices = set(user.get("approved_login_devices") or [])

    if not user.get("login_ips") and not user.get("login_devices"):
        return True, ""

    if ip in approved_ips and device_id in approved_devices:
        return True, ""

    upsert_pending_login_request(user, ip, device_id, device_label)
    notify_login_security_event(user, ip, device_id, device_label, projected=True)
    return (
        False,
        "Thiết bị hoặc IP mới chưa được mentor duyệt. Vui lòng liên hệ mentor để được cấp quyền đăng nhập.",
    )


def record_successful_login(user: dict) -> None:
    ip, device_id, device_label = get_login_context()
    now = datetime.now(timezone.utc)
    location = get_request_login_location()

    login_ips = list(user.get("login_ips") or [])
    login_devices = list(user.get("login_devices") or [])
    login_events = list(user.get("login_events") or [])
    approved_ips = set(user.get("approved_login_ips") or [])
    approved_devices = set(user.get("approved_login_devices") or [])
    existing_ips = {entry.get("ip") for entry in login_ips}
    existing_devices = {entry.get("device_id") for entry in login_devices}
    new_ip = ip not in existing_ips
    new_device = device_id not in existing_devices
    is_first = not login_ips and not login_devices

    if is_first:
        approved_ips.add(ip)
        approved_devices.add(device_id)

    ip_entry = next((entry for entry in login_ips if entry.get("ip") == ip), None)
    if ip_entry:
        ip_entry["last_seen"] = now
        ip_entry["count"] = ip_entry.get("count", 0) + 1
        apply_location_fields(ip_entry, location, now)
    else:
        ip_entry = {"ip": ip, "first_seen": now, "last_seen": now, "count": 1}
        apply_location_fields(ip_entry, location, now)
        login_ips.append(ip_entry)

    device_entry = next(
        (entry for entry in login_devices if entry.get("device_id") == device_id),
        None,
    )
    if device_entry:
        device_entry["last_seen"] = now
        device_entry["count"] = device_entry.get("count", 0) + 1
        device_entry["last_ip"] = ip
        device_entry["label"] = device_label
        apply_location_fields(device_entry, location, now)
    else:
        device_entry = {
            "device_id": device_id,
            "label": device_label,
            "first_seen": now,
            "last_seen": now,
            "count": 1,
            "last_ip": ip,
        }
        apply_location_fields(device_entry, location, now)
        login_devices.append(device_entry)

    login_events.insert(
        0,
        {
            "at": now,
            "ip": ip,
            "device_id": device_id,
            "device_label": device_label,
            "location_label": location.get("location_label", ""),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
        },
    )
    login_events = login_events[:MAX_LOGIN_EVENTS]

    updates = {
        "login_ips": login_ips,
        "login_devices": login_devices,
        "login_events": login_events,
        "login_unique_ip_count": len(login_ips),
        "login_unique_device_count": len(login_devices),
        "approved_login_ips": sorted(approved_ips),
        "approved_login_devices": sorted(approved_devices),
    }

    users.update_one({"_id": user["_id"]}, {"$set": updates})

    if new_ip or new_device or is_first:
        notify_login_security_event(user, ip, device_id, device_label)


def sync_parent_account(mentee: dict, parent_email: str) -> None:
    from bson import ObjectId

    parent_email = (parent_email or "").strip().lower()
    old_parent_email = (mentee.get("parent_email") or "").strip().lower()

    if old_parent_email and old_parent_email != parent_email:
        old_parent = users.find_one({"email": old_parent_email, "role": ROLE_PARENT})
        if old_parent and old_parent.get("linked_mentee_id") == mentee["_id"]:
            users.update_one(
                {"_id": old_parent["_id"]},
                {"$unset": {"linked_mentee_id": "", "linked_mentee_name": ""}},
            )

    if not parent_email:
        return

    if not EMAIL_REGEX.match(parent_email):
        return

    mentee_name = mentee.get("full_name") or mentee.get("username", "")
    parent_username = f"ph_{mentee.get('username', 'mentee')}"[:40]
    existing_parent = users.find_one({"email": parent_email})

    if existing_parent:
        if existing_parent.get("role") not in (ROLE_PARENT, ROLE_MENTEE, None):
            return
        users.update_one(
            {"_id": existing_parent["_id"]},
            {
                "$set": {
                    "role": ROLE_PARENT,
                    "linked_mentee_id": mentee["_id"],
                    "linked_mentee_name": mentee_name,
                    "full_name": f"Phụ huynh {mentee_name}",
                },
            },
        )
        return

    try:
        from auth.security import hash_password

        users.insert_one(
            {
                "username": parent_username,
                "email": parent_email,
                "password": hash_password(PARENT_DEFAULT_PASSWORD),
                "role": ROLE_PARENT,
                "linked_mentee_id": mentee["_id"],
                "linked_mentee_name": mentee_name,
                "full_name": f"Phụ huynh {mentee_name}",
                "created_at": datetime.now(timezone.utc),
            },
        )
    except DuplicateKeyError:
        users.update_one(
            {"email": parent_email},
            {
                "$set": {
                    "role": ROLE_PARENT,
                    "linked_mentee_id": mentee["_id"],
                    "linked_mentee_name": mentee_name,
                    "full_name": f"Phụ huynh {mentee_name}",
                },
            },
        )


def get_linked_mentee_for_parent(parent: dict):
    from bson import ObjectId

    mentee_id = parent.get("linked_mentee_id")
    if not mentee_id:
        return None, (jsonify({"detail": "Tài khoản phụ huynh chưa liên kết mentee"}), 404)
    try:
        mentee = users.find_one({"_id": ObjectId(mentee_id)})
    except Exception:
        mentee = None
    if not mentee:
        return None, (jsonify({"detail": "Không tìm thấy hồ sơ mentee liên kết"}), 404)
    return mentee, None


def mentee_users_query(extra: dict | None = None) -> dict:
    query = {"role": {"$ne": ROLE_PARENT}}
    if extra:
        query.update(extra)
    return query


def mentee_account_status(user: dict) -> str:
    return (user.get("status") or ADMIN_STATUS_APPROVED).strip().lower()


def mentee_is_approved(user: dict) -> bool:
    return mentee_account_status(user) == ADMIN_STATUS_APPROVED


def approved_mentee_status_filter() -> dict:
    return {
        "$or": [
            {"status": {"$exists": False}},
            {"status": ADMIN_STATUS_APPROVED},
        ]
    }


def registration_block_message(user: dict) -> tuple[str, str | None]:
    mentor = (user.get("mentor") or "").strip()
    team_label = f"team {mentor}" if mentor else "mentor"
    status = mentee_account_status(user)
    if status == ADMIN_STATUS_PENDING:
        return (
            f"Tài khoản đang chờ {team_label} duyệt. Vui lòng đợi mentor phê duyệt trước khi đăng nhập.",
            "registration_pending",
        )
    if status == ADMIN_STATUS_REJECTED:
        return (
            f"Tài khoản đã bị {team_label} từ chối. Liên hệ mentor nếu bạn cần hỗ trợ.",
            "registration_rejected",
        )
    return ("Tài khoản chưa được kích hoạt.", "registration_blocked")


def record_mentee_login(user: dict) -> None:
    record_successful_login(user)

