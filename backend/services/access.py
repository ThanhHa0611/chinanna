
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

from auth.security import *
from auth.users import *
from auth.login_tracking import *
from auth.validators import *
from services.admins import *
from services.apply_documents import *
from services.apply_progress import *
from services.feedback import *
from services.files import *
from services.hdnk_nckh import *
from services.inbox import *
from services.notifications import *
from services.utils import *

def apply_access_review(target: dict, reviewer: dict, decision: str):
    from bson import ObjectId

    now = datetime.now(timezone.utc)
    admins.update_one(
        {"_id": target["_id"]},
        {
            "$set": {
                "status": decision,
                "reviewed_at": now,
                "reviewed_by": str(reviewer["_id"]),
            },
            "$unset": {"email_action_tokens": ""},
        },
    )

    verb = "phê duyệt" if decision == ADMIN_STATUS_APPROVED else "từ chối"
    log_mentor_activity(
        reviewer,
        "access_review",
        f"{reviewer.get('email')} đã {verb} quyền admin cho {target.get('email')}",
        target_admin_id=str(target["_id"]),
    )
    log_mentor_activity(
        target,
        "access_review_result",
        f"Tài khoản {target.get('email')} đã được {verb}",
    )
    return verb


def handle_email_admin_access_action(action_key: str, decision: str):
    from flask import request

    from services.inbox import email_action_urls, render_email_action_page

    token = (request.args.get("token") or "").strip()
    if not token:
        return render_email_action_page(
            title="Link không hợp lệ",
            message="Thiếu mã xác thực trong link.",
            success=False,
        )

    target = admins.find_one({f"email_action_tokens.{action_key}": token})
    if not target:
        return render_email_action_page(
            title="Link không hợp lệ",
            message="Link đã hết hạn hoặc không tồn tại.",
            success=False,
        )

    tokens = target.get("email_action_tokens") or {}
    expires_at = tokens.get("expires_at")
    if expires_at:
        if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return render_email_action_page(
                title="Link đã hết hạn",
                message="Vui lòng duyệt trực tiếp trên app mentor.",
                success=False,
            )

    if target.get("status") != ADMIN_STATUS_PENDING:
        return render_email_action_page(
            title="Đã xử lý trước đó",
            message=f"Tài khoản {target.get('email', '')} đã được xử lý.",
            success=True,
        )

    reviewer = admins.find_one({"email": ADMIN_NOTIFY_EMAIL}) or admins.find_one(
        {"email": {"$in": SUPER_ADMIN_EMAILS}}
    )
    if not reviewer:
        reviewer = {"email": ADMIN_NOTIFY_EMAIL, "mentor_name": ""}

    verb = apply_access_review(target, reviewer, decision)
    urls = email_action_urls(tokens)
    return render_email_action_page(
        title="Đã xử lý yêu cầu mentor",
        message=(
            f"Đã <strong>{verb}</strong> tài khoản mentor "
            f"<strong>{target.get('email', '')}</strong>. "
            f'Bạn có thể <a href="{urls.get("admin_page", "")}" style="color:#eb2233;font-weight:600;">mở app mentor</a>.'
        ),
        success=True,
    )


def mentee_admin_list_query(admin: dict) -> dict:
    query = mentee_users_query(mentee_filter_for_admin(admin))
    query.update(approved_mentee_status_filter())
    return query


def pending_mentee_registration_query(admin: dict) -> dict:
    query = {
        "role": ROLE_MENTEE,
        "status": ADMIN_STATUS_PENDING,
    }
    branch = activity_branch_for_admin(admin)
    if branch:
        query["mentor"] = branch
    return query


def admin_can_review_mentee_registration(admin: dict, mentee: dict) -> bool:
    if not admin_is_approved(admin):
        return False
    if (mentee.get("role") or ROLE_MENTEE) != ROLE_MENTEE:
        return False
    if mentee_account_status(mentee) != ADMIN_STATUS_PENDING:
        return False
    branch = activity_branch_for_admin(admin)
    if not branch:
        return is_super_admin(admin)
    return (mentee.get("mentor") or "").strip() == branch


