
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

def admin_display_name(admin: dict) -> str:
    return (
        (admin.get("full_name") or "").strip()
        or (admin.get("username") or "").strip()
        or (admin.get("email") or "").strip()
        or "Mentor"
    )


def is_thanh_ha_mentee(user: dict | None) -> bool:
    return (user.get("mentor") or "").strip() == "Thanh Hà" if user else False


def admin_display_name(admin: dict | None) -> str:
    if not admin:
        return ""
    return (admin.get("full_name") or admin.get("username") or admin.get("email") or "").strip()


def admin_response(admin: dict) -> dict:
    return {
        "id": str(admin["_id"]),
        "username": admin["username"],
        "email": admin["email"],
        "role": ROLE_ADMIN,
        "full_name": admin.get("full_name", ""),
        "mentor_name": admin.get("mentor_name", ""),
        "is_level1_mentor": bool(admin.get("is_level1_mentor")),
        "status": admin.get("status", ADMIN_STATUS_APPROVED),
        "is_super_admin": is_super_admin(admin),
    }


def is_super_admin(admin: dict) -> bool:
    return bool(admin.get("is_super_admin")) or admin.get("email", "").lower() in SUPER_ADMIN_EMAILS


def admin_is_approved(admin: dict) -> bool:
    if is_super_admin(admin):
        return True
    return admin.get("status", ADMIN_STATUS_APPROVED) == ADMIN_STATUS_APPROVED


def mentor_folder_name(mentor_name: str) -> str:
    name = mentor_name.strip() or "Chung"
    return f"Mentor {name}"


def activity_branch_for_admin(admin: dict) -> str | None:
    mentor_name = (admin.get("mentor_name") or "").strip()
    if mentor_name in MENTOR_OPTIONS:
        return mentor_name
    return None


def admin_ids_for_branch(mentor_name: str) -> list[str]:
    return [str(doc["_id"]) for doc in admins.find({"mentor_name": mentor_name}, {"_id": 1})]


def admin_in_activity_branch(viewer: dict, target: dict | None) -> bool:
    branch = activity_branch_for_admin(viewer)
    if not branch:
        return True
    if not target:
        return False
    return (target.get("mentor_name") or "").strip() == branch


def activity_admin_id_filter(admin: dict) -> dict:
    base = {"admin_id": {"$exists": True, "$ne": ""}}
    branch = activity_branch_for_admin(admin)
    if not branch:
        return base
    return {"admin_id": {"$in": admin_ids_for_branch(branch)}}


def access_branch_query(admin: dict) -> dict:
    branch = activity_branch_for_admin(admin)
    if not branch:
        return {}
    return {"mentor_name": branch}


def team_admin_query(admin: dict) -> dict:
    return {
        "status": ADMIN_STATUS_APPROVED,
        "is_super_admin": {"$ne": True},
        **access_branch_query(admin),
    }


def team_admin_ids(admin: dict) -> list[str]:
    return [str(doc["_id"]) for doc in admins.find(team_admin_query(admin), {"_id": 1})]


def admin_in_team(viewer: dict, target: dict | None) -> bool:
    if not target:
        return False
    if target.get("is_super_admin"):
        return False
    if (target.get("status") or "").strip().lower() != ADMIN_STATUS_APPROVED:
        return False
    return admin_in_activity_branch(viewer, target)


def get_mentee_for_superadmin(admin: dict, mentee_id: str):
    from bson import ObjectId
    from bson.errors import InvalidId

    denied = require_system_super_admin(admin)
    if denied:
        return None, denied

    try:
        mentee_oid = ObjectId(mentee_id)
    except InvalidId:
        return None, (jsonify({"detail": "Mentee không tồn tại"}), 404)

    mentee = users.find_one({"_id": mentee_oid})
    if not mentee or mentee.get("role") == ROLE_PARENT:
        return None, (jsonify({"detail": "Mentee không tồn tại"}), 404)

    return mentee, None


