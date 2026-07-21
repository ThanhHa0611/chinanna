"""Mentor inbox tasks: email view/confirm links, reminders, home summary."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_REMINDER_HOURS = 24
TOKEN_TTL_DAYS = 30
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
SNOOZE_PRESETS: list[tuple[int, str]] = [
    (24, "1 ngày"),
    (72, "3 ngày"),
    (168, "1 tuần"),
]

SECTION_DEFINITIONS: list[dict] = [
    {
        "key": "documents",
        "label": "1. Giấy tờ apply",
        "actions": {"document_upload", "document_request"},
    },
    {
        "key": "apply_progress",
        "label": "2. Tiến độ apply",
        "actions": {"apply_progress_request"},
    },
    {
        "key": "feedback",
        "label": "3. Phản hồi",
        "actions": {"feedback"},
    },
    {
        "key": "hdnk_nckh",
        "label": "4. Keep track HDNK + NCKH",
        "actions": {"hdnk_nckh_update", "profile_activity_keeptrack", "profile_activity_keeptrack_abandon", "profile_activity_register"},
    },
    {
        "key": "profile_activities_admin",
        "label": "5. Quản lý hoạt động hồ sơ",
        "actions": {
            "profile_activity_pending_approval",
            "profile_activity_pending_group",
            "profile_activity_pending_reject",
            "profile_activity_finalize_group",
            "profile_activity_assign_group",
        },
    },
    {
        "key": "other",
        "label": "6. Khác",
        "actions": {"preferred_schools", "profile_update"},
    },
]

ACTION_SUMMARY_VERBS: dict[str, str] = {
    "document_upload": "đã nộp giấy tờ",
    "document_request": "cần mentor xử lí giấy tờ",
    "apply_progress_request": "cập nhật tiến độ apply",
    "feedback": "gửi phản hồi",
    "hdnk_nckh_update": "cập nhật HDNK + NCKH",
    "profile_activity_keeptrack": "cập nhật tiến độ hoạt động hồ sơ",
    "profile_activity_keeptrack_abandon": "yêu cầu từ bỏ hoạt động hồ sơ",
    "profile_activity_register": "báo danh hoạt động hồ sơ",
    "profile_activity_pending_approval": "chờ duyệt hoạt động hồ sơ",
    "profile_activity_pending_group": "chờ duyệt phân nhóm",
    "profile_activity_pending_reject": "chờ duyệt từ chối báo danh",
    "profile_activity_finalize_group": "cần chốt nhóm",
    "profile_activity_assign_group": "cần phân nhóm mentee",
    "preferred_schools": "cập nhật trường ưa thích",
    "profile_update": "cập nhật hồ sơ",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _vn_today_start() -> datetime:
    local_now = datetime.now(VN_TZ)
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def format_date_vn_title(value) -> str:
    dt = _parse_dt(value)
    if not dt:
        return ""
    return dt.astimezone(VN_TZ).strftime("%d.%m.%Y")


def format_date_vn_line(value) -> str:
    dt = _parse_dt(value)
    if not dt:
        return ""
    local = dt.astimezone(VN_TZ)
    return f"{local.day}/{local.month}/{local.year}"


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def inbox_section_key(action: str) -> str:
    for section in SECTION_DEFINITIONS:
        if action in section["actions"]:
            return section["key"]
    return "other"


def inbox_section_label(action: str) -> str:
    for section in SECTION_DEFINITIONS:
        if action in section["actions"]:
            return section["label"]
    return SECTION_DEFINITIONS[-1]["label"]


def task_display_state(doc: dict) -> str:
    if doc.get("status") == "done":
        return "done"
    if doc.get("viewed_at"):
        return "viewed"
    return "new"


def format_mentee_action_line(doc: dict) -> str:
    """Display line for daily summary: «Hà Phương đã nộp giấy tờ»."""
    mentee = (doc.get("mentee_name") or doc.get("mentee_email") or "Mentee").strip()
    action = doc.get("action") or ""
    verb = ACTION_SUMMARY_VERBS.get(action)
    if verb:
        detail = doc.get("description") or doc.get("title") or ""
        if action in ("document_upload", "document_request") and detail:
            return f"{mentee} {verb}: {detail}"
        profile_admin_actions = {
            "profile_activity_pending_approval",
            "profile_activity_pending_group",
            "profile_activity_pending_reject",
            "profile_activity_finalize_group",
            "profile_activity_assign_group",
        }
        if action in profile_admin_actions:
            label = (doc.get("title") or doc.get("description") or "").strip()
            if label:
                return f"{mentee} {verb}: {label}"
        return f"{mentee} {verb}"
    title = doc.get("title") or doc.get("description") or "Có cập nhật mới"
    return f"{mentee} · {title}"


def format_task_summary_line(doc: dict) -> str:
    created = _parse_dt(doc.get("created_at"))
    date_part = ""
    if created:
        local = created.astimezone(VN_TZ)
        date_part = f"{local.day}/{local.month}/{local.year}"
    action_line = format_mentee_action_line(doc)
    return f"{date_part} · {action_line}" if date_part else action_line


def format_reminder_hint(next_reminder_at) -> str:
    dt = _parse_dt(next_reminder_at)
    if not dt:
        return ""
    local = dt.astimezone(VN_TZ)
    today = datetime.now(VN_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    reminder_day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if reminder_day == tomorrow:
        return "nhắc dự kiến ngày mai"
    return f"nhắc dự kiến {local.day}/{local.month}/{local.year}"


def resolve_inbox_processed_by_name(doc: dict) -> str:
    stored = (doc.get("processed_by_name") or "").strip()
    if stored:
        return stored
    return (doc.get("mentor_name") or "").strip()


def format_processed_by_label(doc: dict) -> str:
    name = resolve_inbox_processed_by_name(doc)
    return f"Xử lí bởi {name}" if name else ""


def format_task_status_line(doc: dict) -> str:
    if doc.get("status") == "done":
        processor_label = format_processed_by_label(doc)
        if processor_label:
            return f"Đã xử lí · {processor_label}"
        return "Đã xử lí"
    if not doc.get("viewed_at"):
        return "Chưa xem"
    parts = ["Đã xem", "chưa xử lí"]
    reminder = format_reminder_hint(doc.get("next_reminder_at"))
    if reminder:
        parts.append(reminder)
    return " · ".join(parts)


def _daily_summary_sort_key(item: dict) -> tuple:
    is_done = item.get("status") == "done" or item.get("is_processed")
    group = 1 if is_done else 0
    if is_done:
        ts = _parse_dt(item.get("processed_at")) or _parse_dt(item.get("created_at"))
    else:
        ts = _parse_dt(item.get("created_at"))
    ts_rank = -(ts.timestamp()) if ts else 0
    return (group, ts_rank)


def sort_daily_summary_items(items: list[dict]) -> list[dict]:
    """Pending/unprocessed first, processed last; newest first within each group."""
    return sorted(items, key=_daily_summary_sort_key)


def _vn_day_start_from_dt(dt: datetime) -> datetime:
    local = dt.astimezone(VN_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc)


def _vn_day_start_from_key(date_key: str) -> datetime | None:
    """Parse YYYY-MM-DD (VN calendar day) to UTC start."""
    try:
        year, month, day = (int(part) for part in date_key.split("-"))
        local = datetime(year, month, day, tzinfo=VN_TZ)
        return local.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _vn_morning_on_day(day_start_utc: datetime, hour: int = 8) -> datetime:
    local = day_start_utc.astimezone(VN_TZ)
    morning = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    return morning.astimezone(timezone.utc)


def doc_belongs_to_vn_day(doc: dict, day_start: datetime) -> bool:
    day_end = day_start + timedelta(days=1)
    for field in ("created_at", "processed_at"):
        dt = _parse_dt(doc.get(field))
        if dt and day_start <= dt < day_end:
            return True
    return False


def task_visible_on_daily_board(doc: dict) -> bool:
    if doc.get("status") == "pending":
        return True
    if doc.get("status") != "done":
        return False
    today_start = _vn_today_start()
    for field in ("processed_at", "created_at"):
        dt = _parse_dt(doc.get(field))
        if dt and dt >= today_start:
            return True
    return False


def serialize_inbox_task(doc: dict, *, base_url: str = "") -> dict:
    display_state = task_display_state(doc)
    # Docs cũ chưa có trường has_file thì giữ mặc định True để không giấu link
    # file hợp lệ; task mới không có file (has_file=False) sẽ không phát file_url.
    has_file = doc.get("has_file", True)
    payload = {
        "id": str(doc["_id"]),
        "mentee_id": doc.get("mentee_id", ""),
        "mentee_name": doc.get("mentee_name", ""),
        "mentee_email": doc.get("mentee_email", ""),
        "mentor_name": doc.get("mentor_name", ""),
        "action": doc.get("action", ""),
        "section_key": inbox_section_key(doc.get("action", "")),
        "section_label": inbox_section_label(doc.get("action", "")),
        "title": doc.get("title", ""),
        "description": doc.get("description", ""),
        "summary_line": format_task_summary_line(doc),
        "doc_id": doc.get("doc_id", ""),
        "has_file": has_file,
        "status": doc.get("status", "pending"),
        "display_state": display_state,
        "processed_at": doc["processed_at"].isoformat() if doc.get("processed_at") else "",
        "processed_via": doc.get("processed_via", ""),
        "processed_by": doc.get("processed_by", ""),
        "processed_by_name": resolve_inbox_processed_by_name(doc) if doc.get("status") == "done" else "",
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else "",
        "next_reminder_at": doc["next_reminder_at"].isoformat() if doc.get("next_reminder_at") else "",
        "reminder_interval_hours": doc.get("reminder_interval_hours", DEFAULT_REMINDER_HOURS),
        "viewed_at": doc["viewed_at"].isoformat() if doc.get("viewed_at") else "",
    }
    payload["action_line"] = format_mentee_action_line(doc)
    payload["status_line"] = format_task_status_line(doc)
    payload["processed_by_label"] = (
        format_processed_by_label(doc) if doc.get("status") == "done" else ""
    )
    payload["synthetic"] = bool(doc.get("synthetic"))
    payload["nav_path"] = (doc.get("nav_path") or "").strip()
    if base_url:
        urls = inbox_urls(base_url, doc)
        payload["view_url"] = urls["view"]
        payload["file_url"] = urls["file"] if has_file else ""
        payload["confirm_url"] = urls["confirm"]
        payload["snooze_urls"] = inbox_snooze_urls(base_url, doc)
    return payload


def build_synthetic_inbox_item(
    *,
    item_id: str,
    mentor_name: str,
    action: str,
    title: str,
    description: str,
    mentee_name: str = "Hệ thống",
    mentee_id: str = "",
    mentee_email: str = "",
    created_at: datetime | None = None,
    nav_path: str = "/profile-activities",
) -> dict:
    now = created_at or _now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return {
        "_id": item_id,
        "synthetic": True,
        "nav_path": nav_path,
        "audience": "mentor",
        "mentor_name": mentor_name,
        "mentee_id": mentee_id,
        "mentee_name": mentee_name,
        "mentee_email": mentee_email,
        "action": action,
        "title": title,
        "description": description,
        "doc_id": "",
        "has_file": False,
        "status": "pending",
        "created_at": now,
        "processed_at": None,
        "processed_via": "",
        "processed_by": "",
        "processed_by_name": "",
        "next_reminder_at": now + timedelta(hours=DEFAULT_REMINDER_HOURS),
        "reminder_interval_hours": DEFAULT_REMINDER_HOURS,
        "last_reminder_at": None,
        "viewed_at": None,
    }


def merge_inbox_items(*groups: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            item_id = str(item.get("id") or item.get("_id") or "")
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            merged.append(item)
    merged.sort(
        key=lambda row: _parse_dt(row.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return merged


def inbox_urls(base_url: str, task: dict) -> dict[str, str]:
    base = base_url.rstrip("/")
    view = f"{base}/api/email/inbox/view?token={task.get('view_token', '')}"
    confirm = f"{base}/api/email/inbox/confirm?token={task.get('confirm_token', '')}"
    file_url = f"{base}/api/email/inbox/file?token={task.get('view_token', '')}"
    return {"view": view, "confirm": confirm, "file": file_url}


def inbox_snooze_urls(base_url: str, task: dict) -> list[dict[str, str | int]]:
    base = base_url.rstrip("/")
    token = task.get("view_token", "")
    return [
        {
            "hours": hours,
            "label": label,
            "url": f"{base}/api/email/inbox/snooze?token={token}&hours={hours}",
        }
        for hours, label in SNOOZE_PRESETS
    ]


def mentee_doc_urls(base_url: str, task: dict) -> dict[str, str]:
    base = base_url.rstrip("/")
    view = f"{base}/api/email/mentee/view?token={task.get('view_token', '')}"
    file_url = f"{base}/api/email/mentee/file?token={task.get('view_token', '')}"
    return {"view": view, "file": file_url}


def create_mentor_inbox_task(
    collection,
    *,
    mentor_name: str,
    mentee_id: str,
    mentee_name: str,
    mentee_email: str,
    action: str,
    title: str,
    description: str,
    doc_id: str = "",
    has_file: bool = True,
    reminder_hours: int = DEFAULT_REMINDER_HOURS,
) -> dict:
    now = _now()
    doc = {
        "audience": "mentor",
        "mentor_name": mentor_name,
        "mentee_id": str(mentee_id),
        "mentee_name": mentee_name,
        "mentee_email": mentee_email,
        "action": action,
        "title": title,
        "description": description,
        "doc_id": doc_id or "",
        "has_file": has_file,
        "status": "pending",
        "created_at": now,
        "processed_at": None,
        "processed_via": "",
        "processed_by": "",
        "processed_by_name": "",
        "next_reminder_at": now + timedelta(hours=reminder_hours),
        "reminder_interval_hours": reminder_hours,
        "last_reminder_at": None,
        "view_token": secrets.token_urlsafe(32),
        "confirm_token": secrets.token_urlsafe(32),
        "token_expires_at": now + timedelta(days=TOKEN_TTL_DAYS),
    }
    result = collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def create_mentee_view_task(
    collection,
    *,
    mentee_id: str,
    mentee_email: str,
    mentee_name: str,
    action: str,
    title: str,
    description: str,
    doc_id: str = "",
    mentor_name: str = "",
) -> dict:
    now = _now()
    doc = {
        "audience": "mentee",
        "mentor_name": mentor_name,
        "mentee_id": str(mentee_id),
        "mentee_name": mentee_name,
        "mentee_email": mentee_email,
        "action": action,
        "title": title,
        "description": description,
        "doc_id": doc_id or "",
        "status": "info",
        "created_at": now,
        "view_token": secrets.token_urlsafe(32),
        "confirm_token": "",
        "token_expires_at": now + timedelta(days=TOKEN_TTL_DAYS),
    }
    result = collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def find_task_by_token(collection, token: str, field: str = "view_token") -> dict | None:
    if not token:
        return None
    doc = collection.find_one({field: token})
    if not doc:
        return None
    expires = doc.get("token_expires_at")
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires < _now():
        return None
    return doc


def mentor_inbox_filter(admin: dict, mentor_name: str) -> dict:
    if admin.get("is_super_admin"):
        return {"audience": "mentor"}
    branch = (mentor_name or admin.get("mentor_name") or "").strip()
    if branch:
        return {"audience": "mentor", "mentor_name": branch}
    return {"audience": "mentor", "mentor_name": "__none__"}


def list_inbox_for_admin(collection, admin: dict, *, limit: int = 80, base_url: str = "") -> list[dict]:
    mentor_name = (admin.get("mentor_name") or "").strip()
    filt = mentor_inbox_filter(admin, mentor_name)
    cursor = collection.find(filt).sort("created_at", -1).limit(limit * 2)
    items = []
    for doc in cursor:
        if task_visible_on_daily_board(doc):
            items.append(serialize_inbox_task(doc, base_url=base_url))
        if len(items) >= limit:
            break
    return items


def enrich_daily_summary_item(item: dict) -> dict:
    is_processed = item.get("status") == "done"
    processed_by_name = resolve_inbox_processed_by_name(item) if is_processed else ""
    processed_by_label = format_processed_by_label(item) if is_processed else ""
    summary_line = item.get("summary_line") or format_task_summary_line(item)
    return {
        **item,
        "summary_line": summary_line,
        "action_line": format_mentee_action_line(item),
        "is_processed": is_processed,
        "status_label": "Đã xử lí" if is_processed else "Chưa xử lí",
        "status_line": format_task_status_line(item),
        "processed_by_name": processed_by_name,
        "processed_by_label": processed_by_label,
        "scheduled_at": item.get("next_reminder_at") or "",
    }


def build_daily_summary(items: list[dict]) -> dict:
    today_label = format_date_vn_line(_now())
    summary_items = sort_daily_summary_items([enrich_daily_summary_item(item) for item in items])
    pending_count = sum(1 for item in summary_items if not item.get("is_processed"))
    return {
        "date_label": today_label,
        "title": "Tóm tắt ngày",
        "items": summary_items,
        "item_count": len(summary_items),
        "pending_count": pending_count,
    }


def build_daily_board(items: list[dict]) -> dict:
    today_label = format_date_vn_title(_now())
    sections = []
    for section in SECTION_DEFINITIONS:
        section_items = [item for item in items if item.get("section_key") == section["key"]]
        pending_count = sum(1 for item in section_items if item.get("status") == "pending")
        sections.append(
            {
                "key": section["key"],
                "label": section["label"],
                "items": section_items,
                "item_count": len(section_items),
                "pending_count": pending_count,
            }
        )
    return {
        "date_label": today_label,
        "title": f"Mail · Tổng hợp Du học Trung Quốc ngày {today_label}",
        "sections": sections,
    }


def list_archive_days(collection, admin: dict, *, limit: int = 30) -> list[dict]:
    mentor_name = (admin.get("mentor_name") or "").strip()
    filt = mentor_inbox_filter(admin, mentor_name)
    today_start = _vn_today_start()
    cursor = collection.find(filt).sort("created_at", -1).limit(500)
    day_counts: dict[str, dict] = {}
    for doc in cursor:
        doc_id = str(doc["_id"])
        touched_days: set[str] = set()
        for field in ("created_at", "processed_at"):
            dt = _parse_dt(doc.get(field))
            if not dt:
                continue
            day_start = _vn_day_start_from_dt(dt)
            if day_start >= today_start:
                continue
            key = day_start.astimezone(VN_TZ).strftime("%Y-%m-%d")
            touched_days.add(key)
        for key in touched_days:
            bucket = day_counts.setdefault(
                key,
                {
                    "date": key,
                    "date_label": format_date_vn_line(_vn_day_start_from_key(key)),
                    "item_count": 0,
                    "pending_count": 0,
                    "_seen": set(),
                },
            )
            if doc_id in bucket["_seen"]:
                continue
            bucket["_seen"].add(doc_id)
            bucket["item_count"] += 1
            if doc.get("status") == "pending":
                bucket["pending_count"] += 1
    days = []
    for row in day_counts.values():
        row.pop("_seen", None)
        days.append(row)
    days.sort(key=lambda row: row["date"], reverse=True)
    return days[:limit]


def list_inbox_for_day(
    collection,
    admin: dict,
    date_key: str,
    *,
    limit: int = 100,
    base_url: str = "",
) -> list[dict]:
    day_start = _vn_day_start_from_key(date_key)
    if not day_start:
        return []
    day_end = day_start + timedelta(days=1)
    mentor_name = (admin.get("mentor_name") or "").strip()
    filt = mentor_inbox_filter(admin, mentor_name)
    filt["$or"] = [
        {"created_at": {"$gte": day_start, "$lt": day_end}},
        {"processed_at": {"$gte": day_start, "$lt": day_end}},
    ]
    cursor = collection.find(filt).sort("created_at", -1).limit(limit)
    items = []
    for doc in cursor:
        items.append(serialize_inbox_task(doc, base_url=base_url))
    return items


def build_archive_day_summary(items: list[dict], date_key: str) -> dict:
    day_start = _vn_day_start_from_key(date_key)
    date_label = format_date_vn_line(day_start) if day_start else date_key
    summary_items = sort_daily_summary_items([enrich_daily_summary_item(item) for item in items])
    pending_count = sum(1 for item in summary_items if not item.get("is_processed"))
    return {
        "date": date_key,
        "date_label": date_label,
        "title": "Tóm tắt ngày",
        "items": summary_items,
        "item_count": len(summary_items),
        "pending_count": pending_count,
    }


def ensure_stale_pending_daily_reminders(collection) -> int:
    """Roll unprocessed items from previous days to today's morning reminder."""
    today_start = _vn_today_start()
    morning = _vn_morning_on_day(today_start, 8)
    now = _now()
    target = morning if now < morning else now
    result = collection.update_many(
        {
            "audience": "mentor",
            "status": "pending",
            "created_at": {"$lt": today_start},
            "next_reminder_at": {"$lt": today_start},
        },
        {"$set": {"next_reminder_at": target, "reminder_interval_hours": DEFAULT_REMINDER_HOURS}},
    )
    return result.modified_count


