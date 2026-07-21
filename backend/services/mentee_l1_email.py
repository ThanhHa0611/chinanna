"""Email thông báo + duyệt qua link cho mentor cấp 1 (đăng ký mentee, chỉnh sửa apply progress)."""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from bson import ObjectId

from config import (
    ADMIN_STATUS_APPROVED,
    ADMIN_STATUS_PENDING,
    ADMIN_STATUS_REJECTED,
    APPLY_PROGRESS_PENDING_REJECTED,
    APPLY_PROGRESS_PENDING_WAITING,
    EMAIL_ACTION_TOKEN_DAYS,
    ROLE_MENTEE,
)
from database import admins, users
from services.apply_progress import (
    get_apply_progress_rows_raw,
    mark_apply_progress_activity_processed,
)
from services.admins import admin_display_name, log_mentor_activity
from services.misc import extract_apply_progress_fields
from services.inbox import render_email_action_page

BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://127.0.0.1:8000").strip().rstrip("/")
MENTOR_ADMIN_URL = os.getenv("MENTOR_ADMIN_URL", "http://localhost:5174/access-requests").strip().rstrip("/")
MENTOR_MENTEES_URL = os.getenv("MENTOR_MENTEES_URL", "http://localhost:5174/mentees").strip().rstrip("/")


def level1_mentor_notify_emails(mentor_name: str) -> list[str]:
    branch = (mentor_name or "").strip()
    emails: set[str] = set()
    for doc in admins.find({
        "mentor_name": branch,
        "status": ADMIN_STATUS_APPROVED,
        "is_level1_mentor": True,
    }):
        email = (doc.get("email") or "").strip().lower()
        if email:
            emails.add(email)
    return sorted(emails)


def _token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=EMAIL_ACTION_TOKEN_DAYS)


def _create_action_tokens() -> dict:
    return {
        "approve": secrets.token_urlsafe(32),
        "reject": secrets.token_urlsafe(32),
        "expires_at": _token_expiry(),
    }


def _tokens_valid(tokens: dict | None) -> bool:
    if not tokens or not tokens.get("approve") or not tokens.get("reject"):
        return False
    expires_at = tokens.get("expires_at")
    if not expires_at:
        return False
    if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at >= datetime.now(timezone.utc)


def _find_l1_reviewer(mentor_name: str) -> dict:
    doc = admins.find_one({
        "mentor_name": (mentor_name or "").strip(),
        "status": ADMIN_STATUS_APPROVED,
        "is_level1_mentor": True,
    })
    if doc:
        return doc
    return {
        "email": "l1-email-action@duhoctrungquoc.local",
        "full_name": "Mentor cấp 1",
        "mentor_name": mentor_name,
        "is_level1_mentor": True,
    }


def _registration_urls(tokens: dict[str, str]) -> dict[str, str]:
    return {
        "approve": f"{BACKEND_PUBLIC_URL}/api/email/l1/registration/approve?token={tokens['approve']}",
        "reject": f"{BACKEND_PUBLIC_URL}/api/email/l1/registration/reject?token={tokens['reject']}",
        "admin_page": MENTOR_ADMIN_URL,
    }


def _apply_progress_urls(tokens: dict[str, str]) -> dict[str, str]:
    return {
        "approve": f"{BACKEND_PUBLIC_URL}/api/email/l1/apply-progress/approve?token={tokens['approve']}",
        "reject": f"{BACKEND_PUBLIC_URL}/api/email/l1/apply-progress/reject?token={tokens['reject']}",
        "admin_page": MENTOR_MENTEES_URL,
    }


def notify_l1_mentee_registration(mentee: dict) -> bool:
    mentor_name = (mentee.get("mentor") or "").strip()
    if not mentor_name or mentee_account_status(mentee) != ADMIN_STATUS_PENDING:
        return False

    emails = level1_mentor_notify_emails(mentor_name)
    if not emails:
        return False

    tokens = _create_action_tokens()
    users.update_one(
        {"_id": ObjectId(mentee["_id"])},
        {"$set": {"mentee_l1_email_tokens": {"registration": tokens}}},
    )

    requested_at = mentee.get("requested_at") or mentee.get("created_at")
    if hasattr(requested_at, "strftime"):
        requested_label = requested_at.strftime("%d/%m/%Y %H:%M UTC")
    else:
        requested_label = str(requested_at or "")

    from email_notify import send_l1_mentee_request_email

    urls = _registration_urls(tokens)
    sent = False
    for email in emails:
        if send_l1_mentee_request_email(
            to_email=email,
            subject="[Mentor Du học Trung Quốc] Mentee đăng ký mới cần duyệt",
            title="Mentee đăng ký mới",
            description=(
                f"Mentee {mentee.get('username', '')} "
                f"({mentee.get('email', '')}) vừa đăng ký team {mentor_name}."
            ),
            details=[
                ("Tên đăng nhập", mentee.get("username", "")),
                ("Email", mentee.get("email", "")),
                ("Team mentor", mentor_name),
                ("Zalo", mentee.get("zalo_phone", "—")),
                ("Vị trí đăng ký", mentee.get("registration_location_label", "—")),
                ("Thời gian", requested_label),
            ],
            approve_url=urls["approve"],
            reject_url=urls["reject"],
            admin_page_url=urls["admin_page"],
        ):
            sent = True
    return sent


