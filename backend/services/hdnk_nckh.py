
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

def normalize_hdnk_nckh_entry(
    raw: dict | None,
    entry_id: str | None = None,
    preserve_mentor: dict | None = None,
) -> dict:
    source = raw or {}
    participation = (source.get("participation_type") or "").strip()
    if participation == HDNK_NCKH_GROUP_INTERNAL_LEGACY:
        participation = HDNK_NCKH_GROUP_INTERNAL
    if participation not in HDNK_NCKH_PARTICIPATION_TYPES:
        participation = ""
    progress = (source.get("progress") or "").strip()
    if progress not in HDNK_NCKH_PROGRESS_OPTIONS:
        progress = ""
    has_award = bool(source.get("has_award"))
    award_level = (source.get("award_level") or "").strip()
    if not has_award or award_level not in HDNK_NCKH_AWARD_LEVELS:
        award_level = ""
    zalo_group_name = (source.get("zalo_group_name") or "").strip()
    if participation != HDNK_NCKH_GROUP_INTERNAL:
        zalo_group_name = ""

    mentor_note = ""
    reminder_due_at = None
    if preserve_mentor:
        mentor_note = (preserve_mentor.get("mentor_note") or "").strip()
        reminder_due_at = preserve_mentor.get("reminder_due_at")
    else:
        mentor_note = (source.get("mentor_note") or "").strip()
        reminder_raw = source.get("reminder_due_at")
        if isinstance(reminder_raw, str) and reminder_raw.strip():
            date_part = reminder_raw.strip()[:10]
            try:
                reminder_due_at = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                reminder_due_at = parse_iso_datetime(reminder_raw)
        elif reminder_raw:
            reminder_due_at = parse_iso_datetime(reminder_raw)

    return {
        "entry_id": entry_id or source.get("entry_id") or str(uuid.uuid4()),
        "start_date": (source.get("start_date") or "").strip(),
        "category": (source.get("category") or "").strip(),
        "participation_type": participation,
        "zalo_group_name": zalo_group_name,
        "progress": progress,
        "has_award": has_award,
        "award_level": award_level,
        "mentor_note": mentor_note,
        "reminder_due_at": reminder_due_at,
    }


def format_hdnk_reminder_date(value) -> str:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime("%Y-%m-%d")


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


def serialize_hdnk_nckh_payload(user: dict, for_mentee: bool = False) -> dict:
    from services.admins import is_thanh_ha_mentee

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


def hdnk_nckh_mentee_snapshot(entry: dict) -> dict:
    return serialize_hdnk_nckh_entry(entry, for_mentee=True)


def get_hdnk_nckh_entries_raw(user: dict) -> list[dict]:
    stored = user.get("hdnk_nckh_entries")
    if not isinstance(stored, list):
        return []
    entries: list[dict] = []
    for item in stored[:HDNK_NCKH_MAX_ENTRIES]:
        if not isinstance(item, dict):
            continue
        entries.append(normalize_hdnk_nckh_entry(item))
    return entries


def hdnk_nckh_entries_equal(left: list[dict], right: list[dict]) -> bool:
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if hdnk_nckh_mentee_snapshot(a) != hdnk_nckh_mentee_snapshot(b):
            return False
    return True


HDNK_NCKH_DIFF_FIELDS = (
    ("start_date", "Ngày bắt đầu"),
    ("category", "Hạng mục tham gia"),
    ("participation_type", "Hình thức tham gia"),
    ("zalo_group_name", "Tên nhóm Zalo"),
    ("progress", "Tiến độ"),
    ("award", "Giải thưởng"),
    ("mentor_note", "Ghi chú của mentor"),
    ("reminder_due_at", "Ngày nhắc nhở"),
)


def _hdnk_nckh_field_display(entry: dict, field: str) -> str:
    if field == "award":
        if entry.get("has_award"):
            return entry.get("award_level") or "có giải"
        return ""
    value = entry.get(field)
    if field == "reminder_due_at":
        return format_hdnk_reminder_date(value)
    if isinstance(value, bool):
        return "có" if value else "không"
    return (value or "").strip() if isinstance(value, str) else (value or "")


def _hdnk_nckh_entry_label(entry: dict) -> str:
    return entry.get("category") or "(chưa đặt tên)"


