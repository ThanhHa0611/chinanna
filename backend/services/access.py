
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


def list_pending_access_requests(admin: dict) -> list:
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


def count_pending_access_requests(admin: dict) -> int:
    total = users.count_documents(pending_mentee_registration_query(admin))
    if is_super_admin(admin):
        total += admins.count_documents(
            {"status": ADMIN_STATUS_PENDING, **access_branch_query(admin)}
        )
    return total


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

