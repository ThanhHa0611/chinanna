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
    ProfileActivityBulkImportError,
    ProfileActivityKeeptrackError,
    ProfileActivityRegistrationError,
    ProfileActivityUpdateError,
    add_mentee_to_group,
    approve_pending_group,
    approve_pending_mentor_reject,
    approve_keeptrack_abandon,
    approve_profile_activity,
    bulk_view_individual_keeptrack_reviews,
    create_profile_activity,
    delete_activity,
    delete_activity_group,
    enforce_participant_capacity,
    finalize_group_and_sync_hdnk,
    group_is_approved,
    invite_mentees_to_activity,
    ProfileActivityGroupDeleteError,
    ProfileActivityGroupLeaderError,
    ProfileActivityInviteError,
    set_group_leader,
    list_pending_individual_keeptrack_reviews,
    list_pending_keeptrack_abandon_requests,
    list_progress_tracking_for_admin,
    move_mentee_to_group,
    notify_group_assignment,
    parse_profile_activities_bulk_excel,
    parse_profile_activity_from_description,
    reject_individual_keeptrack_review,
    reject_keeptrack_abandon,
    reject_pending_group,
    reject_pending_mentor_reject,
    reject_profile_activity,
    remove_progress_tracking_row,
    remove_mentee_from_group,
    sanitize_profile_activity_input,
    serialize_admin_profile_activity,
    serialize_admin_registration,
    submit_mentor_reject_registration,
    suggest_group_name,
    update_activity_keeptrack,
    update_profile_activity,
    upsert_activity_group,
    view_individual_keeptrack_review,
)


def _get_activity_or_404(activity_id: str, admin: dict):
    try:
        oid = ObjectId(activity_id)
    except InvalidId:
        return None, (jsonify({"detail": "Hoạt động không tồn tại"}), 404)
    activity = profile_activities.find_one({"_id": oid})
    if not activity:
        return None, (jsonify({"detail": "Hoạt động không tồn tại"}), 404)
    if not _admin_can_access_activity(admin, activity):
        # Không tiết lộ sự tồn tại của hoạt động thuộc nhánh mentor khác.
        return None, (jsonify({"detail": "Hoạt động không tồn tại"}), 404)
    return activity, None


def _admin_can_access_activity(admin: dict, activity: dict) -> bool:
    if is_super_admin(admin):
        return True
    admin_mentor = (admin.get("mentor_name") or "").strip()
    if not admin_mentor:
        return True
    activity_mentor = (activity.get("mentor_name") or "").strip()
    if not activity_mentor:
        return True
    return activity_mentor == admin_mentor


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
    response = serialize_admin_profile_activity(created, admin=admin)
    if created.get("approval_status") == "pending_l1_approval":
        response["message"] = "Hoạt động đã gửi, chờ mentor cấp 1 duyệt trước khi hiển thị cho mentee."
    return jsonify(response), 201


@app.post("/api/admin/profile-activities/bulk-import/parse")
@with_db
def admin_bulk_import_parse_profile_activities():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"detail": "Chưa chọn file để tải lên"}), 400
    if not uploaded.filename.lower().endswith(".xlsx"):
        return jsonify({"detail": "Chỉ hỗ trợ file Excel (.xlsx)"}), 400

    try:
        result = parse_profile_activities_bulk_excel(uploaded)
    except ProfileActivityBulkImportError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify(result)


