
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

def extract_apply_progress_fields(row: dict | None) -> dict[str, str]:
    source = row or {}
    return {field: str(source.get(field) or "").strip() for field in APPLY_PROGRESS_FIELDS}


def mask_apply_progress_value(field: str, value: str, viewer: str) -> str:
    cleaned = (value or "").strip()
    if field == "progress" and cleaned == APPLY_PROGRESS_PROGRESS_L2_ONLY:
        if viewer in {"mentee", "parent"}:
            return ""
    return cleaned


def validate_apply_progress_field_values(fields: dict, viewer: str) -> str | None:
    scholarship = (fields.get("scholarship_type") or "").strip()
    progress = (fields.get("progress") or "").strip()
    if scholarship and scholarship not in APPLY_PROGRESS_SCHOLARSHIP_TYPES:
        return f"Loại hb không hợp lệ: {scholarship}"
    allowed_progress = set(apply_progress_progress_options_for_viewer(viewer))
    if progress and progress not in allowed_progress:
        if (
            viewer == "mentor_l2"
            and progress == APPLY_PROGRESS_PROGRESS_L1_ONLY
        ):
            pass
        else:
            return f"Tiến độ không hợp lệ: {progress}"
    return None


def get_mentor_l2_activity_raw(user: dict) -> list[dict]:
    stored = user.get("mentor_l2_activity")
    if not isinstance(stored, list):
        return []
    return [item for item in stored if isinstance(item, dict)]


def apply_progress_fields_equal(left: dict | None, right: dict | None) -> bool:
    from services.misc import extract_apply_progress_fields
    return extract_apply_progress_fields(left) == extract_apply_progress_fields(right)


def admin_is_level1_mentor(admin: dict | None) -> bool:
    if not admin:
        return False
    if admin.get("is_level1_mentor"):
        return True
    mentor = (admin.get("mentor_name") or "").strip()
    display = (admin.get("full_name") or admin.get("username") or "").strip()
    return mentor in MENTOR_OPTIONS and display == mentor


def is_thanh_ha_l1_mentor(admin: dict | None) -> bool:
    if not admin:
        return False
    return admin_is_level1_mentor(admin) and (admin.get("mentor_name") or "").strip() == "Thanh Hà"


def apply_progress_viewer_key(admin: dict | None = None, *, mentee: bool = False, parent: bool = False) -> str:
    from services.admins import is_super_admin
    if mentee:
        return "mentee"
    if parent:
        return "parent"
    if admin and is_super_admin(admin):
        return "superadmin"
    if admin and admin_is_level1_mentor(admin):
        return "mentor_l1"
    if admin:
        return "mentor_l2"
    return "mentee"


def apply_progress_scholarship_options() -> list[str]:
    return list(APPLY_PROGRESS_SCHOLARSHIP_TYPES)


def apply_progress_progress_options_for_viewer(viewer: str) -> list[str]:
    options = list(APPLY_PROGRESS_PROGRESS_BASE)
    if viewer in {"mentor_l1", "superadmin"}:
        options.append(APPLY_PROGRESS_PROGRESS_L1_ONLY)
    if viewer in {"mentor_l2", "superadmin"}:
        options.append(APPLY_PROGRESS_PROGRESS_L2_ONLY)
    return options


def is_l2_mentor_admin(admin: dict | None) -> bool:
    from services.admins import admin_is_approved, is_super_admin
    if not admin or not admin_is_approved(admin):
        return False
    if is_super_admin(admin):
        return False
    return not admin_is_level1_mentor(admin)


def serialize_mentor_l2_activity(raw: dict) -> dict:
    created_at = raw.get("created_at")
    ack_at = raw.get("l1_ack_at")
    return {
        "id": raw.get("id") or "",
        "section": raw.get("section") or "",
        "action": raw.get("action") or "",
        "mentor_name": raw.get("mentor_name") or "",
        "summary": raw.get("summary") or "",
        "l1_unread": bool(raw.get("l1_unread")),
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at or "",
        "l1_ack_at": ack_at.isoformat() if hasattr(ack_at, "isoformat") else ack_at or "",
    }


def count_mentor_l2_activity_unread(user: dict) -> int:
    from services.misc import get_mentor_l2_activity_raw
    return sum(1 for item in get_mentor_l2_activity_raw(user) if item.get("l1_unread"))


def mentor_l2_activity_has_unread(user: dict) -> bool:
    if user.get("mentor_l2_activity_l1_unread"):
        return True
    return count_mentor_l2_activity_unread(user) > 0