def summarize_hdnk_nckh_changes(
    before: list[dict],
    after: list[dict],
    fallback: str = "Bảng Keep track HDNK + NCKH đã được cập nhật.",
) -> str:
    """Build a concise, Vietnamese, human-readable diff between two HDNK+NCKH entry lists.

    Entries are matched by ``entry_id``. Entries only in ``after`` are reported as added,
    entries only in ``before`` as removed, and entries in both with differing fields as
    changed (listing old -> new per field). Falls back to ``fallback`` if no differences
    are identifiable, so callers never receive a blank description.
    """
    before_by_id = {entry.get("entry_id"): entry for entry in before if entry.get("entry_id")}
    after_by_id = {entry.get("entry_id"): entry for entry in after if entry.get("entry_id")}

    lines: list[str] = []

    for entry in after:
        entry_id = entry.get("entry_id")
        old_entry = before_by_id.get(entry_id) if entry_id else None
        if old_entry is None:
            details = []
            start_date = _hdnk_nckh_field_display(entry, "start_date")
            if start_date:
                details.append(f"ngày {start_date}")
            participation_type = _hdnk_nckh_field_display(entry, "participation_type")
            if participation_type:
                details.append(participation_type)
            zalo_group_name = _hdnk_nckh_field_display(entry, "zalo_group_name")
            if zalo_group_name:
                details.append(f"nhóm {zalo_group_name}")
            progress = _hdnk_nckh_field_display(entry, "progress")
            if progress:
                details.append(progress)
            award = _hdnk_nckh_field_display(entry, "award")
            if award:
                details.append(award)
            detail_text = ", ".join(details)
            label = _hdnk_nckh_entry_label(entry)
            lines.append(f"Thêm mục mới: {label}" + (f" ({detail_text})" if detail_text else ""))
            continue

        diffs = []
        for field, field_label in HDNK_NCKH_DIFF_FIELDS:
            old_value = _hdnk_nckh_field_display(old_entry, field)
            new_value = _hdnk_nckh_field_display(entry, field)
            if old_value != new_value:
                diffs.append(f"{field_label}: {old_value or '(trống)'} → {new_value or '(trống)'}")
        if diffs:
            label = _hdnk_nckh_entry_label(entry) or _hdnk_nckh_entry_label(old_entry)
            lines.append(f"{label}: " + "; ".join(diffs))

    for entry in before:
        entry_id = entry.get("entry_id")
        if entry_id and entry_id not in after_by_id:
            lines.append(f"Đã xóa mục: {_hdnk_nckh_entry_label(entry)}")

    if not lines:
        return fallback
    return "\n".join(lines)


def validate_hdnk_nckh_entries(entries: list[dict]) -> str | None:
    if len(entries) > HDNK_NCKH_MAX_ENTRIES:
        return f"Tối đa {HDNK_NCKH_MAX_ENTRIES} mục"
    for index, item in enumerate(entries, start=1):
        normalized = normalize_hdnk_nckh_entry(item)
        if not normalized["start_date"]:
            return f"Mục {index}: cần ngày bắt đầu"
        if not normalized["category"]:
            return f"Mục {index}: cần hạng mục tham gia"
        if not normalized["participation_type"]:
            return f"Mục {index}: cần chọn loại tham gia"
        if normalized["participation_type"] == HDNK_NCKH_GROUP_INTERNAL and not normalized["zalo_group_name"]:
            return f"Mục {index}: cần tên nhóm Zalo"
        if not normalized["progress"]:
            return f"Mục {index}: cần tiến độ"
        if normalized["has_award"] and not normalized["award_level"]:
            return f"Mục {index}: cần chọn loại giải"
    return None


def ensure_hdnk_nckh_reminder_sync(user: dict) -> dict:
    from services.admins import is_thanh_ha_mentee

    if not is_thanh_ha_mentee(user):
        return user

    now = datetime.now(timezone.utc)
    set_fields: dict = {}
    entries = get_hdnk_nckh_entries_raw(user)

    if user.get("hdnk_nckh_l1_unread"):
        mentee_updated = parse_iso_datetime(user.get("hdnk_nckh_mentee_updated_at"))
        if mentee_updated and now >= mentee_updated + timedelta(days=HDNK_NCKH_REMINDER_DAYS):
            last_sent = parse_iso_datetime(user.get("hdnk_nckh_last_reminder_sent_at"))
            should_notify = not last_sent or now >= last_sent + timedelta(days=HDNK_NCKH_REMINDER_DAYS)
            if should_notify and not user.get("hdnk_nckh_reminder_unread"):
                set_fields["hdnk_nckh_reminder_unread"] = True
                set_fields["hdnk_nckh_last_reminder_sent_at"] = now

    for entry in entries:
        custom_due = parse_iso_datetime(entry.get("reminder_due_at"))
        if custom_due and now >= custom_due:
            if not user.get("hdnk_nckh_reminder_unread"):
                set_fields["hdnk_nckh_reminder_unread"] = True
            break

    if set_fields:
        from bson import ObjectId

        users.update_one({"_id": ObjectId(user["_id"])}, {"$set": set_fields})
        user = {**user, **set_fields}
    return user

