
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
from services.utils import *

@app.get("/api/documents/personal-declaration")
@with_db
def get_personal_declaration():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    existing = user.get("personal_declaration") or {}
    if personal_declaration_has_form(existing):
        return jsonify(serialize_personal_declaration_response(existing))

    return jsonify({"exists": False})


@app.get("/api/documents/personal-declaration/file")
@with_db
def download_personal_declaration_file():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    record = user.get("personal_declaration") or {}
    stored_name = (record.get("stored_name") or "").strip()
    if record.get("mode") != "local_docx" or not stored_name:
        return jsonify({"detail": "Chưa có file kê khai docx."}), 404

    from services import storage
    from services.files import make_inline_file_response

    data = storage.read_bytes(storage.storage_key(user["_id"], "personal-declaration", stored_name))
    if data is None:
        return jsonify({"detail": "File kê khai không tồn tại."}), 404

    return make_inline_file_response(
        data,
        stored_name,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.patch("/api/documents/personal-declaration")
@with_db
def register_personal_declaration_link():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    from google_docs import build_doc_url, parse_google_doc_id

    existing = user.get("personal_declaration") or {}
    data = request.get_json(silent=True) or {}
    doc_url = (data.get("url") or "").strip()
    doc_id = parse_google_doc_id(doc_url)
    if not doc_id:
        return jsonify({"detail": "Link Google Docs không hợp lệ."}), 400

    google_url = build_doc_url(doc_id)
    existing_online_id = (
        (existing.get("google_doc_id") or "").strip()
        or (
            (existing.get("doc_id") or "").strip()
            if (existing.get("mode") or "") in ("google_docs", "google_docs_manual")
            else ""
        )
    )
    if existing_online_id == doc_id:
        return jsonify(serialize_personal_declaration_response(existing))

    from bson import ObjectId

    now = datetime.now(timezone.utc)
    if existing.get("stored_name"):
        record = {
            **existing,
            "google_doc_id": doc_id,
            "google_doc_url": google_url,
            "url": google_url,
            "mode": "local_with_google",
            "updated_at": now,
        }
        if not record.get("local_file_url"):
            record["local_file_url"] = get_personal_declaration_local_file_url(existing)
        if not record.get("created_at"):
            record["created_at"] = now
    elif not personal_declaration_has_form(existing):
        record = {
            "doc_id": doc_id,
            "google_doc_id": doc_id,
            "google_doc_url": google_url,
            "url": google_url,
            "title": f"Kê khai thông tin - {user.get('username', '')}",
            "mode": "google_docs_manual",
            "created_at": now,
        }
    else:
        record = {
            **existing,
            "doc_id": doc_id,
            "google_doc_id": doc_id,
            "google_doc_url": google_url,
            "url": google_url,
            "mode": "google_docs_manual",
            "updated_at": now,
        }
        if not record.get("created_at"):
            record["created_at"] = now

    users.update_one({"_id": ObjectId(user["_id"])}, {"$set": {"personal_declaration": record}})
    fresh = users.find_one({"_id": ObjectId(user["_id"])}) or user
    fresh = mark_apply_document_unread(fresh, "personal-declaration")
    notify_mentors_mentee_document_upload(fresh, "personal-declaration")
    prune_apply_missing_reminder(ObjectId(user["_id"]), "personal-declaration")
    saved = fresh.get("personal_declaration") or record
    return jsonify(serialize_personal_declaration_response(saved))


@app.post("/api/documents/personal-declaration")
@with_db
def create_personal_declaration():
    from services.misc import attempt_create_personal_declaration, save_personal_declaration_record
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    from bson import ObjectId

    existing = user.get("personal_declaration") or {}
    if personal_declaration_has_form(existing):
        return jsonify(serialize_personal_declaration_response(existing))

    try:
        from google_docs import create_personal_declaration_doc  # noqa: F401
    except ImportError:
        return jsonify({
            "detail": "Thiếu thư viện Google API. Chạy: pip install -r requirements.txt",
        }), 503

    try:
        doc_info = attempt_create_personal_declaration(user)
    except RuntimeError as exc:
        return jsonify({"detail": str(exc)}), 503

    if doc_info.get("needs_manual_copy"):
        return jsonify(
            {
                "exists": False,
                "needs_manual_copy": True,
                "copy_url": doc_info.get("copy_url", ""),
                "mode": "manual_copy",
            },
        )

    record = {
        **doc_info,
        "created_at": datetime.now(timezone.utc),
    }

    updated = save_personal_declaration_record(user["_id"], record)
    if updated:
        saved = updated.get("personal_declaration") or record
        updated = mark_apply_document_unread(updated, "personal-declaration")
        notify_mentors_mentee_document_upload(updated, "personal-declaration")
        prune_apply_missing_reminder(ObjectId(user["_id"]), "personal-declaration")
        return jsonify(serialize_personal_declaration_response(saved)), 201

    fresh = users.find_one({"_id": ObjectId(user["_id"])})
    saved = (fresh or {}).get("personal_declaration") or {}
    if personal_declaration_has_form(saved):
        return jsonify(serialize_personal_declaration_response(saved))

    return jsonify({"detail": "Không thể tạo form kê khai. Thử lại sau."}), 500


@app.get("/api/documents/apply")
@with_db
def list_apply_documents():
    from services.misc import count_mentee_unread_mentor_uploads, serialize_apply_missing_reminder
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    from bson import ObjectId

    sync_apply_missing_reminder(ObjectId(user["_id"]))
    user = users.find_one({"_id": ObjectId(user["_id"])}) or user

    apply_docs = user.get("apply_documents") or {}
    items = [
        serialize_apply_document(doc_id, apply_docs.get(doc_id), user)
        for doc_id in sorted(VALID_APPLY_DOC_IDS)
    ]
    return jsonify({
        "items": items,
        "uploaded_count": count_uploaded_apply_documents(user),
        "total_count": len(VALID_APPLY_DOC_IDS),
        "feedback_unread_count": count_mentee_feedback_unread(user),
        "mentor_upload_unread_count": count_mentee_unread_mentor_uploads(user),
        "missing_reminder": serialize_apply_missing_reminder(user),
        "missing_reminder_unread": apply_missing_reminder_unread(user),
        "preferred_schools_note": user.get("preferred_schools_note", ""),
    })


@app.patch("/api/documents/apply/preferred-schools-note")
@with_db
def update_preferred_schools_note():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()
    if len(note) > 2000:
        return jsonify({"detail": "Ghi chú không được vượt quá 2000 ký tự"}), 400

    from bson import ObjectId

    old_note = (user.get("preferred_schools_note") or "").strip()
    now = datetime.now(timezone.utc)
    set_fields = {
        "preferred_schools_note": note,
        "preferred_schools_note_updated_at": now,
    }
    if note != old_note:
        set_fields["preferred_schools_note_mentor_unread"] = True

    users.update_one({"_id": ObjectId(user["_id"])}, {"$set": set_fields})
    if note != old_note:
        fresh = users.find_one({"_id": ObjectId(user["_id"])}) or user
        preview = note if len(note) <= 400 else f"{note[:397]}..."
        notify_mentors_mentee_activity(
            fresh,
            action="preferred_schools",
            title=f"{fresh.get('full_name') or fresh.get('username', 'Mentee')} cập nhật trường ưa thích",
            description=preview or "Mentee đã cập nhật ghi chú trường ưa thích.",
        )
    return jsonify({
        "note": note,
        "updated_at": now.isoformat(),
        "mentor_unread": note != old_note,
    })


@app.get("/api/documents/apply-progress")
@with_db
def get_apply_progress():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    return jsonify(serialize_apply_progress_payload(user, "mentee"))


@app.post("/api/documents/apply-progress/ack")
@with_db
def mentee_ack_apply_progress():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    from bson import ObjectId

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {"apply_progress_mentee_unread": False}},
    )
    fresh = users.find_one({"_id": ObjectId(user["_id"])}) or user
    return jsonify(serialize_apply_progress_payload(fresh, "mentee"))


