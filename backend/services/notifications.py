
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

def mentor_branch_notify_emails(mentor_name: str) -> list[str]:
    # Chỉ gửi về email trưởng branch — các tài khoản mentor thường chỉ nhận
    # mail cấp quyền (duyệt mentee đăng ký), không nhận bảng tin hàng ngày.
    branch = (mentor_name or "").strip()
    email = (MENTOR_BRANCH_NOTIFY_EMAILS.get(branch, "") or "").strip().lower()
    return [email] if email else []


def notify_mentors_mentee_document_upload(user: dict, doc_id: str):
    mentor_name = (user.get("mentor") or "").strip()
    if not mentor_name:
        return

    from inbox_tasks import create_mentor_inbox_task

    doc_label = APPLY_DOC_LABELS.get(doc_id, doc_id)
    mentee_name = user.get("full_name") or user.get("username") or user.get("email", "")
    mentee_id = str(user.get("_id", ""))

    create_mentor_inbox_task(
        mentor_inbox,
        mentor_name=mentor_name,
        mentee_id=mentee_id,
        mentee_name=mentee_name,
        mentee_email=user.get("email", ""),
        action="document_upload",
        title=f"{mentee_name} upload {doc_label}",
        description=f"Mentee vừa nộp giấy tờ: {doc_label}",
        doc_id=doc_id,
        has_file=doc_id not in NO_FILE_UPLOAD_DOC_IDS,
    )


def notify_mentors_mentee_document_request(user: dict, doc_id: str, request_note: str = ""):
    """Notify mentors that a mentee flagged a document for mentor attention
    (e.g. "mentor làm hộ" / "cần sửa" / score update) without an actual file
    to preview. Unlike notify_mentors_mentee_document_upload, this never
    promises a viewable file in the inbox task."""
    mentor_name = (user.get("mentor") or "").strip()
    if not mentor_name:
        return

    from inbox_tasks import create_mentor_inbox_task

    doc_label = APPLY_DOC_LABELS.get(doc_id, doc_id)
    mentee_name = user.get("full_name") or user.get("username") or user.get("email", "")
    mentee_id = str(user.get("_id", ""))
    note_suffix = f" ({request_note})" if request_note else ""

    create_mentor_inbox_task(
        mentor_inbox,
        mentor_name=mentor_name,
        mentee_id=mentee_id,
        mentee_name=mentee_name,
        mentee_email=user.get("email", ""),
        action="document_request",
        title=f"{mentee_name} yêu cầu xử lí {doc_label}{note_suffix}",
        description=f"Mentee cần mentor xử lí giấy tờ: {doc_label}{note_suffix}",
        doc_id=doc_id,
        has_file=False,
    )


def notify_mentee_mentor_document_upload(user: dict, doc_id: str, mentor_name: str = ""):
    from inbox_tasks import create_mentee_view_task, mentee_doc_urls
    from services.mentee_email_prefs import mentee_email_notify_documents_enabled

    doc_label = APPLY_DOC_LABELS.get(doc_id, doc_id)
    mentee_name = user.get("full_name") or user.get("username") or user.get("email", "")
    profile_url = os.getenv("MENTEE_PROFILE_URL", "http://localhost:5173/profile").strip()
    mentor_label = mentor_name or user.get("mentor") or "Mentor"
    mentee_id = str(user.get("_id", ""))

    view_url = ""
    if doc_id not in NO_FILE_UPLOAD_DOC_IDS:
        task = create_mentee_view_task(
            mentor_inbox,
            mentee_id=mentee_id,
            mentee_email=user.get("email", ""),
            mentee_name=mentee_name,
            action="mentor_document_upload",
            title=f"Mentor tải lên {doc_label}",
            description=f"Mentor {mentor_label} đã tải lên {doc_label} cho bạn.",
            doc_id=doc_id,
            mentor_name=mentor_label,
        )
        view_url = mentee_doc_urls(BACKEND_PUBLIC_URL, task)["view"]

    if not mentee_email_notify_documents_enabled(user):
        return

    try:
        from email_notify import send_mentee_mentor_document_upload_email

        send_mentee_mentor_document_upload_email(
            to_email=user.get("email", ""),
            mentee_name=mentee_name,
            mentor_name=mentor_label,
            document_label=doc_label,
            profile_url=profile_url,
            view_url=view_url,
        )
    except Exception:
        pass