def serialize_pending_mentee_registration(user: dict) -> dict:
    requested_at = user.get("requested_at")
    return {
        "id": str(user["_id"]),
        "username": user.get("username", ""),
        "email": user.get("email", ""),
        "mentor": user.get("mentor", ""),
        "requested_at": requested_at.isoformat() if hasattr(requested_at, "isoformat") else requested_at or "",
        "registration_location_label": user.get("registration_location_label", ""),
        "zalo_phone": user.get("zalo_phone", ""),
    }


def serialize_unified_access_request_mentor(doc: dict) -> dict:
    return {
        **serialize_access_admin(doc),
        "request_type": "mentor",
        "role_label": "Mentor",
        "team": doc.get("mentor_name", ""),
    }


def serialize_unified_access_request_mentee(doc: dict) -> dict:
    base = serialize_pending_mentee_registration(doc)
    return {
        **base,
        "request_type": "mentee",
        "role_label": "Mentee",
        "team": base.get("mentor", ""),
        "full_name": doc.get("full_name", ""),
    }


def resolve_login_request_subject(account_user: dict) -> tuple[dict | None, dict]:
    if account_user.get("role") == ROLE_PARENT:
        from bson import ObjectId

        mentee_id = account_user.get("linked_mentee_id")
        if not mentee_id:
            return None, account_user
        try:
            mentee = users.find_one({"_id": ObjectId(mentee_id)})
        except Exception:
            mentee = None
        return mentee, account_user
    return account_user, account_user


def admin_can_review_mentee_login_request(
    admin: dict,
    account_user: dict,
    subject_mentee: dict,
) -> bool:
    if not admin_is_approved(admin):
        return False
    if not mentee_is_approved(subject_mentee):
        return False
    mentor_filter = mentee_filter_for_admin(admin)
    if mentor_filter and subject_mentee.get("mentor") != mentor_filter.get("mentor"):
        return False
    return True