@app.put("/api/documents/apply-progress")
@with_db
def mentee_update_apply_progress():
    from services.misc import extract_apply_progress_fields, validate_apply_progress_field_values
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    submitted_rows = data.get("rows")
    if not isinstance(submitted_rows, list) or not submitted_rows:
        return jsonify({"detail": "Danh sách dòng không hợp lệ"}), 400

    current_rows = {row["row_num"]: row for row in get_apply_progress_rows_raw(user)}
    now = datetime.now(timezone.utc)
    updated_rows = []
    submitted_row_nums: list[int] = []

    for item in submitted_rows:
        if not isinstance(item, dict):
            continue
        row_num = int(item.get("row_num") or 0)
        if row_num not in current_rows:
            continue
        current = current_rows[row_num]
        submitted_fields = extract_apply_progress_fields(item)
        validation_error = validate_apply_progress_field_values(submitted_fields, "mentee")
        if validation_error:
            return jsonify({"detail": validation_error}), 400
        published_fields = extract_apply_progress_fields(current)

        if apply_progress_fields_equal(submitted_fields, published_fields):
            pending = None
            pending_status = ""
            pending_at = None
            rejection_note = ""
        else:
            pending = submitted_fields
            pending_status = APPLY_PROGRESS_PENDING_WAITING
            pending_at = now
            rejection_note = ""
            submitted_row_nums.append(row_num)

        updated_rows.append(
            {
                "row_num": row_num,
                **published_fields,
                "pending": pending,
                "pending_status": pending_status,
                "pending_at": pending_at,
                "rejection_note": rejection_note,
            },
        )

    if not updated_rows:
        return jsonify({"detail": "Không có dòng hợp lệ để cập nhật"}), 400

    untouched = [
        row
        for num, row in current_rows.items()
        if num not in {item["row_num"] for item in updated_rows}
    ]
    merged = sorted(updated_rows + untouched, key=lambda row: row["row_num"])

    from bson import ObjectId

    for row_num in submitted_row_nums:
        push_apply_progress_activity(
            user["_id"],
            {
                "type": "mentee_request",
                "row_num": row_num,
                "processed": False,
                "summary": f"Mentee chỉnh sửa dòng {row_num} chờ duyệt",
            },
        )
    if submitted_row_nums:
        rows_label = ", ".join(str(num) for num in submitted_row_nums)
        notify_mentors_mentee_activity(
            user,
            action="apply_progress_request",
            title=f"{user.get('full_name') or user.get('username', 'Mentee')} cập nhật tiến độ apply",
            description=f"Mentee gửi chỉnh sửa dòng {rows_label} chờ mentor duyệt.",
        )
        from services.mentee_l1_email import notify_l1_mentee_apply_progress_edit

        notify_l1_mentee_apply_progress_edit(user, submitted_row_nums)

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {
            "$set": {
                "apply_progress_rows": merged,
                "apply_progress_updated_at": now,
                "apply_progress_mentor_unread": True,
            },
        },
    )
    fresh = users.find_one({"_id": ObjectId(user["_id"])}) or user
    return jsonify(serialize_apply_progress_payload(fresh, "mentee"))


