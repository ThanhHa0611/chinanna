
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

def _apply_doc_vn_today_start() -> datetime:
    from zoneinfo import ZoneInfo

    vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
    local_now = datetime.now(vn_tz)
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def _apply_doc_vn_day_start(value) -> datetime | None:
    from zoneinfo import ZoneInfo

    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
    local = dt.astimezone(vn_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc)


def apply_document_is_processed(record: dict | None) -> bool:
    record = record or {}
    return bool(record.get("mentor_processed_at"))


def is_apply_document_unread(doc_id: str, record: dict | None, user: dict | None = None) -> bool:
    """True when mentor should pay attention (new upload, or viewed but not processed past due)."""
    record = record or {}
    user = user or {}
    if record.get("mentor_handles") or record.get("needs_mentor_edit"):
        return True
    if doc_id == "language":
        scores = record.get("language_scores") or {}
        if scores.get("mentor_handles_update"):
            return True
    if not apply_document_has_content(doc_id, record, user):
        return False
    if apply_document_is_processed(record):
        return False

    now = datetime.now(timezone.utc)
    scheduled = record.get("scheduled_process_at")
    if scheduled:
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        if scheduled > now:
            return False

    viewed_at = record.get("mentor_viewed_at")
    if not viewed_at:
        return True

    if viewed_at.tzinfo is None:
        viewed_at = viewed_at.replace(tzinfo=timezone.utc)
    viewed_day = _apply_doc_vn_day_start(viewed_at)
    today_start = _apply_doc_vn_today_start()
    if viewed_day and viewed_day >= today_start and not scheduled:
        return False
    return True


def count_mentee_unread_mentor_uploads(user: dict) -> int:
    apply_docs = user.get("apply_documents") or {}
    count = 0
    for doc_id in MENTOR_UPLOADABLE_DOC_IDS:
        record = apply_docs.get(doc_id) or {}
        if record.get("mentee_unread_upload"):
            count += 1
    return count


def serialize_apply_missing_reminder(user: dict) -> dict | None:
    reminder = user.get("apply_missing_reminder") or {}
    doc_ids = [doc_id for doc_id in (reminder.get("doc_ids") or []) if doc_id in VALID_APPLY_DOC_IDS]
    if not doc_ids:
        return None
    return {
        "message": reminder.get("message") or APPLY_MISSING_REMINDER_MESSAGE,
        "doc_ids": doc_ids,
        "items": [
            {
                "doc_id": doc_id,
                "label": APPLY_DOC_LABELS.get(doc_id, doc_id),
            }
            for doc_id in doc_ids
        ],
        "unread": bool(reminder.get("mentee_unread")),
        "sent_at": reminder["sent_at"].isoformat() if reminder.get("sent_at") else "",
    }


def serialize_language_scores(scores: dict) -> dict:
    languages = normalize_language_list(scores)
    updates = scores.get("score_updates") or []
    serialized_updates = []
    for entry in updates[-20:]:
        serialized_updates.append({
            "id": entry.get("id", ""),
            "language": entry.get("language", ""),
            "skill": entry.get("skill", ""),
            "value_type": entry.get("value_type", ""),
            "previous_value": entry.get("previous_value", ""),
            "new_value": entry.get("new_value", ""),
            "exam_date": entry.get("exam_date", ""),
            "submitted_at": entry["submitted_at"].isoformat()
            if entry.get("submitted_at")
            else entry.get("submitted_at", ""),
        })

    legacy_lang = languages[0] if len(languages) == 1 else "english"
    legacy_scores = language_block_for(scores, legacy_lang)

    return {
        "languages": languages,
        "language_type": languages[0] if len(languages) == 1 else "",
        "certificate_name": scores.get("certificate_name", ""),
        "english": language_block_for(scores, "english"),
        "chinese": language_block_for(scores, "chinese"),
        "scores": legacy_scores,
        "score_updated_at": scores.get("score_updated_at", ""),
        "latest_exam": scores.get("latest_exam") or {},
        "score_updates": serialized_updates,
        "mentor_handles_update": bool(scores.get("mentor_handles_update")),
        "mentor_handles_update_at": scores["mentor_handles_update_at"].isoformat()
        if scores.get("mentor_handles_update_at")
        else "",
    }