def notify_mentors_mentee_feedback(user: dict, content: str):
    mentor_name = (user.get("mentor") or "").strip()
    if not mentor_name:
        return

    from inbox_tasks import create_mentor_inbox_task

    mentee_name = user.get("full_name") or user.get("username") or user.get("email", "")
    preview = content if len(content) <= 500 else f"{content[:497]}..."

    create_mentor_inbox_task(
        mentor_inbox,
        mentor_name=mentor_name,
        mentee_id=str(user.get("_id", "")),
        mentee_name=mentee_name,
        mentee_email=user.get("email", ""),
        action="feedback",
        title=f"{mentee_name} gửi phản hồi",
        description=preview,
    )


def notify_mentors_mentee_activity(
    user: dict,
    *,
    action: str,
    title: str,
    description: str,
    doc_id: str = "",
    reminder_hours: int = 24,
):
    mentor_name = (user.get("mentor") or "").strip()
    if not mentor_name:
        return

    from inbox_tasks import create_mentor_inbox_task

    mentee_name = user.get("full_name") or user.get("username") or user.get("email", "")
    create_mentor_inbox_task(
        mentor_inbox,
        mentor_name=mentor_name,
        mentee_id=str(user.get("_id", "")),
        mentee_name=mentee_name,
        mentee_email=user.get("email", ""),
        action=action,
        title=title,
        description=description,
        doc_id=doc_id,
        reminder_hours=reminder_hours,
    )


def notify_mentee_mentor_activity(
    mentee: dict,
    *,
    action: str,
    title: str,
    description: str,
    doc_id: str = "",
    mentor_name: str = "",
    mentor_admin: dict | None = None,
):
    from inbox_tasks import create_mentee_view_task, mentee_doc_urls
    from services.mentee_email_prefs import (
        is_document_email_action,
        is_profile_activity_status_action,
        mentee_email_notify_documents_enabled,
    )

    mentee_name = mentee.get("full_name") or mentee.get("username") or mentee.get("email", "")
    mentor_label = mentor_name or (mentor_admin or {}).get("mentor_name") or mentee.get("mentor") or "Mentor"
    profile_url = os.getenv("MENTEE_PROFILE_URL", "http://localhost:5173/profile").strip()
    view_url = ""
    if doc_id and doc_id not in NO_FILE_UPLOAD_DOC_IDS:
        task = create_mentee_view_task(
            mentor_inbox,
            mentee_id=str(mentee.get("_id", "")),
            mentee_email=mentee.get("email", ""),
            mentee_name=mentee_name,
            action=action,
            title=title,
            description=description,
            doc_id=doc_id,
            mentor_name=mentor_label,
        )
        view_url = mentee_doc_urls(BACKEND_PUBLIC_URL, task)["view"]
    elif description:
        task = create_mentee_view_task(
            mentor_inbox,
            mentee_id=str(mentee.get("_id", "")),
            mentee_email=mentee.get("email", ""),
            mentee_name=mentee_name,
            action=action,
            title=title,
            description=description,
            mentor_name=mentor_label,
        )
        view_url = mentee_doc_urls(BACKEND_PUBLIC_URL, task)["view"]

    if is_profile_activity_status_action(action):
        return

    send_email = True
    if is_document_email_action(action):
        send_email = mentee_email_notify_documents_enabled(mentee)

    if not send_email:
        return

    try:
        from email_notify import send_mentee_activity_email

        send_mentee_activity_email(
            to_email=mentee.get("email", ""),
            mentee_name=mentee_name,
            title=title,
            description=description,
            mentor_name=mentor_label,
            view_url=view_url,
            profile_url=profile_url,
        )
    except Exception:
        pass


def notify_mentee_inbox_processed(task: dict):
    from bson import ObjectId

    mentee_id = task.get("mentee_id") or ""
    if not mentee_id:
        return

    try:
        mentee = users.find_one({"_id": ObjectId(mentee_id)})
    except Exception:
        return
    if not mentee:
        return

    action = task.get("action") or ""
    action_titles = {
        "document_upload": "Mentor đã xử lí giấy tờ của bạn",
        "feedback": "Mentor đã xử lí phản hồi của bạn",
        "apply_progress_request": "Mentor đã xử lí tiến độ apply",
        "hdnk_nckh_update": "Mentor đã xử lí HDNK + NCKH",
        "preferred_schools": "Mentor đã xử lí ghi chú trường ưa thích",
    }
    title = action_titles.get(action, "Mentor đã xử lí yêu cầu của bạn")
    description = task.get("description") or task.get("title") or ""
    notify_mentee_mentor_activity(
        mentee,
        action=f"inbox_processed_{action or 'generic'}",
        title=title,
        description=f"Mentor đã xác nhận đã xử lí: {description}",
        doc_id=task.get("doc_id") or "",
        mentor_name=task.get("mentor_name") or "",
    )