@app.get("/api/documents/hdnk-nckh")
@with_db
def get_hdnk_nckh():
    from services.misc import serialize_hdnk_nckh_payload
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    if not is_thanh_ha_mentee(user):
        return jsonify({"detail": "Mục này chỉ dành cho mentee team Thanh Hà."}), 403

    return jsonify(serialize_hdnk_nckh_payload(user, for_mentee=True))


@app.put("/api/documents/hdnk-nckh")
@with_db
def update_hdnk_nckh():
    from services.misc import serialize_hdnk_nckh_payload
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    if not is_thanh_ha_mentee(user):
        return jsonify({"detail": "Mục này chỉ dành cho mentee team Thanh Hà."}), 403

    data = request.get_json(silent=True) or {}
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        return jsonify({"detail": "Danh sách mục không hợp lệ"}), 400

    existing = get_hdnk_nckh_entries_raw(user)
    normalized: list[dict] = []
    for item in raw_entries[:HDNK_NCKH_MAX_ENTRIES]:
        if not isinstance(item, dict):
            continue
        entry_id = (item.get("entry_id") or "").strip()
        match = next((row for row in existing if row.get("entry_id") == entry_id), None)
        normalized.append(
            normalize_hdnk_nckh_entry(
                item,
                entry_id=match.get("entry_id") if match else None,
                preserve_mentor=match,
            ),
        )

    validation_error = validate_hdnk_nckh_entries(normalized)
    if validation_error:
        return jsonify({"detail": validation_error}), 400

    from bson import ObjectId

    now = datetime.now(timezone.utc)
    changed = not hdnk_nckh_entries_equal(existing, normalized)
    set_fields: dict = {"hdnk_nckh_entries": normalized}
    if changed:
        set_fields.update(
            {
                "hdnk_nckh_mentee_updated_at": now,
                "hdnk_nckh_l1_unread": True,
                "hdnk_nckh_reminder_unread": False,
                "hdnk_nckh_last_reminder_sent_at": None,
            },
        )

    users.update_one({"_id": ObjectId(user["_id"])}, {"$set": set_fields})
    fresh = users.find_one({"_id": ObjectId(user["_id"])}) or user
    if changed:
        try:
            notify_mentors_mentee_activity(
                fresh,
                action="hdnk_nckh_update",
                title=f"{fresh.get('full_name') or fresh.get('username', 'Mentee')} cập nhật HDNK + NCKH",
                description=summarize_hdnk_nckh_changes(
                    existing,
                    normalized,
                    fallback="Mentee vừa cập nhật bảng Keep track HDNK + NCKH.",
                ),
            )
        except Exception:
            pass
    return jsonify(serialize_hdnk_nckh_payload(fresh, for_mentee=True))