def bulk_confirm_inbox_tasks(
    collection,
    task_ids: list[str],
    *,
    via: str = "app",
    processed_by: str = "",
    processed_by_name: str = "",
    admin: dict | None = None,
) -> dict:
    from bson import ObjectId
    from bson.errors import InvalidId

    scope = mentor_inbox_filter(admin, "") if admin is not None else {"audience": "mentor"}

    succeeded = 0
    failed = 0
    confirmed_tasks: list[dict] = []

    for task_id in task_ids:
        task_id = (task_id or "").strip()
        if not task_id:
            failed += 1
            continue
        try:
            oid = ObjectId(task_id)
        except InvalidId:
            failed += 1
            continue

        existing = collection.find_one({**scope, "_id": oid})
        if not existing:
            failed += 1
            continue
        if existing.get("status") == "done":
            continue

        task = confirm_inbox_task(
            collection,
            task_id=task_id,
            via=via,
            processed_by=processed_by,
            processed_by_name=processed_by_name,
            admin=admin,
        )
        if not task or task.get("status") != "done":
            failed += 1
            continue
        succeeded += 1
        confirmed_tasks.append(task)

    return {
        "succeeded": succeeded,
        "failed": failed,
        "tasks": confirmed_tasks,
    }


def confirm_inbox_task(
    collection,
    *,
    task_id=None,
    confirm_token=None,
    via: str = "app",
    processed_by: str = "",
    processed_by_name: str = "",
    admin: dict | None = None,
) -> dict | None:
    from bson import ObjectId
    from bson.errors import InvalidId

    doc = None
    if confirm_token:
        doc = find_task_by_token(collection, confirm_token, "confirm_token")
    elif task_id:
        scope = mentor_inbox_filter(admin, "") if admin is not None else {"audience": "mentor"}
        try:
            doc = collection.find_one({**scope, "_id": ObjectId(task_id)})
        except InvalidId:
            return None
    if not doc or doc.get("status") == "done":
        return doc

    now = _now()
    processor_name = (processed_by_name or "").strip() or (doc.get("mentor_name") or "").strip()
    processor_id = (processed_by or "").strip()
    patch = {
        "status": "done",
        "processed_at": now,
        "processed_via": via,
        "processed_by": processor_id,
        "processed_by_name": processor_name,
        "next_reminder_at": None,
    }
    collection.update_one({"_id": doc["_id"]}, {"$set": patch})
    doc.update(patch)
    return doc


