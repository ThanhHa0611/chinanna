
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

@app.get("/api/superadmin/access-requests")
@with_db
def superadmin_access_requests():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    denied = require_system_super_admin(admin)
    if denied:
        return denied

    return jsonify(list_pending_access_requests(admin))


@app.patch("/api/superadmin/access-requests/<request_id>")
@with_db
def superadmin_review_access_request(request_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    denied = require_system_super_admin(admin)
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    request_type = (data.get("request_type") or "mentor").strip().lower()
    if request_type == "mentee":
        return apply_mentee_registration_review(admin, request_id, data)

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

    decision = (data.get("status") or "").strip()
    if decision not in {ADMIN_STATUS_APPROVED, ADMIN_STATUS_REJECTED}:
        return jsonify({"detail": "Trạng thái phê duyệt không hợp lệ"}), 400

    if target.get("status") != ADMIN_STATUS_PENDING:
        return jsonify({"detail": "Yêu cầu này đã được xử lý trước đó"}), 400

    verb = apply_access_review(target, admin, decision)
    return jsonify({"message": f"Đã {verb} tài khoản mentor {target.get('email')}"})


@app.get("/api/superadmin/mentors")
@with_db
def superadmin_list_mentors():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    denied = require_system_super_admin(admin)
    if denied:
        return denied

    pipeline = [
        {"$match": {"admin_id": {"$exists": True, "$ne": ""}}},
        {
            "$group": {
                "_id": "$admin_id",
                "count": {"$sum": 1},
                "last_at": {"$max": "$created_at"},
            }
        },
    ]
    activity_map = {
        group["_id"]: {"count": group["count"], "last_at": group.get("last_at")}
        for group in mentor_activities.aggregate(pipeline)
    }

    teams: dict[str, list] = {}
    cursor = admins.find({"status": ADMIN_STATUS_APPROVED}).sort([("mentor_name", 1), ("full_name", 1)])
    for admin_doc in cursor:
        team = (admin_doc.get("mentor_name") or "").strip() or "Chung"
        item = serialize_superadmin_mentor_item(
            admin_doc,
            activity_map.get(str(admin_doc["_id"])),
        )
        teams.setdefault(team, []).append(item)

    team_order = ["Thanh Hà", "Mai Chi"]
    team_order = [name for name in team_order if name in teams]
    for team_name in sorted(teams.keys()):
        if team_name not in team_order:
            team_order.append(team_name)

    return jsonify({
        "teams": [
            {
                "team": team_name,
                "team_label": f"team {team_name}" if team_name != "Chung" else "Chung",
                "mentors": teams[team_name],
            }
            for team_name in team_order
        ]
    })


@app.get("/api/superadmin/mentors/<admin_id>/activities")
@with_db
def superadmin_mentor_activities(admin_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    denied = require_system_super_admin(admin)
    if denied:
        return denied

    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        target_admin = admins.find_one({"_id": ObjectId(admin_id)})
    except InvalidId:
        return jsonify({"detail": "Mentor không tồn tại"}), 404

    if not target_admin:
        return jsonify({"detail": "Mentor không tồn tại"}), 404

    cursor = mentor_activities.find({"admin_id": admin_id}).sort("created_at", -1).limit(300)
    admin_items = [activity_response(doc) for doc in cursor]

    team = (target_admin.get("mentor_name") or "").strip()
    team_items = []
    if team:
        team_cursor = mentor_activities.find({
            "mentor_name": team,
            "$or": [
                {"admin_id": {"$exists": False}},
                {"admin_id": ""},
                {"admin_id": {"$ne": admin_id}},
            ],
        }).sort("created_at", -1).limit(200)
        for doc in team_cursor:
            item = activity_response(doc)
            item["source"] = "team"
            team_items.append(item)

    combined = admin_items + team_items
    combined.sort(key=lambda row: row.get("created_at", ""), reverse=True)
    return jsonify({
        "mentor": serialize_superadmin_mentor_item(target_admin, None),
        "items": combined[:400],
    })


@app.get("/api/superadmin/mentees")
@with_db
def superadmin_list_mentees():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    denied = require_system_super_admin(admin)
    if denied:
        return denied

    groups: dict[str, list] = {}
    cursor = users.find(mentee_users_query()).sort([("mentor", 1), ("full_name", 1), ("username", 1)])
    for mentee in cursor:
        mentor = (mentee.get("mentor") or "").strip() or "Chưa gán mentor"
        groups.setdefault(mentor, []).append(serialize_admin_mentee_summary(mentee, admin))

    team_order = ["Thanh Hà", "Mai Chi"]
    team_order = [name for name in team_order if name in groups]
    for mentor_name in sorted(groups.keys()):
        if mentor_name not in team_order:
            team_order.append(mentor_name)

    def mentor_group_label(name: str) -> str:
        if name in MENTOR_OPTIONS:
            return f"Mentor {name}"
        return name

    grouped = [
        {
            "mentor": mentor_name,
            "mentor_label": mentor_group_label(mentor_name),
            "mentees": groups[mentor_name],
        }
        for mentor_name in team_order
    ]
    total_count = sum(len(group["mentees"]) for group in grouped)

    return jsonify({
        "total_count": total_count,
        "groups": grouped,
    })


@app.get("/api/superadmin/mentees/<mentee_id>")
@with_db
def superadmin_get_mentee(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    mentee, error = get_mentee_for_superadmin(admin, mentee_id)
    if error:
        return error

    if mentee.get("login_anomaly_superadmin_unread"):
        users.update_one(
            {"_id": mentee["_id"]},
            {"$set": {"login_anomaly_superadmin_unread": False}},
        )
        mentee["login_anomaly_superadmin_unread"] = False

    return jsonify(serialize_admin_mentee_detail(mentee, admin))


@app.get("/api/superadmin/mentees/<mentee_id>/feedback")
@with_db
def superadmin_list_mentee_feedback(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    mentee, error = get_mentee_for_superadmin(admin, mentee_id)
    if error:
        return error

    cursor = feedback_app.find({"user_id": mentee["_id"]}).sort("created_at", -1)
    items = [feedback_response(doc, admin) for doc in cursor]
    unread_count = count_mentor_unread_feedback(mentee["_id"])
    return jsonify({"items": items, "unread_count": unread_count})


@app.get("/api/superadmin/mentees/<mentee_id>/documents/<doc_id>/file")
@with_db
def superadmin_view_mentee_document_file(mentee_id: str, doc_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if doc_id not in VALID_APPLY_DOC_IDS or doc_id in NO_FILE_UPLOAD_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    mentee, error = get_mentee_for_superadmin(admin, mentee_id)
    if error:
        return error

    record = (mentee.get("apply_documents") or {}).get(doc_id) or {}
    stored_name = record.get("stored_name")
    if not stored_name:
        return jsonify({"detail": "Chưa có file tải lên"}), 404

    from services import storage
    from services.files import make_inline_file_response

    data = storage.read_bytes(storage.storage_key(mentee["_id"], doc_id, stored_name))
    if data is None:
        return jsonify({"detail": "File không tồn tại trên hệ thống"}), 404

    return make_inline_file_response(
        data,
        record.get("original_name") or stored_name,
        record.get("mime_type") or None,
    )