def notify_l1_mentee_apply_progress_edit(mentee: dict, row_nums: list[int]) -> bool:
    # Apply-progress edits are in-app inbox only; email is for cấp quyền + cảnh báo.
    return False


def mentee_account_status(user: dict) -> str:
    return (user.get("status") or ADMIN_STATUS_APPROVED).strip().lower()


def _find_mentee_by_registration_token(token: str, action_key: str) -> dict | None:
    return users.find_one({f"mentee_l1_email_tokens.registration.{action_key}": token})


def _find_mentee_by_apply_progress_token(token: str, action_key: str) -> tuple[dict | None, dict | None]:
    for mentee in users.find({"mentee_l1_email_tokens.apply_progress": {"$exists": True}}):
        bucket = (mentee.get("mentee_l1_email_tokens") or {}).get("apply_progress") or {}
        for request_id, payload in bucket.items():
            if isinstance(payload, dict) and payload.get(action_key) == token:
                return mentee, {**payload, "request_id": request_id}
    return None, None


def _clear_registration_tokens(mentee_id) -> None:
    users.update_one(
        {"_id": ObjectId(mentee_id)},
        {"$unset": {"mentee_l1_email_tokens.registration": ""}},
    )


def _clear_apply_progress_tokens(mentee_id, request_id: str) -> None:
    users.update_one(
        {"_id": ObjectId(mentee_id)},
        {"$unset": {f"mentee_l1_email_tokens.apply_progress.{request_id}": ""}},
    )


def _approve_apply_progress_rows(mentee: dict, row_nums: list[int], reviewer: dict, *, via_email: bool = True) -> list[int]:
    rows = get_apply_progress_rows_raw(mentee)
    now = datetime.now(timezone.utc)
    processed: list[int] = []

    for row_num in row_nums:
        if row_num < 1 or row_num > len(rows):
            continue
        target = rows[row_num - 1]
        pending = target.get("pending")
        if not isinstance(pending, dict) or target.get("pending_status") != APPLY_PROGRESS_PENDING_WAITING:
            continue

        approved_fields = extract_apply_progress_fields(pending)
        rows[row_num - 1] = {
            "row_num": row_num,
            **approved_fields,
            "pending": None,
            "pending_status": "",
            "pending_at": None,
            "rejection_note": "",
        }
        mark_apply_progress_activity_processed(mentee["_id"], row_num, reviewer, "approve")
        processed.append(row_num)

    if processed:
        users.update_one(
            {"_id": ObjectId(mentee["_id"])},
            {
                "$set": {
                    "apply_progress_rows": rows,
                    "apply_progress_updated_at": now,
                    "apply_progress_mentee_unread": True,
                    "apply_progress_mentor_unread": False,
                },
            },
        )
        from services.notifications import notify_mentee_mentor_activity

        mentor_label = admin_display_name(reviewer)
        fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
        notify_mentee_mentor_activity(
            fresh,
            action="apply_progress_review",
            title="Mentor phản hồi tiến độ apply",
            description=(
                f"Mentor {mentor_label} duyệt chỉnh sửa dòng {', '.join(map(str, processed))}"
                + (" (qua email)." if via_email else ".")
            ),
            mentor_name=mentor_label,
            mentor_admin=reviewer if reviewer.get("_id") else None,
        )
    return processed


def _reject_apply_progress_rows(
    mentee: dict,
    row_nums: list[int],
    reviewer: dict,
    *,
    via_email: bool = True,
) -> list[int]:
    rows = get_apply_progress_rows_raw(mentee)
    now = datetime.now(timezone.utc)
    processed: list[int] = []

    for row_num in row_nums:
        if row_num < 1 or row_num > len(rows):
            continue
        target = rows[row_num - 1]
        pending = target.get("pending")
        if not isinstance(pending, dict) or target.get("pending_status") != APPLY_PROGRESS_PENDING_WAITING:
            continue

        rows[row_num - 1] = {
            **target,
            "pending_status": APPLY_PROGRESS_PENDING_REJECTED,
            "rejection_note": "Từ chối qua email",
        }
        mark_apply_progress_activity_processed(mentee["_id"], row_num, reviewer, "reject")
        processed.append(row_num)

    if processed:
        users.update_one(
            {"_id": ObjectId(mentee["_id"])},
            {
                "$set": {
                    "apply_progress_rows": rows,
                    "apply_progress_updated_at": now,
                    "apply_progress_mentee_unread": True,
                },
            },
        )
        from services.notifications import notify_mentee_mentor_activity

        mentor_label = admin_display_name(reviewer)
        fresh = users.find_one({"_id": ObjectId(mentee["_id"])}) or mentee
        notify_mentee_mentor_activity(
            fresh,
            action="apply_progress_review",
            title="Mentor phản hồi tiến độ apply",
            description=(
                f"Mentor {mentor_label} từ chối chỉnh sửa dòng {', '.join(map(str, processed))}"
                + (" (qua email)." if via_email else ".")
            ),
            mentor_name=mentor_label,
            mentor_admin=reviewer if reviewer.get("_id") else None,
        )
    return processed


