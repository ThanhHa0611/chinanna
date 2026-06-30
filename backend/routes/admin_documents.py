
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

@app.get("/api/admin/mentees/<mentee_id>/documents/<doc_id>/file")
@with_db
def admin_view_mentee_document_file(mentee_id: str, doc_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if doc_id not in VALID_APPLY_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    if doc_id == "personal-declaration":
        declaration = mentee.get("personal_declaration") or {}
        stored_name = (declaration.get("stored_name") or "").strip()
        if not stored_name:
            return jsonify({"detail": "Chưa có file kê khai docx trên hệ thống."}), 404

        file_path = UPLOAD_ROOT / str(mentee["_id"]) / "personal-declaration" / stored_name
        if not file_path.is_file():
            return jsonify({"detail": "File kê khai không tồn tại."}), 404

        return send_file(
            file_path,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=False,
            download_name=stored_name,
        )

    if doc_id in NO_FILE_UPLOAD_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    record = (mentee.get("apply_documents") or {}).get(doc_id) or {}
    stored_name = record.get("stored_name")
    if not stored_name:
        return jsonify({"detail": "Chưa có file tải lên"}), 404

    file_path = apply_doc_upload_dir(str(mentee["_id"]), doc_id) / stored_name
    if not file_path.is_file():
        return jsonify({"detail": "File không tồn tại trên hệ thống"}), 404

    return send_file(
        file_path,
        as_attachment=False,
        download_name=record.get("original_name") or stored_name,
        mimetype=record.get("mime_type") or None,
    )


@app.get("/api/admin/mentees/<mentee_id>/documents/<doc_id>/download")
@with_db
def admin_download_mentee_document(mentee_id: str, doc_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if doc_id not in VALID_APPLY_DOC_IDS or doc_id in NO_FILE_UPLOAD_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    record = (mentee.get("apply_documents") or {}).get(doc_id) or {}
    stored_name = record.get("stored_name")
    if not stored_name:
        return jsonify({"detail": "Chưa có file để tải"}), 404

    file_path = apply_doc_upload_dir(str(mentee["_id"]), doc_id) / stored_name
    if not file_path.is_file():
        return jsonify({"detail": "File không tồn tại trên hệ thống"}), 404

    output_format = (request.args.get("format") or "pdf").strip().lower()
    variant = (request.args.get("variant") or "original").strip().lower()
    if output_format not in {"pdf", "png"}:
        return jsonify({"detail": "Định dạng tải xuống không hợp lệ"}), 400
    if variant not in {"original", "compress_3mb", "compress_1mb"}:
        return jsonify({"detail": "Tùy chọn dung lượng không hợp lệ"}), 400

    scholarship_system = normalize_scholarship_system(mentee.get("scholarship_system", ""))

    try:
        from document_processing import process_document_file

        payload, out_ext = process_document_file(
            file_path,
            output_format=output_format,
            variant=variant,
        )
    except Exception as exc:
        return jsonify({"detail": str(exc) or "Không xử lý được file tải xuống"}), 400

    download_name = build_apply_download_filename(doc_id, scholarship_system, out_ext)
    mimetype = "image/png" if out_ext.lower() == ".png" else record.get("mime_type")
    return make_download_response(payload, download_name, mimetype)


@app.get("/api/admin/mentees/<mentee_id>/documents/supporting-materials/download")
@with_db
def admin_download_supporting_materials(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    output_format = (request.args.get("format") or "pdf").strip().lower()
    variant = (request.args.get("variant") or "original").strip().lower()
    if output_format not in {"pdf", "png"}:
        return jsonify({"detail": "Định dạng tải xuống không hợp lệ"}), 400
    if variant not in {"original", "compress_3mb", "compress_1mb"}:
        return jsonify({"detail": "Tùy chọn dung lượng không hợp lệ"}), 400

    scholarship_system = normalize_scholarship_system(mentee.get("scholarship_system", ""))
    apply_docs = mentee.get("apply_documents") or {}
    zip_entries = []

    try:
        from document_processing import build_zip_bytes, process_document_file

        for doc_id in SUPPORTING_MATERIAL_DOC_IDS:
            record = apply_docs.get(doc_id) or {}
            stored_name = record.get("stored_name")
            if not stored_name:
                continue
            file_path = apply_doc_upload_dir(str(mentee["_id"]), doc_id) / stored_name
            if not file_path.is_file():
                continue
            payload, out_ext = process_document_file(
                file_path,
                output_format=output_format,
                variant=variant,
            )
            entry_name = build_apply_download_filename(doc_id, scholarship_system, out_ext)
            zip_entries.append((entry_name, payload))
    except Exception as exc:
        return jsonify({"detail": str(exc) or "Không xử lý được gói tài liệu"}), 400

    if not zip_entries:
        return jsonify({"detail": "Chưa có CV, bài báo hoặc tài liệu khác để tải"}), 404

    zip_name = build_apply_download_filename("supporting-materials", scholarship_system, ".zip")
    zip_bytes = build_zip_bytes(zip_entries)
    return make_download_response(zip_bytes, zip_name, "application/zip")


@app.post("/api/admin/mentees/<mentee_id>/documents/download-selected")
@with_db
def admin_download_selected_documents(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    body = request.get_json(silent=True) or {}
    raw_doc_ids = body.get("doc_ids") or []
    if not isinstance(raw_doc_ids, list) or not raw_doc_ids:
        return jsonify({"detail": "Chọn ít nhất một giấy tờ để tải"}), 400

    doc_ids = []
    for doc_id in raw_doc_ids:
        if doc_id not in VALID_APPLY_DOC_IDS or doc_id in NO_FILE_UPLOAD_DOC_IDS:
            return jsonify({"detail": f"Mục giấy tờ không hợp lệ: {doc_id}"}), 400
        if doc_id not in doc_ids:
            doc_ids.append(doc_id)

    output_format = (body.get("format") or "pdf").strip().lower()
    variant = (body.get("variant") or "original").strip().lower()
    if output_format not in {"pdf", "png"}:
        return jsonify({"detail": "Định dạng tải xuống không hợp lệ"}), 400
    if variant not in {"original", "compress_3mb", "compress_1mb"}:
        return jsonify({"detail": "Tùy chọn dung lượng không hợp lệ"}), 400

    scholarship_system = normalize_scholarship_system(mentee.get("scholarship_system", ""))
    apply_docs = mentee.get("apply_documents") or {}

    try:
        from document_processing import build_zip_bytes, process_document_file

        zip_entries = []
        for doc_id in doc_ids:
            record = apply_docs.get(doc_id) or {}
            stored_name = record.get("stored_name")
            if not stored_name:
                return jsonify({"detail": f"Chưa có file cho mục {APPLY_DOC_LABELS.get(doc_id, doc_id)}"}), 404
            file_path = apply_doc_upload_dir(str(mentee["_id"]), doc_id) / stored_name
            if not file_path.is_file():
                return jsonify({"detail": "File không tồn tại trên hệ thống"}), 404
            payload, out_ext = process_document_file(
                file_path,
                output_format=output_format,
                variant=variant,
            )
            entry_name = build_apply_download_filename(doc_id, scholarship_system, out_ext)
            zip_entries.append((entry_name, payload))
    except Exception as exc:
        return jsonify({"detail": str(exc) or "Không xử lý được file tải xuống"}), 400

    if len(zip_entries) == 1:
        entry_name, payload = zip_entries[0]
        mimetype = "image/png" if entry_name.lower().endswith(".png") else "application/pdf"
        return make_download_response(payload, entry_name, mimetype)

    zip_name = build_apply_download_filename("supporting-materials", scholarship_system, ".zip")
    zip_bytes = build_zip_bytes(zip_entries)
    return make_download_response(zip_bytes, zip_name, "application/zip")


@app.post("/api/admin/mentees/<mentee_id>/documents/approve-selected")
@with_db
def admin_bulk_approve_documents(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    body = request.get_json(silent=True) or {}
    raw_doc_ids = body.get("doc_ids") or []
    if not isinstance(raw_doc_ids, list) or not raw_doc_ids:
        return jsonify({"detail": "Chọn ít nhất một giấy tờ để duyệt"}), 400

    from bson import ObjectId

    apply_docs = mentee.get("apply_documents") or {}
    doc_ids: list[str] = []
    for doc_id in raw_doc_ids:
        if doc_id not in VALID_APPLY_DOC_IDS:
            return jsonify({"detail": f"Mục giấy tờ không hợp lệ: {doc_id}"}), 400
        if doc_id in doc_ids:
            continue
        record = apply_docs.get(doc_id) or {}
        if not apply_document_has_content(doc_id, record, mentee):
            return jsonify({
                "detail": f"Mentee chưa có nội dung cho mục {APPLY_DOC_LABELS.get(doc_id, doc_id)}",
            }), 400
        if record.get("mentor_status") == DOC_MENTOR_STATUS_APPROVED:
            continue
        doc_ids.append(doc_id)

    if not doc_ids:
        return jsonify({"detail": "Các giấy tờ đã chọn đều đã được duyệt trước đó"}), 400

    now = datetime.now(timezone.utc)
    updates: dict = {}
    for doc_id in doc_ids:
        record = apply_docs.get(doc_id) or {}
        updates[f"apply_documents.{doc_id}.mentor_status"] = DOC_MENTOR_STATUS_APPROVED
        updates[f"apply_documents.{doc_id}.mentor_note"] = record.get("mentor_note") or ""
        updates[f"apply_documents.{doc_id}.mentor_updated_at"] = now
        updates[f"apply_documents.{doc_id}.mentor_viewed_at"] = now
        updates[f"apply_documents.{doc_id}.mentor_processed_at"] = now
        updates[f"apply_documents.{doc_id}.mentee_unread_feedback"] = True
        if doc_id == "personal-declaration" and not record:
            updates[f"apply_documents.{doc_id}"] = {
                "mentor_status": DOC_MENTOR_STATUS_APPROVED,
                "mentor_note": "",
                "mentor_updated_at": now,
                "mentor_viewed_at": now,
                "mentor_processed_at": now,
                "mentee_unread_feedback": True,
            }

    unset_fields = {f"apply_documents.{doc_id}.scheduled_process_at": "" for doc_id in doc_ids}
    users.update_one({"_id": ObjectId(mentee["_id"])}, {"$set": updates, "$unset": unset_fields})

    for doc_id in doc_ids:
        sync_apply_inbox_confirm(mentee_id, doc_id, via="app")

    labels = [APPLY_DOC_LABELS.get(doc_id, doc_id) for doc_id in doc_ids]
    notify_mentee_mentor_activity(
        mentee,
        action="document_bulk_approve",
        title=f"Mentor duyệt {len(doc_ids)} giấy tờ",
        description="Mentor đã duyệt: " + ", ".join(labels),
        mentor_admin=admin,
    )
    log_mentor_activity(
        admin,
        "document_bulk_approve",
        f"Duyệt hàng loạt {len(doc_ids)} giấy tờ — {mentee.get('email', mentee_id)}: {', '.join(labels)}",
        mentee_id=mentee_id,
    )
    if is_l2_mentor_admin(admin):
        push_l2_mentor_activity(
            mentee_id,
            admin,
            "documents",
            "document_bulk_approve",
            f"Duyệt hàng loạt {len(doc_ids)} giấy tờ",
        )

    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    items = [
        serialize_apply_document_for_admin(
            doc_id,
            (fresh.get("apply_documents") or {}).get(doc_id) or {},
            fresh,
            mentee_id,
        )
        for doc_id in doc_ids
    ]
    return jsonify({
        "message": f"Đã duyệt {len(doc_ids)} giấy tờ",
        "approved_count": len(doc_ids),
        "items": items,
    })


@app.post("/api/admin/mentees/<mentee_id>/documents/<doc_id>/view")
@with_db
def admin_mark_mentee_document_viewed(mentee_id: str, doc_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if doc_id not in VALID_APPLY_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    from bson import ObjectId

    now = datetime.now(timezone.utc)
    apply_docs = mentee.get("apply_documents") or {}
    record = apply_docs.get(doc_id) or {}

    if not apply_document_has_content(doc_id, record, mentee):
        return jsonify({"detail": "Mentee chưa có giấy tờ này"}), 400

    updates = {
        f"apply_documents.{doc_id}.mentor_viewed_at": now,
    }
    if doc_id == "personal-declaration" and not record:
        updates[f"apply_documents.{doc_id}"] = {
            "mentor_viewed_at": now,
            "mentor_status": DOC_MENTOR_STATUS_WAITING,
        }

    users.update_one({"_id": ObjectId(mentee["_id"])}, {"$set": updates})
    sync_apply_inbox_view(mentee_id, doc_id)

    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    fresh_record = (fresh.get("apply_documents") or {}).get(doc_id) or {}
    item = serialize_apply_document_for_admin(doc_id, fresh_record, fresh, mentee_id)
    return jsonify(item)


@app.post("/api/admin/mentees/<mentee_id>/documents/<doc_id>/process")
@with_db
def admin_mark_mentee_document_processed(mentee_id: str, doc_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if doc_id not in VALID_APPLY_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    from bson import ObjectId

    now = datetime.now(timezone.utc)
    apply_docs = mentee.get("apply_documents") or {}
    record = apply_docs.get(doc_id) or {}

    if not apply_document_has_content(doc_id, record, mentee):
        return jsonify({"detail": "Mentee chưa có giấy tờ này"}), 400

    updates = {
        f"apply_documents.{doc_id}.mentor_viewed_at": now,
        f"apply_documents.{doc_id}.mentor_processed_at": now,
    }
    users.update_one(
        {"_id": ObjectId(mentee["_id"])},
        {
            "$set": updates,
            "$unset": {f"apply_documents.{doc_id}.scheduled_process_at": ""},
        },
    )
    sync_apply_inbox_confirm(mentee_id, doc_id, via="app")

    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    fresh_record = (fresh.get("apply_documents") or {}).get(doc_id) or {}
    item = serialize_apply_document_for_admin(doc_id, fresh_record, fresh, mentee_id)
    return jsonify(item)


@app.patch("/api/admin/mentees/<mentee_id>/documents/<doc_id>/schedule")
@with_db
def admin_schedule_mentee_document_process(mentee_id: str, doc_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if doc_id not in VALID_APPLY_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    reminder_at_raw = (data.get("scheduled_at") or data.get("reminder_at") or "").strip()
    if not reminder_at_raw:
        return jsonify({"detail": "Cần scheduled_at (ISO datetime)"}), 400

    try:
        reminder_at = datetime.fromisoformat(reminder_at_raw.replace("Z", "+00:00"))
    except ValueError:
        return jsonify({"detail": "Thời gian hẹn không hợp lệ"}), 400

    if reminder_at.tzinfo is None:
        reminder_at = reminder_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if reminder_at <= now:
        return jsonify({"detail": "Thời gian hẹn phải ở tương lai"}), 400

    from bson import ObjectId

    apply_docs = mentee.get("apply_documents") or {}
    record = apply_docs.get(doc_id) or {}
    if not apply_document_has_content(doc_id, record, mentee):
        return jsonify({"detail": "Mentee chưa có giấy tờ này"}), 400

    users.update_one(
        {"_id": ObjectId(mentee["_id"])},
        {"$set": {f"apply_documents.{doc_id}.scheduled_process_at": reminder_at}},
    )
    sync_apply_inbox_schedule(mentee_id, doc_id, reminder_at=reminder_at)

    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    fresh_record = (fresh.get("apply_documents") or {}).get(doc_id) or {}
    item = serialize_apply_document_for_admin(doc_id, fresh_record, fresh, mentee_id)
    return jsonify({"message": "Đã hẹn ngày xử lí", "item": item})


@app.get("/api/admin/language-updates")
@with_db
def admin_language_updates():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    query = mentee_filter_for_admin(admin)
    cursor = users.find(query).sort("created_at", -1)
    items = []

    for mentee in cursor:
        language_record = (mentee.get("apply_documents") or {}).get("language") or {}
        scores = language_record.get("language_scores") or {}
        if scores.get("mentor_handles_update"):
            items.append({
                "id": f"mentor-handles-{mentee['_id']}",
                "update_type": "mentor_handles",
                "mentee_id": str(mentee["_id"]),
                "mentee_name": mentee.get("full_name", ""),
                "mentee_username": mentee.get("username", ""),
                "mentee_email": mentee.get("email", ""),
                "mentor": mentee.get("mentor", ""),
                "certificate_name": scores.get("certificate_name", ""),
                "language": "",
                "language_label": "—",
                "group": "",
                "skill": "",
                "skill_label": "Mentor làm",
                "value_type": "yêu cầu",
                "previous_value": "",
                "new_value": "Mentee yêu cầu mentor cập nhật điểm",
                "exam_date": "",
                "submitted_at": scores["mentor_handles_update_at"].isoformat()
                if scores.get("mentor_handles_update_at")
                else "",
                "mentor_status": language_record.get("mentor_status", ""),
            })
        for entry in reversed(scores.get("score_updates") or []):
            items.append({
                "id": entry.get("id", ""),
                "update_type": "score_update",
                "mentee_id": str(mentee["_id"]),
                "mentee_name": mentee.get("full_name", ""),
                "mentee_username": mentee.get("username", ""),
                "mentee_email": mentee.get("email", ""),
                "mentor": mentee.get("mentor", ""),
                "certificate_name": scores.get("certificate_name", ""),
                "language": entry.get("language", ""),
                "language_label": LANGUAGE_LABELS.get(entry.get("language", ""), entry.get("language", "")),
                "group": entry.get("group", ""),
                "skill": entry.get("skill", ""),
                "skill_label": SKILL_LABELS.get(entry.get("skill", ""), entry.get("skill", "")),
                "value_type": entry.get("value_type", ""),
                "previous_value": entry.get("previous_value", ""),
                "new_value": entry.get("new_value", ""),
                "exam_date": entry.get("exam_date", ""),
                "submitted_at": entry["submitted_at"].isoformat()
                if entry.get("submitted_at")
                else "",
                "mentor_status": language_record.get("mentor_status", ""),
            })

    items.sort(key=lambda item: item.get("submitted_at", ""), reverse=True)
    return jsonify(items)


@app.post("/api/admin/mentees/<mentee_id>/documents/<doc_id>/upload")
@with_db
def admin_upload_mentee_document(mentee_id: str, doc_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if doc_id not in MENTOR_UPLOADABLE_DOC_IDS:
        return jsonify({"detail": "Chỉ mentor mới được tải lên mục này"}), 400

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"detail": "Chưa chọn file để tải lên"}), 400

    try:
        record, updated_user = save_apply_document_upload(
            mentee,
            doc_id,
            uploaded,
            uploaded_by="mentor",
            admin=admin,
        )
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 400

    doc_label = APPLY_DOC_LABELS.get(doc_id, doc_id)
    log_mentor_activity(
        admin,
        "document_upload",
        f"Mentor tải lên {doc_label} cho {mentee.get('email', mentee_id)}",
        mentee_id=mentee_id,
        doc_id=doc_id,
    )
    if is_l2_mentor_admin(admin):
        push_l2_mentor_activity(
            mentee_id,
            admin,
            "documents",
            "document_upload",
            f"Mentor tải lên giấy tờ {doc_label}",
        )

    return jsonify(
        serialize_apply_document_for_admin(doc_id, record, updated_user, mentee_id),
    ), 201


@app.patch("/api/admin/mentees/<mentee_id>/documents/<doc_id>")
@with_db
def admin_review_apply_document(mentee_id: str, doc_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if doc_id not in VALID_APPLY_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    data = request.get_json(silent=True) or {}
    mentor_status = data.get("mentor_status", "").strip()
    mentor_note = data.get("mentor_note", "").strip()

    if mentor_note and not mentor_status:
        mentor_status = DOC_MENTOR_STATUS_REVISION

    allowed_statuses = {
        DOC_MENTOR_STATUS_WAITING,
        DOC_MENTOR_STATUS_APPROVED,
        DOC_MENTOR_STATUS_REVISION,
    }
    if mentor_status not in allowed_statuses:
        return jsonify({"detail": "Trạng thái phản hồi không hợp lệ"}), 400

    if mentor_status == DOC_MENTOR_STATUS_REVISION and not mentor_note:
        return jsonify({"detail": "Vui lòng nhập nhận xét cho mentee"}), 400

    from bson import ObjectId

    try:
        mentee_oid = ObjectId(mentee_id)
    except Exception:
        return jsonify({"detail": "Mentee không hợp lệ"}), 400

    mentee = users.find_one({"_id": mentee_oid})
    if not mentee:
        return jsonify({"detail": "Mentee không tồn tại"}), 404

    mentor_filter = mentee_filter_for_admin(admin)
    if mentor_filter and mentee.get("mentor") != mentor_filter.get("mentor"):
        return jsonify({"detail": "Không có quyền xem mentee này"}), 403

    now = datetime.now(timezone.utc)
    updates = {
        f"apply_documents.{doc_id}.mentor_status": mentor_status,
        f"apply_documents.{doc_id}.mentor_note": mentor_note,
        f"apply_documents.{doc_id}.mentor_updated_at": now,
        f"apply_documents.{doc_id}.mentor_viewed_at": now,
        f"apply_documents.{doc_id}.mentor_processed_at": now,
        f"apply_documents.{doc_id}.mentee_unread_feedback": True,
    }

    if doc_id == "personal-declaration" and not (mentee.get("apply_documents") or {}).get(doc_id):
        updates[f"apply_documents.{doc_id}"] = {
            "mentor_status": mentor_status,
            "mentor_note": mentor_note,
            "mentor_updated_at": now,
            "mentor_viewed_at": now,
            "mentor_processed_at": now,
            "mentee_unread_feedback": True,
        }

    users.update_one({"_id": mentee_oid}, {"$set": updates, "$unset": {f"apply_documents.{doc_id}.scheduled_process_at": ""}})
    sync_apply_inbox_confirm(mentee_id, doc_id, via="app")

    doc_label = APPLY_DOC_LABELS.get(doc_id, doc_id)
    profile_url = os.getenv("MENTEE_PROFILE_URL", "http://localhost:5173/profile").strip()
    feedback_description = f"Trạng thái: {mentor_status}. Nhận xét: {mentor_note or '—'}"
    try:
        from email_notify import send_mentee_document_feedback_email
        from inbox_tasks import create_mentee_view_task, mentee_doc_urls

        task = create_mentee_view_task(
            mentor_inbox,
            mentee_id=mentee_id,
            mentee_email=mentee.get("email", ""),
            mentee_name=mentee.get("full_name") or mentee.get("username", ""),
            action="document_feedback",
            title=f"Phản hồi giấy tờ {doc_label}",
            description=feedback_description,
            doc_id=doc_id if doc_id not in NO_FILE_UPLOAD_DOC_IDS else "",
            mentor_name=admin.get("mentor_name") or admin.get("full_name") or "",
        )
        view_url = mentee_doc_urls(BACKEND_PUBLIC_URL, task)["view"]
        send_mentee_document_feedback_email(
            to_email=mentee.get("email", ""),
            mentee_name=mentee.get("full_name") or mentee.get("username", ""),
            document_label=doc_label,
            mentor_status=mentor_status,
            mentor_note=mentor_note or "—",
            profile_url=profile_url,
            view_url=view_url,
        )
    except Exception:
        pass

    log_mentor_activity(
        admin,
        "document_review",
        f"Phản hồi giấy tờ {doc_id} của {mentee.get('email', mentee_id)}: {mentor_status}",
        mentee_id=mentee_id,
        doc_id=doc_id,
    )
    if is_l2_mentor_admin(admin):
        doc_label = APPLY_DOC_LABELS.get(doc_id, doc_id)
        push_l2_mentor_activity(
            mentee_id,
            admin,
            "documents",
            "document_review",
            f"Phản hồi giấy tờ {doc_label}: {mentor_status}",
        )

    fresh = users.find_one({"_id": mentee_oid}) or mentee
    record = (fresh.get("apply_documents") or {}).get(doc_id) or {}
    return jsonify(serialize_apply_document_for_admin(doc_id, record, fresh, mentee_id))


@app.post("/api/admin/mentees/<mentee_id>/documents/remind-missing")
@with_db
def admin_remind_missing_documents(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    data = request.get_json(silent=True) or {}
    requested_ids = data.get("doc_ids") or []
    if not isinstance(requested_ids, list) or not requested_ids:
        return jsonify({"detail": "Chọn ít nhất một giấy tờ còn thiếu để nhắc nhở"}), 400

    from bson import ObjectId

    try:
        mentee_oid = ObjectId(mentee_id)
    except Exception:
        return jsonify({"detail": "Mentee không hợp lệ"}), 400

    mentee = users.find_one({"_id": mentee_oid})
    if not mentee:
        return jsonify({"detail": "Mentee không tồn tại"}), 404

    mentor_filter = mentee_filter_for_admin(admin)
    if mentor_filter and mentee.get("mentor") != mentor_filter.get("mentor"):
        return jsonify({"detail": "Không có quyền với mentee này"}), 403

    apply_docs = mentee.get("apply_documents") or {}
    valid_missing_ids = []
    for doc_id in requested_ids:
        if doc_id not in VALID_APPLY_DOC_IDS:
            continue
        record = apply_docs.get(doc_id) or {}
        if not apply_document_has_content(doc_id, record, mentee):
            valid_missing_ids.append(doc_id)

    if not valid_missing_ids:
        return jsonify({"detail": "Không có giấy tờ thiếu hợp lệ để nhắc nhở"}), 400

    now = datetime.now(timezone.utc)
    reminder = {
        "doc_ids": sorted(set(valid_missing_ids)),
        "message": APPLY_MISSING_REMINDER_MESSAGE,
        "mentee_unread": True,
        "sent_at": now,
        "sent_by": str(admin["_id"]),
    }
    users.update_one({"_id": mentee_oid}, {"$set": {"apply_missing_reminder": reminder}})

    labels = [APPLY_DOC_LABELS.get(doc_id, doc_id) for doc_id in reminder["doc_ids"]]
    log_mentor_activity(
        admin,
        "apply_missing_reminder",
        f"Nhắc nhở giấy tờ thiếu — {mentee.get('email', mentee_id)}: {', '.join(labels)}",
        mentee_id=mentee_id,
    )
    if is_l2_mentor_admin(admin):
        push_l2_mentor_activity(
            mentee_id,
            admin,
            "documents",
            "remind_missing",
            f"Nhắc mentee bổ sung giấy tờ: {', '.join(labels)}",
        )

    return jsonify({
        "message": "Đã gửi nhắc nhở tới mentee",
        "missing_reminder": serialize_apply_missing_reminder({**mentee, "apply_missing_reminder": reminder}),
    })