def serialize_hdnk_nckh_entry(entry: dict, for_mentee: bool = False) -> dict:
    payload = {
        "entry_id": entry.get("entry_id") or "",
        "start_date": entry.get("start_date") or "",
        "category": entry.get("category") or "",
        "participation_type": entry.get("participation_type") or "",
        "zalo_group_name": entry.get("zalo_group_name") or "",
        "progress": entry.get("progress") or "",
        "has_award": bool(entry.get("has_award")),
        "award_level": entry.get("award_level") or "",
    }
    if for_mentee:
        return payload
    payload["mentor_note"] = entry.get("mentor_note") or ""
    payload["reminder_due_at"] = format_hdnk_reminder_date(entry.get("reminder_due_at"))
    return payload


def extract_apply_progress_fields(row: dict | None) -> dict[str, str]:
    source = row or {}
    return {field: str(source.get(field) or "").strip() for field in APPLY_PROGRESS_FIELDS}


def serialize_hdnk_nckh_payload(user: dict, for_mentee: bool = False) -> dict:
    user = ensure_hdnk_nckh_reminder_sync(user)
    mentee_updated = user.get("hdnk_nckh_mentee_updated_at")
    entries_raw = get_hdnk_nckh_entries_raw(user)
    return {
        "enabled": is_thanh_ha_mentee(user),
        "entries": [serialize_hdnk_nckh_entry(entry, for_mentee=for_mentee) for entry in entries_raw],
        "mentee_updated_at": mentee_updated.isoformat() if hasattr(mentee_updated, "isoformat") else "",
        "l1_unread": bool(user.get("hdnk_nckh_l1_unread")),
        "reminder_unread": bool(user.get("hdnk_nckh_reminder_unread")),
        "participation_type_options": list(HDNK_NCKH_PARTICIPATION_TYPES),
        "progress_options": list(HDNK_NCKH_PROGRESS_OPTIONS),
        "award_level_options": list(HDNK_NCKH_AWARD_LEVELS),
    }


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


def attempt_create_personal_declaration(user: dict) -> dict:
    from google_docs import (
        build_doc_url,
        create_personal_declaration_doc,
        create_personal_declaration_local_copy,
        get_manual_copy_url,
        has_google_credentials,
    )

    username = user.get("username") or user.get("email") or "mentee"
    upload_path = UPLOAD_ROOT / str(user["_id"])

    if has_google_credentials():
        try:
            return create_personal_declaration_doc(username)
        except RuntimeError:
            pass

    try:
        local = create_personal_declaration_local_copy(username, upload_path)
        local["local_file_url"] = f"{BACKEND_PUBLIC_URL}/api/documents/personal-declaration/file"
        return local
    except RuntimeError:
        return {
            "needs_manual_copy": True,
            "copy_url": get_manual_copy_url(),
            "mode": "manual_copy",
        }


def save_personal_declaration_record(user_id, record: dict) -> dict | None:
    from bson import ObjectId
    from pymongo import ReturnDocument

    updated = users.find_one_and_update(
        {
            "_id": ObjectId(user_id),
            "$or": [
                {"personal_declaration": {"$exists": False}},
                {"personal_declaration.doc_id": {"$exists": False}},
                {"personal_declaration.url": {"$in": ["", None]}},
            ],
        },
        {"$set": {"personal_declaration": record}},
        return_document=ReturnDocument.AFTER,
    )
    if updated and personal_declaration_has_form(updated.get("personal_declaration") or {}):
        return updated

    fresh = users.find_one({"_id": ObjectId(user_id)})
    saved = (fresh or {}).get("personal_declaration") or {}
    if personal_declaration_has_form(saved):
        return fresh
    return None

