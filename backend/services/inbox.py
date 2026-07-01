
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

def render_email_action_page(*, title: str, message: str, success: bool = True):
    accent = "#059669" if success else "#eb2233"
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
</head>
<body style="font-family: Arial, sans-serif; background:#fdf5f2; margin:0; padding:2rem;">
  <div style="max-width:520px; margin:0 auto; background:#fff; border-radius:12px; padding:2rem; box-shadow:0 8px 30px rgba(0,0,0,0.08);">
    <h1 style="color:{accent}; font-size:1.35rem; margin-top:0;">{title}</h1>
    <p style="line-height:1.6; color:#333;">{message}</p>
    <p style="margin-top:1.5rem;">
      <a href="{os.getenv('MENTOR_ADMIN_URL', 'http://localhost:5174/access-requests')}"
         style="color:#eb2233; font-weight:600;">Mở trang quản lý mentor</a>
    </p>
  </div>
</body>
</html>"""
    return make_response(html, 200 if success else 400)


def render_inbox_snooze_html(task: dict) -> str:
    from inbox_tasks import inbox_snooze_urls

    snooze_urls = inbox_snooze_urls(BACKEND_PUBLIC_URL, task)
    if not snooze_urls:
        return ""
    links = " · ".join(
        f'<a href="{item["url"]}" style="color:#666;text-decoration:underline;">{item["label"]}</a>'
        for item in snooze_urls
    )
    return (
        f'<p style="font-size:0.85rem;color:#666;margin-top:1rem;">'
        f"Nhắc lại sau: {links}</p>"
    )


def render_email_view_page(*, title: str, body_html: str, file_url: str = ""):
    embed = ""
    if file_url:
        embed = f"""
        <div style="margin-top:1rem;border:1px solid #eee;border-radius:8px;overflow:hidden;">
          <iframe src="{file_url}" title="Xem tài liệu" style="width:100%;height:70vh;border:0;background:#fafafa;"></iframe>
        </div>
        """
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
</head>
<body style="font-family: Arial, sans-serif; background:#fdf5f2; margin:0; padding:1rem;">
  <div style="max-width:720px; margin:0 auto; background:#fff; border-radius:12px; padding:1.25rem; box-shadow:0 8px 30px rgba(0,0,0,0.08);">
    <h1 style="color:#eb2233; font-size:1.25rem; margin-top:0;">{title}</h1>
    {body_html}
    {embed}
  </div>
</body>
</html>"""
    return make_response(html, 200)


def apply_inbox_view_side_effects(task: dict):
    from bson import ObjectId

    now = datetime.now(timezone.utc)
    doc_id = task.get("doc_id") or ""
    mentee_id = task.get("mentee_id") or ""
    action = task.get("action") or ""

    if not mentee_id:
        return

    try:
        mentee_oid = ObjectId(mentee_id)
    except Exception:
        return

    if action == "document_upload" and doc_id:
        users.update_one(
            {"_id": mentee_oid},
            {
                "$set": {
                    f"apply_documents.{doc_id}.mentor_viewed_at": now,
                }
            },
        )


def apply_inbox_confirm_side_effects(task: dict):
    from bson import ObjectId

    now = datetime.now(timezone.utc)
    doc_id = task.get("doc_id") or ""
    mentee_id = task.get("mentee_id") or ""
    action = task.get("action") or ""

    if not mentee_id:
        return

    try:
        mentee_oid = ObjectId(mentee_id)
    except Exception:
        return

    if action == "document_upload" and doc_id:
        users.update_one(
            {"_id": mentee_oid},
            {
                "$set": {
                    f"apply_documents.{doc_id}.mentor_viewed_at": now,
                    f"apply_documents.{doc_id}.mentor_processed_at": now,
                },
                "$unset": {f"apply_documents.{doc_id}.scheduled_process_at": ""},
            },
        )
    elif action == "feedback":
        feedback_app.update_many(
            {"user_id": mentee_oid, "mentor_unread": True},
            {"$set": {"mentor_unread": False}},
        )
    elif action == "apply_progress_request":
        users.update_one(
            {"_id": mentee_oid},
            {"$set": {"apply_progress_mentor_unread": False}},
        )
    elif action == "hdnk_nckh_update":
        users.update_one(
            {"_id": mentee_oid},
            {
                "$set": {
                    "hdnk_nckh_l1_unread": False,
                    "hdnk_nckh_reminder_unread": False,
                    "hdnk_nckh_l1_ack_at": now,
                }
            },
        )
    elif action == "preferred_schools":
        users.update_one(
            {"_id": mentee_oid},
            {"$set": {"preferred_schools_note_mentor_unread": False}},
        )


def build_inbox_document_payload(task: dict):
    from services.apply_documents import apply_doc_upload_dir, build_apply_download_filename, normalize_scholarship_system
    from bson import ObjectId

    doc_id = task.get("doc_id") or ""
    mentee_id = task.get("mentee_id") or ""
    if not doc_id or doc_id in NO_FILE_UPLOAD_DOC_IDS:
        return None, "Mục này không có file PDF để xem trực tiếp"

    try:
        mentee_oid = ObjectId(mentee_id)
    except Exception:
        return None, "Mentee không hợp lệ"

    mentee = users.find_one({"_id": mentee_oid})
    if not mentee:
        return None, "Mentee không tồn tại"

    record = (mentee.get("apply_documents") or {}).get(doc_id) or {}
    stored_name = record.get("stored_name")
    if not stored_name:
        return None, "Chưa có file để xem"

    scholarship_system = normalize_scholarship_system(mentee.get("scholarship_system", ""))
    from services import storage

    try:
        from document_processing import process_document_file

        with storage.local_path(storage.storage_key(mentee["_id"], doc_id, stored_name)) as file_path:
            if file_path is None:
                return None, "File không tồn tại trên hệ thống"
            payload, out_ext = process_document_file(
                file_path,
                output_format="pdf",
                variant="original",
            )
    except Exception as exc:
        return None, str(exc) or "Không xử lý được file"

    download_name = build_apply_download_filename(doc_id, scholarship_system, out_ext)
    mimetype = "application/pdf" if out_ext.lower() == ".pdf" else record.get("mime_type")
    return (payload, download_name, mimetype), None


def send_daily_inbox_summary_for_mentor(mentor_name: str, tasks: list[dict]) -> bool:
    # In-app reminder scheduling only. Daily inbox email is sent once at 10:00 VN
    # via services.mentor_inbox_digest (not per-item / not per-reminder).
    return bool(tasks)


def create_email_action_tokens(admin_id) -> dict[str, str]:
    expires_at = datetime.now(timezone.utc) + timedelta(days=EMAIL_ACTION_TOKEN_DAYS)
    tokens = {
        "approve": secrets.token_urlsafe(32),
        "reject": secrets.token_urlsafe(32),
        "expires_at": expires_at,
    }
    from bson import ObjectId

    admins.update_one({"_id": ObjectId(admin_id)}, {"$set": {"email_action_tokens": tokens}})
    return tokens


def email_action_urls(tokens: dict[str, str]) -> dict[str, str]:
    return {
        "approve": f"{BACKEND_PUBLIC_URL}/api/admin/access-requests/email/approve?token={tokens['approve']}",
        "reject": f"{BACKEND_PUBLIC_URL}/api/admin/access-requests/email/reject?token={tokens['reject']}",
        "admin_page": os.getenv("MENTOR_ADMIN_URL", "http://localhost:5174/access-requests"),
    }

