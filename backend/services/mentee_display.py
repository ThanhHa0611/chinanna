"""Helpers hiển thị tên mentee cho mentor (tag VMH theo ngày đăng ký)."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from config import VMH_REGISTRATION_CUTOFF_DATE


def mentee_registration_date_vn(user: dict) -> date | None:
    """Ngày đăng ký theo lịch Việt Nam (date | None)."""
    created = user.get("created_at")
    if isinstance(created, str) and created.strip():
        try:
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", created.strip())
            if not match:
                return None
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if not isinstance(created, datetime):
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return created.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date()


def mentee_shows_vmh_tag(user: dict) -> bool:
    reg_date = mentee_registration_date_vn(user)
    if not reg_date:
        return False
    try:
        year, month, day = (int(part) for part in VMH_REGISTRATION_CUTOFF_DATE.split("-"))
        cutoff = date(year, month, day)
    except (TypeError, ValueError, AttributeError):
        cutoff = date(2023, 7, 23)
    return reg_date > cutoff


def format_mentee_name_for_mentor(user: dict, fallback: str = "") -> str:
    name = (
        (user.get("full_name") or "").strip()
        or (user.get("username") or "").strip()
        or (user.get("email") or "").strip()
        or (fallback or "").strip()
    )
    if not name:
        return fallback or ""
    return f"{name} (VMH)" if mentee_shows_vmh_tag(user) else name