def serialize_superadmin_mentor_item(admin_doc: dict, activity_stats: dict | None = None) -> dict:
    team = (admin_doc.get("mentor_name") or "").strip() or "Chung"
    display_name = admin_display_name(admin_doc)
    admin_id = str(admin_doc["_id"])
    stats = activity_stats or {}
    team_label = f"team {team}" if team != "Chung" else "Chung"
    return {
        "admin_id": admin_id,
        "display_name": display_name,
        "email": admin_doc.get("email", ""),
        "mentor_name": team,
        "team_label": team_label,
        "label": f"{display_name} ({team_label})",
        "is_level1_mentor": bool(admin_doc.get("is_level1_mentor")),
        "is_super_admin": is_super_admin(admin_doc),
        "activity_count": stats.get("count", 0),
        "last_activity_at": stats["last_at"].isoformat() if stats.get("last_at") else "",
    }


def activity_team_admin_id_filter(admin: dict) -> dict:
    allowed = team_admin_ids(admin)
    if not allowed:
        return {"admin_id": "__none__"}
    return {"admin_id": {"$in": allowed}}


def serialize_access_admin(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "username": doc.get("username", ""),
        "email": doc.get("email", ""),
        "full_name": doc.get("full_name", ""),
        "mentor_name": doc.get("mentor_name", ""),
        "requested_at": doc["requested_at"].isoformat() if doc.get("requested_at") else "",
        "reviewed_at": doc["reviewed_at"].isoformat() if doc.get("reviewed_at") else "",
    }


def log_mentor_activity(admin: dict, action: str, description: str, **extra):
    mentor_name = admin.get("mentor_name", "") or admin.get("full_name", "")
    mentor_activities.insert_one({
        "mentor_folder": mentor_folder_name(mentor_name),
        "mentor_name": mentor_name,
        "admin_id": str(admin["_id"]),
        "admin_email": admin.get("email", ""),
        "action": action,
        "description": description,
        "created_at": datetime.now(timezone.utc),
        **extra,
    })


def activity_response(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "admin_id": doc.get("admin_id", ""),
        "mentor_folder": doc.get("mentor_folder", ""),
        "mentor_name": doc.get("mentor_name", ""),
        "admin_email": doc.get("admin_email", ""),
        "action": doc.get("action", ""),
        "description": doc.get("description", ""),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else "",
    }


def admin_display_name(admin_doc: dict | None, fallback_email: str = "") -> str:
    if not admin_doc:
        return fallback_email or "Không rõ"
    if admin_doc.get("full_name"):
        return admin_doc["full_name"]
    if admin_doc.get("mentor_name"):
        return admin_doc["mentor_name"]
    return admin_doc.get("email", fallback_email)


def mentee_filter_for_admin(admin: dict) -> dict:
    mentor_name = admin.get("mentor_name", "").strip()
    if mentor_name:
        return {"mentor": mentor_name}
    return {}


def get_mentee_for_admin(admin: dict, mentee_id: str):
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        mentee_oid = ObjectId(mentee_id)
    except InvalidId:
        return None, (jsonify({"detail": "Mentee không tồn tại"}), 404)

    mentee = users.find_one({"_id": mentee_oid})
    if not mentee:
        return None, (jsonify({"detail": "Mentee không tồn tại"}), 404)

    if not mentee_is_approved(mentee):
        return None, (jsonify({"detail": "Mentee chưa được duyệt hoặc không tồn tại"}), 404)

    mentor_filter = mentee_filter_for_admin(admin)
    if mentor_filter and mentee.get("mentor") != mentor_filter.get("mentor"):
        return None, (jsonify({"detail": "Không có quyền xem mentee này"}), 403)

    return mentee, None


