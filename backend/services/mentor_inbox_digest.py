"""Daily 10:00 AM Vietnam-time digest of unprocessed mentor inbox items."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from zoneinfo import ZoneInfo

from database import admins, db, mentor_inbox
from inbox_tasks import format_mentee_action_line, inbox_section_label
from services.notifications import mentor_branch_notify_emails

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_digest_state = db["digest_state"]


def is_inbox_digest_window() -> bool:
    """True during the 10:00–10:59 Asia/Ho_Chi_Minh hour."""
    return datetime.now(VN_TZ).hour == 10


def _vn_today_start() -> datetime:
    local_now = datetime.now(VN_TZ)
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def _digest_already_sent_today(mentor_name: str) -> bool:
    today_start = _vn_today_start()
    if admins.find_one(
        {"mentor_name": mentor_name, "last_inbox_digest_sent_at": {"$gte": today_start}}
    ):
        return True
    return bool(
        _digest_state.find_one(
            {
                "kind": "mentor_inbox",
                "mentor_name": mentor_name,
                "sent_at": {"$gte": today_start},
            }
        )
    )


def _mark_digest_sent(mentor_name: str) -> None:
    now = datetime.now(timezone.utc)
    admins.update_many(
        {"mentor_name": mentor_name},
        {"$set": {"last_inbox_digest_sent_at": now}},
    )
    _digest_state.update_one(
        {"kind": "mentor_inbox", "mentor_name": mentor_name},
        {"$set": {"sent_at": now}},
        upsert=True,
    )


def list_unprocessed_items_for_mentor(mentor_name: str) -> list[dict]:
    branch = (mentor_name or "").strip()
    if not branch:
        return []
    return list(
        mentor_inbox.find(
            {"audience": "mentor", "mentor_name": branch, "status": "pending"},
        ).sort("created_at", -1)
    )


def format_digest_line(doc: dict) -> str:
    section = inbox_section_label(doc.get("action") or "")
    action_line = format_mentee_action_line(doc)
    return f"[{section}] {action_line}"


def send_inbox_digest_for_mentor(mentor_name: str, *, dry_run: bool = False) -> dict:
    branch = (mentor_name or "").strip()
    if not branch:
        return {"sent": False, "reason": "no_mentor", "count": 0}

    items = list_unprocessed_items_for_mentor(branch)
    if not items:
        return {"sent": False, "reason": "empty", "count": 0, "mentor_name": branch}

    if _digest_already_sent_today(branch):
        return {"sent": False, "reason": "already_sent_today", "count": len(items), "mentor_name": branch}

    lines = [format_digest_line(item) for item in items]
    notify_emails = mentor_branch_notify_emails(branch)
    if not notify_emails:
        return {"sent": False, "reason": "no_email", "count": len(items), "mentor_name": branch}

    if dry_run:
        return {
            "sent": False,
            "dry_run": True,
            "count": len(lines),
            "lines": lines,
            "mentor_name": branch,
            "emails": notify_emails,
        }

    from email_notify import send_mentor_inbox_digest_email

    admin_url = os.getenv("MENTOR_ADMIN_URL", "http://localhost:5174/").strip()
    sent_any = False
    for email in notify_emails:
        if send_mentor_inbox_digest_email(
            to_email=email,
            item_lines=lines,
            admin_url=admin_url,
        ):
            sent_any = True

    if sent_any:
        _mark_digest_sent(branch)

    return {
        "sent": sent_any,
        "count": len(lines),
        "mentor_name": branch,
        "email_count": len(notify_emails),
    }


def process_mentor_inbox_digests(*, dry_run: bool = False) -> dict:
    mentor_names = mentor_inbox.distinct(
        "mentor_name",
        {"audience": "mentor", "status": "pending"},
    )
    results: list[dict] = []
    sent_count = 0
    skipped_empty = 0
    skipped_already_sent = 0

    for mentor_name in sorted((name or "").strip() for name in mentor_names if (name or "").strip()):
        outcome = send_inbox_digest_for_mentor(mentor_name, dry_run=dry_run)
        results.append(outcome)
        if outcome.get("sent"):
            sent_count += 1
        elif outcome.get("reason") == "empty":
            skipped_empty += 1
        elif outcome.get("reason") == "already_sent_today":
            skipped_already_sent += 1

    return {
        "processed": len(results),
        "sent_count": sent_count,
        "skipped_empty": skipped_empty,
        "skipped_already_sent": skipped_already_sent,
        "dry_run": dry_run,
        "results": results if dry_run else None,
    }
