
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
    if participation != "nhóm Trơn Tru":
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


def hdnk_nckh_mentee_snapshot(entry: dict) -> dict:
    from services.misc import serialize_hdnk_nckh_entry
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
        if normalized["participation_type"] == "nhóm Trơn Tru" and not normalized["zalo_group_name"]:
            return f"Mục {index}: cần tên nhóm Zalo"
        if not normalized["progress"]:
            return f"Mục {index}: cần tiến độ"
        if normalized["has_award"] and not normalized["award_level"]:
            return f"Mục {index}: cần chọn loại giải"
    return None


def ensure_hdnk_nckh_reminder_sync(user: dict) -> dict:
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

