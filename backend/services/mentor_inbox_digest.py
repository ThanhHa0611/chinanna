"""Daily 10:00 AM Vietnam-time digest of yesterday's mentor inbox activity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from config import BACKEND_PUBLIC_URL
from database import db, mentor_inbox
from inbox_tasks import (
    _vn_day_start_from_key,
    build_archive_day_summary,
    list_inbox_for_day,
)
from services.notifications import mentor_branch_notify_emails

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_digest_state = db["digest_state"]


def is_inbox_digest_window() -> bool:
    """True during the 10:00–10:59 Asia/Ho_Chi_Minh hour."""
    return datetime.now(VN_TZ).hour == 10


def _yesterday_date_key() -> str:
    local_now = datetime.now(VN_TZ)
    yesterday = (local_now - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return yesterday.strftime("%Y-%m-%d")


def _digest_already_sent(mentor_name: str, date_key: str) -> bool:
    return bool(
        _digest_state.find_one(
            {
                "kind": "mentor_inbox_daily",
                "mentor_name": mentor_name,
                "summary_date_key": date_key,
            }
        )
    )


def _mark_digest_sent(mentor_name: str, date_key: str) -> None:
    now = datetime.now(timezone.utc)
    _digest_state.update_one(
        {
            "kind": "mentor_inbox_daily",
            "mentor_name": mentor_name,
            "summary_date_key": date_key,
        },
        {"$set": {"sent_at": now}},
        upsert=True,
    )


def list_mentors_with_inbox_on_day(date_key: str) -> list[str]:
    day_start = _vn_day_start_from_key(date_key)
    if not day_start:
        return []
    day_end = day_start + timedelta(days=1)
    mentor_names = mentor_inbox.distinct(
        "mentor_name",
        {
            "audience": "mentor",
            "$or": [
                {"created_at": {"$gte": day_start, "$lt": day_end}},
                {"processed_at": {"$gte": day_start, "$lt": day_end}},
            ],
        },
    )
    return sorted((name or "").strip() for name in mentor_names if (name or "").strip())


def send_inbox_digest_for_mentor(
    mentor_name: str,
    *,
    date_key: str | None = None,
    dry_run: bool = False,
) -> dict:
    branch = (mentor_name or "").strip()
    if not branch:
        return {"sent": False, "reason": "no_mentor", "count": 0}

    summary_date_key = date_key or _yesterday_date_key()
    admin = {"mentor_name": branch}
    items = list_inbox_for_day(
        mentor_inbox,
        admin,
        summary_date_key,
        limit=200,
        base_url=BACKEND_PUBLIC_URL,
    )
    if not items:
        return {
            "sent": False,
            "reason": "empty",
            "count": 0,
            "mentor_name": branch,
            "date_key": summary_date_key,
        }

    summary = build_archive_day_summary(items, summary_date_key)
    summary_items = summary.get("items") or []
    if not summary_items:
        return {
            "sent": False,
            "reason": "empty",
            "count": 0,
            "mentor_name": branch,
            "date_key": summary_date_key,
        }

    if _digest_already_sent(branch, summary_date_key):
        return {
            "sent": False,
            "reason": "already_sent",
            "count": len(summary_items),
            "mentor_name": branch,
            "date_key": summary_date_key,
        }

    notify_emails = mentor_branch_notify_emails(branch)
    if not notify_emails:
        return {
            "sent": False,
            "reason": "no_email",
            "count": len(summary_items),
            "mentor_name": branch,
            "date_key": summary_date_key,
        }

    date_label = summary.get("date_label") or summary_date_key

    if dry_run:
        return {
            "sent": False,
            "dry_run": True,
            "count": len(summary_items),
            "items": summary_items,
            "mentor_name": branch,
            "date_key": summary_date_key,
            "date_label": date_label,
            "emails": notify_emails,
        }

    from email_notify import send_daily_inbox_summary_email

    sent_any = False
    for email in notify_emails:
        if send_daily_inbox_summary_email(
            to_email=email,
            date_label=date_label,
            items=summary_items,
        ):
            sent_any = True

    if sent_any:
        _mark_digest_sent(branch, summary_date_key)

    return {
        "sent": sent_any,
        "count": len(summary_items),
        "mentor_name": branch,
        "date_key": summary_date_key,
        "date_label": date_label,
        "email_count": len(notify_emails),
    }


def process_mentor_inbox_digests(*, dry_run: bool = False, date_key: str | None = None) -> dict:
    summary_date_key = date_key or _yesterday_date_key()
    mentor_names = list_mentors_with_inbox_on_day(summary_date_key)
    results: list[dict] = []
    sent_count = 0
    skipped_empty = 0
    skipped_already_sent = 0

    for mentor_name in mentor_names:
        outcome = send_inbox_digest_for_mentor(
            mentor_name,
            date_key=summary_date_key,
            dry_run=dry_run,
        )
        results.append(outcome)
        if outcome.get("sent"):
            sent_count += 1
        elif outcome.get("reason") == "empty":
            skipped_empty += 1
        elif outcome.get("reason") == "already_sent":
            skipped_already_sent += 1

    return {
        "date_key": summary_date_key,
        "processed": len(results),
        "sent_count": sent_count,
        "skipped_empty": skipped_empty,
        "skipped_already_sent": skipped_already_sent,
        "dry_run": dry_run,
        "results": results if dry_run else None,
    }
