
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

@app.get("/api/admin/mentees/<mentee_id>")
@with_db
def admin_get_mentee(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    if is_super_admin(admin) and mentee.get("login_anomaly_superadmin_unread"):
        users.update_one(
            {"_id": mentee["_id"]},
            {"$set": {"login_anomaly_superadmin_unread": False}},
        )
        mentee["login_anomaly_superadmin_unread"] = False

    return jsonify(serialize_admin_mentee_detail(mentee, admin))


@app.delete("/api/admin/mentees/<mentee_id>")
@with_db
def admin_delete_mentee(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if not is_super_admin(admin) and not admin_is_level1_mentor(admin):
        return jsonify({"detail": "Chỉ mentor cấp 1 mới được xóa mentee."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    mentee_name = mentee.get("full_name") or mentee.get("username") or mentee.get("email", "")
    remove_mentee_account(mentee)
    log_mentor_activity(
        admin,
        "delete_mentee",
        f"Xóa mentee {mentee_name} ({mentee.get('email', '')})",
        mentee_id=mentee_id,
    )
    return jsonify({"message": f"Đã xóa mentee {mentee_name}"})


@app.put("/api/admin/mentees/<mentee_id>/apply-progress")
@with_db
def admin_update_apply_progress(mentee_id: str):
    from services.misc import extract_apply_progress_fields, validate_apply_progress_field_values
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    submitted_rows = data.get("rows")
    if not isinstance(submitted_rows, list) or not submitted_rows:
        return jsonify({"detail": "Danh sách dòng không hợp lệ"}), 400

    viewer = apply_progress_viewer_key(admin)
    current_rows = {row["row_num"]: row for row in get_apply_progress_rows_raw(mentee)}
    now = datetime.now(timezone.utc)
    merged_by_num = dict(current_rows)
    changed_rows: list[int] = []

    for item in submitted_rows:
        if not isinstance(item, dict):
            continue
        row_num = int(item.get("row_num") or 0)
        if row_num not in merged_by_num:
            continue
        previous_fields = extract_apply_progress_fields(merged_by_num[row_num])
        published_fields = extract_apply_progress_fields(item)
        if viewer == "mentor_l2":
            prev_progress = previous_fields.get("progress", "")
            if prev_progress == APPLY_PROGRESS_PROGRESS_L1_ONLY:
                published_fields["progress"] = prev_progress
        validation_error = validate_apply_progress_field_values(published_fields, viewer)
        if validation_error:
            return jsonify({"detail": validation_error}), 400
        if not apply_progress_fields_equal(previous_fields, published_fields):
            changed_rows.append(row_num)
        merged_by_num[row_num] = {
            "row_num": row_num,
            **published_fields,
            "pending": None,
            "pending_status": "",
            "pending_at": None,
            "rejection_note": "",
        }

    merged = [merged_by_num[num] for num in range(1, get_apply_progress_row_count(mentee) + 1)]

    from bson import ObjectId

    set_fields = {
        "apply_progress_rows": merged,
        "apply_progress_updated_at": now,
        "apply_progress_mentor_unread": False,
    }
    if changed_rows:
        if admin_is_level1_mentor(admin) or is_super_admin(admin):
            set_fields["apply_progress_mentee_unread"] = True
            if admin_is_level1_mentor(admin) and not is_super_admin(admin):
                set_fields["apply_progress_l2_unread"] = True
                push_apply_progress_activity(
                    mentee["_id"],
                    {
                        "type": "l1_update",
                        "row_num": changed_rows[0],
                        "processed": False,
                        "summary": f"Mentor cấp 1 cập nhật tiến độ apply (dòng {', '.join(map(str, changed_rows))})",
                    },
                )
            elif is_super_admin(admin):
                set_fields["apply_progress_mentee_unread"] = True
        elif is_l2_mentor_admin(admin):
            push_l2_mentor_activity(
                mentee["_id"],
                admin,
                "applyProgress",
                "update",
                f"Cập nhật tiến độ apply (dòng {', '.join(map(str, changed_rows))})",
            )

    users.update_one({"_id": ObjectId(mentee["_id"])}, {"$set": set_fields})
    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    if changed_rows and (admin_is_level1_mentor(admin) or is_super_admin(admin)):
        mentor_label = admin_display_name(admin)
        notify_mentee_mentor_activity(
            fresh,
            action="apply_progress_update",
            title="Mentor cập nhật tiến độ apply",
            description=(
                f"Mentor {mentor_label} cập nhật tiến độ apply "
                f"(dòng {', '.join(map(str, changed_rows))})."
            ),
            mentor_name=mentor_label,
            mentor_admin=admin,
        )
    payload = serialize_apply_progress_payload(fresh, viewer, include_activity=True)
    return jsonify(payload)


@app.post("/api/admin/mentees/<mentee_id>/apply-progress/rows")
@with_db
def admin_modify_apply_progress_rows(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip().lower()
    if action not in {"add", "remove"}:
        return jsonify({"detail": "Hành động phải là add hoặc remove"}), 400

    from bson import ObjectId

    count = get_apply_progress_row_count(mentee)
    now = datetime.now(timezone.utc)
    viewer = apply_progress_viewer_key(admin)

    if action == "add":
        if count >= APPLY_PROGRESS_ROW_MAX:
            return jsonify({"detail": f"Tối đa {APPLY_PROGRESS_ROW_MAX} nguyện vọng"}), 400
        new_count = count + 1
        users.update_one(
            {"_id": ObjectId(mentee["_id"])},
            {
                "$set": {
                    "apply_progress_row_count": new_count,
                    "apply_progress_updated_at": now,
                },
            },
        )
        if is_l2_mentor_admin(admin):
            push_l2_mentor_activity(
                mentee["_id"],
                admin,
                "applyProgress",
                "add_rows",
                "Thêm nguyện vọng apply",
            )
    else:
        if count <= APPLY_PROGRESS_ROW_MIN:
            return jsonify({"detail": "Cần ít nhất 1 nguyện vọng"}), 400
        new_count = count - 1
        rows = get_apply_progress_rows_raw(mentee)[:new_count]
        users.update_one(
            {"_id": ObjectId(mentee["_id"])},
            {
                "$set": {
                    "apply_progress_row_count": new_count,
                    "apply_progress_rows": rows,
                    "apply_progress_updated_at": now,
                },
            },
        )
        if is_l2_mentor_admin(admin):
            push_l2_mentor_activity(
                mentee["_id"],
                admin,
                "applyProgress",
                "remove_rows",
                "Bớt nguyện vọng apply",
            )

    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    return jsonify(serialize_apply_progress_payload(fresh, viewer, include_activity=True))


@app.post("/api/admin/mentees/<mentee_id>/apply-progress/review")
@with_db
def admin_review_apply_progress(mentee_id: str):
    from services.misc import extract_apply_progress_fields
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    row_num = int(data.get("row_num") or 0)
    action = (data.get("action") or "").strip().lower()
    rejection_note = (data.get("rejection_note") or "").strip()

    row_count = get_apply_progress_row_count(mentee)
    if row_num < 1 or row_num > row_count:
        return jsonify({"detail": "Dòng không hợp lệ"}), 400
    if action not in {"approve", "reject"}:
        return jsonify({"detail": "Hành động phải là approve hoặc reject"}), 400

    rows = get_apply_progress_rows_raw(mentee)
    target = rows[row_num - 1]
    pending = target.get("pending")
    if not isinstance(pending, dict) or target.get("pending_status") != APPLY_PROGRESS_PENDING_WAITING:
        return jsonify({"detail": "Dòng này không có chỉnh sửa chờ duyệt"}), 400

    now = datetime.now(timezone.utc)
    if action == "approve":
        approved_fields = extract_apply_progress_fields(pending)
        rows[row_num - 1] = {
            "row_num": row_num,
            **approved_fields,
            "pending": None,
            "pending_status": "",
            "pending_at": None,
            "rejection_note": "",
        }
    else:
        rows[row_num - 1] = {
            **target,
            "pending_status": APPLY_PROGRESS_PENDING_REJECTED,
            "rejection_note": rejection_note,
        }

    from bson import ObjectId

    mark_apply_progress_activity_processed(mentee["_id"], row_num, admin, action)
    if is_l2_mentor_admin(admin):
        push_l2_mentor_activity(
            mentee["_id"],
            admin,
            "applyProgress",
            "review",
            (
                f"Duyệt chỉnh sửa tiến độ apply dòng {row_num}"
                if action == "approve"
                else f"Từ chối chỉnh sửa tiến độ apply dòng {row_num}"
            ),
        )

    users.update_one(
        {"_id": ObjectId(mentee["_id"])},
        {
            "$set": {
                "apply_progress_rows": rows,
                "apply_progress_updated_at": now,
                "apply_progress_mentee_unread": True,
            },
        },
    )
    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    mentor_label = admin_display_name(admin)
    notify_mentee_mentor_activity(
        fresh,
        action="apply_progress_review",
        title="Mentor phản hồi tiến độ apply",
        description=(
            f"Mentor {mentor_label} {'duyệt' if action == 'approve' else 'từ chối'} "
            f"chỉnh sửa dòng {row_num}."
            + (f" Ghi chú: {rejection_note}" if rejection_note else "")
        ),
        mentor_name=mentor_label,
        mentor_admin=admin,
    )
    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    viewer = apply_progress_viewer_key(admin)
    return jsonify(serialize_apply_progress_payload(fresh, viewer, include_activity=True))


@app.post("/api/admin/mentees/<mentee_id>/l2-activity/ack")
@with_db
def admin_ack_l2_activity(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if not admin_is_level1_mentor(admin) and not is_super_admin(admin):
        return jsonify({"detail": "Chỉ mentor cấp 1 mới xác nhận thông báo từ mentor cấp 2."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    section = (data.get("section") or "").strip() or None
    payload = ack_mentor_l2_activity(mentee["_id"], admin, section)
    return jsonify(payload)


@app.post("/api/admin/mentees/<mentee_id>/apply-progress/ack-l2")
@with_db
def admin_ack_apply_progress_l2(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if admin_is_level1_mentor(admin) and not is_super_admin(admin):
        return jsonify({"detail": "Chỉ mentor cấp 2 cần xác nhận thông báo này."}), 400

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    from bson import ObjectId

    now = datetime.now(timezone.utc)
    stored = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    activity = get_apply_progress_activity_raw(stored)
    for item in activity:
        if item.get("type") == "l1_update" and not item.get("processed"):
            item["processed"] = True
            item["processed_at"] = now
            item["processed_by_name"] = admin_display_name(admin)
            item["mentor_unread"] = False

    users.update_one(
        {"_id": ObjectId(mentee["_id"])},
        {
            "$set": {
                "apply_progress_l2_unread": False,
                "apply_progress_activity": activity,
            },
        },
    )
    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    viewer = apply_progress_viewer_key(admin)
    return jsonify(serialize_apply_progress_payload(fresh, viewer, include_activity=True))


@app.get("/api/admin/mentees/<mentee_id>/feedback")
@with_db
def admin_list_mentee_feedback(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    cursor = feedback_app.find({"user_id": mentee["_id"]}).sort("created_at", -1)
    items = [feedback_response(doc, admin) for doc in cursor]
    unread_count = count_mentor_unread_feedback(mentee["_id"])
    return jsonify({"items": items, "unread_count": unread_count})


@app.post("/api/admin/mentees/<mentee_id>/feedback/mark-read")
@with_db
def admin_mark_mentee_feedback_read(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    feedback_app.update_many(
        {
            "user_id": mentee["_id"],
            "$or": [
                {"mentor_unread": True},
                {"mentor_unread": {"$exists": False}, "status": FEEDBACK_STATUS_PENDING},
            ],
        },
        {
            "$set": {
                "mentor_unread": False,
                "mentee_status_label": FEEDBACK_MENTEE_RECEIVED,
            }
        },
    )
    return jsonify({
        "message": "Đã đánh dấu đã đọc",
        "unread_count": count_mentor_unread_feedback(mentee["_id"]),
    })


@app.post("/api/admin/mentees/<mentee_id>/preferred-schools-note/ack")
@with_db
def admin_ack_preferred_schools_note(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    from bson import ObjectId

    users.update_one(
        {"_id": ObjectId(mentee["_id"])},
        {"$set": {"preferred_schools_note_mentor_unread": False}},
    )
    return jsonify({
        "preferred_schools_note_unread": False,
        "preferred_schools_note": mentee.get("preferred_schools_note", ""),
    })


@app.post("/api/admin/mentees/<mentee_id>/hdnk-nckh/ack")
@with_db
def admin_ack_hdnk_nckh(mentee_id: str):
    from services.misc import serialize_hdnk_nckh_payload
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if not is_thanh_ha_l1_mentor(admin):
        return jsonify({"detail": "Chỉ mentor Thanh Hà cấp 1 mới xử lí mục này."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    if not is_thanh_ha_mentee(mentee):
        return jsonify({"detail": "Mentee không thuộc team Thanh Hà."}), 400

    from bson import ObjectId

    now = datetime.now(timezone.utc)
    users.update_one(
        {"_id": ObjectId(mentee["_id"])},
        {
            "$set": {
                "hdnk_nckh_l1_unread": False,
                "hdnk_nckh_reminder_unread": False,
                "hdnk_nckh_l1_ack_at": now,
            },
        },
    )
    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    payload = serialize_hdnk_nckh_payload(fresh)
    return jsonify(payload)


@app.patch("/api/admin/mentees/<mentee_id>/hdnk-nckh/reminder")
@with_db
def admin_set_hdnk_nckh_reminder(mentee_id: str):
    from services.misc import serialize_hdnk_nckh_payload
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    if not is_thanh_ha_l1_mentor(admin):
        return jsonify({"detail": "Chỉ mentor Thanh Hà cấp 1 mới đặt nhắc nhở."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    if not is_thanh_ha_mentee(mentee):
        return jsonify({"detail": "Mentee không thuộc team Thanh Hà."}), 400

    data = request.get_json(silent=True) or {}
    reminder_date = (data.get("reminder_due_at") or "").strip()
    entry_id = (data.get("entry_id") or "").strip()
    set_fields: dict = {"hdnk_nckh_reminder_unread": False}

    parsed = None
    if reminder_date:
        try:
            parsed = datetime.strptime(reminder_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return jsonify({"detail": "Ngày nhắc nhở không hợp lệ (YYYY-MM-DD)"}), 400

    if entry_id:
        entries = get_hdnk_nckh_entries_raw(mentee)
        if not any(row.get("entry_id") == entry_id for row in entries):
            return jsonify({"detail": "Không tìm thấy mục keep track."}), 404
        updated_entries = []
        for row in entries:
            if row.get("entry_id") == entry_id:
                row = {**row, "reminder_due_at": parsed}
            updated_entries.append(row)
        set_fields["hdnk_nckh_entries"] = updated_entries
    else:
        return jsonify({"detail": "Cần entry_id để đặt ngày nhắc theo hạng mục."}), 400

    from bson import ObjectId

    users.update_one({"_id": ObjectId(mentee["_id"])}, {"$set": set_fields})
    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    fresh = ensure_hdnk_nckh_reminder_sync(fresh)
    return jsonify(serialize_hdnk_nckh_payload(fresh))


@app.put("/api/admin/mentees/<mentee_id>/hdnk-nckh")
@with_db
def admin_update_hdnk_nckh(mentee_id: str):
    from services.misc import serialize_hdnk_nckh_payload
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    if not is_thanh_ha_mentee(mentee):
        return jsonify({"detail": "Mentee không thuộc team Thanh Hà."}), 400

    data = request.get_json(silent=True) or {}
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        return jsonify({"detail": "Danh sách mục không hợp lệ"}), 400

    existing = get_hdnk_nckh_entries_raw(mentee)
    existing_by_id = {row.get("entry_id"): row for row in existing if row.get("entry_id")}
    normalized: list[dict] = []
    for item in raw_entries[:HDNK_NCKH_MAX_ENTRIES]:
        if not isinstance(item, dict):
            continue
        entry_id = (item.get("entry_id") or "").strip()
        match = existing_by_id.get(entry_id) if entry_id else None
        if is_thanh_ha_l1_mentor(admin):
            normalized.append(
                normalize_hdnk_nckh_entry(item, entry_id=match.get("entry_id") if match else None),
            )
        else:
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

    changed = not hdnk_nckh_entries_equal(existing, normalized)

    from bson import ObjectId

    now = datetime.now(timezone.utc)
    set_fields = {
        "hdnk_nckh_entries": normalized,
        "hdnk_nckh_l1_unread": False,
        "hdnk_nckh_reminder_unread": False,
        "hdnk_nckh_l1_ack_at": now,
        "hdnk_nckh_mentor_updated_at": now,
    }
    users.update_one({"_id": ObjectId(mentee["_id"])}, {"$set": set_fields})
    fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
    if changed:
        notify_mentee_mentor_activity(
            fresh,
            action="hdnk_nckh_update",
            title="Mentor cập nhật HDNK + NCKH",
            description="Mentor đã cập nhật bảng Keep track HDNK + NCKH cho bạn.",
            mentor_name=admin_display_name(admin),
            mentor_admin=admin,
        )
    return jsonify(serialize_hdnk_nckh_payload(fresh))


@app.patch("/api/admin/mentees/<mentee_id>/mentor-info")
@with_db
def admin_update_mentee_mentor_info(mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response

    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    mentee, error = get_mentee_for_admin(admin, mentee_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    set_fields: dict = {}

    if "mentor_apply_direction" in data:
        direction = normalize_mentor_apply_direction(data.get("mentor_apply_direction", ""))
        if data.get("mentor_apply_direction") and not direction:
            return jsonify({"detail": "Hướng apply không hợp lệ"}), 400
        set_fields["mentor_apply_direction"] = direction

    if "apply_degree_level" in data:
        degree = normalize_apply_degree_level(data.get("apply_degree_level", ""))
        if data.get("apply_degree_level") and not degree:
            return jsonify({"detail": "Hệ apply phải là đại, thạc hoặc tiến sĩ"}), 400
        set_fields["apply_degree_level"] = degree

    if "term3_2027_language_semester" in data:
        if not is_thanh_ha_mentee(mentee):
            return jsonify({"detail": "Mục này chỉ dành cho mentee team Thanh Hà."}), 403
        term_value = normalize_term3_2027_language_semester(
            data.get("term3_2027_language_semester", ""),
        )
        if data.get("term3_2027_language_semester") and not term_value:
            return jsonify({"detail": "Chọn Có hoặc Không cho kì tiếng 3/2027"}), 400
        set_fields["term3_2027_language_semester"] = term_value

    if "research_direction" in data:
        if not is_thanh_ha_mentee(mentee):
            return jsonify({"detail": "Mục này chỉ dành cho mentee team Thanh Hà."}), 403
        research_raw = str(data.get("research_direction") or "").strip()
        if len(research_raw) > 200:
            return jsonify({"detail": "Phương hướng NC tối đa 200 ký tự"}), 400
        set_fields["research_direction"] = normalize_research_direction(research_raw)

    if "scholarship_system" in data:
        scholarship_value = (data.get("scholarship_system") or "").strip().lower()
        if scholarship_value and scholarship_value not in SCHOLARSHIP_SYSTEMS:
            return jsonify({"detail": "Hệ tiếng phải là Tiếng Anh hoặc Tiếng Trung"}), 400
        set_fields["scholarship_system"] = scholarship_value

    if not set_fields:
        return jsonify({"detail": "Không có dữ liệu để cập nhật"}), 400

    from bson import ObjectId

    users.update_one({"_id": ObjectId(mentee_id)}, {"$set": set_fields})
    fresh = users.find_one({"_id": ObjectId(mentee_id)})
    return jsonify(serialize_admin_mentee_detail(fresh, admin))