@app.post("/api/documents/apply/<doc_id>/upload")
@with_db
def upload_apply_document(doc_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    if doc_id not in VALID_APPLY_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    if doc_id in NO_FILE_UPLOAD_DOC_IDS:
        return jsonify({"detail": "Mục này dùng Google Docs, không tải file trực tiếp"}), 400

    if doc_id in MENTEE_UPLOAD_BLOCKED_DOC_IDS:
        return jsonify({
            "detail": "Mục này do mentor tải lên — bạn chỉ cần xem và tải file.",
        }), 403

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"detail": "Chưa chọn file để tải lên"}), 400

    try:
        record, updated_user = save_apply_document_upload(
            user,
            doc_id,
            uploaded,
            uploaded_by="mentee",
        )
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 400

    return jsonify(serialize_apply_document(doc_id, record, updated_user)), 201


@app.get("/api/documents/apply/<doc_id>/file")
@with_db
def download_apply_document(doc_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    if doc_id not in VALID_APPLY_DOC_IDS or doc_id in NO_FILE_UPLOAD_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    record = (user.get("apply_documents") or {}).get(doc_id) or {}
    stored_name = record.get("stored_name")
    if not stored_name:
        return jsonify({"detail": "Chưa có file tải lên"}), 404

    from services import storage
    from services.files import make_inline_file_response

    data = storage.read_bytes(storage.storage_key(user["_id"], doc_id, stored_name))
    if data is None:
        return jsonify({"detail": "File không tồn tại trên hệ thống"}), 404

    return make_inline_file_response(
        data,
        record.get("original_name") or stored_name,
        record.get("mime_type") or None,
    )


@app.put("/api/documents/apply/language/scores")
@with_db
def update_language_scores():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    languages = data.get("languages") or []
    if isinstance(languages, str):
        languages = [languages]
    languages = [str(lang).strip().lower() for lang in languages if str(lang).strip().lower() in LANGUAGE_TYPES]
    languages = list(dict.fromkeys(languages))

    if not languages:
        return jsonify({"detail": "Chọn ít nhất Tiếng Anh hoặc Tiếng Trung"}), 400

    score_date = data.get("score_updated_at", "").strip()
    if score_date and not re.match(r"^\d{4}-\d{2}-\d{2}$", score_date):
        return jsonify({"detail": "Ngày cập nhật điểm không hợp lệ (YYYY-MM-DD)"}), 400

    def parse_block(lang: str) -> dict:
        block = data.get(lang) or {}
        if not isinstance(block, dict):
            block = {}
        return {key: str(block.get(key, "")).strip() for key in skill_keys_for_language(lang)}

    from bson import ObjectId

    existing = (user.get("apply_documents") or {}).get("language") or {}
    existing_scores = existing.get("language_scores") or {}
    now = datetime.now(timezone.utc)

    scores = {
        "languages": languages,
        "certificate_name": str(data.get("certificate_name", "")).strip(),
        "english": parse_block("english"),
        "chinese": parse_block("chinese"),
        "score_updated_at": score_date or now.strftime("%Y-%m-%d"),
        "updated_at": now,
        "score_updates": existing_scores.get("score_updates") or [],
        "mentor_handles_update": bool(existing_scores.get("mentor_handles_update")),
        "mentor_handles_update_at": existing_scores.get("mentor_handles_update_at"),
    }

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {
            "$set": {
                "apply_documents.language.language_scores": scores,
                "apply_documents.language.mentor_status": DOC_MENTOR_STATUS_WAITING,
            }
        },
        upsert=False,
    )

    updated = users.find_one({"_id": ObjectId(user["_id"])})
    language_record = (updated.get("apply_documents") or {}).get("language") or {}
    language_record["language_scores"] = scores
    fresh = mark_apply_document_unread(updated, "language")
    notify_mentors_mentee_document_request(fresh, "language", "cập nhật điểm")
    language_record = (fresh.get("apply_documents") or {}).get("language") or {}
    language_record["language_scores"] = scores
    sync_apply_missing_reminder(ObjectId(user["_id"]))
    return jsonify(serialize_apply_document("language", language_record, fresh))


