from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import jsonify, request

from auth.security import get_authenticated_admin
from database import profile_activities, users, with_db
from extensions import app
from services.admins import admin_display_name, admin_is_approved
from services.apply_documents import mentor_apply_direction_label
from services.profile_activities import (
    create_profile_activity,
    finalize_group_and_sync_hdnk,
    notify_group_assignment,
    parse_profile_activity_from_description,
    sanitize_profile_activity_input,
    serialize_admin_profile_activity,
    update_group_response,
    _upsert_group,
)


def _get_activity_or_404(activity_id: str):
    try:
        oid = ObjectId(activity_id)
    except InvalidId:
        return None, (jsonify({"detail": "Hoạt động không tồn tại"}), 404)
    activity = profile_activities.find_one({"_id": oid})
    if not activity:
        return None, (jsonify({"detail": "Hoạt động không tồn tại"}), 404)
    return activity, None


def _admin_activity_query(admin: dict) -> dict:
    mentor_name = (admin.get("mentor_name") or "").strip()
    if mentor_name:
        return {"mentor_name": mentor_name}
    return {}


def _resolve_group_name(activity: dict, mentee_id: str) -> str:
    for group in activity.get("groups", []):
        if mentee_id in (group.get("mentee_ids") or []):
            return group.get("group_name", "")
    return ""


def _serialize_registration(activity: dict, state: dict) -> dict:
    mentee_id = state.get("mentee_id", "")
    if not ObjectId.is_valid(mentee_id):
        return {}
    mentee = users.find_one({"_id": ObjectId(mentee_id)})
    if not mentee:
        return {}
    return {
        "mentee_id": mentee_id,
        "mentee_name": mentee.get("full_name") or mentee.get("username") or mentee.get("email", ""),
        "zalo_phone": mentee.get("zalo_phone", ""),
        "apply_major": mentor_apply_direction_label(mentee.get("mentor_apply_direction", ""))
        or mentee.get("apply_direction", ""),
        "group_name": _resolve_group_name(activity, mentee_id),
        "group_response_status": state.get("group_response_status", "pending"),
        "group_response_note": state.get("group_response_note", ""),
    }


@app.post("/api/admin/profile-activities/parse")
@with_db
def admin_parse_profile_activity():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    data = request.get_json(silent=True) or {}
    description = str(data.get("description") or "").strip()
    if not description:
        return jsonify({"detail": "Vui lòng nhập mô tả hoạt động"}), 400
    return jsonify(parse_profile_activity_from_description(description))


@app.post("/api/admin/profile-activities")
@with_db
def admin_create_profile_activity():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    data = request.get_json(silent=True) or {}
    parsed = parse_profile_activity_from_description(str(data.get("description") or ""))
    payload = sanitize_profile_activity_input(data, parsed_fallback=parsed)
    if not payload.get("activity_name"):
        return jsonify({"detail": "Tên hoạt động là bắt buộc"}), 400
    created = create_profile_activity(admin, payload)
    return jsonify(serialize_admin_profile_activity(created)), 201


@app.get("/api/admin/profile-activities")
@with_db
def admin_list_profile_activities():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    cursor = profile_activities.find(_admin_activity_query(admin)).sort("created_at", -1)
    return jsonify([serialize_admin_profile_activity(doc) for doc in cursor])


@app.get("/api/admin/profile-activities/<activity_id>/registrations")
@with_db
def admin_activity_registrations(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    registrations = []
    for state in activity.get("mentee_states", []):
        if not state.get("registered_at"):
            continue
        row = _serialize_registration(activity, state)
        if row:
            registrations.append(row)
    return jsonify({"items": registrations})


@app.patch("/api/admin/profile-activities/<activity_id>/groups")
@with_db
def admin_upsert_activity_group(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    group = _upsert_group(activity, data)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": activity.get("groups", []), "updated_at": datetime.now(timezone.utc)}},
    )
    return jsonify({"group": group, "groups": activity.get("groups", [])})


@app.post("/api/admin/profile-activities/<activity_id>/groups/<group_id>/notify")
@with_db
def admin_notify_activity_group(activity_id: str, group_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    group = next((row for row in activity.get("groups", []) if row.get("group_id") == group_id), None)
    if not group:
        return jsonify({"detail": "Nhóm không tồn tại"}), 404
    notify_group_assignment(activity, group)
    return jsonify({"message": "Đã gửi thông báo nhóm"})


@app.post("/api/admin/profile-activities/<activity_id>/groups/<group_id>/finalize")
@with_db
def admin_finalize_activity_group(activity_id: str, group_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    finalize_group_and_sync_hdnk(activity, group_id, admin_display_name(admin))
    return jsonify({"message": "Đã chốt nhóm và đồng bộ HDNK + NCKH"})


@app.post("/api/admin/profile-activities/<activity_id>/responses/<mentee_id>")
@with_db
def admin_set_group_response(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    if not ObjectId.is_valid(mentee_id):
        return jsonify({"detail": "Mentee không tồn tại"}), 404
    mentee = users.find_one({"_id": ObjectId(mentee_id)})
    if not mentee:
        return jsonify({"detail": "Mentee không tồn tại"}), 404
    data = request.get_json(silent=True) or {}
    update_group_response(activity, mentee, data.get("status", ""), data.get("note", ""))
    return jsonify({"message": "Đã cập nhật phản hồi nhóm"})
