"""Mentee extracurricular activity digest — removed (no daily emails)."""

from __future__ import annotations


def process_mentee_activity_digests(*, dry_run: bool = False) -> dict:
    return {
        "processed": 0,
        "sent_count": 0,
        "skipped_empty": 0,
        "dry_run": dry_run,
        "removed": True,
        "results": None,
    }


def send_activity_digest_for_mentee(mentee: dict, *, dry_run: bool = False) -> dict:
    return {"sent": False, "reason": "removed", "count": 0}


def is_activity_digest_window() -> bool:
    return False