@app.patch("/api/documents/apply/language/mentor-handles")
@with_db
def set_language_mentor_handles():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    mentor_handles = bool(data.get("mentor_handles_update"))

    from bson import ObjectId

    existing = (user.get("apply_documents") or {}).get("language") or {}
    existing_scores = existing.get("language_scores") or {}
    now = datetime.now(timezone.utc)

    updated_scores = {
        **existing_scores,
        "mentor_handles_update": mentor_handles,
        "mentor_handles_update_at": now if mentor_handles else None,
        "updated_at": now,
    }

    update_fields = {
        "apply_documents.language.language_scores": updated_scores,
        "apply_documents.language.mentor_handles": mentor_handles,
    }
    if mentor_handles:
        update_fields["apply_documents.language.mentor_unread"] = True
        update_fields["apply_documents.language.mentor_status"] = DOC_MENTOR_STATUS_WAITING

    users.update_one({"_id": ObjectId(user["_id"])}, {"$set": update_fields}, upsert=False)

    if mentor_handles:
        updated_user = users.find_one({"_id": ObjectId(user["_id"])}) or user
        updated_user = mark_apply_document_unread(updated_user, "language")
        notify_mentors_mentee_document_request(updated_user, "language", "mentor làm")
        log_mentee_document_event(
            user,
            "language_mentor_handles",
            f"Mentee {user.get('full_name') or user.get('username')} yêu cầu mentor cập nhật điểm ngoại ngữ.",
        )

    updated = users.find_one({"_id": ObjectId(user["_id"])})
    language_record = (updated.get("apply_documents") or {}).get("language") or {}
    language_record["language_scores"] = updated_scores
    return jsonify(serialize_apply_document("language", language_record, updated))


