
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

@app.get("/api/admin/inbox")
@with_db
def admin_inbox_list():
    from inbox_tasks import (
        build_daily_board,
        build_daily_summary,
        ensure_stale_pending_daily_reminders,
        list_archive_days,
        list_inbox_for_admin,
        process_due_reminders,
    )

    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    ensure_stale_pending_daily_reminders(mentor_inbox)
    process_due_reminders(mentor_inbox, send_daily_inbox_summary_for_mentor)
    items = list_inbox_for_admin(mentor_inbox, admin, limit=100, base_url=BACKEND_PUBLIC_URL)
    pending = [item for item in items if item.get("status") == "pending"]
    board = build_daily_board(items)
    daily_summary = build_daily_summary(items)
    archive_days = list_archive_days(mentor_inbox, admin, limit=30)
    return jsonify({
        "items": items,
        "pending_count": len(pending),
        "board": board,
        "daily_summary": daily_summary,
        "archive_days": archive_days,
    })


@app.get("/api/admin/inbox/archive/<date_key>")
@with_db
def admin_inbox_archive_day(date_key: str):
    from inbox_tasks import build_archive_day_summary, list_inbox_for_day

    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    items = list_inbox_for_day(
        mentor_inbox,
        admin,
        date_key,
        limit=100,
        base_url=BACKEND_PUBLIC_URL,
    )
    summary = build_archive_day_summary(items, date_key)
    return jsonify(summary)


@app.get("/api/admin/inbox/<task_id>/file")
@with_db
def admin_inbox_task_file(task_id: str):
    from bson import ObjectId
    from bson.errors import InvalidId
    from inbox_tasks import mentor_inbox_filter

    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    try:
        oid = ObjectId(task_id)
    except InvalidId:
        return jsonify({"detail": "Không tìm thấy công việc"}), 404

    mentor_name = (admin.get("mentor_name") or "").strip()
    filt = mentor_inbox_filter(admin, mentor_name)
    filt["_id"] = oid
    task = mentor_inbox.find_one(filt)
    if not task:
        return jsonify({"detail": "Không tìm thấy công việc"}), 404

    doc_id = (task.get("doc_id") or "").strip()
    mentee_id = (task.get("mentee_id") or "").strip()
    if doc_id == "personal-declaration" and mentee_id:
        mentee, error = get_mentee_for_admin(admin, mentee_id)
        if error:
            return error
        declaration = mentee.get("personal_declaration") or {}
        stored_name = (declaration.get("stored_name") or "").strip()
        if not stored_name:
            return jsonify({"detail": "Chưa có file kê khai docx trên hệ thống."}), 404
        from services import storage
        from services.files import make_inline_file_response

        data = storage.read_bytes(storage.storage_key(mentee["_id"], "personal-declaration", stored_name))
        if data is None:
            return jsonify({"detail": "File kê khai không tồn tại."}), 404
        return make_inline_file_response(
            data,
            stored_name,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    result, error = build_inbox_document_payload(task)
    if error:
        return jsonify({"detail": error}), 404

    payload, download_name, mimetype = result
    return make_inline_file_response(payload, download_name, mimetype)


@app.post("/api/admin/inbox/<task_id>/view")
@with_db
def admin_inbox_view(task_id: str):
    from bson import ObjectId
    from bson.errors import InvalidId
    from inbox_tasks import mentor_inbox_filter, record_inbox_view, serialize_inbox_task

    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    try:
        oid = ObjectId(task_id)
    except InvalidId:
        return jsonify({"detail": "Không tìm thấy công việc"}), 404

    filt = mentor_inbox_filter(admin, "")
    filt["_id"] = oid
    task = mentor_inbox.find_one(filt)
    if not task:
        return jsonify({"detail": "Không tìm thấy công việc"}), 404

    task = record_inbox_view(mentor_inbox, task) or task
    apply_inbox_view_side_effects(task)
    return jsonify({
        "message": "Đã ghi nhận xem",
        "item": serialize_inbox_task(task, base_url=BACKEND_PUBLIC_URL),
    })


@app.post("/api/admin/inbox/bulk-confirm")
@with_db
def admin_inbox_bulk_confirm():
    from inbox_tasks import bulk_confirm_inbox_tasks, serialize_inbox_task

    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    data = request.get_json(silent=True) or {}
    raw_ids = data.get("task_ids") or data.get("ids") or []
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"detail": "Danh sách trống"}), 400

    result = bulk_confirm_inbox_tasks(
        mentor_inbox,
        raw_ids,
        via="app",
        processed_by=str(admin["_id"]),
        processed_by_name=admin_display_name(admin),
        admin=admin,
    )
    succeeded = result["succeeded"]
    failed = result["failed"]
    confirmed_tasks = result["tasks"]

    for task in confirmed_tasks:
        apply_inbox_confirm_side_effects(task)
        notify_mentee_inbox_processed(task)

    if succeeded == 0:
        return jsonify({"detail": "Không xử lý được mục nào", "succeeded": 0, "failed": failed}), 400

    message = f"Đã xử lí {succeeded} mục"
    if failed:
        message += f" ({failed} lỗi)"
    return jsonify({
        "message": message,
        "succeeded": succeeded,
        "failed": failed,
        "items": [serialize_inbox_task(task) for task in confirmed_tasks],
    })


@app.post("/api/admin/inbox/<task_id>/confirm")
@with_db
def admin_inbox_confirm(task_id: str):
    from inbox_tasks import confirm_inbox_task, serialize_inbox_task

    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    task = confirm_inbox_task(
        mentor_inbox,
        task_id=task_id,
        via="app",
        processed_by=str(admin["_id"]),
        processed_by_name=admin_display_name(admin),
        admin=admin,
    )
    if not task:
        return jsonify({"detail": "Không tìm thấy công việc"}), 404
    apply_inbox_confirm_side_effects(task)
    notify_mentee_inbox_processed(task)
    return jsonify({
        "message": "Đã xác nhận xử lí",
        "item": serialize_inbox_task(task),
    })


@app.patch("/api/admin/inbox/<task_id>/reminder")
@with_db
def admin_inbox_reminder(task_id: str):
    from inbox_tasks import update_reminder_schedule

    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    data = request.get_json(silent=True) or {}
    hours = data.get("hours")
    reminder_at_raw = (data.get("reminder_at") or "").strip()
    reminder_at = None

    if reminder_at_raw:
        try:
            reminder_at = datetime.fromisoformat(reminder_at_raw.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"detail": "Thời gian nhắc không hợp lệ"}), 400
    elif hours is not None:
        try:
            hours = int(hours)
        except (TypeError, ValueError):
            return jsonify({"detail": "Giờ nhắc lại không hợp lệ"}), 400
    else:
        return jsonify({"detail": "Cần hours hoặc reminder_at"}), 400

    item = update_reminder_schedule(
        mentor_inbox,
        task_id,
        hours=hours if reminder_at is None else None,
        reminder_at=reminder_at,
    )
    if not item:
        return jsonify({"detail": "Không tìm thấy công việc đang chờ"}), 404
    return jsonify({"message": "Đã cập nhật lịch nhắc", "item": item})

