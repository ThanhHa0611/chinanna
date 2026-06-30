
from config import PROFILE_INFO_REMINDER_MESSAGE, PROFILE_INFO_FIELD_LABELS
from database import users


def _field_value(user: dict, key: str) -> str:
    return str(user.get(key) or "").strip()


def get_missing_profile_field_keys(user: dict) -> list[str]:
    missing = []
    for key in PROFILE_INFO_FIELD_LABELS:
        if not _field_value(user, key):
            missing.append(key)
    return missing


def missing_profile_field_items(user: dict) -> list[dict]:
    return [
        {"key": key, "label": PROFILE_INFO_FIELD_LABELS[key]}
        for key in get_missing_profile_field_keys(user)
    ]


def is_profile_info_complete(user: dict) -> bool:
    return not get_missing_profile_field_keys(user)


def serialize_profile_info_reminder(user: dict) -> dict | None:
    reminder = user.get("profile_info_reminder") or {}
    if not reminder.get("sent_at"):
        return None

    stored_keys = [
        key
        for key in (reminder.get("field_keys") or [])
        if key in PROFILE_INFO_FIELD_LABELS
    ]
    still_missing = get_missing_profile_field_keys(user)
    field_keys = [key for key in stored_keys if key in still_missing] or still_missing
    if not field_keys and not reminder.get("mentee_unread"):
        return None

    return {
        "message": reminder.get("message") or PROFILE_INFO_REMINDER_MESSAGE,
        "field_keys": field_keys,
        "items": [
            {"key": key, "label": PROFILE_INFO_FIELD_LABELS[key]}
            for key in field_keys
        ],
        "unread": bool(reminder.get("mentee_unread")),
        "sent_at": reminder["sent_at"].isoformat() if reminder.get("sent_at") else "",
    }


def profile_info_reminder_unread(user: dict) -> bool:
    reminder = serialize_profile_info_reminder(user)
    return bool(reminder and reminder.get("unread"))


def sync_profile_info_reminder(user_id):
    user = users.find_one({"_id": user_id})
    if not user:
        return
    reminder = user.get("profile_info_reminder") or {}
    if not reminder:
        return
    if is_profile_info_complete(user):
        users.update_one({"_id": user_id}, {"$unset": {"profile_info_reminder": ""}})
        return
    stored_keys = [
        key
        for key in (reminder.get("field_keys") or [])
        if key in PROFILE_INFO_FIELD_LABELS
    ]
    still_missing = get_missing_profile_field_keys(user)
    field_keys = [key for key in stored_keys if key in still_missing]
    if not field_keys:
        users.update_one({"_id": user_id}, {"$unset": {"profile_info_reminder": ""}})
        return
    users.update_one(
        {"_id": user_id},
        {"$set": {"profile_info_reminder.field_keys": field_keys}},
    )