@app.patch("/api/documents/apply/<doc_id>/mentee-request")
@with_db
def set_apply_document_mentee_request(doc_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    if doc_id not in VALID_APPLY_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    data = request.get_json(silent=True) or {}
    if "mentor_handles" not in data and "needs_mentor_edit" not in data:
        return jsonify({"detail": "Không có dữ liệu để cập nhật"}), 400

    from bson import ObjectId

    existing = (user.get("apply_documents") or {}).get(doc_id) or {}
    now = datetime.now(timezone.utc)
    mentor_handles = (
        bool(data.get("mentor_handles"))
        if "mentor_handles" in data
        else bool(existing.get("mentor_handles"))
    )
    needs_mentor_edit = (
        bool(data.get("needs_mentor_edit"))
        if "needs_mentor_edit" in data
        else bool(existing.get("needs_mentor_edit"))
    )

    set_fields = {
        f"apply_documents.{doc_id}.mentor_handles": mentor_handles,
        f"apply_documents.{doc_id}.needs_mentor_edit": needs_mentor_edit,
        f"apply_documents.{doc_id}.mentor_status": DOC_MENTOR_STATUS_WAITING,
    }
    unset_fields = {}
    if mentor_handles or needs_mentor_edit:
        set_fields[f"apply_documents.{doc_id}.mentor_unread"] = True
        set_fields[f"apply_documents.{doc_id}.mentor_request_at"] = now
        unset_fields[f"apply_documents.{doc_id}.mentor_viewed_at"] = ""
    else:
        set_fields[f"apply_documents.{doc_id}.mentor_unread"] = False

    if doc_id == "language":
        existing_scores = existing.get("language_scores") or {}
        updated_scores = {
            **existing_scores,
            "mentor_handles_update": mentor_handles,
            "mentor_handles_update_at": now if mentor_handles else None,
        }
        set_fields[f"apply_documents.{doc_id}.language_scores"] = updated_scores

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {
            "$set": set_fields,
            **({"$unset": unset_fields} if unset_fields else {}),
        },
    )

    updated = users.find_one({"_id": ObjectId(user["_id"])}) or user
    if mentor_handles or needs_mentor_edit:
        updated = mark_apply_document_unread(updated, doc_id)
        has_existing_file = bool(existing.get("stored_name")) and doc_id not in NO_FILE_UPLOAD_DOC_IDS
        if has_existing_file:
            notify_mentors_mentee_document_upload(updated, doc_id)
        else:
            request_note = "mentor làm" if mentor_handles else "cần sửa"
            notify_mentors_mentee_document_request(updated, doc_id, request_note)

    labels = []
    if mentor_handles:
        labels.append("Mentor làm")
    if needs_mentor_edit:
        labels.append("Gói cơ bản_Cần mentor sửa")
    if labels:
        log_mentee_document_event(
            updated,
            "mentee_request",
            f"{updated.get('full_name') or updated.get('username')} — "
            f"{APPLY_DOC_LABELS.get(doc_id, doc_id)}: {', '.join(labels)}",
        )

    record = (updated.get("apply_documents") or {}).get(doc_id) or {}
    return jsonify(serialize_apply_document(doc_id, record, updated))


