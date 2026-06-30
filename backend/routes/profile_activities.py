from bson import ObjectId
from bson.errors import InvalidId
from flask import jsonify, request

from auth.security import get_authenticated_user, require_mentee_account
from database import profile_activities, with_db
from extensions import app
from services.profile_activities import (
    ProfileActivityGroupResponseError,
    ProfileActivityKeeptrackError,
    ProfileActivityRegistrationError,
    activity_visible_to_mentee,
    build_mentee_activities_response,
    complete_activity_keeptrack,
    mark_activity_read,
    register_for_activity,
    request_keeptrack_abandon,
    serialize_profile_activity_for_feed,
    set_activity_hidden,
    update_group_response,
)


def _find_activity_or_404(activity_id: str):
    try:
        oid = ObjectId(activity_id)
    except InvalidId:
        return None, (jsonify({"detail": "Hoạt động không tồn tại"}), 404)
    activity = profile_activities.find_one({"_id": oid})
    if not activity:
        return None, (jsonify({"detail": "Hoạt động không tồn tại"}), 404)
    return activity, None


@app.get("/api/profile-activities")
@with_db
def mentee_list_profile_activities():
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    return jsonify(build_mentee_activities_response(user, max_other_days=10))


@app.get("/api/profile-activities/<activity_id>")
@with_db
def mentee_get_profile_activity(activity_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    activity, error = _find_activity_or_404(activity_id)
    if error:
        return error
    if not activity_visible_to_mentee(activity):
        return jsonify({"detail": "Hoạt động không tồn tại"}), 404
    mark_activity_read(activity, user)
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    payload = serialize_profile_activity_for_feed(refreshed, user, include_hidden=True)
    return jsonify(payload)


@app.post("/api/profile-activities/<activity_id>/read")
@with_db
def mentee_mark_profile_activity_read(activity_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    activity, error = _find_activity_or_404(activity_id)
    if error:
        return error
    if not activity_visible_to_mentee(activity):
        return jsonify({"detail": "Hoạt động không tồn tại"}), 404
    mark_activity_read(activity, user)
    return jsonify({"message": "Đã đánh dấu đã đọc"})


@app.post("/api/profile-activities/<activity_id>/hide")
@with_db
def mentee_hide_profile_activity(activity_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    activity, error = _find_activity_or_404(activity_id)
    if error:
        return error
    if not activity_visible_to_mentee(activity):
        return jsonify({"detail": "Hoạt động không tồn tại"}), 404
    data = request.get_json(silent=True) or {}
    hidden = bool(data.get("hidden", True))
    set_activity_hidden(activity, user, hidden)
    return jsonify({"message": "Đã cập nhật trạng thái ẩn"})


@app.post("/api/profile-activities/<activity_id>/register")
@with_db
def mentee_register_profile_activity(activity_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    activity, error = _find_activity_or_404(activity_id)
    if error:
        return error
    if not activity_visible_to_mentee(activity):
        return jsonify({"detail": "Hoạt động không tồn tại"}), 404
    data = request.get_json(silent=True) or {}
    participation_choice = data.get("participation_choice")
    try:
        register_for_activity(activity, user, participation_choice=participation_choice)
    except ProfileActivityRegistrationError as exc:
        return jsonify({"detail": str(exc)}), 400
    return jsonify({"message": "Đã báo danh"})


@app.post("/api/profile-activities/<activity_id>/group-response")
@with_db
def mentee_profile_activity_group_response(activity_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    activity, error = _find_activity_or_404(activity_id)
    if error:
        return error
    if not activity_visible_to_mentee(activity):
        return jsonify({"detail": "Hoạt động không tồn tại"}), 404
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in {"confirmed", "rejected"}:
        return jsonify({"detail": "Trạng thái phản hồi không hợp lệ"}), 400
    try:
        update_group_response(activity, user, status, data.get("note", ""))
    except ProfileActivityGroupResponseError as exc:
        return jsonify({"detail": str(exc)}), 400
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    payload = serialize_profile_activity_for_feed(refreshed, user, include_hidden=True)
    return jsonify({"message": "Đã gửi phản hồi nhóm", "activity": payload})


@app.post("/api/profile-activities/<activity_id>/keeptrack/complete")
@with_db
def mentee_complete_profile_activity_keeptrack(activity_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    activity, error = _find_activity_or_404(activity_id)
    if error:
        return error
    if not activity_visible_to_mentee(activity):
        return jsonify({"detail": "Hoạt động không tồn tại"}), 404
    data = request.get_json(silent=True) or {}
    try:
        complete_activity_keeptrack(activity, str(user["_id"]), data)
    except ProfileActivityKeeptrackError as exc:
        return jsonify({"detail": str(exc)}), 400
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    payload = serialize_profile_activity_for_feed(refreshed, user, include_hidden=True)
    return jsonify({"message": "Đã hoàn thành — tiến độ đã lưu vào Keep track", "activity": payload})


@app.post("/api/profile-activities/<activity_id>/keeptrack/abandon")
@with_db
def mentee_abandon_profile_activity_keeptrack(activity_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    activity, error = _find_activity_or_404(activity_id)
    if error:
        return error
    if not activity_visible_to_mentee(activity):
        return jsonify({"detail": "Hoạt động không tồn tại"}), 404
    data = request.get_json(silent=True) or {}
    try:
        request_keeptrack_abandon(activity, str(user["_id"]), data.get("note", ""))
    except ProfileActivityKeeptrackError as exc:
        return jsonify({"detail": str(exc)}), 400
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    payload = serialize_profile_activity_for_feed(refreshed, user, include_hidden=True)
    return jsonify({"message": "Đã gửi yêu cầu từ bỏ — chờ mentor xác nhận", "activity": payload})


@app.patch("/api/profile-activities/<activity_id>/keeptrack")
@with_db
def mentee_update_profile_activity_keeptrack(activity_id: str):
    user, error_response = get_authenticated_user()
    if error_response:
        return error_response
    user, error_response = require_mentee_account(user)
    if error_response:
        return error_response

    activity, error = _find_activity_or_404(activity_id)
    if error:
        return error
    if not activity_visible_to_mentee(activity):
        return jsonify({"detail": "Hoạt động không tồn tại"}), 404
    return jsonify({"detail": "Vui lòng dùng Hoàn thành hoặc Từ bỏ để cập nhật tiến độ."}), 400