def push_l2_mentor_activity(mentee_id, admin: dict, section: str, action: str, summary: str) -> None:
    from services.admins import admin_display_name
    if not is_l2_mentor_admin(admin):
        return

    from bson import ObjectId

    name = admin_display_name(admin)
    record = {
        "id": str(uuid.uuid4()),
        "section": section,
        "action": action,
        "mentor_name": name,
        "mentor_id": str(admin["_id"]),
        "summary": f"{name}: {summary}",
        "created_at": datetime.now(timezone.utc),
        "l1_unread": True,
        "l1_ack_at": None,
    }
    users.update_one(
        {"_id": ObjectId(mentee_id)},
        {
            "$push": {
                "mentor_l2_activity": {
                    "$each": [record],
                    "$position": 0,
                    "$slice": 100,
                },
            },
            "$set": {"mentor_l2_activity_l1_unread": True},
        },
    )


def ack_mentor_l2_activity(mentee_id, admin: dict, section: str | None = None) -> dict:
    from services.admins import admin_display_name
    from services.misc import get_mentor_l2_activity_raw
    from bson import ObjectId

    mentee = users.find_one({"_id": ObjectId(mentee_id)})
    if not mentee:
        return {"mentor_l2_activity": [], "mentor_l2_activity_l1_unread": False, "mentor_l2_activity_unread_count": 0}

    now = datetime.now(timezone.utc)
    activity = get_mentor_l2_activity_raw(mentee)
    changed = False
    for item in activity:
        if not item.get("l1_unread"):
            continue
        if section and item.get("section") != section:
            continue
        item["l1_unread"] = False
        item["l1_ack_at"] = now
        item["l1_ack_by"] = admin_display_name(admin)
        changed = True

    still_unread = any(item.get("l1_unread") for item in activity)
    if changed:
        users.update_one(
            {"_id": ObjectId(mentee_id)},
            {
                "$set": {
                    "mentor_l2_activity": activity,
                    "mentor_l2_activity_l1_unread": still_unread,
                },
            },
        )
        mentee = {**mentee, "mentor_l2_activity": activity, "mentor_l2_activity_l1_unread": still_unread}

    serialized = [serialize_mentor_l2_activity(item) for item in get_mentor_l2_activity_raw(mentee)]
    unread_count = sum(1 for item in serialized if item.get("l1_unread"))
    return {
        "mentor_l2_activity": serialized,
        "mentor_l2_activity_l1_unread": unread_count > 0,
        "mentor_l2_activity_unread_count": unread_count,
    }


def push_apply_progress_activity(user_id, entry: dict) -> None:
    from bson import ObjectId

    record = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc),
        "processed": False,
        "processed_at": None,
        "processed_by_name": "",
        "mentor_unread": True,
        **entry,
    }
    users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$push": {
                "apply_progress_activity": {
                    "$each": [record],
                    "$position": 0,
                    "$slice": 100,
                },
            },
        },
    )


def serialize_apply_progress_activity(raw: dict) -> dict:
    created_at = raw.get("created_at")
    processed_at = raw.get("processed_at")
    return {
        "id": raw.get("id") or "",
        "type": raw.get("type") or "",
        "row_num": int(raw.get("row_num") or 0),
        "action": raw.get("action") or "",
        "summary": raw.get("summary") or "",
        "processed": bool(raw.get("processed")),
        "mentor_unread": bool(raw.get("mentor_unread")),
        "processed_by_name": raw.get("processed_by_name") or "",
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at or "",
        "processed_at": processed_at.isoformat() if hasattr(processed_at, "isoformat") else processed_at or "",
    }


def get_apply_progress_activity_raw(user: dict) -> list[dict]:
    stored = user.get("apply_progress_activity")
    if not isinstance(stored, list):
        return []
    return [item for item in stored if isinstance(item, dict)]