def serialize_admin_mentee_summary(user: dict, admin: dict | None = None) -> dict:
    from services.misc import get_mentor_l2_activity_raw
    summary = {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "full_name": user.get("full_name", ""),
        "date_of_birth": user.get("date_of_birth", ""),
        "mentor": user.get("mentor", ""),
        "parent_email": user.get("parent_email", ""),
        "apply_clone_email": user.get("apply_clone_email", ""),
        "apply_clone_password": user.get("apply_clone_password", ""),
        "created_at": user["created_at"].isoformat() if user.get("created_at") else "",
        "personal_declaration_url": get_personal_declaration_mentor_url(
            user.get("personal_declaration") or {},
        ),
        "unread_documents_count": count_unread_apply_documents(user),
        "processed_documents_count": count_processed_apply_documents(user),
        "scholarship_system": user.get("scholarship_system", ""),
        "scholarship_system_label": scholarship_system_label(user.get("scholarship_system", "")),
        "apply_direction": user.get("apply_direction", ""),
        "mentor_apply_direction": user.get("mentor_apply_direction", ""),
        "mentor_apply_direction_label": mentor_apply_direction_label(
            user.get("mentor_apply_direction", ""),
        ),
        "apply_degree_level": user.get("apply_degree_level", ""),
        "apply_degree_level_label": apply_degree_level_label(user.get("apply_degree_level", "")),
        "preferred_schools_note": user.get("preferred_schools_note", ""),
        "preferred_schools_note_unread": bool(user.get("preferred_schools_note_mentor_unread")),
        "apply_progress_pending_count": count_apply_progress_pending(user),
        "apply_progress_l2_unread": bool(user.get("apply_progress_l2_unread")),
        "zalo_phone": user.get("zalo_phone", ""),
        "account_password": user.get("mentor_visible_password", ""),
        "uploaded_count": count_uploaded_apply_documents(user),
        "approved_count": count_approved_apply_documents(user),
        "total_documents_count": len(VALID_APPLY_DOC_IDS),
        "submitted_schools_count": count_submitted_apply_schools(user),
        "total_schools_count": get_apply_progress_row_count(user),
    }
    if admin and admin_is_level1_mentor(admin):
        activity = get_mentor_l2_activity_raw(user)
        summary["mentor_l2_activity_l1_unread"] = mentor_l2_activity_has_unread(user)
        summary["mentor_l2_activity_unread_count"] = count_mentor_l2_activity_unread(user)
        summary["mentor_l2_activity"] = [serialize_mentor_l2_activity(item) for item in activity[:20]]
    else:
        summary["mentor_l2_activity_l1_unread"] = False
        summary["mentor_l2_activity_unread_count"] = 0
        summary["mentor_l2_activity"] = []
    if is_thanh_ha_mentee(user):
        user = ensure_hdnk_nckh_reminder_sync(user)
        summary["hdnk_nckh_l1_unread"] = bool(user.get("hdnk_nckh_l1_unread"))
        summary["hdnk_nckh_reminder_unread"] = bool(user.get("hdnk_nckh_reminder_unread"))
        summary["term3_2027_language_semester"] = user.get("term3_2027_language_semester", "")
        summary["term3_2027_language_semester_label"] = term3_2027_language_semester_label(
            user.get("term3_2027_language_semester", ""),
        )
        summary["research_direction"] = user.get("research_direction", "")
        summary["research_direction_label"] = research_direction_label(
            user.get("research_direction", ""),
        )
    else:
        summary["hdnk_nckh_l1_unread"] = False
        summary["hdnk_nckh_reminder_unread"] = False
        summary["term3_2027_language_semester"] = ""
        summary["term3_2027_language_semester_label"] = ""
        summary["research_direction"] = ""
        summary["research_direction_label"] = ""
    login_data = serialize_login_tracking(
        user,
        include_superadmin_flags=bool(admin and is_super_admin(admin)),
    )
    summary.update(
        {
            "login_unique_ip_count": login_data["login_unique_ip_count"],
            "login_unique_device_count": login_data["login_unique_device_count"],
            "login_ips": login_data["login_ips"],
            "login_devices": login_data["login_devices"],
            "pending_login_requests": login_data["pending_login_requests"],
            "pending_login_requests_count": login_data["pending_login_requests_count"],
            "login_anomaly": login_data["login_anomaly"],
        },
    )
    if admin and is_super_admin(admin):
        summary["login_anomaly_unread"] = login_data.get("login_anomaly_unread", False)
    summary["unread_feedback_count"] = count_mentor_unread_feedback(user["_id"])
    summary["needs_attention"] = mentee_needs_attention(summary, admin)
    return summary