@app.post("/api/admin/profile-activities/bulk-import/create")
@with_db
def admin_bulk_import_create_profile_activities():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify({"detail": "Thiếu danh sách hoạt động cần tạo."}), 400

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row_index = item.get("row_index")
        try:
            payload = sanitize_profile_activity_input(item)
            if not payload.get("activity_name"):
                raise ValueError("Không thể tạo tên hoạt động — vui lòng điền loại hoạt động")
            created = create_profile_activity(admin, payload)
            results.append(
                {
                    "row_index": row_index,
                    "success": True,
                    "activity": serialize_admin_profile_activity(created, admin=admin),
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 - one bad row must not abort the whole batch
            results.append(
                {
                    "row_index": row_index,
                    "success": False,
                    "activity": None,
                    "error": str(exc) or "Không tạo được hoạt động",
                }
            )
    return jsonify({"results": results})


@app.get("/api/admin/profile-activities")
@with_db
def admin_list_profile_activities():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    cursor = profile_activities.find(_admin_activity_query(admin)).sort("created_at", -1)
    items = [serialize_admin_profile_activity(doc, admin=admin) for doc in cursor]
    total_pending_count = sum(item.get("pending_action_count", 0) for item in items)
    return jsonify({"items": items, "total_pending_count": total_pending_count})


@app.patch("/api/admin/profile-activities/<activity_id>")
@with_db
def admin_update_profile_activity(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    try:
        updated = update_profile_activity(activity, admin, data)
    except ProfileActivityUpdateError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify(serialize_admin_profile_activity(updated, admin=admin))


@app.delete("/api/admin/profile-activities/<activity_id>")
@with_db
def admin_delete_profile_activity(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    success, message = delete_activity(activity_id, admin)
    if not success:
        status = 404 if "không tồn tại" in message else 403
        return jsonify({"detail": message}), status
    return jsonify({"message": message})


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

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    if activity.get("approval_status") == "approved":
        return jsonify(serialize_admin_profile_activity(activity, admin=admin))
    updated = approve_profile_activity(activity, admin)
    return jsonify(serialize_admin_profile_activity(updated, admin=admin))


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

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    updated = reject_profile_activity(activity, admin)
    return jsonify(serialize_admin_profile_activity(updated, admin=admin))


@app.get("/api/admin/profile-activities/<activity_id>/registrations")
@with_db
def admin_activity_registrations(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
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


@app.post("/api/admin/profile-activities/<activity_id>/invite")
@with_db
def admin_invite_mentees_to_activity(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    mentee_ids = data.get("mentee_ids")
    if not isinstance(mentee_ids, list) or not mentee_ids:
        return jsonify({"detail": "Vui lòng chọn ít nhất một mentee để mời."}), 400

    try:
        result = invite_mentees_to_activity(activity, mentee_ids, admin)
    except ProfileActivityInviteError as exc:
        return jsonify({"detail": str(exc)}), 400

    return jsonify(
        {
            "invited_count": len(result.get("invited") or []),
            "skipped": result.get("skipped") or [],
            "activity": serialize_admin_profile_activity(result["activity"], admin=admin),
        }
    )


@app.get("/api/admin/profile-activities/<activity_id>/groups/suggest-name")
@with_db
def admin_suggest_activity_group_name(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    return jsonify({"suggested_name": suggest_group_name(activity)})


@app.patch("/api/admin/profile-activities/<activity_id>/groups")
@with_db
def admin_upsert_activity_group(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    group, requires_l1 = upsert_activity_group(activity, data, admin)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": activity.get("groups", []), "updated_at": datetime.now(timezone.utc)}},
    )
    saved_group = None
    groups_response = activity.get("groups", [])
    if not requires_l1:
        refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
        saved_group = next(
            (row for row in refreshed.get("groups", []) if row.get("group_id") == group.get("group_id")),
            None,
        )
        if saved_group and group_is_approved(saved_group) and not saved_group.get("notification_sent_at"):
            notify_group_assignment(refreshed, saved_group)
        # Creating/editing a group is an instant mentor approval for non-L1-gated
        # admins, so this can also be the action that pushes the activity over its
        # participant_limit — re-check capacity here too.
        refreshed = enforce_participant_capacity(refreshed)
        groups_response = refreshed.get("groups", [])
    response = {"group": group, "groups": groups_response}
    if requires_l1:
        response["message"] = "Đã gửi phân nhóm, chờ mentor cấp 1 duyệt trước khi mentee thấy."
    elif saved_group and group_is_approved(saved_group):
        response["message"] = "Đã tạo nhóm — mentee sẽ nhận thông báo sau khi chốt nhóm."
    return jsonify(response)


@app.post("/api/admin/profile-activities/<activity_id>/groups/<group_id>/add-mentee")
@with_db
def admin_add_mentee_to_group(activity_id: str, group_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    mentee_id = str(data.get("mentee_id") or "").strip()
    if not mentee_id:
        return jsonify({"detail": "Thiếu mentee_id"}), 400
    try:
        group, requires_l1 = add_mentee_to_group(activity, group_id, mentee_id, admin)
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 404
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": activity.get("groups", []), "updated_at": datetime.now(timezone.utc)}},
    )
    groups_response = activity.get("groups", [])
    if not requires_l1:
        refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
        refreshed = enforce_participant_capacity(refreshed)
        groups_response = refreshed.get("groups", [])
    response = {"group": group, "groups": groups_response}
    if requires_l1:
        response["message"] = "Đã gửi thêm mentee vào nhóm, chờ mentor cấp 1 duyệt."
    return jsonify(response)


@app.post("/api/admin/profile-activities/<activity_id>/groups/<group_id>/remove-mentee")
@with_db
def admin_remove_mentee_from_group(activity_id: str, group_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    mentee_id = str(data.get("mentee_id") or "").strip()
    if not mentee_id:
        return jsonify({"detail": "Thiếu mentee_id"}), 400
    try:
        group, requires_l1 = remove_mentee_from_group(activity, group_id, mentee_id, admin)
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 404
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": activity.get("groups", []), "updated_at": datetime.now(timezone.utc)}},
    )
    response = {"group": group, "groups": activity.get("groups", [])}
    if requires_l1:
        response["message"] = "Đã gửi xóa mentee khỏi nhóm, chờ mentor cấp 1 duyệt."
    return jsonify(response)


@app.post("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/move-group")
@with_db
def admin_move_mentee_group(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    target_group_id = str(data.get("target_group_id") or "").strip()
    if not target_group_id:
        return jsonify({"detail": "Thiếu target_group_id"}), 400
    try:
        group, requires_l1 = move_mentee_to_group(activity, mentee_id, target_group_id, admin)
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 404
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": activity.get("groups", []), "updated_at": datetime.now(timezone.utc)}},
    )
    response = {"group": group, "groups": activity.get("groups", [])}
    if requires_l1:
        response["message"] = "Đã gửi chuyển nhóm, chờ mentor cấp 1 duyệt."
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

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    group = next((row for row in activity.get("groups", []) if row.get("group_id") == group_id), None)
    if not group:
        return jsonify({"detail": "Nhóm không tồn tại"}), 404
    updated = approve_pending_group(activity, group_id, admin)
    return jsonify(
        {
            "message": "Đã duyệt phân nhóm — mentee sẽ nhận thông báo.",
            "activity": serialize_admin_profile_activity(updated, admin=admin),
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

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    group = next((row for row in activity.get("groups", []) if row.get("group_id") == group_id), None)
    if not group:
        return jsonify({"detail": "Nhóm không tồn tại"}), 404
    updated = reject_pending_group(activity, group_id)
    return jsonify(
        {
            "message": "Đã từ chối phân nhóm.",
            "activity": serialize_admin_profile_activity(updated, admin=admin),
        }
    )


@app.delete("/api/admin/profile-activities/<activity_id>/groups/<group_id>")
@with_db
def admin_delete_activity_group(activity_id: str, group_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    try:
        updated = delete_activity_group(activity, group_id, admin)
    except ProfileActivityGroupDeleteError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify(
        {
            "message": "Đã xóa nhóm — mentee (nếu có) trở về trạng thái chờ phân nhóm.",
            "activity": serialize_admin_profile_activity(updated, admin=admin),
        }
    )


@app.post("/api/admin/profile-activities/<activity_id>/groups/<group_id>/finalize")
@with_db
def admin_finalize_activity_group(activity_id: str, group_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    group = next((row for row in activity.get("groups", []) if row.get("group_id") == group_id), None)
    if not group:
        return jsonify({"detail": "Nhóm không tồn tại"}), 404
    if not group_is_approved(group):
        return jsonify({"detail": "Nhóm đang chờ mentor cấp 1 duyệt."}), 400
    try:
        finalize_group_and_sync_hdnk(activity, group_id, admin_display_name(admin))
    except ProfileActivityKeeptrackError as exc:
        return jsonify({"detail": str(exc)}), 400
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    return jsonify(
        {
            "message": "Đã chốt nhóm và đồng bộ HDNK + NCKH",
            "activity": serialize_admin_profile_activity(refreshed, admin=admin),
        }
    )


@app.patch("/api/admin/profile-activities/<activity_id>/groups/<group_id>/leader")
@with_db
def admin_set_activity_group_leader(activity_id: str, group_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    mentee_id = str(data.get("mentee_id") or "").strip()
    if not mentee_id:
        return jsonify({"detail": "Vui lòng chọn mentee làm nhóm trưởng."}), 400
    try:
        updated = set_group_leader(activity, group_id, mentee_id)
    except ProfileActivityGroupLeaderError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify(
        {
            "message": "Đã chọn nhóm trưởng.",
            "activity": serialize_admin_profile_activity(updated, admin=admin),
        }
    )


@app.post("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/reject")
@with_db
def admin_reject_activity_registration(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
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

    activity, error = _get_activity_or_404(activity_id, admin)
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

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    if not ObjectId.is_valid(mentee_id):
        return jsonify({"detail": "Mentee không tồn tại"}), 404
    reject_pending_mentor_reject(activity, mentee_id)
    return jsonify({"message": "Đã hủy yêu cầu từ chối báo danh."})


@app.patch("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/keeptrack")
@with_db
def admin_update_activity_keeptrack(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    if not ObjectId.is_valid(mentee_id):
        return jsonify({"detail": "Mentee không tồn tại"}), 404
    mentee = users.find_one({"_id": ObjectId(mentee_id)})
    if not mentee:
        return jsonify({"detail": "Mentee không tồn tại"}), 404
    data = request.get_json(silent=True) or {}
    try:
        update_activity_keeptrack(activity, mentee_id, data, from_mentor=True)
    except ProfileActivityKeeptrackError as exc:
        return jsonify({"detail": str(exc)}), 400
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    state = next(
        (item for item in refreshed.get("mentee_states", []) if item.get("mentee_id") == mentee_id),
        {},
    )
    return jsonify(
        {
            "message": "Đã cập nhật tiến độ",
            "registration": serialize_admin_registration(refreshed, state, mentee),
        }
    )


@app.get("/api/admin/profile-activities/keeptrack-reviews")
@with_db
def admin_list_keeptrack_reviews():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    items = list_pending_individual_keeptrack_reviews(admin)
    return jsonify({"items": items, "total_pending_count": len(items)})


@app.post("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/keeptrack-reviews/view")
@with_db
def admin_view_keeptrack_review(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    try:
        view_individual_keeptrack_review(activity, mentee_id, admin)
    except ProfileActivityKeeptrackError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify({"message": "Đã xem cập nhật tiến độ"})


@app.post("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/keeptrack-reviews/reject")
@with_db
def admin_reject_keeptrack_review(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        reject_individual_keeptrack_review(activity, mentee_id, admin, data.get("note", ""))
    except ProfileActivityKeeptrackError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify({"message": "Đã từ chối và hoàn tác tiến độ mentee"})


@app.post("/api/admin/profile-activities/keeptrack-reviews/view-bulk")
@with_db
def admin_bulk_view_keeptrack_reviews():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify({"detail": "Thiếu danh sách cập nhật tiến độ."}), 400
    updated = bulk_view_individual_keeptrack_reviews(items, admin)
    return jsonify({"message": f"Đã đánh dấu đã xem {updated} cập nhật.", "updated_count": updated})


@app.get("/api/admin/profile-activities/keeptrack-abandon-requests")
@with_db
def admin_list_keeptrack_abandon_requests():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    items = list_pending_keeptrack_abandon_requests(admin)
    return jsonify({"items": items, "total_pending_count": len(items)})


@app.post("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/keeptrack-abandon/approve")
@with_db
def admin_approve_keeptrack_abandon(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    try:
        approve_keeptrack_abandon(activity, mentee_id, admin)
    except ProfileActivityKeeptrackError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify({"message": "Đã đồng ý từ bỏ — hoạt động đã gỡ khỏi Keep track"})


@app.post("/api/admin/profile-activities/<activity_id>/registrations/<mentee_id>/keeptrack-abandon/reject")
@with_db
def admin_reject_keeptrack_abandon(activity_id: str, mentee_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        reject_keeptrack_abandon(activity, mentee_id, admin, data.get("note", ""))
    except ProfileActivityKeeptrackError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify({"message": "Đã từ chối yêu cầu từ bỏ — mentee tiếp tục theo dõi hoạt động"})


@app.get("/api/admin/profile-activities/progress-tracking")
@with_db
def admin_list_progress_tracking():
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activities = list_progress_tracking_for_admin(admin)
    row_count = sum(len(item.get("rows") or []) for item in activities)
    return jsonify({"activities": activities, "row_count": row_count})


@app.delete("/api/admin/profile-activities/<activity_id>/progress-tracking")
@with_db
def admin_remove_progress_tracking_row(activity_id: str):
    admin, error_response = get_authenticated_admin()
    if error_response:
        return error_response
    if not admin_is_approved(admin):
        return jsonify({"detail": "Tài khoản chưa được cấp quyền admin."}), 403

    activity, error = _get_activity_or_404(activity_id, admin)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        remove_progress_tracking_row(
            activity,
            row_type=data.get("type", ""),
            group_id=data.get("group_id", ""),
            mentee_id=data.get("mentee_id", ""),
            admin=admin,
        )
    except ProfileActivityKeeptrackError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify({"message": "Đã gỡ khỏi bảng theo dõi tiến độ"})
