"""Daily 10:00 AM Vietnam-time digest of mentor profile activities for mentees."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from auth.users import approved_mentee_status_filter
from config import ROLE_MENTEE
from database import profile_activities, users
from services.mentee_email_prefs import mentee_email_notify_activities_enabled
from services.profile_activities import (
    PROFILE_ACTIVITY_APPROVAL_APPROVED,
    compose_activity_name,
    serialize_profile_activity_for_feed,
)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _digest_since(mentee: dict) -> datetime:
    last_sent = mentee.get("last_activity_digest_sent_at")
    if last_sent:
        if getattr(last_sent, "tzinfo", None) is None:
            return last_sent.replace(tzinfo=timezone.utc)
        return last_sent
    return datetime.now(timezone.utc) - timedelta(hours=24)


def list_activities_for_mentee_digest(mentee: dict) -> list[dict]:
    mentor = (mentee.get("mentor") or "").strip()
    if not mentor:
        return []

    since = _digest_since(mentee)
    query = {
        "mentor_name": mentor,
        "$or": [
            {"approval_status": {"$exists": False}},
            {"approval_status": PROFILE_ACTIVITY_APPROVAL_APPROVED},
        ],
        "updated_at": {"$gt": since},
    }
    visible: list[dict] = []
    seen_ids: set[str] = set()
    for doc in profile_activities.find(query).sort("updated_at", 1):
        doc_id = str(doc.get("_id", ""))
        if doc_id in seen_ids:
            continue
        payload = serialize_profile_activity_for_feed(doc, mentee, exclude_from_feed=True)
        if not payload:
            continue
        seen_ids.add(doc_id)
        visible.append(doc)
    return visible


def send_activity_digest_for_mentee(mentee: dict, *, dry_run: bool = False) -> dict:
    if not mentee_email_notify_activities_enabled(mentee):
        return {"sent": False, "reason": "disabled", "count": 0}

    email = (mentee.get("email") or "").strip()
    if not email:
        return {"sent": False, "reason": "no_email", "count": 0}

    activities = list_activities_for_mentee_digest(mentee)
    if not activities:
        return {"sent": False, "reason": "empty", "count": 0}

    names = [compose_activity_name(item) for item in activities]
    count = len(names)

    if dry_run:
        return {
            "sent": False,
            "dry_run": True,
            "count": count,
            "activity_names": names,
            "mentee_id": str(mentee.get("_id", "")),
            "email": email,
        }

    import os

    from email_notify import send_mentee_activity_digest_email

    profile_url = os.getenv("MENTEE_PROFILE_URL", "http://localhost:5173/profile").strip()
    mentee_name = mentee.get("full_name") or mentee.get("username") or email

    sent = send_mentee_activity_digest_email(
        to_email=email,
        mentee_name=mentee_name,
        activity_names=names,
        profile_url=profile_url,
    )
    if sent:
        now = datetime.now(timezone.utc)
        users.update_one(
            {"_id": mentee["_id"]},
            {"$set": {"last_activity_digest_sent_at": now}},
        )
    return {"sent": bool(sent), "count": count, "mentee_id": str(mentee["_id"])}


def process_mentee_activity_digests(*, dry_run: bool = False) -> dict:
    query = {
        "role": ROLE_MENTEE,
        "email_notify_activities": True,
        **approved_mentee_status_filter(),
    }
    results: list[dict] = []
    sent_count = 0
    skipped_count = 0

    for mentee in users.find(query):
        outcome = send_activity_digest_for_mentee(mentee, dry_run=dry_run)
        results.append(outcome)
        if outcome.get("sent"):
            sent_count += 1
        elif outcome.get("reason") == "empty":
            skipped_count += 1

    return {
        "processed": len(results),
        "sent_count": sent_count,
        "skipped_empty": skipped_count,
        "dry_run": dry_run,
        "results": results if dry_run else None,
    }


def is_activity_digest_window() -> bool:
    """True during the 10:00–10:59 Asia/Ho_Chi_Minh hour."""
    return datetime.now(VN_TZ).hour == 10
