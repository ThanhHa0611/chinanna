
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

def apply_doc_upload_dir(user_id: str, doc_id: str) -> Path:
    return UPLOAD_ROOT / str(user_id) / doc_id


def apply_document_is_processed(record: dict | None) -> bool:
    record = record or {}
    return bool(record.get("mentor_processed_at"))


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


def serialize_apply_document(doc_id: str, record: dict | None, user: dict | None = None) -> dict:
    from services.misc import serialize_language_scores

    record = record or {}
    item = {
        "doc_id": doc_id,
        "uploaded": bool(record.get("stored_name")),
        "original_name": record.get("original_name", ""),
        "uploaded_at": record["uploaded_at"].isoformat() if record.get("uploaded_at") else "",
        "mentor_status": record.get("mentor_status", ""),
        "mentor_note": record.get("mentor_note", ""),
        "mentor_updated_at": record["mentor_updated_at"].isoformat()
        if record.get("mentor_updated_at")
        else "",
        "mentee_unread_feedback": bool(record.get("mentee_unread_feedback")),
        "mentee_unread_upload": bool(record.get("mentee_unread_upload")),
        "uploaded_by": record.get("uploaded_by") or "mentee",
        "uploaded_by_name": record.get("uploaded_by_name", ""),
        "mentor_handles": bool(record.get("mentor_handles")),
        "needs_mentor_edit": bool(record.get("needs_mentor_edit")),
    }

    if doc_id == "personal-declaration":
        declaration = (user or {}).get("personal_declaration") or {}
        has_form = personal_declaration_has_form(declaration)
        item["uploaded"] = has_form
        item["declaration_url"] = get_personal_declaration_mentor_url(declaration)
        item["declaration_has_online"] = bool(get_personal_declaration_online_url(declaration))
        item["declaration_has_local"] = bool(declaration.get("stored_name"))
        item["mentor_status"] = record.get("mentor_status") or (
            DOC_MENTOR_STATUS_WAITING if has_form else ""
        )

    if doc_id == "language":
        item.update(serialize_language_scores(record.get("language_scores") or {}))
        if (record.get("language_scores") or {}).get("mentor_handles_update"):
            item["mentor_handles"] = True

    return item


def apply_document_has_content(doc_id: str, record: dict | None, user: dict | None = None) -> bool:
    record = record or {}
    if doc_id == "language":
        if record.get("stored_name"):
            return True
        scores = record.get("language_scores") or {}
        return bool(scores.get("languages") or scores.get("score_updates"))
    return bool(serialize_apply_document(doc_id, record, user).get("uploaded"))


def count_unread_apply_documents(user: dict) -> int:
    from services.misc import is_apply_document_unread

    apply_docs = user.get("apply_documents") or {}
    unread = 0
    for doc_id in VALID_APPLY_DOC_IDS:
        record = apply_docs.get(doc_id) or {}
        if is_apply_document_unread(doc_id, record, user):
            unread += 1
    return unread


def count_processed_apply_documents(user: dict) -> int:
    apply_docs = user.get("apply_documents") or {}
    count = 0
    for doc_id in VALID_APPLY_DOC_IDS:
        record = apply_docs.get(doc_id) or {}
        if not apply_document_has_content(doc_id, record, user):
            continue
        if apply_document_is_processed(record):
            count += 1
    return count


def find_pending_apply_inbox_task(mentee_id: str, doc_id: str) -> dict | None:
    return mentor_inbox.find_one(
        {
            "audience": "mentor",
            "mentee_id": str(mentee_id),
            "doc_id": doc_id,
            "action": "document_upload",
            "status": "pending",
        },
        sort=[("created_at", -1)],
    )


def sync_apply_inbox_view(mentee_id: str, doc_id: str):
    from inbox_tasks import record_inbox_view

    task = find_pending_apply_inbox_task(mentee_id, doc_id)
    if task:
        record_inbox_view(mentor_inbox, task)


def sync_apply_inbox_confirm(mentee_id: str, doc_id: str, *, via: str = "app", admin=None):
    from inbox_tasks import confirm_inbox_task
    from services.admins import admin_display_name

    task = find_pending_apply_inbox_task(mentee_id, doc_id)
    if task:
        processed_by = str(admin["_id"]) if admin and admin.get("_id") else ""
        processed_by_name = admin_display_name(admin) if admin else ""
        confirm_inbox_task(
            mentor_inbox,
            task_id=str(task["_id"]),
            via=via,
            processed_by=processed_by,
            processed_by_name=processed_by_name,
        )


