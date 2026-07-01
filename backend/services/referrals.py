"""Referral points: mentor-entered referrer Zalo phone on activity creation."""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from auth.validators import normalize_zalo_phone
from config import ROLE_MENTEE, ROLE_PARENT
from database import pending_referrals, users


def referral_points_for_user(user: dict | None) -> int:
    if not user:
        return 0
    try:
        return max(0, int(user.get("referral_points") or 0))
    except (TypeError, ValueError):
        return 0


def _find_mentee_by_zalo_phone(phone: str) -> dict | None:
    if not phone:
        return None
    return users.find_one(
        {
            "zalo_phone": phone,
            "role": {"$nin": [ROLE_PARENT, None]},
        }
    )


def _increment_referral_points(mentee_id: ObjectId, amount: int = 1) -> None:
    if amount <= 0:
        return
    users.update_one({"_id": mentee_id}, {"$inc": {"referral_points": amount}})


def award_referrer_phone_for_activity(*, phone: str, activity_id: ObjectId) -> str:
    """Award referral point(s) for one activity's referrer phone.

    Returns: ``"awarded"`` if matched an existing mentee, ``"pending"`` if stored
    for later, ``"skipped"`` if phone empty.
    """
    normalized = normalize_zalo_phone(phone)
    if not normalized:
        return "skipped"

    mentee = _find_mentee_by_zalo_phone(normalized)
    now = datetime.now(timezone.utc)
    if mentee:
        _increment_referral_points(mentee["_id"], 1)
        return "awarded"

    pending_referrals.insert_one(
        {
            "phone": normalized,
            "activity_id": str(activity_id),
            "created_at": now,
            "fulfilled_at": None,
            "mentee_id": None,
        }
    )
    return "pending"


def fulfill_pending_referrals_for_phone(phone: str, mentee_id: ObjectId | str) -> int:
    """Retroactively award pending referral points when a mentee gets this Zalo phone."""
    normalized = normalize_zalo_phone(phone)
    if not normalized:
        return 0

    now = datetime.now(timezone.utc)
    mentee_oid = mentee_id if isinstance(mentee_id, ObjectId) else ObjectId(str(mentee_id))
    pending = list(
        pending_referrals.find(
            {"phone": normalized, "fulfilled_at": None},
        )
    )
    if not pending:
        return 0

    count = len(pending)
    _increment_referral_points(mentee_oid, count)
    pending_referrals.update_many(
        {"_id": {"$in": [doc["_id"] for doc in pending]}},
        {"$set": {"fulfilled_at": now, "mentee_id": str(mentee_oid)}},
    )
    return count
