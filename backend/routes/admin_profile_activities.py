from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import jsonify, request

from auth.security import get_authenticated_admin
from database import profile_activities, users, with_db
from extensions import app
from services.admins import admin_display_name, admin_is_approved, is_super_admin
from services.apply_progress import admin_is_level1_mentor
from services.profile_activities import (
    approve_pending_group,
    approve_pending_mentor_reject,
    approve_profile_activity,
    create_profile_activity,
    finalize_group_and_sync_hdnk,
    group_is_approved,
    notify_group_assignment,
    parse_profile_activity_from_description,
    reject_pending_group,
    reject_pending_mentor_reject,
    reject_profile_activity,
    sanitize_profile_activity_input,
    serialize_admin_profile_activity,
    serialize_admin_registration,
    submit_mentor_reject_registration,
    upsert_activity_group,
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


def _can_review_profile_activity(admin: dict) -> bool:
    return bool(is_super_admin(admin) or admin_is_level1_mentor(admin))


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
        return jsonify({"detail": "Không thể tạo tên hoạt động — vui lòng điền loại hoạt động"}), 400
    created = create_profile_activity(admin, payload)
    response = serialize_admin_profile_activity(created)
    if created.get("approval_status") == "pending_l1_approval":
        response["message"] = "Hoạt động đã gửi, chờ mentor cấp 1 duyệt trước khi hiển thị cho mentee."
    return jsonify(response), 201


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


@app.post("/api/admin/profile-activities/<activity_id>/approve")
@with_db
def admin_approve_profile_activity(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403
    if not _can_review_profile_activity(admin):
        return jsonify({"detail": "Chỉ mentor cấp 1 mới được duyệt hoạt động."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    if activity.get("approval_status") == "approved":
        return jsonify(serialize_admin_profile_activity(activity))
    updated = approve_profile_activity(activity, admin)
    return jsonify(serialize_admin_profile_activity(updated))


@app.post("/api/admin/profile-activities/<activity_id>/reject")
@with_db
def admin_reject_profile_activity(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403
    if not _can_review_profile_activity(admin):
        return jsonify({"detail": "Chỉ mentor cấp 1 mới được từ chối hoạt động."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    updated = reject_profile_activity(activity, admin)
    return jsonify(serialize_admin_profile_activity(updated))


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
        mentee_id = state.get("mentee_id", "")
        if not ObjectId.is_valid(mentee_id):
            continue
        mentee = users.find_one({"_id": ObjectId(mentee_id)})
        if not mentee:
            continue
        registrations.append(serialize_admin_registration(activity, state, mentee))
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
    group, requires_l1 = upsert_activity_group(activity, data, admin)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": activity.get("groups", []), "updated_at": datetime.now(timezone.utc)}},
    )
    response = {"group": group, "groups": activity.get("groups", [])}
    if requires_l1:
        response["message"] = "Đã gửi phân nhóm, chờ mentor cấp 1 duyệt trước khi mentee thấy."
    return jsonify(response)


@app.post("/api/admin/profile-activities/<activity_id>/groups/<group_id>/approve")
@with_db
def admin_approve_activity_group(activity_id: str, group_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403
    if not _can_review_profile_activity(admin):
        return jsonify({"detail": "Chỉ mentor cấp 1 mới được duyệt phân nhóm."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    group = next((row for row in activity.get("groups", []) if row.get("group_id") == group_id), None)
    if not group:
        return jsonify({"detail": "Nhóm không tồn tại"}), 404
    updated = approve_pending_group(activity, group_id, admin)
    return jsonify(
        {
            "message": "Đã duyệt phân nhóm — mentee sẽ nhận thông báo.",
            "activity": serialize_admin_profile_activity(updated),
        }
    )


@app.post("/api/admin/profile-activities/<activity_id>/groups/<group_id>/reject")
@with_db
def admin_reject_activity_group(activity_id: str, group_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403
    if not _can_review_profile_activity(admin):
        return jsonify({"detail": "Chỉ mentor cấp 1 mới được từ chối phân nhóm."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    group = next((row for row in activity.get("groups", []) if row.get("group_id") == group_id), None)
    if not group:
        return jsonify({"detail": "Nhóm không tồn tại"}), 404
    updated = reject_pending_group(activity, group_id)
    return jsonify(
        {
            "message": "Đã từ chối phân nhóm.",
            "activity": serialize_admin_profile_activity(updated),
        }
    )


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
    if not group_is_approved(group):
        return jsonify({"detail": "Nhóm đang chờ mentor cấp 1 duyệt."}), 400
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
    group = next((row for row in activity.get("groups", []) if row.get("group_id") == group_id), None)
    if not group:
        return jsonify({"detail": "Nhóm không tồn tại"}), 404
    if not group_is_approved(group):
        return jsonify({"detail": "Nhóm đang chờ mentor cấp 1 duyệt."}), 400
    finalize_group_and_sync_hdnk(activity, group_id, admin_display_name(admin))
    return jsonify({"message": "Đã chốt nhóm và đồng bộ HDNK + NCKH"})


@app.post("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/reject")
@with_db
def admin_reject_activity_registration(activity_id: str, mentee_id: str):
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
    updated, requires_l1 = submit_mentor_reject_registration(
        activity, mentee, admin, data.get("note", "")
    )
    if requires_l1:
        return jsonify({"message": "Đã gửi từ chối, chờ mentor cấp 1 duyệt trước khi mentee thấy."})
    return jsonify({"message": "Đã từ chối báo danh mentee."})


@app.post("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/reject/approve")
@with_db
def admin_approve_reject_activity_registration(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403
    if not _can_review_profile_activity(admin):
        return jsonify({"detail": "Chỉ mentor cấp 1 mới được duyệt từ chối báo danh."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    if not ObjectId.is_valid(mentee_id):
        return jsonify({"detail": "Mentee không tồn tại"}), 404
    approve_pending_mentor_reject(activity, mentee_id, admin)
    return jsonify({"message": "Đã duyệt từ chối báo danh — mentee sẽ được thông báo."})


@app.post("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/reject/deny")
@with_db
def admin_deny_reject_activity_registration(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403
    if not _can_review_profile_activity(admin):
        return jsonify({"detail": "Chỉ mentor cấp 1 mới được hủy yêu cầu từ chối."}), 403

    activity, error = _get_activity_or_404(activity_id)
    if error:
        return error
    if not ObjectId.is_valid(mentee_id):
        return jsonify({"detail": "Mentee không tồn tại"}), 404
    reject_pending_mentor_reject(activity, mentee_id)
    return jsonify({"message": "Đã hủy yêu cầu từ chối báo danh."})