def record_inbox_view(collection, task: dict) -> dict | None:
    if not task or task.get("audience") != "mentor" or task.get("status") != "pending":
        return task

    now = _now()
    interval = task.get("reminder_interval_hours") or DEFAULT_REMINDER_HOURS
    collection.update_one(
        {"_id": task["_id"]},
        {
            "$set": {
                "viewed_at": now,
                "next_reminder_at": now + timedelta(hours=interval),
            }
        },
    )
    return collection.find_one({"_id": task["_id"]})


def snooze_inbox_by_token(collection, view_token: str, hours: int) -> dict | None:
    task = find_task_by_token(collection, view_token, "view_token")
    if not task or task.get("audience") != "mentor" or task.get("status") != "pending":
        return None
    if hours <= 0 or hours > 24 * 30:
        return None

    now = _now()
    collection.update_one(
        {"_id": task["_id"]},
        {
            "$set": {
                "reminder_interval_hours": hours,
                "next_reminder_at": now + timedelta(hours=hours),
            }
        },
    )
    return collection.find_one({"_id": task["_id"]})


def update_reminder_schedule(
    collection,
    task_id: str,
    *,
    hours: int | None = None,
    reminder_at: datetime | None = None,
) -> dict | None:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(task_id)
    except InvalidId:
        return None

    doc = collection.find_one({"_id": oid, "audience": "mentor", "status": "pending"})
    if not doc:
        return None

    now = _now()
    patch: dict = {}
    if reminder_at is not None:
        if reminder_at.tzinfo is None:
            reminder_at = reminder_at.replace(tzinfo=timezone.utc)
        if reminder_at <= now:
            return None
        delta = reminder_at - now
        patch["reminder_interval_hours"] = max(1, int(delta.total_seconds() // 3600))
        patch["next_reminder_at"] = reminder_at
    elif hours is not None and hours > 0:
        patch["reminder_interval_hours"] = hours
        patch["next_reminder_at"] = now + timedelta(hours=hours)
    else:
        return serialize_inbox_task(doc)

    collection.update_one({"_id": oid}, {"$set": patch})
    doc = collection.find_one({"_id": oid})
    return serialize_inbox_task(doc)


def process_due_reminders(collection, send_daily_summary) -> int:
    """Group due tasks by mentor and send one daily summary email per mentor."""
    now = _now()
    filt = {
        "audience": "mentor",
        "status": "pending",
        "next_reminder_at": {"$lte": now},
    }

    due_docs = list(collection.find(filt).sort("created_at", 1).limit(200))
    if not due_docs:
        return 0

    by_mentor: dict[str, list[dict]] = {}
    for doc in due_docs:
        mentor = (doc.get("mentor_name") or "").strip() or "__none__"
        by_mentor.setdefault(mentor, []).append(doc)

    sent = 0
    for mentor_name, tasks in by_mentor.items():
        if mentor_name == "__none__":
            continue
        try:
            if send_daily_summary(mentor_name, tasks):
                for doc in tasks:
                    interval = doc.get("reminder_interval_hours") or DEFAULT_REMINDER_HOURS
                    collection.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "last_reminder_at": now,
                                "next_reminder_at": now + timedelta(hours=interval),
                            }
                        },
                    )
                sent += 1
        except Exception:
            continue
    return sent