def sync_apply_inbox_schedule(mentee_id: str, doc_id: str, *, reminder_at: datetime):
    from inbox_tasks import update_reminder_schedule

    task = find_pending_apply_inbox_task(mentee_id, doc_id)
    if task:
        update_reminder_schedule(
            mentor_inbox,
            str(task["_id"]),
            reminder_at=reminder_at,
        )


def apply_missing_reminder_unread(user: dict) -> bool:
    from services.misc import serialize_apply_missing_reminder

    reminder = serialize_apply_missing_reminder(user)
    return bool(reminder and reminder.get("unread"))


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


def prune_apply_missing_reminder(user_id, uploaded_doc_id: str):
    user = users.find_one({"_id": user_id})
    if not user:
        return
    reminder = user.get("apply_missing_reminder") or {}
    doc_ids = [doc_id for doc_id in (reminder.get("doc_ids") or []) if doc_id != uploaded_doc_id]
    if not doc_ids:
        users.update_one({"_id": user_id}, {"$unset": {"apply_missing_reminder": ""}})
        return
    users.update_one(
        {"_id": user_id},
        {"$set": {"apply_missing_reminder.doc_ids": doc_ids}},
    )


def apply_doc_id_still_missing(user: dict, doc_id: str) -> bool:
    if doc_id not in VALID_APPLY_DOC_IDS:
        return False
    if doc_id == "personal-declaration":
        return not personal_declaration_has_form(user.get("personal_declaration") or {})
    record = (user.get("apply_documents") or {}).get(doc_id) or {}
    return not apply_document_has_content(doc_id, record, user)


def sync_apply_missing_reminder(user_id):
    user = users.find_one({"_id": user_id})
    if not user:
        return
    reminder = user.get("apply_missing_reminder") or {}
    doc_ids = [doc_id for doc_id in (reminder.get("doc_ids") or []) if doc_id in VALID_APPLY_DOC_IDS]
    if not doc_ids:
        return
    still_missing = [doc_id for doc_id in doc_ids if apply_doc_id_still_missing(user, doc_id)]
    if still_missing == doc_ids:
        return
    if not still_missing:
        users.update_one({"_id": user_id}, {"$unset": {"apply_missing_reminder": ""}})
        return
    users.update_one(
        {"_id": user_id},
        {"$set": {"apply_missing_reminder.doc_ids": still_missing}},
    )