def serialize_unified_access_request_mentee_login(
    account_user: dict,
    pending_entry: dict,
    subject_mentee: dict,
) -> dict:
    def fmt_dt(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value or ""

    old_info = get_primary_known_ip_info(account_user)
    old_device_raw = get_primary_known_device_label(account_user)
    new_device_raw = pending_entry.get("device_label", "")
    requested_at = pending_entry.get("requested_at")
    is_parent = account_user.get("role") == ROLE_PARENT
    mentee_name = subject_mentee.get("full_name") or subject_mentee.get("username", "")

    return {
        "id": pending_entry.get("id", ""),
        "user_id": str(account_user["_id"]),
        "request_type": "mentee_login_ip",
        "role_label": "Phụ huynh" if is_parent else "Đăng nhập",
        "mentee_name": mentee_name,
        "full_name": (account_user.get("full_name") or mentee_name)
        if not is_parent
        else (account_user.get("full_name") or "Phụ huynh"),
        "email": account_user.get("email", ""),
        "username": account_user.get("username", ""),
        "team": subject_mentee.get("mentor", ""),
        "requested_at": fmt_dt(requested_at),
        "old_ip": old_info.get("ip", ""),
        "old_location_label": old_info.get("location_label", ""),
        "new_ip": pending_entry.get("ip", ""),
        "new_location_label": format_location_label(
            location_label=pending_entry.get("location_label", ""),
            latitude=pending_entry.get("latitude"),
            longitude=pending_entry.get("longitude"),
        ),
        "old_device_label": short_device_label(old_device_raw),
        "new_device_label": short_device_label(new_device_raw),
        "zalo_phone": subject_mentee.get("zalo_phone", ""),
    }


def iter_users_with_pending_login_requests(admin: dict):
    base_match = {"pending_login_requests": {"$elemMatch": {"status": LOGIN_REQUEST_PENDING}}}
    branch = activity_branch_for_admin(admin)

    mentee_query = mentee_users_query()
    mentee_query.update(base_match)
    mentee_query.update(approved_mentee_status_filter())
    if branch:
        mentee_query["mentor"] = branch

    for doc in users.find(mentee_query):
        yield doc

    parent_query = {**base_match, "role": ROLE_PARENT}
    for parent in users.find(parent_query):
        subject_mentee, _ = resolve_login_request_subject(parent)
        if not subject_mentee or not mentee_is_approved(subject_mentee):
            continue
        if branch and subject_mentee.get("mentor") != branch:
            continue
        yield parent


def append_pending_mentee_login_access_requests(admin: dict, items: list) -> None:
    for account_user in iter_users_with_pending_login_requests(admin):
        subject_mentee, _ = resolve_login_request_subject(account_user)
        if not subject_mentee:
            continue
        for entry in account_user.get("pending_login_requests") or []:
            if entry.get("status") != LOGIN_REQUEST_PENDING:
                continue
            items.append(
                serialize_unified_access_request_mentee_login(
                    account_user,
                    entry,
                    subject_mentee,
                ),
            )


def count_pending_mentee_login_requests(admin: dict) -> int:
    total = 0
    for account_user in iter_users_with_pending_login_requests(admin):
        total += count_pending_login_requests(account_user)
    return total


def list_pending_registration_requests(admin: dict) -> list:
    items: list[dict] = []
    if is_super_admin(admin):
        mentor_query = {"status": ADMIN_STATUS_PENDING, **access_branch_query(admin)}
        for doc in admins.find(mentor_query).sort("requested_at", -1):
            items.append(serialize_unified_access_request_mentor(doc))

    mentee_query = pending_mentee_registration_query(admin)
    for doc in users.find(mentee_query).sort("requested_at", -1):
        items.append(serialize_unified_access_request_mentee(doc))

    items.sort(key=lambda item: item.get("requested_at") or "", reverse=True)
    return items


def list_pending_login_ip_requests(admin: dict) -> list:
    items: list[dict] = []
    append_pending_mentee_login_access_requests(admin, items)
    items.sort(key=lambda item: item.get("requested_at") or "", reverse=True)
    return items


def list_pending_access_requests(admin: dict) -> list:
    items = list_pending_registration_requests(admin)
    append_pending_mentee_login_access_requests(admin, items)
    items.sort(key=lambda item: item.get("requested_at") or "", reverse=True)
    return items


def count_pending_registration_requests(admin: dict) -> int:
    total = users.count_documents(pending_mentee_registration_query(admin))
    if is_super_admin(admin):
        total += admins.count_documents(
            {"status": ADMIN_STATUS_PENDING, **access_branch_query(admin)}
        )
    return total


def count_pending_access_requests(admin: dict) -> int:
    return count_pending_registration_requests(admin) + count_pending_mentee_login_requests(admin)


def apply_mentee_login_ip_review(admin: dict, user_id: str, request_id: str, data: dict):
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        user_oid = ObjectId(user_id)
    except InvalidId:
        return jsonify({"detail": "Tài khoản không hợp lệ"}), 400

    target_user = users.find_one({"_id": user_oid})
    if not target_user:
        return jsonify({"detail": "Tài khoản không tồn tại"}), 404

    subject_mentee, _ = resolve_login_request_subject(target_user)
    if not subject_mentee:
        return jsonify({"detail": "Không tìm thấy mentee liên kết"}), 404

    if not admin_can_review_mentee_login_request(admin, target_user, subject_mentee):
        return jsonify({"detail": "Không có quyền duyệt yêu cầu này"}), 403

    decision = (data.get("status") or "").strip().lower()
    if decision not in {ADMIN_STATUS_APPROVED, ADMIN_STATUS_REJECTED}:
        return jsonify({"detail": "Trạng thái phê duyệt không hợp lệ"}), 400

    pending = list(target_user.get("pending_login_requests") or [])
    matched = next(
        (
            entry
            for entry in pending
            if entry.get("id") == request_id and entry.get("status") == LOGIN_REQUEST_PENDING
        ),
        None,
    )
    if not matched:
        return jsonify({"detail": "Yêu cầu đăng nhập không tồn tại hoặc đã xử lý"}), 404

    now = datetime.now(timezone.utc)
    update_fields: dict = {"pending_login_requests": pending}

    if decision == ADMIN_STATUS_APPROVED:
        matched["status"] = LOGIN_REQUEST_APPROVED
        matched["approved_at"] = now
        matched["approved_by"] = str(admin["_id"])
        approved_ips = set(target_user.get("approved_login_ips") or [])
        approved_devices = set(target_user.get("approved_login_devices") or [])
        approved_ips.add(matched.get("ip", ""))
        approved_devices.add(matched.get("device_id", ""))
        update_fields["approved_login_ips"] = sorted(filter(None, approved_ips))
        update_fields["approved_login_devices"] = sorted(filter(None, approved_devices))
        verb = "duyệt"
        action = "login_approve"
    else:
        matched["status"] = LOGIN_REQUEST_REJECTED
        matched["rejected_at"] = now
        matched["rejected_by"] = str(admin["_id"])
        verb = "từ chối"
        action = "login_reject"

    still_pending = any(entry.get("status") == LOGIN_REQUEST_PENDING for entry in pending)
    update_fields["pending_login_unread"] = still_pending
    users.update_one({"_id": user_oid}, {"$set": update_fields})

    account_label = "phụ huynh" if target_user.get("role") == ROLE_PARENT else "mentee"
    log_mentor_activity(
        admin,
        action,
        f"{admin.get('email')} đã {verb} đăng nhập {account_label} "
        f"{target_user.get('email', user_id)} (IP {matched.get('ip', '')})",
        mentee_id=str(subject_mentee["_id"]),
    )
    if is_l2_mentor_admin(admin):
        push_l2_mentor_activity(
            str(subject_mentee["_id"]),
            admin,
            "device",
            action,
            f"{verb.capitalize()} đăng nhập {account_label} (IP {matched.get('ip', '') or '—'})",
        )

    return jsonify(
        {
            "message": f"Đã {verb} đăng nhập {account_label} (IP {matched.get('ip', '')})",
            "status": decision,
        },
    )


def apply_mentee_registration_review(admin: dict, mentee_id: str, data: dict):
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        mentee_oid = ObjectId(mentee_id)
    except InvalidId:
        return jsonify({"detail": "Yêu cầu không tồn tại"}), 404

    mentee = users.find_one({"_id": mentee_oid})
    if not mentee:
        return jsonify({"detail": "Yêu cầu không tồn tại"}), 404

    if not admin_can_review_mentee_registration(admin, mentee):
        return jsonify({"detail": "Không có quyền phê duyệt yêu cầu này"}), 403

    decision = (data.get("status") or "").strip().lower()
    if decision not in {ADMIN_STATUS_APPROVED, ADMIN_STATUS_REJECTED}:
        return jsonify({"detail": "Trạng thái phê duyệt không hợp lệ"}), 400

    if mentee_account_status(mentee) != ADMIN_STATUS_PENDING:
        return jsonify({"detail": "Yêu cầu này đã được xử lý trước đó"}), 400

    now = datetime.now(timezone.utc)
    update_fields = {
        "status": decision,
        "reviewed_at": now,
        "reviewed_by": str(admin["_id"]),
    }
    if decision == ADMIN_STATUS_REJECTED:
        note = (data.get("note") or "").strip()
        if note:
            update_fields["rejection_note"] = note

    users.update_one({"_id": mentee_oid}, {"$set": update_fields})

    verb = "duyệt" if decision == ADMIN_STATUS_APPROVED else "từ chối"
    mentor_label = (mentee.get("mentor") or "").strip()
    log_mentor_activity(
        admin,
        "mentee_registration_review",
        f"{admin.get('email')} đã {verb} đăng ký mentee {mentee.get('email')} ({mentor_label})",
        target_user_id=str(mentee_oid),
    )

    return jsonify({
        "message": f"Đã {verb} đăng ký mentee {mentee.get('email')}",
        "status": decision,
    })