def handle_email_registration_action(action_key: str, decision: str):
    from flask import request

    token = (request.args.get("token") or "").strip()
    if not token:
        return render_email_action_page(
            title="Link không hợp lệ",
            message="Thiếu mã xác thực trong link.",
            success=False,
        )

    mentee = _find_mentee_by_registration_token(token, action_key)
    if not mentee:
        return render_email_action_page(
            title="Link không hợp lệ",
            message="Link đã hết hạn hoặc không tồn tại.",
            success=False,
        )

    tokens = (mentee.get("mentee_l1_email_tokens") or {}).get("registration") or {}
    if not _tokens_valid(tokens):
        _clear_registration_tokens(mentee["_id"])
        return render_email_action_page(
            title="Link đã hết hạn",
            message="Vui lòng duyệt trực tiếp trên app mentor.",
            success=False,
        )

    if mentee_account_status(mentee) != ADMIN_STATUS_PENDING:
        _clear_registration_tokens(mentee["_id"])
        return render_email_action_page(
            title="Đã xử lý trước đó",
            message=f"Đăng ký của {mentee.get('email', '')} đã được xử lý.",
            success=True,
        )

    reviewer = _find_l1_reviewer(mentee.get("mentor", ""))
    now = datetime.now(timezone.utc)
    status = ADMIN_STATUS_APPROVED if decision == ADMIN_STATUS_APPROVED else ADMIN_STATUS_REJECTED
    users.update_one(
        {"_id": ObjectId(mentee["_id"])},
        {
            "$set": {
                "status": status,
                "reviewed_at": now,
                "reviewed_by": str(reviewer.get("_id") or "email"),
            },
        },
    )
    _clear_registration_tokens(mentee["_id"])

    verb = "duyệt" if status == ADMIN_STATUS_APPROVED else "từ chối"
    log_mentor_activity(
        reviewer,
        "mentee_registration_review",
        f"{reviewer.get('email', 'Mentor L1')} đã {verb} đăng ký mentee {mentee.get('email')} (qua email)",
        target_user_id=str(mentee["_id"]),
    )

    return render_email_action_page(
        title="Đã xử lý đăng ký mentee",
        message=f"Đã <strong>{verb}</strong> đăng ký của <strong>{mentee.get('email', '')}</strong>.",
        success=True,
    )


def handle_email_apply_progress_action(action_key: str, decision: str):
    from flask import request

    token = (request.args.get("token") or "").strip()
    if not token:
        return render_email_action_page(
            title="Link không hợp lệ",
            message="Thiếu mã xác thực trong link.",
            success=False,
        )

    mentee, payload = _find_mentee_by_apply_progress_token(token, action_key)
    if not mentee or not payload:
        return render_email_action_page(
            title="Link không hợp lệ",
            message="Link đã hết hạn hoặc không tồn tại.",
            success=False,
        )

    if not _tokens_valid(payload):
        _clear_apply_progress_tokens(mentee["_id"], payload["request_id"])
        return render_email_action_page(
            title="Link đã hết hạn",
            message="Vui lòng duyệt trực tiếp trên app mentor.",
            success=False,
        )

    row_nums = [int(num) for num in (payload.get("row_nums") or [])]
    reviewer = _find_l1_reviewer(mentee.get("mentor", ""))

    if decision == ADMIN_STATUS_APPROVED:
        processed = _approve_apply_progress_rows(mentee, row_nums, reviewer)
        verb = "duyệt"
    else:
        processed = _reject_apply_progress_rows(mentee, row_nums, reviewer)
        verb = "từ chối"

    _clear_apply_progress_tokens(mentee["_id"], payload["request_id"])

    if not processed:
        return render_email_action_page(
            title="Không thể xử lý",
            message="Các dòng này không còn chỉnh sửa chờ duyệt.",
            success=False,
        )

    log_mentor_activity(
        reviewer,
        "apply_progress_email_review",
        f"{reviewer.get('email', 'Mentor L1')} đã {verb} chỉnh sửa apply dòng {', '.join(map(str, processed))} (qua email)",
        mentee_id=str(mentee["_id"]),
    )

    return render_email_action_page(
        title="Đã xử lý chỉnh sửa apply",
        message=(
            f"Đã <strong>{verb}</strong> chỉnh sửa dòng "
            f"<strong>{', '.join(map(str, processed))}</strong> của "
            f"<strong>{mentee.get('email', '')}</strong>."
        ),
        success=True,
    )