def mentee_needs_attention(summary: dict, admin: dict | None = None) -> bool:
    if (summary.get("unread_documents_count") or 0) > 0:
        return True
    if summary.get("preferred_schools_note_unread"):
        return True
    if (summary.get("unread_feedback_count") or 0) > 0:
        return True
    if (summary.get("apply_progress_pending_count") or 0) > 0:
        return True
    if admin and not admin_is_level1_mentor(admin) and summary.get("apply_progress_l2_unread"):
        return True
    if admin and admin_is_level1_mentor(admin) and summary.get("mentor_l2_activity_l1_unread"):
        return True
    if admin and is_thanh_ha_l1_mentor(admin):
        if summary.get("hdnk_nckh_l1_unread") or summary.get("hdnk_nckh_reminder_unread"):
            return True
    return False


def count_mentees_needing_attention(admin: dict) -> int:
    from services.access import mentee_admin_list_query

    total = 0
    for user in users.find(mentee_admin_list_query(admin)):
        summary = serialize_admin_mentee_summary(user, admin)
        if summary.get("needs_attention"):
            total += 1
    return total


def serialize_admin_mentee_detail(user: dict, admin: dict | None = None) -> dict:
    from services.misc import serialize_hdnk_nckh_payload
    apply_docs = user.get("apply_documents") or {}
    documents = [
        serialize_apply_document_for_admin(doc_id, apply_docs.get(doc_id), user, str(user["_id"]))
        for doc_id in sorted(VALID_APPLY_DOC_IDS)
    ]
    documents.append(serialize_supporting_materials_for_admin(user))
    summary = serialize_admin_mentee_summary(user, admin)
    viewer = apply_progress_viewer_key(admin)
    summary["documents"] = documents
    summary["admin_documents_count"] = len(documents)
    summary["uploaded_count"] = count_uploaded_apply_documents(user)
    summary["approved_count"] = count_approved_apply_documents(user)
    summary["total_documents_count"] = len(VALID_APPLY_DOC_IDS)
    summary["apply_progress"] = serialize_apply_progress_payload(user, viewer, include_activity=True)
    summary["apply_progress_pending_count"] = summary["apply_progress"]["pending_count"]
    if is_thanh_ha_mentee(user):
        summary["hdnk_nckh"] = serialize_hdnk_nckh_payload(user)
    else:
        summary["hdnk_nckh"] = {"enabled": False, "entries": []}

    parent_email = (user.get("parent_email") or "").strip().lower()
    if parent_email:
        parent_user = users.find_one({"email": parent_email, "role": ROLE_PARENT})
        if parent_user:
            summary["parent_account"] = {
                "id": str(parent_user["_id"]),
                "email": parent_user.get("email", ""),
                "full_name": parent_user.get("full_name", ""),
                **serialize_login_tracking(
                    parent_user,
                    include_superadmin_flags=bool(admin and is_super_admin(admin)),
                ),
            }
    from services.profile_info import (
        missing_profile_field_items,
        serialize_profile_info_reminder,
    )

    summary["missing_profile_fields"] = missing_profile_field_items(user)
    summary["profile_info_reminder"] = serialize_profile_info_reminder(user)
    return summary


def remove_mentee_account(mentee: dict) -> None:
    from bson import ObjectId

    mentee_id = mentee["_id"]
    feedback_app.delete_many({"user_id": mentee_id})

    parent_email = (mentee.get("parent_email") or "").strip().lower()
    if parent_email:
        parent = users.find_one({"email": parent_email, "role": ROLE_PARENT})
        if parent and parent.get("linked_mentee_id") == mentee_id:
            users.delete_one({"_id": parent["_id"]})

    upload_path = UPLOAD_ROOT / str(mentee_id)
    if upload_path.is_dir():
        shutil.rmtree(upload_path, ignore_errors=True)

    users.delete_one({"_id": ObjectId(mentee_id)})