def mark_apply_progress_activity_processed(user_id, row_num: int, admin: dict, action: str) -> None:
    from services.admins import admin_display_name
    from bson import ObjectId

    now = datetime.now(timezone.utc)
    name = admin_display_name(admin)
    stored = users.find_one({"_id": ObjectId(user_id)}, {"apply_progress_activity": 1}) or {}
    activity = get_apply_progress_activity_raw(stored)
    updated = False
    for item in activity:
        if item.get("type") == "mentee_request" and int(item.get("row_num") or 0) == row_num and not item.get("processed"):
            item["processed"] = True
            item["processed_at"] = now
            item["processed_by_name"] = name
            item["action"] = action
            item["mentor_unread"] = False
            item["summary"] = (
                f"Đã duyệt chỉnh sửa dòng {row_num}"
                if action == "approve"
                else f"Đã từ chối chỉnh sửa dòng {row_num}"
            )
            updated = True
            break
    if updated:
        users.update_one({"_id": ObjectId(user_id)}, {"$set": {"apply_progress_activity": activity}})
    push_apply_progress_activity(
        user_id,
        {
            "type": "mentor_review",
            "row_num": row_num,
            "action": action,
            "processed": True,
            "processed_at": now,
            "processed_by_name": name,
            "mentor_unread": False,
            "summary": (
                f"Đã duyệt chỉnh sửa dòng {row_num}"
                if action == "approve"
                else f"Đã từ chối chỉnh sửa dòng {row_num}"
            ),
        },
    )


def get_apply_progress_row_count(user: dict) -> int:
    raw = user.get("apply_progress_row_count")
    if isinstance(raw, int) and APPLY_PROGRESS_ROW_MIN <= raw <= APPLY_PROGRESS_ROW_MAX:
        return raw
    return APPLY_PROGRESS_ROW_DEFAULT


def get_apply_progress_rows_raw(user: dict) -> list[dict]:
    from services.misc import extract_apply_progress_fields
    row_count = get_apply_progress_row_count(user)
    stored = user.get("apply_progress_rows")
    by_num: dict[int, dict] = {}
    if isinstance(stored, list):
        for item in stored:
            if not isinstance(item, dict):
                continue
            row_num = int(item.get("row_num") or 0)
            if 1 <= row_num <= APPLY_PROGRESS_ROW_MAX:
                by_num[row_num] = item

    rows: list[dict] = []
    for row_num in range(1, row_count + 1):
        existing = by_num.get(row_num) or {}
        pending = existing.get("pending")
        rows.append(
            {
                "row_num": row_num,
                **extract_apply_progress_fields(existing),
                "pending": extract_apply_progress_fields(pending) if isinstance(pending, dict) else None,
                "pending_status": str(existing.get("pending_status") or "").strip(),
                "pending_at": existing.get("pending_at"),
                "rejection_note": str(existing.get("rejection_note") or "").strip(),
            },
        )
    return rows


def serialize_apply_progress_row(row: dict, viewer: str = "mentee") -> dict:
    from services.misc import extract_apply_progress_fields, mask_apply_progress_value
    pending = row.get("pending")
    pending_fields = extract_apply_progress_fields(pending) if isinstance(pending, dict) else None
    if pending_fields and not any(pending_fields.values()):
        pending_fields = None
    pending_at = row.get("pending_at")
    pending_status = row.get("pending_status") or ""
    has_pending = bool(pending_fields) and pending_status == APPLY_PROGRESS_PENDING_WAITING
    fields = extract_apply_progress_fields(row)
    masked_fields = {
        key: mask_apply_progress_value(key, value, viewer)
        for key, value in fields.items()
    }
    masked_pending = None
    if pending_fields:
        masked_pending = {
            key: mask_apply_progress_value(key, value, viewer)
            for key, value in pending_fields.items()
        }
    return {
        "row_num": row["row_num"],
        **masked_fields,
        "pending": masked_pending,
        "pending_status": pending_status,
        "pending_at": pending_at.isoformat() if hasattr(pending_at, "isoformat") else pending_at or "",
        "rejection_note": row.get("rejection_note") or "",
        "has_pending": has_pending,
    }


def serialize_apply_progress_payload(user: dict, viewer: str = "mentee", include_activity: bool = False) -> dict:
    rows = [serialize_apply_progress_row(row, viewer) for row in get_apply_progress_rows_raw(user)]
    updated_at = user.get("apply_progress_updated_at")
    payload = {
        "rows": rows,
        "row_count": get_apply_progress_row_count(user),
        "pending_count": sum(1 for row in rows if row.get("has_pending")),
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at or "",
        "scholarship_type_options": apply_progress_scholarship_options(),
        "progress_options": apply_progress_progress_options_for_viewer(viewer),
        "mentee_unread": bool(user.get("apply_progress_mentee_unread")),
        "l2_unread": bool(user.get("apply_progress_l2_unread")),
    }
    if include_activity:
        activity = [serialize_apply_progress_activity(item) for item in get_apply_progress_activity_raw(user)]
        payload["activity"] = activity
        payload["unprocessed_activity_count"] = sum(
            1 for item in activity if not item.get("processed")
        )
    return payload


def count_apply_progress_pending(user: dict) -> int:
    return serialize_apply_progress_payload(user)["pending_count"]