@app.post("/api/documents/apply/language/score-update")
@with_db
def submit_language_score_update():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    exam_date = str(data.get("exam_date", "")).strip()
    if exam_date and not re.match(r"^\d{4}-\d{2}-\d{2}$", exam_date):
        return jsonify({"detail": "Ngày thi không hợp lệ (YYYY-MM-DD)"}), 400

    from bson import ObjectId

    existing = (user.get("apply_documents") or {}).get("language") or {}
    existing_scores = existing.get("language_scores") or {}
    languages = normalize_language_list(existing_scores)

    if not languages:
        return jsonify({"detail": "Lưu thông tin chứng chỉ trước khi cập nhật điểm thi mới"}), 400

    now = datetime.now(timezone.utc)
    updated_scores = {
        **existing_scores,
        "languages": languages,
        "english": language_block_for(existing_scores, "english"),
        "chinese": language_block_for(existing_scores, "chinese"),
    }
    new_log_entries = []
    applied_summary = []

    for language in languages:
        incoming = data.get(language) or {}
        if not isinstance(incoming, dict):
            continue

        current_block = dict(updated_scores.get(language) or empty_language_skill_scores(language))
        language_applied = []
        exam_day = exam_date or now.strftime("%Y-%m-%d")

        if language == "english":
            apply_score_group_update(
                current_block=current_block,
                incoming=incoming,
                group_keys=ENGLISH_OVERALL_GROUP,
                trigger_key="overall",
                language=language,
                group_name="overall",
                exam_date=exam_day,
                now=now,
                new_log_entries=new_log_entries,
                language_applied=language_applied,
            )
        elif language == "chinese":
            apply_score_group_update(
                current_block=current_block,
                incoming=incoming,
                group_keys=CHINESE_OVERALL_GROUP,
                trigger_key="overall",
                language=language,
                group_name="overall",
                exam_date=exam_day,
                now=now,
                new_log_entries=new_log_entries,
                language_applied=language_applied,
            )
            apply_score_group_update(
                current_block=current_block,
                incoming=incoming,
                group_keys=CHINESE_HSKK_GROUP,
                trigger_key="hskk",
                language=language,
                group_name="hskk",
                exam_date=exam_day,
                now=now,
                new_log_entries=new_log_entries,
                language_applied=language_applied,
            )

        if language_applied:
            updated_scores[language] = current_block
            latest_overall = current_block.get("overall", "")
            updated_scores["latest_exam"] = {
                **(existing_scores.get("latest_exam") or {}),
                language: {
                    "overall": latest_overall,
                    "exam_date": exam_date or now.strftime("%Y-%m-%d"),
                    "updated_skills": language_applied,
                    "updated_at": now.isoformat(),
                },
            }
            applied_summary.append({
                "language": language,
                "skills": language_applied,
                "overall": latest_overall,
            })

    if not new_log_entries:
        return jsonify({
            "detail": (
                "Không có nhóm điểm nào được cập nhật. "
                "Overall/HSKK mới phải cao hơn điểm hiện tại mới cập nhật cả nhóm tương ứng."
            ),
        }), 400

    updated_scores["updated_at"] = now
    updated_scores["score_updates"] = (existing_scores.get("score_updates") or []) + new_log_entries
    if exam_date:
        updated_scores["score_updated_at"] = exam_date

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {
            "$set": {
                "apply_documents.language.language_scores": updated_scores,
                "apply_documents.language.mentor_status": DOC_MENTOR_STATUS_WAITING,
                "apply_documents.language.mentor_unread": True,
            },
            "$unset": {"apply_documents.language.mentor_viewed_at": ""},
        },
    )

    summary_parts = []
    for item in applied_summary:
        lang_label = LANGUAGE_LABELS.get(item["language"], item["language"])
        skills_text = ", ".join(SKILL_LABELS.get(skill, skill) for skill in item["skills"])
        overall_text = f" — Overall mới: {item['overall']}" if item.get("overall") else ""
        summary_parts.append(f"{lang_label}: {skills_text}{overall_text}")

    log_mentee_document_event(
        user,
        "language_score_update",
        f"{user.get('full_name') or user.get('username')} cập nhật điểm thi mới ({'; '.join(summary_parts)})",
        applied=applied_summary,
        exam_date=exam_date or now.strftime("%Y-%m-%d"),
        certificate_name=existing_scores.get("certificate_name", ""),
    )

    updated = users.find_one({"_id": ObjectId(user["_id"])})
    if existing.get("stored_name"):
        notify_mentors_mentee_document_upload(updated or user, "language")
    else:
        notify_mentors_mentee_document_request(updated or user, "language", "cập nhật điểm")
    sync_apply_missing_reminder(ObjectId(user["_id"]))
    updated = users.find_one({"_id": ObjectId(user["_id"])}) or updated
    language_record = (updated.get("apply_documents") or {}).get("language") or {}
    language_record["language_scores"] = updated_scores
    response = serialize_apply_document("language", language_record, updated)
    response["applied_updates"] = applied_summary
    return jsonify(response), 201


@app.post("/api/documents/apply/ack-missing-reminder")
@with_db
def mentee_ack_missing_reminder():
    from services.misc import serialize_apply_missing_reminder
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    from bson import ObjectId

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {"apply_missing_reminder.mentee_unread": False}},
    )
    fresh = users.find_one({"_id": ObjectId(user["_id"])}) or user
    return jsonify({
        "message": "Đã xem",
        "missing_reminder": serialize_apply_missing_reminder(fresh),
        "missing_reminder_unread": apply_missing_reminder_unread(fresh),
    })


@app.post("/api/documents/apply/<doc_id>/ack-upload")
@with_db
def mentee_ack_document_upload(doc_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    if doc_id not in MENTOR_UPLOADABLE_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    from bson import ObjectId

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {f"apply_documents.{doc_id}.mentee_unread_upload": False}},
    )
    fresh = users.find_one({"_id": ObjectId(user["_id"])}) or user
    record = (fresh.get("apply_documents") or {}).get(doc_id) or {}
    return jsonify(serialize_apply_document(doc_id, record, fresh))


@app.post("/api/documents/apply/<doc_id>/ack-feedback")
@with_db
def mentee_ack_document_feedback(doc_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response

    if doc_id not in VALID_APPLY_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    from bson import ObjectId

    users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {f"apply_documents.{doc_id}.mentee_unread_feedback": False}},
    )
    fresh = users.find_one({"_id": ObjectId(user["_id"])}) or user
    record = (fresh.get("apply_documents") or {}).get(doc_id) or {}
    return jsonify(serialize_apply_document(doc_id, record, fresh))