def normalize_scholarship_system(value: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in SCHOLARSHIP_SYSTEMS else "english"


def build_apply_download_filename(doc_id: str, scholarship_system: str, ext: str) -> str:
    names = APPLY_DOC_DOWNLOAD_NAMES.get(doc_id) or APPLY_DOC_LABELS.get(doc_id, doc_id)
    scholarship_system = normalize_scholarship_system(scholarship_system)
    if isinstance(names, tuple):
        _vi, zh, en = names
        base = zh if scholarship_system == "chinese" else en
    else:
        base = str(names)
    safe = re.sub(r'[<>:"/\\|?*\n\r]', "-", base).strip(" .")
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return f"{safe}{ext}"


def scholarship_system_label(value: str) -> str:
    return SCHOLARSHIP_SYSTEM_LABELS.get((value or "").strip(), "")


def normalize_apply_degree_level(value: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in APPLY_DEGREE_LEVELS else ""


def apply_degree_level_label(value: str) -> str:
    return APPLY_DEGREE_LEVEL_LABELS.get(normalize_apply_degree_level(value), "")


def apply_degree_level_short_label(value: str) -> str:
    label = apply_degree_level_label(value)
    if not label:
        return ""
    return re.sub(r"\s*\([^)]*\)", "", label).strip()


def mentee_apply_language_summary(user: dict) -> str:
    language_doc = (user.get("apply_documents") or {}).get("language") or {}
    scores = language_doc.get("language_scores") or {}
    certificate_name = str(scores.get("certificate_name") or "").strip()
    english = scores.get("english") or {}
    chinese = scores.get("chinese") or {}
    overall = str(english.get("overall") or chinese.get("overall") or "").strip()
    if certificate_name and overall:
        return f"{certificate_name} {overall}"
    return certificate_name or overall


def mentee_keeptrack_profile_summary_parts(user: dict) -> dict[str, str]:
    empty = "—"
    system = apply_degree_level_short_label(user.get("apply_degree_level", ""))
    major = mentor_apply_direction_label(user.get("mentor_apply_direction", ""))
    if not major:
        major = str(user.get("apply_direction") or "").strip()
    research = research_direction_label(user.get("research_direction", ""))
    language = mentee_apply_language_summary(user)
    return {
        "apply_system": system or empty,
        "apply_major": major or empty,
        "research_direction": research or empty,
        "apply_language": language or empty,
    }


def mentee_keeptrack_profile_summary_line(user: dict) -> str:
    parts = mentee_keeptrack_profile_summary_parts(user)
    return " - ".join(
        [
            parts["apply_system"],
            parts["apply_major"],
            parts["research_direction"],
            parts["apply_language"],
        ]
    )


def normalize_term3_2027_language_semester(value: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in TERM3_2027_LANGUAGE_VALUES else ""


def term3_2027_language_semester_label(value: str) -> str:
    return TERM3_2027_LANGUAGE_LABELS.get(normalize_term3_2027_language_semester(value), "")


def normalize_research_direction(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) > 200:
        return ""
    return raw


def research_direction_label(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered == "co":
        return "Hướng NC"
    if lowered == "khong":
        return ""
    return raw


def normalize_mentor_apply_direction(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered in MENTOR_APPLY_DIRECTIONS:
        return lowered
    return MENTOR_APPLY_DIRECTION_LEGACY.get(lowered) or MENTOR_APPLY_DIRECTION_LEGACY.get(raw) or ""


def mentor_apply_direction_label(value: str) -> str:
    code = normalize_mentor_apply_direction(value)
    if code:
        return MENTOR_APPLY_DIRECTION_LABELS.get(code, "")
    raw = (value or "").strip()
    return raw


def apply_doc_display_label(doc_id: str, scholarship_system: str) -> str:
    names = APPLY_DOC_DOWNLOAD_NAMES.get(doc_id)
    if isinstance(names, tuple):
        _vi, zh, en = names
        return zh if normalize_scholarship_system(scholarship_system) == "chinese" else en
    return APPLY_DOC_LABELS.get(doc_id, doc_id)


def count_supporting_material_files(user: dict) -> int:
    apply_docs = user.get("apply_documents") or {}
    user_id = str(user["_id"])
    count = 0
    for doc_id in SUPPORTING_MATERIAL_DOC_IDS:
        record = apply_docs.get(doc_id) or {}
        stored_name = record.get("stored_name")
        if not stored_name:
            continue
        file_path = apply_doc_upload_dir(user_id, doc_id) / stored_name
        if file_path.is_file():
            count += 1
    return count


def serialize_supporting_materials_for_admin(user: dict) -> dict:
    file_count = count_supporting_material_files(user)
    scholarship_system = normalize_scholarship_system(user.get("scholarship_system", ""))
    return {
        "doc_id": "supporting-materials",
        "label": "Gộp CV + Bài báo + Tài liệu khác",
        "download_label": apply_doc_display_label("supporting-materials", scholarship_system),
        "uploaded": file_count > 0,
        "has_file": file_count > 0,
        "mentor_only": True,
        "is_bundle": True,
        "bundle_doc_ids": list(SUPPORTING_MATERIAL_DOC_IDS),
        "bundle_file_count": file_count,
        "original_name": "",
        "uploaded_at": "",
        "mentor_status": "",
        "mentor_note": "",
        "mentor_updated_at": "",
        "mentor_unread": False,
        "mentor_viewed_at": "",
        "mentor_handles": False,
        "needs_mentor_edit": False,
        "mentor_request_active": False,
        "mentee_unread_feedback": False,
    }


def serialize_apply_document_for_admin(doc_id: str, record: dict | None, user: dict, mentee_id: str) -> dict:
    from services.misc import is_apply_document_unread

    item = serialize_apply_document(doc_id, record, user)
    scholarship_system = normalize_scholarship_system(user.get("scholarship_system", ""))
    item["label"] = APPLY_DOC_LABELS.get(doc_id, doc_id)
    item["download_label"] = apply_doc_display_label(doc_id, scholarship_system)
    item["uploaded"] = apply_document_has_content(doc_id, record, user)
    item["mentor_unread"] = is_apply_document_unread(doc_id, record, user)
    item["mentor_viewed_at"] = (
        record.get("mentor_viewed_at").isoformat() if record and record.get("mentor_viewed_at") else ""
    )
    item["mentor_processed_at"] = (
        record.get("mentor_processed_at").isoformat()
        if record and record.get("mentor_processed_at")
        else ""
    )
    item["scheduled_process_at"] = (
        record.get("scheduled_process_at").isoformat()
        if record and record.get("scheduled_process_at")
        else ""
    )
    item["mentor_processed"] = apply_document_is_processed(record)
    if item["uploaded"] and doc_id not in NO_FILE_UPLOAD_DOC_IDS and (record or {}).get("stored_name"):
        item["has_file"] = True
    else:
        item["has_file"] = False
    if doc_id == "personal-declaration":
        declaration = user.get("personal_declaration") or {}
        item["declaration_url"] = get_personal_declaration_mentor_url(declaration)
        item["declaration_has_online"] = bool(get_personal_declaration_online_url(declaration))
        item["declaration_has_local"] = bool(declaration.get("stored_name"))
        if declaration.get("stored_name"):
            item["has_file"] = True
    record_data = record or {}
    item["mentor_handles"] = bool(record_data.get("mentor_handles")) or (
        doc_id == "language" and bool((record_data.get("language_scores") or {}).get("mentor_handles_update"))
    )
    item["needs_mentor_edit"] = bool(record_data.get("needs_mentor_edit"))
    item["mentor_request_active"] = item["mentor_handles"] or item["needs_mentor_edit"]
    return item


def save_apply_document_upload(user: dict, doc_id: str, uploaded, *, uploaded_by: str, admin: dict | None = None):
    from services.admins import admin_display_name
    from bson import ObjectId

    original_name = uploaded.filename.strip()
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError("Chỉ hỗ trợ file JPG, PNG, PDF, DOC, DOCX")

    uploaded.seek(0, os.SEEK_END)
    size = uploaded.tell()
    uploaded.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise ValueError("File không được vượt quá 15MB")

    user_id = str(user["_id"])
    upload_dir = apply_doc_upload_dir(user_id, doc_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    existing = (user.get("apply_documents") or {}).get(doc_id) or {}
    old_name = existing.get("stored_name")
    if old_name:
        old_path = upload_dir / old_name
        if old_path.is_file():
            old_path.unlink()

    stored_name = f"{uuid.uuid4().hex}{ext}"
    save_path = upload_dir / stored_name
    uploaded.save(save_path)

    now = datetime.now(timezone.utc)
    record = {
        "original_name": original_name,
        "stored_name": stored_name,
        "mime_type": uploaded.mimetype or "",
        "size": size,
        "uploaded_at": now,
        "mentor_note": "",
        "mentor_updated_at": None,
        "uploaded_by": uploaded_by,
        "uploaded_by_name": admin_display_name(admin) if uploaded_by == "mentor" and admin else "",
        "mentee_unread_feedback": False,
    }

    if uploaded_by == "mentor":
        record.update(
            {
                "mentor_status": DOC_MENTOR_STATUS_APPROVED,
                "mentor_unread": False,
                "mentor_viewed_at": now,
                "mentor_processed_at": now,
                "mentee_unread_upload": True,
            },
        )
    else:
        record.update(
            {
                "mentor_status": DOC_MENTOR_STATUS_WAITING,
                "mentor_unread": True,
                "mentee_unread_upload": False,
            },
        )
        record.pop("mentor_viewed_at", None)
        record.pop("mentor_processed_at", None)
        record.pop("scheduled_process_at", None)
        if doc_id == "language":
            prev_scores = existing.get("language_scores")
            if prev_scores:
                record["language_scores"] = prev_scores

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {f"apply_documents.{doc_id}": record}},
    )

    updated_user = users.find_one({"_id": ObjectId(user["_id"])}) or user
    prune_apply_missing_reminder(ObjectId(user["_id"]), doc_id)

    if uploaded_by == "mentor":
        notify_mentee_mentor_document_upload(
            updated_user,
            doc_id,
            mentor_name=admin_display_name(admin) if admin else "",
        )
    else:
        mark_apply_document_unread(updated_user, doc_id)
        notify_mentors_mentee_document_upload(updated_user, doc_id)

    return record, updated_user


def mark_apply_document_unread(user: dict, doc_id: str) -> dict:
    """Flip a document's mentor_unread flag. Does NOT send any mentor
    notification — callers must explicitly call notify_mentors_mentee_document_upload
    (real file ready to view) or notify_mentors_mentee_document_request (no file,
    e.g. mentor_handles / needs_mentor_edit / score-only updates) right after,
    using whichever is appropriate for that event."""
    from bson import ObjectId

    set_fields = {f"apply_documents.{doc_id}.mentor_unread": True}
    if doc_id == "personal-declaration":
        set_fields[f"apply_documents.{doc_id}.mentor_status"] = DOC_MENTOR_STATUS_WAITING
    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {
            "$set": set_fields,
            "$unset": {
                f"apply_documents.{doc_id}.mentor_viewed_at": "",
                f"apply_documents.{doc_id}.mentor_processed_at": "",
                f"apply_documents.{doc_id}.scheduled_process_at": "",
            },
        },
    )
    fresh = users.find_one({"_id": ObjectId(user["_id"])}) or user
    return fresh


def skill_keys_for_language(lang: str) -> tuple[str, ...]:
    if lang == "chinese":
        return CHINESE_SKILL_KEYS
    return ENGLISH_SKILL_KEYS


def empty_language_skill_scores(lang: str = "english") -> dict:
    return {key: "" for key in skill_keys_for_language(lang)}


def parse_score_number(value: str) -> float | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(value).strip())
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def should_update_score(old_value: str, new_value: str) -> bool:
    new_value = str(new_value).strip()
    old_value = str(old_value).strip()
    if not new_value:
        return False

    old_num = parse_score_number(old_value)
    new_num = parse_score_number(new_value)
    if new_num is not None and old_num is not None:
        return new_num > old_num
    if new_num is not None and not old_value:
        return True
    return bool(new_value) and new_value != old_value


def apply_score_group_update(
    *,
    current_block: dict,
    incoming: dict,
    group_keys: tuple[str, ...],
    trigger_key: str,
    language: str,
    group_name: str,
    exam_date: str,
    now: datetime,
    new_log_entries: list,
    language_applied: list,
) -> bool:
    trigger_new = str(incoming.get(trigger_key, "")).strip()
    if not trigger_new:
        return False

    previous_trigger = current_block.get(trigger_key, "")
    if not should_update_score(previous_trigger, trigger_new):
        return False

    changed = False
    for skill in group_keys:
        new_value = str(incoming.get(skill, "")).strip()
        if not new_value:
            continue

        previous_value = current_block.get(skill, "")
        current_block[skill] = new_value
        new_log_entries.append({
            "id": uuid.uuid4().hex,
            "language": language,
            "group": group_name,
            "skill": skill,
            "value_type": "new",
            "previous_value": previous_value,
            "new_value": new_value,
            "exam_date": exam_date,
            "submitted_at": now,
        })
        if skill not in language_applied:
            language_applied.append(skill)
        changed = True

    return changed


def normalize_language_list(scores: dict) -> list[str]:
    languages = scores.get("languages") or []
    if isinstance(languages, str):
        languages = [languages]
    normalized = []
    for lang in languages:
        value = str(lang).strip().lower()
        if value in LANGUAGE_TYPES and value not in normalized:
            normalized.append(value)
    legacy = scores.get("language_type", "").strip().lower()
    if legacy in LANGUAGE_TYPES and legacy not in normalized:
        normalized.append(legacy)
    return normalized


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


def language_block_for(scores: dict, lang: str) -> dict:
    keys = skill_keys_for_language(lang)
    nested = scores.get(lang) or {}
    if isinstance(nested, dict) and any(str(nested.get(key, "")).strip() for key in keys):
        return {key: str(nested.get(key, "")).strip() for key in keys}

    legacy_keys = skill_keys_for_language(scores.get("language_type", "").strip().lower())
    if scores.get("language_type", "").strip().lower() == lang:
        return {key: str(scores.get(key, "")).strip() for key in legacy_keys}

    return empty_language_skill_scores(lang)


def log_mentee_document_event(user: dict, action: str, description: str, **extra):
    from services.admins import mentor_folder_name
    mentor_name = user.get("mentor", "").strip() or "Chung"
    mentor_activities.insert_one({
        "mentor_folder": mentor_folder_name(mentor_name),
        "mentor_name": mentor_name,
        "mentee_id": str(user["_id"]),
        "mentee_email": user.get("email", ""),
        "mentee_username": user.get("username", ""),
        "action": action,
        "description": description,
        "created_at": datetime.now(timezone.utc),
        **extra,
    })


def count_uploaded_apply_documents(user: dict) -> int:
    apply_docs = user.get("apply_documents") or {}
    count = 0
    for doc_id in VALID_APPLY_DOC_IDS:
        if doc_id == "personal-declaration":
            if personal_declaration_has_form(user.get("personal_declaration") or {}):
                count += 1
            continue
        if (apply_docs.get(doc_id) or {}).get("stored_name"):
            count += 1
    return count


def count_approved_apply_documents(user: dict) -> int:
    apply_docs = user.get("apply_documents") or {}
    count = 0
    for doc_id in VALID_APPLY_DOC_IDS:
        record = apply_docs.get(doc_id) or {}
        if not apply_document_has_content(doc_id, record, user):
            continue
        if record.get("mentor_status") == DOC_MENTOR_STATUS_APPROVED:
            count += 1
    return count


def count_submitted_apply_schools(user: dict) -> int:
    count = 0
    for row in get_apply_progress_rows_raw(user):
        if (row.get("progress") or "").strip() == "Đã submit":
            count += 1
    return count


def get_personal_declaration_online_url(record: dict | None) -> str:
    record = record or {}
    google_url = (record.get("google_doc_url") or "").strip()
    if google_url and "docs.google.com" in google_url:
        return google_url

    mode = (record.get("mode") or "").strip()
    if mode in ("google_docs", "google_docs_manual"):
        url = (record.get("url") or "").strip()
        if url and "docs.google.com" in url:
            return url

    doc_id = (record.get("google_doc_id") or "").strip()
    if not doc_id and mode in ("google_docs", "google_docs_manual"):
        doc_id = (record.get("doc_id") or "").strip()
    if doc_id and not doc_id.startswith("local-"):
        from google_docs import build_doc_url

        return build_doc_url(doc_id)

    url = (record.get("url") or "").strip()
    if "docs.google.com" in url:
        return url
    return ""


def get_personal_declaration_local_file_url(record: dict | None) -> str:
    record = record or {}
    local_url = (record.get("local_file_url") or "").strip()
    if local_url:
        return local_url

    stored_name = (record.get("stored_name") or "").strip()
    if not stored_name:
        return ""

    url = (record.get("url") or "").strip()
    if url and "personal-declaration/file" in url:
        return url
    return f"{BACKEND_PUBLIC_URL}/api/documents/personal-declaration/file"


def personal_declaration_has_form(record: dict | None) -> bool:
    record = record or {}
    if get_personal_declaration_online_url(record):
        return True
    if record.get("stored_name"):
        return True
    url = (record.get("url") or "").strip()
    return bool(url)


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


def get_personal_declaration_mentor_url(record: dict | None) -> str:
    return get_personal_declaration_online_url(record)


def serialize_personal_declaration_response(record: dict) -> dict:
    from google_docs import get_manual_copy_url

    created_at = record.get("created_at")
    online_url = get_personal_declaration_online_url(record)
    local_file_url = get_personal_declaration_local_file_url(record)
    has_online = bool(online_url)
    has_local = bool(record.get("stored_name"))
    mode = record.get("mode") or ("local_docx" if has_local and not has_online else "google_docs")

    return {
        "exists": personal_declaration_has_form(record),
        "doc_id": record.get("doc_id", ""),
        "url": online_url or local_file_url or (record.get("url") or ""),
        "google_doc_url": online_url,
        "local_file_url": local_file_url,
        "has_online_link": has_online,
        "has_local_file": has_local,
        "manual_copy_url": "" if has_online else get_manual_copy_url(),
        "title": record.get("title", ""),
        "mode": mode,
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at or "",
    }

