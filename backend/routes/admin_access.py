
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

@app.post("/api/admin/users/<user_id>/login-requests/<request_id>/approve")
@with_db
def admin_approve_login_request(user_id: str, request_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    from bson import ObjectId

    try:
        user_oid = ObjectId(user_id)
    except Exception:
        return jsonify({"detail": "Tài khoản không hợp lệ"}), 400

    target_user = users.find_one({"_id": user_oid})
    if not target_user:
        return jsonify({"detail": "Tài khoản không tồn tại"}), 404

    subject_mentee = target_user
    if target_user.get("role") == ROLE_PARENT:
        subject_mentee, error = get_linked_mentee_for_parent(target_user)
        if error:
            return error

    mentor_filter = mentee_filter_for_admin(admin)
    if mentor_filter and subject_mentee.get("mentor") != mentor_filter.get("mentor"):
        return jsonify({"detail": "Không có quyền duyệt tài khoản này"}), 403

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
    approved_ips = set(target_user.get("approved_login_ips") or [])
    approved_devices = set(target_user.get("approved_login_devices") or [])
    approved_ips.add(matched.get("ip", ""))
    approved_devices.add(matched.get("device_id", ""))
    matched["status"] = LOGIN_REQUEST_APPROVED
    matched["approved_at"] = now
    matched["approved_by"] = str(admin["_id"])

    still_pending = any(entry.get("status") == LOGIN_REQUEST_PENDING for entry in pending)
    users.update_one(
        {"_id": user_oid},
        {
            "$set": {
                "pending_login_requests": pending,
                "approved_login_ips": sorted(filter(None, approved_ips)),
                "approved_login_devices": sorted(filter(None, approved_devices)),
                "pending_login_unread": still_pending,
            },
        },
    )

    account_label = "phụ huynh" if target_user.get("role") == ROLE_PARENT else "mentee"
    log_mentor_activity(
        admin,
        "login_approve",
        f"Duyệt đăng nhập {account_label} {target_user.get('email', user_id)} "
        f"(IP {matched.get('ip', '')})",
        mentee_id=str(subject_mentee["_id"]),
    )
    if is_l2_mentor_admin(admin):
        push_l2_mentor_activity(
            str(subject_mentee["_id"]),
            admin,
            "device",
            "login_approve",
            f"Duyệt đăng nhập {account_label} (IP {matched.get('ip', '') or '—'})",
        )

    fresh = users.find_one({"_id": user_oid}) or target_user
    if target_user.get("role") == ROLE_PARENT:
        return jsonify(
            {
                "message": "Đã duyệt thiết bị/IP cho phụ huynh.",
                "login_tracking": serialize_login_tracking(fresh, include_superadmin_flags=False),
            },
        )

    return jsonify(
        {
            "message": "Đã duyệt thiết bị/IP cho mentee.",
            "login_tracking": serialize_login_tracking(fresh, include_superadmin_flags=False),
        },
    )


@app.get("/api/admin/access-requests")
@with_db
def admin_access_requests():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    return jsonify(list_pending_access_requests(admin))


@app.get("/api/admin/access-requests/team")
@with_db
def admin_access_team():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not is_super_admin(admin):
        return jsonify({"detail": "Chỉ super admin mới xem được team admin"}), 403

    query = team_admin_query(admin)
    cursor = admins.find(query).sort("reviewed_at", -1)
    items = [serialize_access_admin(doc) for doc in cursor]
    return jsonify(items)


@app.post("/api/admin/access-requests/team/<admin_id>/revoke")
@with_db
def admin_revoke_team_access(admin_id):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not is_super_admin(admin):
        return jsonify({"detail": "Chỉ super admin mới thu hồi quyền admin"}), 403

    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(admin_id)
    except InvalidId:
        return jsonify({"detail": "Admin không tồn tại"}), 404

    target = admins.find_one({"_id": oid})
    if not target:
        return jsonify({"detail": "Admin không tồn tại"}), 404

    if target.get("is_super_admin"):
        return jsonify({"detail": "Không thể thu hồi quyền super admin"}), 403

    if str(target["_id"]) == str(admin["_id"]):
        return jsonify({"detail": "Không thể thu hồi quyền của chính bạn"}), 403

    if not admin_in_activity_branch(admin, target):
        return jsonify({"detail": "Không có quyền thu hồi admin này"}), 403

    if target.get("status") != ADMIN_STATUS_APPROVED:
        return jsonify({"detail": "Admin này chưa được cấp quyền hoặc đã bị thu hồi"}), 400

    now = datetime.now(timezone.utc)
    admins.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": ADMIN_STATUS_REJECTED,
                "reviewed_at": now,
                "reviewed_by": str(admin["_id"]),
            },
            "$unset": {"email_action_tokens": ""},
        },
    )

    log_mentor_activity(
        admin,
        "access_revoke",
        f"{admin.get('email')} đã thu hồi quyền admin của {target.get('email')}",
        target_admin_id=str(oid),
    )
    log_mentor_activity(
        target,
        "access_revoke_result",
        f"Tài khoản {target.get('email')} đã bị thu hồi quyền admin",
    )

    return jsonify({"message": f"Đã thu hồi quyền admin của {target.get('email')}"})


@app.patch("/api/admin/access-requests/<request_id>")
@with_db
def admin_review_access(request_id):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    data = request.get_json(silent=True) or {}
    request_type = (data.get("request_type") or "mentor").strip().lower()
    if request_type == "mentee":
        return apply_mentee_registration_review(admin, request_id, data)

    if not is_super_admin(admin):
        return jsonify({"detail": "Chỉ super admin mới phê duyệt yêu cầu mentor"}), 403

    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(request_id)
    except InvalidId:
        return jsonify({"detail": "Yêu cầu không tồn tại"}), 404

    target = admins.find_one({"_id": oid})
    if not target:
        return jsonify({"detail": "Yêu cầu không tồn tại"}), 404

    if not admin_in_activity_branch(admin, target):
        return jsonify({"detail": "Không có quyền phê duyệt yêu cầu này"}), 403

    decision = data.get("status", "").strip()

    if decision not in {ADMIN_STATUS_APPROVED, ADMIN_STATUS_REJECTED}:
        return jsonify({"detail": "Trạng thái phê duyệt không hợp lệ"}), 400

    if target.get("status") != ADMIN_STATUS_PENDING:
        return jsonify({"detail": "Yêu cầu này đã được xử lý trước đó"}), 400

    verb = apply_access_review(target, admin, decision)
    return jsonify({"message": f"Đã {verb} tài khoản mentor {target.get('email')}"})


@app.get("/api/admin/access-requests/email/approve")
@with_db
def email_approve_access_request():
    from services.access import handle_email_admin_access_action

    return handle_email_admin_access_action("approve", ADMIN_STATUS_APPROVED)


@app.get("/api/admin/access-requests/email/reject")
@with_db
def email_reject_access_request():
    from services.access import handle_email_admin_access_action

    return handle_email_admin_access_action("reject", ADMIN_STATUS_REJECTED)

