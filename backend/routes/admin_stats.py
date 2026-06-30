
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
from services.profile_activities import count_total_pending_profile_actions
from services.utils import *

@app.get("/api/admin/stats")
@with_db
def admin_stats():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    mentee_query = mentee_admin_list_query(admin)
    mentee_count = users.count_documents(mentee_query)

    mentee_ids = [u["_id"] for u in users.find(mentee_query, {"_id": 1})]
    feedback_query = {"user_id": {"$in": mentee_ids}} if mentee_ids else {}

    feedback_total = feedback_app.count_documents(feedback_query)
    feedback_pending = feedback_app.count_documents({**feedback_query, "status": FEEDBACK_STATUS_PENDING})
    feedback_done = feedback_app.count_documents({**feedback_query, "status": FEEDBACK_STATUS_DONE})

    activity_count = 0
    if is_super_admin(admin):
        activity_count = mentor_activities.count_documents(activity_team_admin_id_filter(admin))
    pending_requests = 0
    if is_super_admin(admin):
        pending_requests = admins.count_documents(
            {"status": ADMIN_STATUS_PENDING, **access_branch_query(admin)}
        )
    pending_mentee_registrations = users.count_documents(pending_mentee_registration_query(admin))
    pending_access_requests_count = count_pending_access_requests(admin)
    mentee_attention_count = count_mentees_needing_attention(admin)
    profile_activities_pending_count = count_total_pending_profile_actions(admin)

    return jsonify({
        "mentee_count": mentee_count,
        "feedback_total": feedback_total,
        "feedback_pending": feedback_pending,
        "feedback_done": feedback_done,
        "activity_count": activity_count,
        "pending_requests": pending_requests,
        "pending_mentee_registrations": pending_mentee_registrations,
        "pending_access_requests_count": pending_access_requests_count,
        "mentee_attention_count": mentee_attention_count,
        "profile_activities_pending_count": profile_activities_pending_count,
    })


@app.get("/api/admin/activities/admins")
@with_db
def admin_activity_admins():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not is_super_admin(admin):
        return jsonify({"detail": "Chỉ super admin mới xem được lịch sử hoạt động"}), 403

    from bson import ObjectId
    from bson.errors import InvalidId

    pipeline = [
        {"$match": activity_team_admin_id_filter(admin)},
        {
            "$group": {
                "_id": "$admin_id",
                "count": {"$sum": 1},
                "last_at": {"$max": "$created_at"},
                "admin_email": {"$last": "$admin_email"},
            }
        },
        {"$sort": {"last_at": -1}},
    ]
    groups = list(mentor_activities.aggregate(pipeline))
    items = []
    for group in groups:
        admin_id = group["_id"]
        admin_doc = None
        try:
            admin_doc = admins.find_one({"_id": ObjectId(admin_id)})
        except InvalidId:
            admin_doc = None

        if not admin_in_team(admin, admin_doc):
            continue

        fallback_email = group.get("admin_email", "")
        items.append({
            "admin_id": admin_id,
            "display_name": admin_display_name(admin_doc, fallback_email),
            "email": admin_doc.get("email", fallback_email) if admin_doc else fallback_email,
            "mentor_name": admin_doc.get("mentor_name", "") if admin_doc else "",
            "activity_count": group["count"],
            "last_activity_at": group["last_at"].isoformat() if group.get("last_at") else "",
        })

    return jsonify(items)


@app.get("/api/admin/activities")
@with_db
def admin_activities():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not is_super_admin(admin):
        return jsonify({"detail": "Chỉ super admin mới xem được lịch sử hoạt động"}), 403

    from bson import ObjectId
    from bson.errors import InvalidId

    admin_id = request.args.get("admin_id", "").strip()
    if not admin_id:
        return jsonify({"detail": "Thiếu admin_id"}), 400

    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        target_admin = admins.find_one({"_id": ObjectId(admin_id)})
    except InvalidId:
        return jsonify({"detail": "Admin không tồn tại"}), 404

    if not target_admin or not admin_in_team(admin, target_admin):
        return jsonify({"detail": "Không có quyền xem lịch sử admin này"}), 403

    cursor = mentor_activities.find({"admin_id": admin_id}).sort("created_at", -1).limit(200)
    return jsonify([activity_response(doc) for doc in cursor])

