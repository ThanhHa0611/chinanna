
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

def count_mentee_feedback_unread(user: dict) -> int:
    apply_docs = user.get("apply_documents") or {}
    count = 0
    for doc_id in VALID_APPLY_DOC_IDS:
        record = apply_docs.get(doc_id) or {}
        if record.get("mentee_unread_feedback"):
            count += 1
    return count


def feedback_messages(doc: dict) -> list[dict]:
    stored = doc.get("messages") or []
    if stored:
        result = []
        for index, message in enumerate(stored):
            created_at = message.get("created_at")
            result.append({
                "id": message.get("id") or f"msg-{index}",
                "sender": message.get("sender", "mentee"),
                "content": message.get("content", ""),
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at or "",
            })
        return result

    messages = []
    if doc.get("content"):
        created_at = doc.get("created_at")
        messages.append({
            "id": "initial",
            "sender": "mentee",
            "content": doc.get("content", ""),
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else "",
        })
    if doc.get("admin_reply"):
        processed_at = doc.get("processed_at") or doc.get("created_at")
        messages.append({
            "id": "legacy-reply",
            "sender": "mentor",
            "content": doc.get("admin_reply", ""),
            "created_at": processed_at.isoformat() if hasattr(processed_at, "isoformat") else "",
        })
    return messages


def feedback_mentor_unread(doc: dict) -> bool:
    if "mentor_unread" in doc:
        return bool(doc.get("mentor_unread"))
    return doc.get("status", FEEDBACK_STATUS_PENDING) == FEEDBACK_STATUS_PENDING


def feedback_mentee_unread(doc: dict) -> bool:
    if "mentee_unread" in doc:
        return bool(doc.get("mentee_unread"))
    return bool(doc.get("admin_reply")) and doc.get("status") == FEEDBACK_STATUS_DONE


def count_mentor_unread_feedback(user_id) -> int:
    from bson import ObjectId

    try:
        oid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
    except Exception:
        return 0
    return feedback_app.count_documents({
        "user_id": oid,
        "$or": [
            {"mentor_unread": True},
            {"mentor_unread": {"$exists": False}, "status": FEEDBACK_STATUS_PENDING},
        ],
    })


def count_mentee_unread_feedback_threads(user_id) -> int:
    from bson import ObjectId

    try:
        oid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
    except Exception:
        return 0
    return feedback_app.count_documents({"user_id": oid, "mentee_unread": True})


def admin_can_see_feedback_processor(admin: dict | None) -> bool:
    from services.admins import is_super_admin
    if not admin:
        return False
    if is_super_admin(admin):
        return True
    if admin.get("is_level1_mentor"):
        return True
    mentor = (admin.get("mentor_name") or "").strip()
    display = (admin.get("full_name") or admin.get("username") or "").strip()
    return mentor in MENTOR_OPTIONS and display == mentor


def resolve_feedback_processor_name(doc: dict) -> str:
    stored = (doc.get("processed_by_name") or "").strip()
    if stored:
        return stored
    processor_id = doc.get("processed_by")
    if not processor_id:
        return ""
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        processor = admins.find_one({"_id": ObjectId(processor_id)})
    except InvalidId:
        return ""
    if not processor:
        return ""
    return processor.get("full_name") or processor.get("email") or processor.get("username") or ""


def feedback_response(doc: dict, admin: dict | None = None) -> dict:
    messages = feedback_messages(doc)
    first_mentee = next((item for item in messages if item["sender"] == "mentee"), None)
    result = {
        "id": str(doc["_id"]),
        "content": doc.get("content") or (first_mentee or {}).get("content", ""),
        "status": doc.get("status", FEEDBACK_STATUS_PENDING),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else "",
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else "",
        "processed_at": doc["processed_at"].isoformat() if doc.get("processed_at") else "",
        "admin_reply": doc.get("admin_reply", ""),
        "username": doc.get("username", ""),
        "email": doc.get("email", ""),
        "user_id": str(doc["user_id"]) if doc.get("user_id") else "",
        "messages": messages,
        "mentor_unread": feedback_mentor_unread(doc),
        "mentee_unread": feedback_mentee_unread(doc),
        "mentee_status_label": doc.get("mentee_status_label", ""),
    }
    if admin and admin_can_see_feedback_processor(admin):
        result["processed_by_name"] = resolve_feedback_processor_name(doc)
    return result

