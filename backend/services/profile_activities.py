from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import openpyxl
from bson import ObjectId

from auth.validators import normalize_zalo_phone
from config import ROLE_PARENT
from database import mentor_inbox, profile_activities, users
from services.apply_documents import (
    mentee_keeptrack_profile_summary_line,
    mentee_keeptrack_profile_summary_parts,
    mentor_apply_direction_label,
)
from services.hdnk_nckh import get_hdnk_nckh_entries_raw, normalize_hdnk_nckh_entry
from services.notifications import notify_mentee_mentor_activity, notify_mentors_mentee_activity
from services.referrals import award_referrer_phone_for_activity

PROFILE_ACTIVITY_TYPES = (
    "Cuộc thi",
    "NCKH",
    "HĐNK",
    "Hội thảo",
    "Chương trình hè",
    "Dự án",
    "Khác",
)

PROFILE_ACTIVITY_APPROVAL_APPROVED = "approved"
PROFILE_ACTIVITY_APPROVAL_PENDING = "pending_l1_approval"
PROFILE_ACTIVITY_APPROVAL_REJECTED = "rejected"
PROFILE_ACTIVITY_APPROVAL_STATUSES = (
    PROFILE_ACTIVITY_APPROVAL_APPROVED,
    PROFILE_ACTIVITY_APPROVAL_PENDING,
    PROFILE_ACTIVITY_APPROVAL_REJECTED,
)
DEFAULT_PROFILE_ACTIVITY_IMPORTANCE = 3

PARTICIPATION_MODES = ("individual", "group", "both", "unknown")
DEFAULT_PARTICIPATION_MODE = "unknown"
PARTICIPATION_MODE_LABELS = {
    "individual": "Cá nhân",
    "group": "Nhóm",
    "both": "Cá nhân hay nhóm đều được",
    "unknown": "Không rõ",
}
MENTEE_PARTICIPATION_CHOICES = ("individual", "group")

KEEPTRACK_PROGRESS_IN_PROGRESS = "in_progress"
KEEPTRACK_PROGRESS_COMPLETED = "completed"
KEEPTRACK_HDNK_PROGRESS_ACTIVE = "đang tiến hành"
KEEPTRACK_HDNK_PROGRESS_DONE = "đã hoàn thành"
KEEPTRACK_UI_LABELS = {
    KEEPTRACK_PROGRESS_IN_PROGRESS: "Đang tiến hành",
    KEEPTRACK_PROGRESS_COMPLETED: "Đã xong",
}


class ProfileActivityKeeptrackError(ValueError):
    pass

_CONTENT_STOPWORDS = frozenset(
    {
        "về",
        "ve",
        "cho",
        "của",
        "cua",
        "và",
        "va",
        "các",
        "cac",
        "the",
        "một",
        "mot",
        "những",
        "nhung",
        "trong",
        "với",
        "voi",
        "từ",
        "tu",
        "đến",
        "den",
        "là",
        "la",
        "của",
        "cua",
        "một",
        "mot",
        "this",
        "that",
        "with",
        "from",
        "for",
        "and",
        "or",
        "các",
        "cac",
        "như",
        "nhu",
        "khi",
        "được",
        "duoc",
        "có",
        "co",
        "không",
        "khong",
        "trên",
        "tren",
        "dưới",
        "duoi",
        "tại",
        "tai",
        "bằng",
        "bang",
        "theo",
        "này",
        "nay",
        "đó",
        "do",
    }
)


class ProfileActivityRegistrationError(ValueError):
    pass

PROFILE_ACTIVITY_MAJOR_OPTIONS = (
    "Kinh tế & Logistics",
    "Truyền thông",
    "Ngôn ngữ & Giáo dục",
    "Y sinh",
    "Nghệ thuật",
    "Xã hội học",
    "Quan hệ quốc tế",
    "Luật",
    "Khác",
)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

_LEGACY_MAJOR_MAP = {
    "Kinh tế": "Kinh tế & Logistics",
    "Logistics": "Kinh tế & Logistics",
    "Giáo dục": "Ngôn ngữ & Giáo dục",
    "Ngôn ngữ": "Ngôn ngữ & Giáo dục",
}

_TYPE_KEYWORDS = [
    (
        "Cuộc thi",
        (
            "cuộc thi",
            "competition",
            "contest",
            "olympiad",
            "olympic",
            "hackathon",
            "challenge",
            "tài năng",
            "tai nang",
            " giải ",
            "award",
            "prize",
            "vòng loại",
            "vong loai",
        ),
    ),
    (
        "NCKH",
        (
            "nckh",
            "nghiên cứu",
            "nghien cuu",
            "research",
            "paper",
            "journal",
            "thesis",
            "dissertation",
            "publication",
            "bài báo",
            "bai bao",
            "science fair",
            "lab ",
            "laboratory",
        ),
    ),
    (
        "Hội thảo",
        (
            "hội thảo",
            "hoi thao",
            "seminar",
            "workshop",
            "webinar",
            "conference",
            "hội nghị",
            "hoi nghi",
            "symposium",
            "forum",
            "diễn đàn",
            "dien dan",
            "talk series",
            "lecture series",
            "masterclass",
        ),
    ),
    (
        "Chương trình hè",
        (
            "chương trình hè",
            "chuong trinh he",
            "summer school",
            "summer camp",
            "summer program",
            "summer institute",
            "pre-college",
            "precollege",
            "trao đổi hè",
            "trao doi he",
            "exchange program",
            "internship program",
            "online course",
            "online courses",
            "free online",
            "free course",
            "mooc",
            "edx",
            "coursera",
            "khóa học online",
            "khoa hoc online",
            "khóa học trực tuyến",
            "khoa hoc truc tuyen",
            "khóa học miễn phí",
            "khoa hoc mien phi",
            "open course",
            "learning program",
        ),
    ),
    (
        "Dự án",
        (
            "dự án",
            "du an",
            "project",
            "startup",
            "incubator",
            "accelerator",
            "hackathon",
            "fellowship program",
            "capstone",
        ),
    ),
    (
        "HĐNK",
        (
            "hoạt động ngoại khóa",
            "hoat dong ngoai khoa",
            "hđnk",
            "hdnk",
            "clb",
            "câu lạc bộ",
            "cau lac bo",
            "volunteer",
            "tình nguyện",
            "tinh nguyen",
            "extracurricular",
            "ngoại khóa",
            "ngoai khoa",
            "community service",
            "leadership program",
        ),
    ),
]

_MAJOR_KEYWORDS = {
    "Kinh tế & Logistics": (
        "kinh tế",
        "kinh te",
        "business",
        "finance",
        "marketing",
        "accounting",
        "logistics",
        "supply chain",
        "chuỗi cung ứng",
        "xuất nhập khẩu",
    ),
    "Truyền thông": ("truyền thông", "truyen thong", "media", "content", "pr"),
    "Ngôn ngữ & Giáo dục": (
        "giáo dục",
        "giao duc",
        "education",
        "sư phạm",
        "ngôn ngữ",
        "ngon ngu",
        "language",
        "translation",
    ),
    "Y sinh": ("y sinh", "medicine", "biomedical", "healthcare", "pharma", "dược", "duoc"),
    "Nghệ thuật": ("nghệ thuật", "nghe thuat", "design", "music", "art"),
    "Xã hội học": ("xã hội", "xa hoi", "social", "humanities", "psychology"),
    "Quan hệ quốc tế": ("quan hệ quốc tế", "quan he quoc te", "international relations"),
    "Luật": ("luật", "luat", "law", "legal"),
}

_MAJOR_ALIASES = {
    "kinh_te": "Kinh tế & Logistics",
    "giao_duc": "Ngôn ngữ & Giáo dục",
    "truyen_thong": "Truyền thông",
    "quan_he_quoc_te": "Quan hệ quốc tế",
    "duoc": "Y sinh",
    "khac": "Khác",
}


def _normalize_date_text(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    value = value.replace(".", "/").replace("-", "/")
    parts = [part for part in value.split("/") if part]
    if len(parts) != 3:
        return raw.strip()
    day, month, year = parts
    if len(year) == 2:
        year = f"20{year}"
    try:
        day_i = int(day)
        month_i = int(month)
        year_i = int(year)
        if day_i < 1 or day_i > 31 or month_i < 1 or month_i > 12:
            return raw.strip()
        return f"{day_i:02d}/{month_i:02d}/{year_i:04d}"
    except ValueError:
        return raw.strip()


def _find_regex_group(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return ""
    return (match.group(1) or "").strip(" .,:;-")


def _extract_name(description: str) -> str:
    lines = [line.strip(" -*•\t") for line in (description or "").splitlines() if line.strip()]
    if not lines:
        return ""
    first = lines[0]
    first = re.sub(r"^(thông tin|hoạt động|event|title|tên)[:\-]\s*", "", first, flags=re.IGNORECASE)
    return first[:500].strip(" .,:;-")


def _first_description_line(description: str) -> str:
    for line in (description or "").splitlines():
        cleaned = line.strip(" -*•\t")
        if cleaned:
            return cleaned
    return ""


def _extract_type(text: str) -> str:
    lowered = (text or "").lower()
    scores: dict[str, int] = {label: 0 for label in PROFILE_ACTIVITY_TYPES if label != "Khác"}
    for label, keywords in _TYPE_KEYWORDS:
        for keyword in keywords:
            if keyword in lowered:
                scores[label] += 1
    best_label, best_score = max(scores.items(), key=lambda item: item[1], default=("Khác", 0))
    if best_score > 0:
        return best_label
    return "Khác"


def _normalize_major_label(raw: str) -> str | None:
    value = str(raw or "").strip()
    if not value:
        return None
    if value in PROFILE_ACTIVITY_MAJOR_OPTIONS:
        return value
    return _LEGACY_MAJOR_MAP.get(value)


def _parse_deadline_date(deadline: str):
    normalized = _normalize_date_text(deadline)
    if not normalized:
        return None
    parts = normalized.split("/")
    if len(parts) != 3:
        return None
    try:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        return datetime(year, month, day, tzinfo=VN_TZ).date()
    except ValueError:
        return None


def get_deadline_badge(deadline: str) -> dict | None:
    deadline_date = _parse_deadline_date(deadline)
    if not deadline_date:
        return None
    today = datetime.now(VN_TZ).date()
    days_left = (deadline_date - today).days
    if days_left < 0:
        return {"label": "Hết hạn", "variant": "expired"}
    if days_left <= 3:
        return {"label": "Còn 3 ngày", "variant": "urgent"}
    if days_left <= 7:
        return {"label": "Còn 7 ngày", "variant": "warning"}
    return None


def _extract_majors(text: str) -> list[str]:
    lowered = (text or "").lower()
    majors: list[str] = []
    for label, keywords in _MAJOR_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            majors.append(label)
    return majors


def _strip_leading_ve(content: str) -> str:
    text = (content or "").strip()
    if re.match(r"^về\s+", text, flags=re.IGNORECASE):
        return re.sub(r"^về\s+", "", text, count=1, flags=re.IGNORECASE).strip()
    return text


def _build_activity_name_line(data: dict) -> str:
    activity_type = (data.get("activity_type") or "").strip() or "Khác"
    organizer = (data.get("organizer") or "").strip()
    content = _strip_leading_ve(data.get("content") or "")
    target = (data.get("target_audience") or "").strip()
    deadline = (data.get("deadline") or "").strip()

    line = activity_type
    if organizer:
        line = f"{line} của {organizer}"
    if content:
        line = f"{line}, về {content}"
    if target:
        line = f"{line} cho {target}"
    if deadline:
        line = f"{line}, dl {deadline}"
    return line.strip() or "Hoạt động hồ sơ"


def compose_activity_name(data: dict) -> str:
    line = _build_activity_name_line(data)
    link = (data.get("link") or "").strip()
    if link:
        line = f"{line} {link}"
    return line


def _normalize_participation_mode(raw) -> str:
    value = str(raw or "").strip().lower()
    if value in PARTICIPATION_MODES:
        return value
    return DEFAULT_PARTICIPATION_MODE


def participation_mode_label(mode: str) -> str:
    return PARTICIPATION_MODE_LABELS.get(_normalize_participation_mode(mode), PARTICIPATION_MODE_LABELS["unknown"])


def _extract_content_keywords(content: str, *, max_words: int = 2) -> str:
    text = _strip_leading_ve(content)
    if not text:
        return ""
    tokens = re.findall(r"[\wÀ-ỹ]+", text, flags=re.UNICODE)
    picked: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in _CONTENT_STOPWORDS or len(lowered) < 2:
            continue
        if token not in picked:
            picked.append(token)
        if len(picked) >= max_words:
            break
    return " ".join(picked)


def suggest_group_name(activity: dict) -> str:
    activity_type = (activity.get("activity_type") or "").strip() or "Khác"
    organizer = (activity.get("organizer") or "").strip()
    suffix = organizer or _extract_content_keywords(activity.get("content") or "")
    group_count = len(activity.get("groups") or [])
    n = group_count + 1
    if suffix:
        return f"{activity_type} {suffix} nhóm {n}"
    return f"{activity_type} nhóm {n}"


def _find_mentee_group(activity: dict, mentee_id: str) -> dict | None:
    for group in activity.get("groups", []):
        mentee_ids = [str(item) for item in (group.get("mentee_ids") or [])]
        if mentee_id in mentee_ids:
            return group
    return None


def _is_auto_solo_group(group: dict | None) -> bool:
    return bool(group and group.get("is_auto_solo"))


def _is_individual_participant(activity: dict, state: dict) -> bool:
    if not state.get("registered_at"):
        return False
    choice = state.get("participation_choice")
    mode = _normalize_participation_mode(activity.get("participation_mode"))
    return choice == "individual" or mode == "individual"


def _is_group_participant(activity: dict, state: dict) -> bool:
    if not state.get("registered_at"):
        return False
    choice = state.get("participation_choice")
    mode = _normalize_participation_mode(activity.get("participation_mode"))
    return choice == "group" or mode == "group"


def _individual_registration_approved(activity: dict, state: dict) -> bool:
    if not _is_individual_participant(activity, state):
        return False
    if (state.get("group_response_status") or "").strip().lower() == "rejected":
        return False
    pending_reject = state.get("mentor_reject_pending") or {}
    if pending_reject.get("approval_status") == PROFILE_ACTIVITY_APPROVAL_PENDING:
        return False
    return (state.get("group_response_status") or "").strip().lower() == "confirmed"


def _group_registration_approved(activity: dict, state: dict, mentee_id: str) -> bool:
    if not _is_group_participant(activity, state):
        return False
    if (state.get("group_response_status") or "").strip().lower() != "confirmed":
        return False
    pending_reject = state.get("mentor_reject_pending") or {}
    if pending_reject.get("approval_status") == PROFILE_ACTIVITY_APPROVAL_PENDING:
        return False
    return _find_mentee_finalized_group(activity, mentee_id) is not None


def _resolve_keeptrack_hdnk_fields(activity: dict, state: dict, mentee_id: str) -> tuple[str, str]:
    if _is_individual_participant(activity, state):
        return "cá nhân", ""
    group = _find_mentee_display_group(activity, mentee_id, state)
    return "nhóm Trơn Tru", (group or {}).get("group_name", "") or ""


def _compose_keeptrack_category(activity: dict) -> str:
    return compose_activity_name(activity)


def _normalize_keeptrack(raw: dict | None) -> dict:
    source = raw or {}
    progress_status = (source.get("progress_status") or "").strip()
    if progress_status not in {KEEPTRACK_PROGRESS_IN_PROGRESS, KEEPTRACK_PROGRESS_COMPLETED}:
        progress_status = ""
    active_flag = bool(source.get("active"))
    if active_flag and not progress_status:
        progress_status = KEEPTRACK_PROGRESS_IN_PROGRESS
    has_award = bool(source.get("has_award"))
    award_level = (source.get("award_level") or "").strip()
    if not has_award or award_level not in {"giải 1", "giải 2", "giải 3", "khác"}:
        award_level = ""
    active = active_flag and progress_status == KEEPTRACK_PROGRESS_IN_PROGRESS
    return {
        "active": active,
        "start_date": (source.get("start_date") or "").strip(),
        "progress_status": progress_status,
        "has_award": has_award,
        "award_level": award_level,
        "hdnk_entry_id": (source.get("hdnk_entry_id") or "").strip(),
        "synced_at": source.get("synced_at"),
    }


def _serialize_keeptrack_for_feed(activity: dict, state: dict) -> dict | None:
    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    abandon_pending = state.get("keeptrack_abandon_pending") or {}
    abandon_reject = state.get("keeptrack_abandon_last_rejection") or {}
    show_bar = keeptrack["active"] or abandon_pending.get("status") == "pending"
    if not show_bar:
        return None
    payload = {
        "active": keeptrack["active"],
        "display_name": _compose_keeptrack_category(activity),
        "link": (activity.get("link") or "").strip(),
        "start_date": keeptrack["start_date"],
        "progress_status": keeptrack["progress_status"] or KEEPTRACK_PROGRESS_IN_PROGRESS,
        "progress_label": KEEPTRACK_UI_LABELS.get(
            keeptrack["progress_status"] or KEEPTRACK_PROGRESS_IN_PROGRESS,
            "Đang tiến hành",
        ),
        "has_award": keeptrack["has_award"],
        "award_level": keeptrack["award_level"],
        "award_level_options": ["giải 1", "giải 2", "giải 3", "khác"],
    }
    if abandon_pending.get("status") == "pending":
        payload["abandon_status"] = "pending"
        payload["review_message"] = "Đã gửi yêu cầu từ bỏ — chờ mentor xác nhận"
    elif abandon_reject.get("rejected_at"):
        payload["abandon_status"] = "rejected"
        payload["review_message"] = (
            (abandon_reject.get("note") or "").strip()
            or "Mentor từ chối yêu cầu từ bỏ — tiếp tục theo dõi hoạt động."
        )
    return payload


def _mentee_excluded_from_feed(state: dict) -> bool:
    """In-progress or completed keeptrack items belong in Panel A / HDNK, not the notification feed."""
    keeptrack_raw = state.get("keeptrack")
    if keeptrack_raw:
        keeptrack = _normalize_keeptrack(keeptrack_raw)
        if keeptrack["active"]:
            return True
        if keeptrack["progress_status"] == KEEPTRACK_PROGRESS_COMPLETED:
            return True
        if keeptrack.get("hdnk_entry_id"):
            return True
    abandon_pending = state.get("keeptrack_abandon_pending") or {}
    if abandon_pending.get("status") == "pending":
        return True
    return False


def _snapshot_keeptrack(raw: dict | None) -> dict:
    keeptrack = _normalize_keeptrack(raw)
    return {
        "active": keeptrack["active"],
        "start_date": keeptrack["start_date"],
        "progress_status": keeptrack["progress_status"],
        "has_award": keeptrack["has_award"],
        "award_level": keeptrack["award_level"],
        "hdnk_entry_id": keeptrack["hdnk_entry_id"],
        "synced_at": keeptrack.get("synced_at"),
    }


def _find_hdnk_entry(entries: list[dict], entry_id: str) -> dict | None:
    if not entry_id:
        return None
    for item in entries:
        if item.get("entry_id") == entry_id:
            return dict(item)
    return None


def _remove_keeptrack_hdnk_entry(mentee: dict, state: dict) -> None:
    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    entry_id = keeptrack.get("hdnk_entry_id")
    if entry_id:
        _restore_mentee_hdnk_entry(mentee, entry_id, None)
    state.pop("keeptrack", None)
    state.pop("keeptrack_pending_review", None)
    state.pop("keeptrack_last_rejection", None)
    state.pop("keeptrack_abandon_pending", None)
    state.pop("keeptrack_abandon_last_rejection", None)


def _restore_mentee_hdnk_entry(mentee: dict, entry_id: str, previous_entry: dict | None) -> None:
    if not entry_id:
        return
    now = datetime.now(timezone.utc)
    entries = get_hdnk_nckh_entries_raw(mentee)
    if previous_entry is None:
        entries = [item for item in entries if item.get("entry_id") != entry_id]
    else:
        match_index = next(
            (index for index, item in enumerate(entries) if item.get("entry_id") == entry_id),
            None,
        )
        if match_index is None:
            entries.insert(0, previous_entry)
        else:
            entries[match_index] = previous_entry
    users.update_one(
        {"_id": mentee["_id"]},
        {
            "$set": {
                "hdnk_nckh_entries": entries[:20],
                "hdnk_nckh_mentee_updated_at": now,
                "hdnk_nckh_l1_unread": True,
            }
        },
    )


def _apply_keeptrack_snapshot(state: dict, snapshot: dict | None) -> None:
    if not snapshot:
        state.pop("keeptrack", None)
        return
    state["keeptrack"] = {
        "active": bool(snapshot.get("active")),
        "start_date": snapshot.get("start_date") or "",
        "progress_status": snapshot.get("progress_status") or "",
        "has_award": bool(snapshot.get("has_award")),
        "award_level": snapshot.get("award_level") or "",
        "hdnk_entry_id": snapshot.get("hdnk_entry_id") or "",
        "synced_at": snapshot.get("synced_at"),
    }


def _keeptrack_progress_description(keeptrack: dict) -> str:
    progress_label = KEEPTRACK_UI_LABELS.get(keeptrack.get("progress_status") or "", "")
    parts = [f"Trạng thái: {progress_label or keeptrack.get('progress_status') or '—'}"]
    if keeptrack.get("start_date"):
        parts.append(f"Ngày bắt đầu: {keeptrack['start_date']}")
    if keeptrack.get("has_award") and keeptrack.get("award_level"):
        parts.append(f"Giải: {keeptrack['award_level']}")
    return " · ".join(parts)


def _upsert_mentee_hdnk_entry(
    mentee: dict,
    *,
    entry_id: str | None,
    entry_data: dict,
    mentor_updated: bool = False,
) -> str:
    now = datetime.now(timezone.utc)
    entries = get_hdnk_nckh_entries_raw(mentee)
    resolved_id = entry_id or str(uuid.uuid4())
    match_index = next(
        (index for index, item in enumerate(entries) if item.get("entry_id") == resolved_id),
        None,
    )
    normalized = normalize_hdnk_nckh_entry(
        entry_data,
        entry_id=resolved_id,
        preserve_mentor=entries[match_index] if match_index is not None else None,
    )
    if match_index is None:
        entries.insert(0, normalized)
    else:
        entries[match_index] = normalized
    set_fields: dict = {"hdnk_nckh_entries": entries[:20]}
    if mentor_updated:
        set_fields["hdnk_nckh_l1_unread"] = True
        set_fields["hdnk_nckh_mentor_updated_at"] = now
    else:
        set_fields["hdnk_nckh_mentee_updated_at"] = now
        set_fields["hdnk_nckh_l1_unread"] = True
        set_fields["hdnk_nckh_reminder_unread"] = False
        set_fields["hdnk_nckh_last_reminder_sent_at"] = None
    users.update_one({"_id": mentee["_id"]}, {"$set": set_fields})
    return resolved_id


def _queue_keeptrack_mentor_review(
    activity: dict,
    state: dict,
    mentee: dict,
    submitted_keeptrack: dict,
    *,
    previous_keeptrack: dict | None = None,
    previous_hdnk_entry: dict | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    state["keeptrack"] = submitted_keeptrack
    state.pop("keeptrack_last_rejection", None)
    state["keeptrack_pending_review"] = {
        "review_id": str(uuid.uuid4()),
        "submitted_at": now,
        "status": "pending",
        "previous_keeptrack": previous_keeptrack,
        "previous_hdnk_entry": previous_hdnk_entry,
        "submitted_keeptrack": submitted_keeptrack,
        "viewed_at": None,
        "viewed_by_admin_id": "",
        "rejected_at": None,
        "rejected_by_admin_id": "",
        "reject_note": "",
    }
    activity_name = compose_activity_name(activity)
    mentee_name = mentee.get("full_name") or mentee.get("username") or mentee.get("email", "")
    notify_mentors_mentee_activity(
        mentee,
        action="profile_activity_keeptrack",
        title=f"{mentee_name} cập nhật tiến độ hoạt động",
        description=(
            f"Hoạt động: {activity_name}. "
            f"{_keeptrack_progress_description(submitted_keeptrack)}"
        ),
    )


def _create_keeptrack_entry(
    activity: dict,
    mentee_id: str,
    *,
    participation_type: str,
    zalo_group_name: str = "",
    notify_mentor: bool = False,
) -> dict:
    state = _get_mentee_state(activity, mentee_id)
    if not state:
        return activity
    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    if keeptrack.get("hdnk_entry_id") and keeptrack.get("progress_status"):
        return activity

    mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    if not mentee:
        return activity

    now = datetime.now(timezone.utc)
    start_date = keeptrack.get("start_date") or now.astimezone(VN_TZ).strftime("%Y-%m-%d")
    entry_id = _upsert_mentee_hdnk_entry(
        mentee,
        entry_id=keeptrack.get("hdnk_entry_id") or None,
        entry_data={
            "start_date": start_date,
            "category": _compose_keeptrack_category(activity),
            "participation_type": participation_type,
            "zalo_group_name": zalo_group_name,
            "progress": KEEPTRACK_HDNK_PROGRESS_ACTIVE,
            "has_award": False,
            "award_level": "",
        },
        mentor_updated=True,
    )
    submitted_keeptrack = {
        "active": True,
        "start_date": start_date,
        "progress_status": KEEPTRACK_PROGRESS_IN_PROGRESS,
        "has_award": False,
        "award_level": "",
        "hdnk_entry_id": entry_id,
        "synced_at": now,
    }
    if notify_mentor:
        _queue_keeptrack_mentor_review(
            activity,
            state,
            mentee,
            submitted_keeptrack,
            previous_keeptrack=None,
            previous_hdnk_entry=None,
        )
    else:
        state["keeptrack"] = submitted_keeptrack
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def maybe_start_individual_keeptrack(activity: dict, mentee_id: str) -> dict:
    state = _get_mentee_state(activity, mentee_id)
    if not state or not _individual_registration_approved(activity, state):
        return activity
    return _create_keeptrack_entry(
        activity,
        mentee_id,
        participation_type="cá nhân",
        notify_mentor=False,
    )


def maybe_start_group_keeptrack(activity: dict, mentee_id: str) -> dict:
    state = _get_mentee_state(activity, mentee_id)
    if not state or not _group_registration_approved(activity, state, mentee_id):
        return activity
    participation_type, zalo_group_name = _resolve_keeptrack_hdnk_fields(activity, state, mentee_id)
    return _create_keeptrack_entry(
        activity,
        mentee_id,
        participation_type=participation_type,
        zalo_group_name=zalo_group_name,
        notify_mentor=False,
    )


def update_activity_keeptrack(
    activity: dict,
    mentee_id: str,
    payload: dict,
    *,
    from_mentor: bool = False,
) -> dict:
    state = _get_mentee_state(activity, mentee_id)
    if not state:
        raise ProfileActivityKeeptrackError("Bạn chưa báo danh hoạt động này.")
    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    pending = state.get("keeptrack_pending_review") or {}
    if pending.get("status") == "pending" and not from_mentor:
        raise ProfileActivityKeeptrackError("Tiến độ đang chờ mentor xác nhận — vui lòng đợi phản hồi.")
    if not keeptrack["active"] and not from_mentor:
        raise ProfileActivityKeeptrackError("Hoạt động không còn trong trạng thái đang tiến hành.")

    progress_status = (payload.get("progress_status") or keeptrack["progress_status"]).strip()
    if progress_status not in {KEEPTRACK_PROGRESS_IN_PROGRESS, KEEPTRACK_PROGRESS_COMPLETED}:
        raise ProfileActivityKeeptrackError("Trạng thái tiến độ không hợp lệ.")

    start_date = (payload.get("start_date") or keeptrack["start_date"] or "").strip()
    if not start_date:
        raise ProfileActivityKeeptrackError("Cần ngày bắt đầu.")

    has_award = bool(payload.get("has_award")) if progress_status == KEEPTRACK_PROGRESS_COMPLETED else False
    award_level = (payload.get("award_level") or "").strip() if has_award else ""
    if has_award and award_level not in {"giải 1", "giải 2", "giải 3", "khác"}:
        raise ProfileActivityKeeptrackError("Cần chọn hạng giải.")

    mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    if not mentee:
        raise ProfileActivityKeeptrackError("Mentee không tồn tại.")

    requires_review = (
        not from_mentor
        and _is_individual_participant(activity, state)
        and _individual_registration_approved(activity, state)
    )
    previous_keeptrack = _snapshot_keeptrack(state.get("keeptrack")) if requires_review else None
    previous_hdnk_entry = None
    if requires_review and keeptrack.get("hdnk_entry_id"):
        previous_hdnk_entry = _find_hdnk_entry(
            get_hdnk_nckh_entries_raw(mentee),
            keeptrack["hdnk_entry_id"],
        )

    now = datetime.now(timezone.utc)
    hdnk_progress = (
        KEEPTRACK_HDNK_PROGRESS_DONE
        if progress_status == KEEPTRACK_PROGRESS_COMPLETED
        else KEEPTRACK_HDNK_PROGRESS_ACTIVE
    )
    participation_type, zalo_group_name = _resolve_keeptrack_hdnk_fields(activity, state, mentee_id)
    entry_id = _upsert_mentee_hdnk_entry(
        mentee,
        entry_id=keeptrack.get("hdnk_entry_id") or None,
        entry_data={
            "start_date": start_date,
            "category": _compose_keeptrack_category(activity),
            "participation_type": participation_type,
            "zalo_group_name": zalo_group_name,
            "progress": hdnk_progress,
            "has_award": has_award,
            "award_level": award_level,
        },
        mentor_updated=from_mentor,
    )
    submitted_keeptrack = {
        "active": progress_status == KEEPTRACK_PROGRESS_IN_PROGRESS,
        "start_date": start_date,
        "progress_status": progress_status,
        "has_award": has_award,
        "award_level": award_level,
        "hdnk_entry_id": entry_id,
        "synced_at": now,
    }
    state["keeptrack"] = submitted_keeptrack
    state.pop("keeptrack_last_rejection", None)

    if requires_review:
        state["keeptrack_pending_review"] = {
            "review_id": str(uuid.uuid4()),
            "submitted_at": now,
            "status": "pending",
            "previous_keeptrack": previous_keeptrack,
            "previous_hdnk_entry": previous_hdnk_entry,
            "submitted_keeptrack": submitted_keeptrack,
            "viewed_at": None,
            "viewed_by_admin_id": "",
            "rejected_at": None,
            "rejected_by_admin_id": "",
            "reject_note": "",
        }
        activity_name = compose_activity_name(activity)
        mentee_name = mentee.get("full_name") or mentee.get("username") or mentee.get("email", "")
        notify_mentors_mentee_activity(
            mentee,
            action="profile_activity_keeptrack",
            title=f"{mentee_name} cập nhật tiến độ hoạt động",
            description=(
                f"Hoạt động: {activity_name}. "
                f"{_keeptrack_progress_description(submitted_keeptrack)}"
            ),
        )

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def complete_activity_keeptrack(activity: dict, mentee_id: str, payload: dict) -> dict:
    state = _get_mentee_state(activity, mentee_id)
    if not state:
        raise ProfileActivityKeeptrackError("Bạn chưa báo danh hoạt động này.")
    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    if not keeptrack["active"]:
        if keeptrack["progress_status"] == KEEPTRACK_PROGRESS_COMPLETED:
            return profile_activities.find_one({"_id": activity["_id"]}) or activity
        raise ProfileActivityKeeptrackError("Hoạt động không còn trong trạng thái đang tiến hành.")
    abandon_pending = state.get("keeptrack_abandon_pending") or {}
    if abandon_pending.get("status") == "pending":
        raise ProfileActivityKeeptrackError("Đang chờ mentor xử lý yêu cầu từ bỏ — không thể hoàn thành.")

    has_award = bool(payload.get("has_award"))
    award_level = (payload.get("award_level") or "").strip() if has_award else ""
    if has_award and award_level not in {"giải 1", "giải 2", "giải 3", "khác"}:
        raise ProfileActivityKeeptrackError("Cần chọn hạng giải.")

    start_date = (keeptrack["start_date"] or "").strip()
    if not start_date:
        raise ProfileActivityKeeptrackError("Cần ngày bắt đầu.")

    mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    if not mentee:
        raise ProfileActivityKeeptrackError("Mentee không tồn tại.")

    participation_type, zalo_group_name = _resolve_keeptrack_hdnk_fields(activity, state, mentee_id)
    now = datetime.now(timezone.utc)
    entry_id = _upsert_mentee_hdnk_entry(
        mentee,
        entry_id=keeptrack.get("hdnk_entry_id") or None,
        entry_data={
            "start_date": start_date,
            "category": _compose_keeptrack_category(activity),
            "participation_type": participation_type,
            "zalo_group_name": zalo_group_name,
            "progress": KEEPTRACK_HDNK_PROGRESS_DONE,
            "has_award": has_award,
            "award_level": award_level,
        },
        mentor_updated=False,
    )
    state["keeptrack"] = {
        "active": False,
        "start_date": start_date,
        "progress_status": KEEPTRACK_PROGRESS_COMPLETED,
        "has_award": has_award,
        "award_level": award_level,
        "hdnk_entry_id": entry_id,
        "synced_at": now,
    }
    state.pop("keeptrack_abandon_pending", None)
    state.pop("keeptrack_abandon_last_rejection", None)
    state.pop("keeptrack_pending_review", None)
    state.pop("keeptrack_last_rejection", None)

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def request_keeptrack_abandon(activity: dict, mentee_id: str, note: str = "") -> dict:
    state = _get_mentee_state(activity, mentee_id)
    if not state:
        raise ProfileActivityKeeptrackError("Bạn chưa báo danh hoạt động này.")
    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    if not keeptrack["active"]:
        raise ProfileActivityKeeptrackError("Hoạt động không còn trong trạng thái đang tiến hành.")
    abandon_pending = state.get("keeptrack_abandon_pending") or {}
    if abandon_pending.get("status") == "pending":
        raise ProfileActivityKeeptrackError("Yêu cầu từ bỏ đang chờ mentor xử lý.")

    mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    if not mentee:
        raise ProfileActivityKeeptrackError("Mentee không tồn tại.")

    now = datetime.now(timezone.utc)
    abandon_note = (note or "").strip()
    state["keeptrack_abandon_pending"] = {
        "request_id": str(uuid.uuid4()),
        "status": "pending",
        "requested_at": now,
        "note": abandon_note,
    }
    state.pop("keeptrack_abandon_last_rejection", None)

    activity_name = compose_activity_name(activity)
    mentee_name = mentee.get("full_name") or mentee.get("username") or mentee.get("email", "")
    notify_mentors_mentee_activity(
        mentee,
        action="profile_activity_keeptrack_abandon",
        title=f"{mentee_name} yêu cầu từ bỏ hoạt động",
        description=(
            f"Hoạt động: {activity_name}."
            + (f" Ghi chú: {abandon_note}" if abandon_note else "")
        ),
    )

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def serialize_pending_keeptrack_abandon(activity: dict, state: dict, mentee: dict) -> dict | None:
    pending = state.get("keeptrack_abandon_pending") or {}
    if pending.get("status") != "pending":
        return None
    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    mentee_id = state.get("mentee_id", "")
    profile_parts = mentee_keeptrack_profile_summary_parts(mentee)
    return {
        "request_id": pending.get("request_id") or f"{activity['_id']}:{mentee_id}",
        "activity_id": str(activity["_id"]),
        "activity_name": compose_activity_name(activity),
        "mentee_id": mentee_id,
        "mentee_name": mentee.get("full_name") or mentee.get("username") or mentee.get("email", ""),
        "mentee_email": mentee.get("email", ""),
        "mentee_profile_summary": mentee_keeptrack_profile_summary_line(mentee),
        "mentee_apply_system": profile_parts["apply_system"],
        "mentee_apply_major": profile_parts["apply_major"],
        "mentee_research_direction": profile_parts["research_direction"],
        "mentee_apply_language": profile_parts["apply_language"],
        "requested_at": pending.get("requested_at").isoformat() if pending.get("requested_at") else "",
        "note": pending.get("note") or "",
        "start_date": keeptrack.get("start_date") or "",
        "progress_label": KEEPTRACK_UI_LABELS.get(keeptrack.get("progress_status") or "", "Đang tiến hành"),
    }


def list_pending_keeptrack_abandon_requests(admin: dict) -> list[dict]:
    items: list[dict] = []
    for activity in profile_activities.find(mentor_profile_activities_query(admin)).sort("updated_at", -1):
        for state in activity.get("mentee_states", []):
            if not state.get("registered_at"):
                continue
            mentee_id = state.get("mentee_id", "")
            if not ObjectId.is_valid(mentee_id):
                continue
            mentee = users.find_one({"_id": ObjectId(mentee_id)})
            if not mentee:
                continue
            row = serialize_pending_keeptrack_abandon(activity, state, mentee)
            if row:
                items.append(row)
    items.sort(key=lambda item: item.get("requested_at") or "", reverse=True)
    return items


def _get_pending_keeptrack_abandon_state(activity: dict, mentee_id: str) -> tuple[dict, dict]:
    state = _get_mentee_state(activity, mentee_id)
    if not state:
        raise ProfileActivityKeeptrackError("Mentee chưa báo danh hoạt động này.")
    pending = state.get("keeptrack_abandon_pending") or {}
    if pending.get("status") != "pending":
        raise ProfileActivityKeeptrackError("Không có yêu cầu từ bỏ đang chờ xử lý.")
    return state, pending


def approve_keeptrack_abandon(activity: dict, mentee_id: str, admin: dict) -> dict:
    state, _pending = _get_pending_keeptrack_abandon_state(activity, mentee_id)
    mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    if not mentee:
        raise ProfileActivityKeeptrackError("Mentee không tồn tại.")

    _remove_keeptrack_hdnk_entry(mentee, state)
    now = datetime.now(timezone.utc)
    activity_name = compose_activity_name(activity)
    notify_mentee_mentor_activity(
        mentee,
        action="profile_activity_keeptrack_abandon_approved",
        title="Mentor đồng ý từ bỏ hoạt động",
        description=f"Mentor đã đồng ý yêu cầu từ bỏ hoạt động '{activity_name}'.",
        mentor_name=activity.get("mentor_name", ""),
    )

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def reject_keeptrack_abandon(activity: dict, mentee_id: str, admin: dict, note: str = "") -> dict:
    state, _pending = _get_pending_keeptrack_abandon_state(activity, mentee_id)
    mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    if not mentee:
        raise ProfileActivityKeeptrackError("Mentee không tồn tại.")

    now = datetime.now(timezone.utc)
    reject_note = (note or "").strip()
    state["keeptrack_abandon_last_rejection"] = {
        "note": reject_note,
        "rejected_at": now,
        "rejected_by_admin_id": str(admin.get("_id", "")),
    }
    state.pop("keeptrack_abandon_pending", None)

    activity_name = compose_activity_name(activity)
    notify_mentee_mentor_activity(
        mentee,
        action="profile_activity_keeptrack_abandon_rejected",
        title="Mentor từ chối yêu cầu từ bỏ",
        description=(
            f"Mentor đã từ chối yêu cầu từ bỏ hoạt động '{activity_name}'."
            + (f" Ghi chú: {reject_note}" if reject_note else "")
        ),
        mentor_name=activity.get("mentor_name", ""),
    )

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def serialize_pending_keeptrack_review(activity: dict, state: dict, mentee: dict) -> dict | None:
    pending = state.get("keeptrack_pending_review") or {}
    if pending.get("status") != "pending":
        return None
    submitted = pending.get("submitted_keeptrack") or {}
    mentee_id = state.get("mentee_id", "")
    profile_parts = mentee_keeptrack_profile_summary_parts(mentee)
    return {
        "review_id": pending.get("review_id") or f"{activity['_id']}:{mentee_id}",
        "activity_id": str(activity["_id"]),
        "activity_name": compose_activity_name(activity),
        "mentee_id": mentee_id,
        "mentee_name": mentee.get("full_name") or mentee.get("username") or mentee.get("email", ""),
        "mentee_email": mentee.get("email", ""),
        "mentee_profile_summary": mentee_keeptrack_profile_summary_line(mentee),
        "mentee_apply_system": profile_parts["apply_system"],
        "mentee_apply_major": profile_parts["apply_major"],
        "mentee_research_direction": profile_parts["research_direction"],
        "mentee_apply_language": profile_parts["apply_language"],
        "submitted_at": pending.get("submitted_at").isoformat() if pending.get("submitted_at") else "",
        "start_date": submitted.get("start_date") or "",
        "progress_status": submitted.get("progress_status") or "",
        "progress_label": KEEPTRACK_UI_LABELS.get(submitted.get("progress_status") or "", ""),
        "has_award": bool(submitted.get("has_award")),
        "award_level": submitted.get("award_level") or "",
        "progress_summary": _keeptrack_progress_description(submitted),
    }


def list_pending_individual_keeptrack_reviews(admin: dict) -> list[dict]:
    items: list[dict] = []
    for activity in profile_activities.find(mentor_profile_activities_query(admin)).sort("updated_at", -1):
        for state in activity.get("mentee_states", []):
            if not state.get("registered_at"):
                continue
            if not _is_individual_participant(activity, state):
                continue
            mentee_id = state.get("mentee_id", "")
            if not ObjectId.is_valid(mentee_id):
                continue
            mentee = users.find_one({"_id": ObjectId(mentee_id)})
            if not mentee:
                continue
            row = serialize_pending_keeptrack_review(activity, state, mentee)
            if row:
                items.append(row)
    items.sort(key=lambda item: item.get("submitted_at") or "", reverse=True)
    return items


def _get_pending_keeptrack_review_state(activity: dict, mentee_id: str) -> tuple[dict, dict]:
    state = _get_mentee_state(activity, mentee_id)
    if not state:
        raise ProfileActivityKeeptrackError("Mentee chưa báo danh hoạt động này.")
    pending = state.get("keeptrack_pending_review") or {}
    if pending.get("status") != "pending":
        raise ProfileActivityKeeptrackError("Không có cập nhật tiến độ đang chờ xử lý.")
    return state, pending


def view_individual_keeptrack_review(activity: dict, mentee_id: str, admin: dict) -> dict:
    state, pending = _get_pending_keeptrack_review_state(activity, mentee_id)
    now = datetime.now(timezone.utc)
    pending["status"] = "viewed"
    pending["viewed_at"] = now
    pending["viewed_by_admin_id"] = str(admin.get("_id", ""))
    state["keeptrack_pending_review"] = pending
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def bulk_view_individual_keeptrack_reviews(items: list[dict], admin: dict) -> int:
    updated = 0
    now = datetime.now(timezone.utc)
    for item in items:
        activity_id = str(item.get("activity_id") or "").strip()
        mentee_id = str(item.get("mentee_id") or "").strip()
        if not ObjectId.is_valid(activity_id) or not mentee_id:
            continue
        activity = profile_activities.find_one({"_id": ObjectId(activity_id)})
        if not activity:
            continue
        try:
            state, pending = _get_pending_keeptrack_review_state(activity, mentee_id)
        except ProfileActivityKeeptrackError:
            continue
        pending["status"] = "viewed"
        pending["viewed_at"] = now
        pending["viewed_by_admin_id"] = str(admin.get("_id", ""))
        state["keeptrack_pending_review"] = pending
        profile_activities.update_one(
            {"_id": activity["_id"]},
            {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
        )
        updated += 1
    return updated


def reject_individual_keeptrack_review(
    activity: dict,
    mentee_id: str,
    admin: dict,
    note: str = "",
) -> dict:
    state, pending = _get_pending_keeptrack_review_state(activity, mentee_id)
    mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    if not mentee:
        raise ProfileActivityKeeptrackError("Mentee không tồn tại.")

    previous_keeptrack = pending.get("previous_keeptrack")
    previous_hdnk_entry = pending.get("previous_hdnk_entry")
    entry_id = (state.get("keeptrack") or {}).get("hdnk_entry_id") or (
        (previous_keeptrack or {}).get("hdnk_entry_id") if previous_keeptrack else ""
    )

    _apply_keeptrack_snapshot(state, previous_keeptrack)
    _restore_mentee_hdnk_entry(mentee, entry_id, previous_hdnk_entry)

    now = datetime.now(timezone.utc)
    reject_note = (note or "").strip()
    state["keeptrack_last_rejection"] = {
        "note": reject_note,
        "rejected_at": now,
        "rejected_by_admin_id": str(admin.get("_id", "")),
    }
    state.pop("keeptrack_pending_review", None)

    activity_name = compose_activity_name(activity)
    notify_mentee_mentor_activity(
        mentee,
        action="profile_activity_keeptrack_rejected",
        title="Mentor từ chối cập nhật tiến độ",
        description=(
            f"Mentor đã từ chối cập nhật tiến độ cho hoạt động '{activity_name}'."
            + (f" Ghi chú: {reject_note}" if reject_note else "")
        ),
        mentor_name=activity.get("mentor_name", ""),
    )

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def _clear_keeptrack_on_reject(state: dict) -> None:
    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    if keeptrack.get("active"):
        state["keeptrack"] = {
            **keeptrack,
            "active": False,
            "progress_status": KEEPTRACK_PROGRESS_COMPLETED,
        }


def _find_mentee_finalized_group(activity: dict, mentee_id: str) -> dict | None:
    for group in activity.get("groups", []):
        if not group_is_approved(group) or _is_auto_solo_group(group):
            continue
        if not group.get("finalized_at"):
            continue
        mentee_ids = [str(item) for item in (group.get("mentee_ids") or [])]
        if mentee_id in mentee_ids:
            return group
    return None


def _find_mentee_display_group(activity: dict, mentee_id: str, state: dict) -> dict | None:
    if state.get("participation_choice") == "individual":
        return None
    if _normalize_participation_mode(activity.get("participation_mode")) == "individual":
        return None
    finalized = _find_mentee_finalized_group(activity, mentee_id)
    if finalized:
        return finalized
    for group in activity.get("groups", []):
        if not group_is_approved(group) or _is_auto_solo_group(group):
            continue
        mentee_ids = [str(item) for item in (group.get("mentee_ids") or [])]
        if mentee_id in mentee_ids:
            return group
    return None


def _mentee_requires_group_confirmation(activity: dict, mentee_id: str, state: dict) -> bool:
    if not state.get("registered_at"):
        return False
    if state.get("participation_choice") == "individual":
        return False
    if _normalize_participation_mode(activity.get("participation_mode")) == "individual":
        return False
    if (state.get("group_response_status") or "").strip().lower() != "pending":
        return False
    return _find_mentee_finalized_group(activity, mentee_id) is not None


def serialize_group_members_for_mentee(group: dict) -> list[dict]:
    member_ids = [str(item) for item in (group.get("mentee_ids") or []) if str(item)]
    if not member_ids:
        return []
    leader_id = str(group.get("leader_mentee_id") or "").strip()
    object_ids = [ObjectId(item) for item in member_ids if ObjectId.is_valid(item)]
    users_by_id = {
        str(user["_id"]): user
        for user in users.find({"_id": {"$in": object_ids}, "role": {"$ne": ROLE_PARENT}})
    }
    members: list[dict] = []
    for member_id in member_ids:
        user = users_by_id.get(member_id)
        if not user:
            continue
        members.append(
            {
                "mentee_id": member_id,
                "full_name": user.get("full_name") or user.get("username") or user.get("email", ""),
                "zalo_phone": user.get("zalo_phone") or "",
                "is_leader": member_id == leader_id,
            }
        )
    return members


def _mentee_awaiting_group_assignment(activity: dict, mentee_id: str, state: dict) -> bool:
    if not state.get("registered_at"):
        return False
    if state.get("participation_choice") != "group":
        return False
    return _find_mentee_group(activity, mentee_id) is None


def _mentee_can_cancel_registration(activity: dict, mentee_id: str, state: dict) -> bool:
    if not state.get("registered_at"):
        return False
    if _normalize_keeptrack(state.get("keeptrack")).get("active"):
        return False
    if _mentee_requires_group_confirmation(activity, mentee_id, state):
        return False
    pending_abandon = state.get("keeptrack_abandon_pending") or {}
    if pending_abandon.get("status") == "pending":
        return False
    return True


def _reset_mentee_registration_state(state: dict) -> None:
    state["registered_at"] = None
    state["participation_choice"] = None
    state["wants_group_leader"] = False
    state["group_response_status"] = None
    state["group_response_note"] = ""
    state["group_response_at"] = None
    state.pop("mentor_reject_pending", None)
    state.pop("keeptrack_abandon_pending", None)
    state.pop("keeptrack_abandon_last_rejection", None)
    state.pop("keeptrack_pending_review", None)
    state.pop("keeptrack", None)


def _remove_mentee_from_all_groups(activity: dict, mentee_id: str) -> None:
    for group in activity.get("groups", []):
        group["mentee_ids"] = [
            str(item) for item in (group.get("mentee_ids") or []) if str(item) != mentee_id
        ]
    activity["groups"] = [
        group
        for group in activity.get("groups", [])
        if group.get("mentee_ids") or not _is_auto_solo_group(group)
    ]


def _normalize_importance(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_PROFILE_ACTIVITY_IMPORTANCE
    return max(0, min(5, value))


def _normalize_participant_limit(raw) -> int:
    """0 (or anything invalid/blank) means "no limit"."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def _normalize_approval_status(raw: str | None) -> str:
    value = (raw or "").strip()
    if value in PROFILE_ACTIVITY_APPROVAL_STATUSES:
        return value
    return PROFILE_ACTIVITY_APPROVAL_APPROVED


def activity_visible_to_mentee(doc: dict) -> bool:
    status = doc.get("approval_status")
    if not status:
        return True
    return status == PROFILE_ACTIVITY_APPROVAL_APPROVED


def admin_requires_l1_approval(admin: dict) -> bool:
    from services.admins import is_super_admin
    from services.apply_progress import admin_is_level1_mentor

    return not (is_super_admin(admin) or admin_is_level1_mentor(admin))


def resolve_initial_approval_status(admin: dict) -> str:
    if admin_requires_l1_approval(admin):
        return PROFILE_ACTIVITY_APPROVAL_PENDING
    return PROFILE_ACTIVITY_APPROVAL_APPROVED


def group_is_approved(group: dict) -> bool:
    return _normalize_approval_status(group.get("approval_status")) == PROFILE_ACTIVITY_APPROVAL_APPROVED


def parse_profile_activity_from_description(description: str) -> dict:
    text = (description or "").strip()
    deadline = _find_regex_group(
        r"(?:deadline|hạn(?: đăng ký| chót)?)[\s:]*([0-3]?\d[\/\-.][01]?\d(?:[\/\-.]\d{2,4})?)",
        text,
    )
    organizer = _find_regex_group(
        r"(?:đơn vị tổ chức|ban tổ chức|organizer|hosted by)[:\s]+([^\n.;]+)",
        text,
    )
    target = _find_regex_group(r"(?:dành cho|đối tượng)[:\s]+([^\n.;]+)", text)
    content = _find_regex_group(r"(?:về|chủ đề|nội dung)[:\s]+([^\n.;]+)", text)
    majors = _extract_majors(text)
    parsed = {
        "activity_type": _extract_type(text),
        "deadline": _normalize_date_text(deadline),
        "organizer": organizer,
        "target_audience": target,
        "content": content,
        "suitable_majors": majors,
    }
    parsed["activity_name"] = compose_activity_name(parsed)
    return parsed


def sanitize_profile_activity_input(data: dict, *, parsed_fallback: dict | None = None) -> dict:
    parsed_fallback = parsed_fallback or {}
    majors = data.get("suitable_majors")
    if not isinstance(majors, list):
        majors = parsed_fallback.get("suitable_majors") or []
    cleaned_majors: list[str] = []
    for major in majors:
        normalized = _normalize_major_label(str(major or ""))
        if normalized and normalized not in cleaned_majors:
            cleaned_majors.append(normalized)
    other = str(data.get("suitable_majors_other") or "").strip()
    if "Khác" not in cleaned_majors:
        other = ""
    activity_type = (data.get("activity_type") or parsed_fallback.get("activity_type") or "Khác").strip()
    if activity_type not in PROFILE_ACTIVITY_TYPES:
        activity_type = "Khác"
    cleaned = {
        "link": str(data.get("link") or "").strip(),
        "description": str(data.get("description") or "").strip(),
        "activity_type": activity_type,
        "deadline": _normalize_date_text(str(data.get("deadline") or parsed_fallback.get("deadline") or "")),
        "organizer": str(data.get("organizer") or parsed_fallback.get("organizer") or "").strip(),
        "target_audience": str(
            data.get("target_audience") or parsed_fallback.get("target_audience") or ""
        ).strip(),
        "content": str(data.get("content") or parsed_fallback.get("content") or "").strip(),
        "attachment_url": str(data.get("attachment_url") or "").strip(),
        "suitable_majors": cleaned_majors,
        "suitable_majors_other": other,
        "importance": _normalize_importance(
            data.get("importance", parsed_fallback.get("importance", DEFAULT_PROFILE_ACTIVITY_IMPORTANCE))
        ),
        "participation_mode": _normalize_participation_mode(
            data.get("participation_mode", parsed_fallback.get("participation_mode", DEFAULT_PARTICIPATION_MODE))
        ),
        "internal_note": str(data.get("internal_note") or "").strip(),
        "participant_limit": _normalize_participant_limit(data.get("participant_limit")),
        "referrer_zalo_phone": normalize_zalo_phone(str(data.get("referrer_zalo_phone") or "")),
    }
    cleaned["activity_name"] = compose_activity_name(cleaned)
    return cleaned


class ProfileActivityBulkImportError(ValueError):
    """Raised when an uploaded bulk-import Excel file is malformed."""


def _normalize_header_label(raw) -> str:
    return str(raw or "").strip().lower()


def parse_profile_activities_bulk_excel(file_stream) -> dict:
    """Parse an uploaded .xlsx file with "Link" and "Mô tả gốc" columns.

    Returns {"items": [cleaned dicts with row_index], "skipped_rows": [{"row_index": int}]}.
    Does not write to the database — pure parse/preview step.
    """
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(file_stream.read()), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001 - surface a clear Vietnamese error regardless of cause
        raise ProfileActivityBulkImportError("Không đọc được file Excel — vui lòng kiểm tra lại file") from exc

    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        raise ProfileActivityBulkImportError("File Excel trống — không có dòng tiêu đề")

    link_col = None
    description_col = None
    for index, raw_label in enumerate(header_row):
        label = _normalize_header_label(raw_label)
        if label == "link":
            link_col = index
        elif label == "mô tả gốc":
            description_col = index

    if link_col is None and description_col is None:
        raise ProfileActivityBulkImportError("Thiếu cột \"Link\" và \"Mô tả gốc\" trong file Excel")
    if link_col is None:
        raise ProfileActivityBulkImportError("Thiếu cột \"Link\" trong file Excel")
    if description_col is None:
        raise ProfileActivityBulkImportError("Thiếu cột \"Mô tả gốc\" trong file Excel")

    items: list[dict] = []
    skipped_rows: list[dict] = []
    for offset, row in enumerate(rows_iter):
        row_index = offset + 2  # 1-based Excel row number, header is row 1
        if row is None or all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        link = str(row[link_col]).strip() if link_col < len(row) and row[link_col] is not None else ""
        description = (
            str(row[description_col]).strip()
            if description_col < len(row) and row[description_col] is not None
            else ""
        )
        if not description:
            skipped_rows.append({"row_index": row_index})
            continue
        parsed = parse_profile_activity_from_description(description)
        cleaned = sanitize_profile_activity_input({"link": link, "description": description}, parsed_fallback=parsed)
        cleaned["row_index"] = row_index
        items.append(cleaned)

    return {"items": items, "skipped_rows": skipped_rows}


def _get_or_create_state(doc: dict, mentee_id: str) -> dict:
    states = doc.setdefault("mentee_states", [])
    for item in states:
        if item.get("mentee_id") == mentee_id:
            return item
    state = {
        "mentee_id": mentee_id,
        "read_at": None,
        "hidden": False,
        "registered_at": None,
        "group_response_status": None,
        "group_response_note": "",
        "group_response_at": None,
        "participation_choice": None,
        "wants_group_leader": False,
    }
    states.append(state)
    return state


def _mentee_major_values(mentee: dict) -> set[str]:
    values = set()
    free_text = [
        mentee.get("apply_direction", ""),
        mentee.get("mentor_apply_direction", ""),
        mentor_apply_direction_label(mentee.get("mentor_apply_direction", "")),
        mentee.get("scholarship_system", ""),
    ]
    lowered = " | ".join(str(item or "").lower() for item in free_text)
    for major, keywords in _MAJOR_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            values.add(major)
    code = (mentee.get("mentor_apply_direction") or "").strip().lower()
    alias = _MAJOR_ALIASES.get(code)
    if alias:
        values.add(alias)
    return values


def _mentee_free_text(mentee: dict) -> str:
    parts = [
        mentee.get("apply_direction", ""),
        mentee.get("mentor_apply_direction", ""),
        mentor_apply_direction_label(mentee.get("mentor_apply_direction", "")),
    ]
    return " | ".join(str(item or "").lower() for item in parts)


def _matches_other_major(activity: dict, mentee: dict) -> bool:
    other = (activity.get("suitable_majors_other") or "").strip().lower()
    if not other:
        return "Khác" in _mentee_major_values(mentee)
    mentee_text = _mentee_free_text(mentee)
    return other in mentee_text


def _mentee_has_notified_group_assignment(activity: dict, mentee_id: str) -> bool:
    return _find_mentee_finalized_group(activity, mentee_id) is not None


def _resolve_group_name_for_admin(activity: dict, mentee_id: str) -> str:
    for group in activity.get("groups", []):
        mentee_ids = [str(item) for item in (group.get("mentee_ids") or [])]
        if mentee_id in mentee_ids:
            return group.get("group_name", "")
    return ""


def _get_mentee_state(activity: dict, mentee_id: str) -> dict | None:
    for item in activity.get("mentee_states", []):
        if item.get("mentee_id") == mentee_id:
            return item
    return None


def _mentee_in_pending_group(activity: dict, mentee_id: str) -> bool:
    for group in activity.get("groups", []):
        mentee_ids = [str(item) for item in (group.get("mentee_ids") or [])]
        if mentee_id in mentee_ids and not group_is_approved(group):
            return True
    return False


def registration_response_display(activity: dict, state: dict, mentee_id: str) -> dict:
    pending_reject = state.get("mentor_reject_pending") or {}
    if pending_reject.get("approval_status") == PROFILE_ACTIVITY_APPROVAL_PENDING:
        return {"status": "pending_l1_approval", "label": "Chờ L1 duyệt"}

    if _mentee_in_pending_group(activity, mentee_id):
        return {"status": "pending_l1_approval", "label": "Chờ L1 duyệt"}

    response = (state.get("group_response_status") or "").strip().lower()
    if response == "confirmed":
        return {"status": "confirmed", "label": "Đã duyệt"}
    if response == "rejected":
        return {"status": "rejected", "label": "Từ chối"}
    if response == "pending":
        if state.get("participation_choice") == "individual":
            return {"status": "confirmed", "label": "Đã duyệt"}
        if _normalize_participation_mode(activity.get("participation_mode")) == "individual":
            return {"status": "confirmed", "label": "Đã duyệt"}
        return {"status": "pending", "label": "Chờ mentee xác nhận"}
    return {"status": "", "label": "—"}


def serialize_admin_registration(activity: dict, state: dict, mentee: dict) -> dict:
    mentee_id = state.get("mentee_id", "")
    display = registration_response_display(activity, state, mentee_id)
    pending_reject = state.get("mentor_reject_pending") or {}
    return {
        "mentee_id": mentee_id,
        "mentee_name": mentee.get("full_name") or mentee.get("username") or mentee.get("email", ""),
        "mentee_profile_summary": mentee_keeptrack_profile_summary_line(mentee),
        "zalo_phone": mentee.get("zalo_phone", ""),
        "apply_major": mentor_apply_direction_label(mentee.get("mentor_apply_direction", ""))
        or mentee.get("apply_direction", ""),
        "group_name": _resolve_group_name_for_admin(activity, mentee_id),
        "group_response_status": state.get("group_response_status") or "",
        "group_response_note": state.get("group_response_note", ""),
        "response_display_status": display["status"],
        "response_display_label": display["label"],
        "pending_l1_group": _mentee_in_pending_group(activity, mentee_id),
        "pending_l1_reject": pending_reject.get("approval_status") == PROFILE_ACTIVITY_APPROVAL_PENDING,
        "mentor_reject_note": pending_reject.get("note", ""),
        "participation_choice": state.get("participation_choice") or "",
        "participation_choice_label": PARTICIPATION_MODE_LABELS.get(state.get("participation_choice") or "", ""),
        "wants_group_leader": bool(state.get("wants_group_leader")),
        "awaiting_group_assignment": _mentee_awaiting_group_assignment(activity, mentee_id, state),
        "keeptrack": _serialize_keeptrack_for_feed(activity, state),
        "keeptrack_pending_review": (
            (state.get("keeptrack_pending_review") or {}).get("status") == "pending"
        ),
    }


def format_activity_feed_line(activity: dict, mentee: dict | None = None) -> str:
    line = _build_activity_name_line(activity)
    stored = (activity.get("activity_name") or "").strip()
    if stored and line in {"Khác", "Hoạt động hồ sơ"} and len(stored) > len(line):
        line = stored
    if not line:
        line = "Hoạt động hồ sơ"
    link = (activity.get("link") or "").strip()
    if link:
        return f"{line}\nLink: {link}"
    return line


def activity_matches_mentee_major(activity: dict, mentee: dict) -> bool:
    suitable = {
        normalized
        for major in (activity.get("suitable_majors") or [])
        if (normalized := _normalize_major_label(major))
    }
    if not suitable:
        return False
    mentee_majors = _mentee_major_values(mentee)
    standard_suitable = suitable - {"Khác"}
    if standard_suitable.intersection(mentee_majors):
        return True
    if "Khác" in suitable:
        return _matches_other_major(activity, mentee)
    return False


def serialize_profile_activity_for_feed(
    doc: dict,
    mentee: dict,
    *,
    include_hidden: bool = False,
    exclude_from_feed: bool = False,
) -> dict:
    mentee_id = str(mentee["_id"])
    state = _get_or_create_state(doc, mentee_id)
    if state.get("hidden") and not include_hidden:
        return {}
    if exclude_from_feed and _mentee_excluded_from_feed(state):
        return {}
    registration_count = sum(1 for item in doc.get("mentee_states", []) if item.get("registered_at"))
    group_response_status = state.get("group_response_status")
    display_group = _find_mentee_display_group(doc, mentee_id, state)
    group_assignment_pending = _mentee_requires_group_confirmation(doc, mentee_id, state)
    group_finalized = bool((display_group or {}).get("finalized_at"))
    group_member_count = len((display_group or {}).get("mentee_ids") or []) if display_group else 0
    group_members: list[dict] = []
    response_status = (group_response_status or "").strip().lower()
    if display_group and (group_finalized or response_status == "confirmed"):
        group_members = serialize_group_members_for_mentee(display_group)
    payload = {
        "id": str(doc["_id"]),
        "activity_name": doc.get("activity_name", ""),
        "activity_type": doc.get("activity_type", "Khác"),
        "link": doc.get("link", ""),
        "deadline": doc.get("deadline", ""),
        "organizer": doc.get("organizer", ""),
        "target_audience": doc.get("target_audience", ""),
        "content": doc.get("content", ""),
        "attachment_url": doc.get("attachment_url", ""),
        "suitable_majors": doc.get("suitable_majors", []),
        "suitable_majors_other": doc.get("suitable_majors_other", ""),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else "",
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else "",
        "read": bool(state.get("read_at")),
        "viewed": bool(state.get("read_at")),
        "hidden": bool(state.get("hidden")),
        "registered": bool(state.get("registered_at")),
        "group_response_status": group_response_status,
        "group_response_note": state.get("group_response_note", ""),
        "group_assignment_pending": group_assignment_pending,
        "group_name": (display_group or {}).get("group_name", "") if display_group else "",
        "group_member_count": group_member_count,
        "group_finalized": group_finalized,
        "group_members": group_members,
        "highlight_star": activity_matches_mentee_major(doc, mentee),
        "importance": _normalize_importance(doc.get("importance", DEFAULT_PROFILE_ACTIVITY_IMPORTANCE)),
        "registration_count": registration_count,
        "deadline_badge": get_deadline_badge(doc.get("deadline", "")),
        "participation_mode": _normalize_participation_mode(doc.get("participation_mode")),
        "participation_mode_label": participation_mode_label(doc.get("participation_mode")),
        "participation_choice": state.get("participation_choice") or "",
        "participation_choice_label": PARTICIPATION_MODE_LABELS.get(state.get("participation_choice") or "", ""),
        "awaiting_group_assignment": _mentee_awaiting_group_assignment(doc, mentee_id, state),
        "needs_participation_choice": _normalize_participation_mode(doc.get("participation_mode"))
        in {"both", "unknown"},
        "invited": bool(state.get("invited_at")) and not bool(state.get("registered_at")),
        "can_cancel_registration": _mentee_can_cancel_registration(doc, mentee_id, state),
    }
    keeptrack = _serialize_keeptrack_for_feed(doc, state)
    if keeptrack:
        payload["keeptrack"] = keeptrack
    payload["feed_line"] = format_activity_feed_line(payload, mentee)
    return payload


def serialize_admin_profile_activity(doc: dict, *, admin: dict | None = None) -> dict:
    mentee_states = doc.get("mentee_states") or []
    registrations = [item for item in mentee_states if item.get("registered_at")]
    pending_action_count = count_pending_actions_for_activity(doc, admin) if admin else 0
    return {
        "id": str(doc["_id"]),
        "activity_name": doc.get("activity_name", ""),
        "activity_type": doc.get("activity_type", "Khác"),
        "link": doc.get("link", ""),
        "description": doc.get("description", ""),
        "deadline": doc.get("deadline", ""),
        "organizer": doc.get("organizer", ""),
        "target_audience": doc.get("target_audience", ""),
        "content": doc.get("content", ""),
        "attachment_url": doc.get("attachment_url", ""),
        "suitable_majors": doc.get("suitable_majors", []),
        "suitable_majors_other": doc.get("suitable_majors_other", ""),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else "",
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else "",
        "registration_count": len(registrations),
        "groups": _serialize_admin_groups(doc),
        "unfinalized_group_reminders": list_unfinalized_group_reminders(doc),
        "importance": _normalize_importance(doc.get("importance", DEFAULT_PROFILE_ACTIVITY_IMPORTANCE)),
        "internal_note": doc.get("internal_note", ""),
        "participant_limit": _normalize_participant_limit(doc.get("participant_limit")),
        "approved_participant_count": count_approved_participants(doc),
        "referrer_zalo_phone": doc.get("referrer_zalo_phone", ""),
        "approval_status": _normalize_approval_status(doc.get("approval_status")),
        "created_by_admin_id": doc.get("created_by_admin_id", ""),
        "approved_at": doc.get("approved_at").isoformat() if doc.get("approved_at") else "",
        "approved_by_admin_id": doc.get("approved_by_admin_id", ""),
        "rejected_at": doc.get("rejected_at").isoformat() if doc.get("rejected_at") else "",
        "rejected_by_admin_id": doc.get("rejected_by_admin_id", ""),
        "deadline_badge": get_deadline_badge(doc.get("deadline", "")),
        "pending_l1_actions": list_pending_l1_group_actions(doc),
        "pending_action_count": pending_action_count,
        "participation_mode": _normalize_participation_mode(doc.get("participation_mode")),
        "participation_mode_label": participation_mode_label(doc.get("participation_mode")),
        "invited_mentee_ids": [
            str(item.get("mentee_id"))
            for item in mentee_states
            if item.get("invited_at") and not item.get("registered_at") and item.get("mentee_id")
        ],
    }


def create_profile_activity(admin: dict, payload: dict) -> dict:
    now = datetime.now(timezone.utc)
    approval_status = resolve_initial_approval_status(admin)
    doc = {
        **payload,
        "mentor_name": (admin.get("mentor_name") or "").strip(),
        "created_by_admin_id": str(admin["_id"]),
        "approval_status": approval_status,
        "created_at": now,
        "updated_at": now,
        "mentee_states": [],
        "groups": [],
    }
    if approval_status == PROFILE_ACTIVITY_APPROVAL_APPROVED:
        doc["approved_at"] = now
        doc["approved_by_admin_id"] = str(admin["_id"])
    result = profile_activities.insert_one(doc)
    created = profile_activities.find_one({"_id": result.inserted_id}) or doc
    if created.get("referrer_zalo_phone"):
        award_referrer_phone_for_activity(
            phone=created["referrer_zalo_phone"],
            activity_id=created["_id"],
        )
    return created


class ProfileActivityUpdateError(ValueError):
    pass


def update_profile_activity(activity: dict, admin: dict, data: dict) -> dict:
    now = datetime.now(timezone.utc)
    parsed = parse_profile_activity_from_description(
        str(data.get("description") or activity.get("description") or "")
    )
    payload = sanitize_profile_activity_input(data, parsed_fallback=parsed)
    if not payload.get("activity_name"):
        raise ProfileActivityUpdateError("Không thể tạo tên hoạt động — vui lòng điền loại hoạt động")

    old_referrer_phone = normalize_zalo_phone(str(activity.get("referrer_zalo_phone") or ""))
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {**payload, "updated_at": now}},
    )
    updated = profile_activities.find_one({"_id": activity["_id"]}) or activity

    new_referrer_phone = payload.get("referrer_zalo_phone") or ""
    if new_referrer_phone and not old_referrer_phone:
        award_referrer_phone_for_activity(phone=new_referrer_phone, activity_id=updated["_id"])

    return updated


def approve_profile_activity(activity: dict, admin: dict) -> dict:
    now = datetime.now(timezone.utc)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "approval_status": PROFILE_ACTIVITY_APPROVAL_APPROVED,
                "approved_at": now,
                "approved_by_admin_id": str(admin["_id"]),
                "rejected_at": None,
                "rejected_by_admin_id": "",
                "updated_at": now,
            }
        },
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def reject_profile_activity(activity: dict, admin: dict) -> dict:
    now = datetime.now(timezone.utc)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "approval_status": PROFILE_ACTIVITY_APPROVAL_REJECTED,
                "rejected_at": now,
                "rejected_by_admin_id": str(admin["_id"]),
                "updated_at": now,
            }
        },
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def _sorted_activities_for_mentee(mentee: dict) -> list[dict]:
    query = {
        "created_at": {"$exists": True},
        "$and": [
            {"$or": [{"mentor_name": {"$exists": False}}, {"mentor_name": mentee.get("mentor", "")}]},
            {
                "$or": [
                    {"approval_status": {"$exists": False}},
                    {"approval_status": PROFILE_ACTIVITY_APPROVAL_APPROVED},
                ]
            },
        ],
    }
    cursor = profile_activities.find(query).sort("created_at", -1)
    return list(cursor)


def list_profile_activities_for_mentee(mentee: dict) -> list[dict]:
    items: list[dict] = []
    for doc in _sorted_activities_for_mentee(mentee):
        payload = serialize_profile_activity_for_feed(doc, mentee, exclude_from_feed=True)
        if payload:
            items.append(payload)
    return items


def list_active_keeptrack_for_mentee(mentee: dict) -> list[dict]:
    mentee_id = str(mentee["_id"])
    items: list[dict] = []
    for doc in _sorted_activities_for_mentee(mentee):
        state = _get_or_create_state(doc, mentee_id)
        keeptrack = _normalize_keeptrack(state.get("keeptrack"))
        abandon_pending = state.get("keeptrack_abandon_pending") or {}
        in_panel = keeptrack["active"] or abandon_pending.get("status") == "pending"
        if not in_panel:
            continue
        payload = serialize_profile_activity_for_feed(doc, mentee, include_hidden=True)
        if payload:
            items.append(payload)
    return items


def build_mentee_activities_response(mentee: dict, *, max_other_days: int = 10) -> dict:
    feed_items = list_profile_activities_for_mentee(mentee)
    grouped = group_mentee_feed_by_day(feed_items, max_other_days=max_other_days)
    grouped["active_keeptrack"] = list_active_keeptrack_for_mentee(mentee)
    return grouped


def group_mentee_feed_by_day(items: list[dict], *, max_other_days: int = 10) -> dict:
    groups: dict[str, dict] = {}
    now = datetime.now(VN_TZ)
    for item in items:
        created = item.get("created_at", "")
        try:
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(VN_TZ)
        except (TypeError, ValueError):
            dt = now
        date_key = dt.strftime("%Y-%m-%d")
        date_label = dt.strftime("%d/%m/%Y")
        if date_key not in groups:
            groups[date_key] = {"date_key": date_key, "date_label": date_label, "items": []}
        groups[date_key]["items"].append(item)

    ordered = [groups[key] for key in sorted(groups.keys(), reverse=True)]
    current_day = ordered[0] if ordered else None
    other_days = ordered[1 : 1 + max_other_days]
    unviewed_count = sum(1 for item in items if not item.get("viewed"))

    return {
        "current_day": current_day,
        "other_days": other_days,
        "unviewed_count": unviewed_count,
        "max_other_days": max_other_days,
    }


def mark_activity_read(activity: dict, mentee: dict) -> dict:
    mentee_id = str(mentee["_id"])
    state = _get_or_create_state(activity, mentee_id)
    state["read_at"] = datetime.now(timezone.utc)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": datetime.now(timezone.utc)}},
    )
    return activity


def set_activity_hidden(activity: dict, mentee: dict, hidden: bool) -> dict:
    mentee_id = str(mentee["_id"])
    state = _get_or_create_state(activity, mentee_id)
    state["hidden"] = bool(hidden)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": datetime.now(timezone.utc)}},
    )
    return activity


def _create_auto_solo_group(activity: dict, mentee_id: str) -> dict:
    now = datetime.now(timezone.utc)
    group = {
        "group_id": str(uuid.uuid4()),
        "group_name": suggest_group_name(activity),
        "mentee_ids": [mentee_id],
        "notification_sent_at": None,
        "finalized_at": None,
        "leader_mentee_id": "",
        "approval_status": PROFILE_ACTIVITY_APPROVAL_APPROVED,
        "submitted_by_admin_id": "system",
        "submitted_at": now,
        "approved_at": now,
        "approved_by_admin_id": "system",
        "is_auto_solo": True,
    }
    groups = activity.get("groups") or []
    groups.append(group)
    activity["groups"] = groups
    return group


class ProfileActivityInviteError(ValueError):
    pass


def _mentee_belongs_to_activity_mentor(mentee: dict, activity: dict) -> bool:
    activity_mentor = (activity.get("mentor_name") or "").strip()
    if not activity_mentor:
        return True
    return (mentee.get("mentor") or "").strip() == activity_mentor


def invite_mentees_to_activity(activity: dict, mentee_ids: list[str], admin: dict) -> dict:
    approval = _normalize_approval_status(activity.get("approval_status"))
    if approval == PROFILE_ACTIVITY_APPROVAL_PENDING:
        raise ProfileActivityInviteError(
            "Hoạt động chưa được duyệt — chưa thể mời mentee tham gia."
        )
    if approval == PROFILE_ACTIVITY_APPROVAL_REJECTED:
        raise ProfileActivityInviteError("Hoạt động đã bị từ chối.")

    now = datetime.now(timezone.utc)
    activity_name = compose_activity_name(activity)
    mentor_label = (
        (admin.get("full_name") or "").strip()
        or (admin.get("mentor_name") or "").strip()
        or (activity.get("mentor_name") or "").strip()
        or "Mentor"
    )
    invited: list[str] = []
    skipped: list[dict] = []

    seen: set[str] = set()
    for raw_id in mentee_ids or []:
        mentee_id = str(raw_id or "").strip()
        if not mentee_id or mentee_id in seen:
            continue
        seen.add(mentee_id)
        if not ObjectId.is_valid(mentee_id):
            skipped.append({"mentee_id": mentee_id, "reason": "invalid"})
            continue
        mentee = users.find_one({"_id": ObjectId(mentee_id)})
        if not mentee:
            skipped.append({"mentee_id": mentee_id, "reason": "not_found"})
            continue
        if not _mentee_belongs_to_activity_mentor(mentee, activity):
            skipped.append({"mentee_id": mentee_id, "reason": "wrong_mentor"})
            continue

        state = _get_or_create_state(activity, mentee_id)
        if state.get("registered_at"):
            skipped.append({"mentee_id": mentee_id, "reason": "already_registered"})
            continue

        was_invited = bool(state.get("invited_at"))
        state["invited_at"] = now
        if not was_invited:
            state["read_at"] = None

        notify_mentee_mentor_activity(
            mentee,
            action="profile_activity_invite",
            title=f"{mentor_label} mời bạn tham gia hoạt động",
            description=(
                f"Hoạt động: {activity_name}. Hãy vào hồ sơ để xem chi tiết và báo danh nhé."
            ),
            mentor_name=activity.get("mentor_name", "") or mentor_label,
            mentor_admin=admin,
        )
        invited.append(mentee_id)

    if invited:
        profile_activities.update_one(
            {"_id": activity["_id"]},
            {
                "$set": {
                    "mentee_states": activity.get("mentee_states", []),
                    "updated_at": now,
                }
            },
        )

    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    return {"invited": invited, "skipped": skipped, "activity": refreshed}


def _resolve_registration_choice(activity: dict, participation_choice: str | None) -> str:
    mode = _normalize_participation_mode(activity.get("participation_mode"))
    if mode == "individual":
        return "individual"
    if mode == "group":
        return "group"
    choice = str(participation_choice or "").strip().lower()
    if choice not in MENTEE_PARTICIPATION_CHOICES:
        raise ProfileActivityRegistrationError(
            "Vui lòng chọn hình thức tham gia: Cá nhân hoặc Nhóm."
        )
    return choice


def register_for_activity(
    activity: dict,
    mentee: dict,
    *,
    participation_choice: str | None = None,
    wants_group_leader: bool | None = None,
) -> dict:
    mentee_id = str(mentee["_id"])
    state = _get_or_create_state(activity, mentee_id)
    if state.get("registered_at"):
        return activity

    effective_choice = _resolve_registration_choice(activity, participation_choice)
    now = datetime.now(timezone.utc)
    limit = _normalize_participant_limit(activity.get("participant_limit"))
    over_capacity = (
        effective_choice == "individual" and limit > 0 and count_approved_participants(activity) >= limit
    )
    state["registered_at"] = now
    state["participation_choice"] = effective_choice
    state["wants_group_leader"] = bool(
        effective_choice == "group" and wants_group_leader
    )

    if over_capacity:
        # Individual registrations are otherwise auto-confirmed immediately below
        # (no separate "pending mentor approval" step to intercept later), so the
        # capacity limit for new individual sign-ups has to be enforced right here.
        state["group_response_status"] = "rejected"
        state["group_response_note"] = PARTICIPANT_LIMIT_AUTO_REJECT_REASON
        state["group_response_at"] = now
    elif effective_choice == "individual":
        _create_auto_solo_group(activity, mentee_id)
        state["group_response_status"] = "confirmed"
        state["group_response_note"] = ""
        state["group_response_at"] = now

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "mentee_states": activity.get("mentee_states", []),
                "groups": activity.get("groups", []),
                "updated_at": now,
            }
        },
    )
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    if over_capacity:
        notify_mentee_mentor_activity(
            mentee,
            action="profile_activity_rejected",
            title="Đã đủ số lượng tham gia",
            description=(
                f"Hoạt động '{compose_activity_name(refreshed)}' đã đủ số lượng tham gia nên báo danh "
                f"của bạn không được duyệt."
            ),
            mentor_name=activity.get("mentor_name", ""),
        )
        return refreshed
    if effective_choice == "individual":
        maybe_start_individual_keeptrack(refreshed, mentee_id)
        refreshed = profile_activities.find_one({"_id": activity["_id"]}) or refreshed
        refreshed = enforce_participant_capacity(refreshed)
        activity_name = compose_activity_name(refreshed)
        mentee_name = mentee.get("full_name") or mentee.get("username") or mentee.get("email", "")
        notify_mentors_mentee_activity(
            mentee,
            action="profile_activity_register",
            title=f"{mentee_name} báo danh hoạt động (cá nhân)",
            description=f"Hoạt động: {activity_name}. Tiến độ đã tự động lưu vào Keep track.",
        )
    elif effective_choice == "group" and state.get("wants_group_leader"):
        activity_name = compose_activity_name(refreshed)
        mentee_name = mentee.get("full_name") or mentee.get("username") or mentee.get("email", "")
        notify_mentors_mentee_activity(
            mentee,
            action="profile_activity_register",
            title=f"{mentee_name} báo danh hoạt động (nhóm) — đăng ký nhóm trưởng",
            description=f"Hoạt động: {activity_name}. Mentee muốn làm nhóm trưởng.",
        )
    return refreshed


def cancel_activity_registration(activity: dict, mentee: dict) -> dict:
    mentee_id = str(mentee["_id"])
    state = _get_mentee_state(activity, mentee_id)
    if not state or not state.get("registered_at"):
        raise ProfileActivityRegistrationError("Bạn chưa báo danh hoạt động này.")
    if not _mentee_can_cancel_registration(activity, mentee_id, state):
        raise ProfileActivityRegistrationError(
            "Không thể hủy đăng kí ở trạng thái hiện tại. Vui lòng liên hệ mentor nếu cần."
        )

    now = datetime.now(timezone.utc)
    if _is_individual_participant(activity, state):
        _remove_keeptrack_hdnk_entry(mentee, state)
    else:
        _clear_keeptrack_on_reject(state)

    _remove_mentee_from_all_groups(activity, mentee_id)
    _reset_mentee_registration_state(state)

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "mentee_states": activity.get("mentee_states", []),
                "groups": activity.get("groups", []),
                "updated_at": now,
            }
        },
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


FINALIZE_GROUP_REMINDER_INTERVAL = timedelta(hours=12)


def _coerce_utc_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return None


def group_needs_finalize_reminder(group: dict) -> bool:
    if _is_auto_solo_group(group):
        return False
    if group.get("finalized_at"):
        return False
    if not (group.get("mentee_ids") or []):
        return False
    if not group_is_approved(group):
        return False
    dismissed = _coerce_utc_datetime(group.get("finalize_reminder_dismissed_at"))
    if not dismissed:
        return True
    return datetime.now(timezone.utc) >= dismissed + FINALIZE_GROUP_REMINDER_INTERVAL


def list_unfinalized_group_reminders(activity: dict) -> list[dict]:
    reminders: list[dict] = []
    for group in activity.get("groups", []) or []:
        if not group_needs_finalize_reminder(group):
            continue
        reminders.append(
            {
                "group_id": group.get("group_id", ""),
                "group_name": group.get("group_name", ""),
                "member_count": len(group.get("mentee_ids") or []),
            }
        )
    return reminders


def dismiss_finalize_group_reminder(activity: dict, group_id: str) -> dict:
    group = _find_group(activity, group_id)
    if not group:
        raise ValueError("Nhóm không tồn tại")
    if not group_needs_finalize_reminder(group):
        raise ValueError("Nhóm này không cần nhắc chốt nhóm.")
    now = datetime.now(timezone.utc)
    group["finalize_reminder_dismissed_at"] = now
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": activity.get("groups", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def _serialize_admin_group_row(group: dict) -> dict:
    row = dict(group)
    for key in (
        "submitted_at",
        "approved_at",
        "finalized_at",
        "notification_sent_at",
        "finalize_reminder_dismissed_at",
    ):
        value = row.get(key)
        if value and hasattr(value, "isoformat"):
            row[key] = value.isoformat()
    row["needs_finalize_reminder"] = group_needs_finalize_reminder(group)
    return row


def _serialize_admin_groups(activity: dict) -> list[dict]:
    return [_serialize_admin_group_row(group) for group in (activity.get("groups") or [])]


def _group_payload(group: dict, *, approval_status: str | None = None) -> dict:
    status = approval_status or _normalize_approval_status(group.get("approval_status"))
    return {
        "group_id": group.get("group_id") or str(uuid.uuid4()),
        "group_name": (group.get("group_name") or "").strip() or "Nhóm mới",
        "mentee_ids": [str(item) for item in (group.get("mentee_ids") or []) if str(item)],
        "notification_sent_at": group.get("notification_sent_at"),
        "finalized_at": group.get("finalized_at"),
        "leader_mentee_id": str(group.get("leader_mentee_id") or "").strip(),
        "approval_status": status,
        "submitted_by_admin_id": group.get("submitted_by_admin_id", ""),
        "submitted_at": group.get("submitted_at"),
        "approved_at": group.get("approved_at"),
        "approved_by_admin_id": group.get("approved_by_admin_id", ""),
        "finalize_reminder_dismissed_at": group.get("finalize_reminder_dismissed_at"),
    }


def _cleanup_empty_auto_solo_groups(activity: dict) -> None:
    activity["groups"] = [
        group
        for group in activity.get("groups", [])
        if not _is_auto_solo_group(group) or group.get("mentee_ids")
    ]


def _promote_mentee_into_group(
    activity: dict,
    mentee_id: str,
    target_group: dict,
    mentee: dict | None = None,
) -> bool:
    """Convert an individual (auto-solo) registration into group participation."""
    if _is_auto_solo_group(target_group):
        return False
    state = _get_mentee_state(activity, mentee_id)
    if not state:
        return False
    source_group = _find_mentee_group(activity, mentee_id)
    was_individual = _is_individual_participant(activity, state) or _is_auto_solo_group(source_group)
    if not was_individual:
        return False

    changed = False
    if state.get("participation_choice") != "group":
        state["participation_choice"] = "group"
        changed = True
    if (state.get("group_response_status") or "").strip().lower() in {"confirmed", "rejected"}:
        state["group_response_status"] = None
        state["group_response_note"] = ""
        state["group_response_at"] = None
        changed = True

    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    if keeptrack.get("active") or keeptrack.get("hdnk_entry_id"):
        if not mentee and ObjectId.is_valid(mentee_id):
            mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
        if mentee:
            _remove_keeptrack_hdnk_entry(mentee, state)
        else:
            _clear_keeptrack_on_reject(state)
        changed = True
    return changed


def add_mentee_to_group(activity: dict, group_id: str, mentee_id: str, admin: dict) -> tuple[dict, bool]:
    group = _find_group(activity, group_id)
    if not group:
        raise ValueError("Nhóm không tồn tại")
    source_group = _find_mentee_group(activity, mentee_id)
    if source_group and source_group.get("group_id") != group_id:
        source_group["mentee_ids"] = [
            str(item)
            for item in (source_group.get("mentee_ids") or [])
            if str(item) != mentee_id
        ]
    mentee_ids = [str(item) for item in (group.get("mentee_ids") or [])]
    if mentee_id not in mentee_ids:
        mentee_ids.append(mentee_id)
    merged, requires_l1 = upsert_activity_group(
        activity,
        {"group_id": group_id, "group_name": group.get("group_name", ""), "mentee_ids": mentee_ids},
        admin,
    )
    if not _is_auto_solo_group(merged):
        _promote_mentee_into_group(activity, mentee_id, merged)
    _cleanup_empty_auto_solo_groups(activity)
    return merged, requires_l1


def remove_mentee_from_group(
    activity: dict, group_id: str, mentee_id: str, admin: dict
) -> tuple[dict, bool]:
    group = _find_group(activity, group_id)
    if not group:
        raise ValueError("Nhóm không tồn tại")
    mentee_ids = [str(item) for item in (group.get("mentee_ids") or []) if str(item) != mentee_id]
    return upsert_activity_group(
        activity,
        {"group_id": group_id, "group_name": group.get("group_name", ""), "mentee_ids": mentee_ids},
        admin,
    )


def move_mentee_to_group(
    activity: dict, mentee_id: str, target_group_id: str, admin: dict
) -> tuple[dict, bool]:
    target_group = _find_group(activity, target_group_id)
    if not target_group:
        raise ValueError("Nhóm đích không tồn tại")
    if _is_auto_solo_group(target_group):
        raise ValueError("Không thể chuyển mentee vào nhóm cá nhân tự động.")
    source_group = _find_mentee_group(activity, mentee_id)
    requires_l1 = admin_requires_l1_approval(admin)
    now = datetime.now(timezone.utc)

    if not requires_l1:
        if source_group and source_group.get("group_id") != target_group_id:
            source_group["mentee_ids"] = [
                str(item)
                for item in (source_group.get("mentee_ids") or [])
                if str(item) != mentee_id
            ]
        target_ids = [str(item) for item in (target_group.get("mentee_ids") or [])]
        if mentee_id not in target_ids:
            target_ids.append(mentee_id)
        target_group["mentee_ids"] = target_ids
        _promote_mentee_into_group(activity, mentee_id, target_group)
        _cleanup_empty_auto_solo_groups(activity)
        return target_group, False

    target_ids = [str(item) for item in (target_group.get("mentee_ids") or [])]
    if mentee_id not in target_ids:
        target_ids.append(mentee_id)
    pending_group = _group_payload(
        {**target_group, "mentee_ids": target_ids},
        approval_status=PROFILE_ACTIVITY_APPROVAL_PENDING,
    )
    pending_group["submitted_by_admin_id"] = str(admin["_id"])
    pending_group["submitted_at"] = now
    pending_group["notification_sent_at"] = None
    pending_group["approved_at"] = None
    pending_group["approved_by_admin_id"] = ""
    pending_group["move_from_group_id"] = (source_group or {}).get("group_id", "")

    groups = activity.get("groups") or []
    for idx, group in enumerate(groups):
        if group.get("group_id") == target_group_id:
            groups[idx] = pending_group
            break
    activity["groups"] = groups
    return pending_group, True


def promote_individual_to_group_participation(
    activity: dict, mentee_id: str, admin: dict
) -> tuple[dict, bool]:
    """Switch an individual mentee to group participation and enable chốt nhóm."""
    state = _get_mentee_state(activity, mentee_id)
    if not state or not state.get("registered_at"):
        raise ValueError("Mentee chưa báo danh hoạt động này.")
    if not _is_individual_participant(activity, state):
        raise ValueError("Mentee không đăng ký hình thức cá nhân.")

    group = _find_mentee_group(activity, mentee_id)
    if not group:
        raise ValueError("Mentee chưa được phân vào nhóm.")

    requires_l1 = admin_requires_l1_approval(admin)
    now = datetime.now(timezone.utc)
    converting_auto_solo = _is_auto_solo_group(group)

    if requires_l1 and converting_auto_solo:
        pending_group = _group_payload(
            {**group, "is_auto_solo": False},
            approval_status=PROFILE_ACTIVITY_APPROVAL_PENDING,
        )
        pending_group["submitted_by_admin_id"] = str(admin["_id"])
        pending_group["submitted_at"] = now
        pending_group["notification_sent_at"] = None
        pending_group["approved_at"] = None
        pending_group["approved_by_admin_id"] = ""
        groups = activity.get("groups") or []
        for idx, row in enumerate(groups):
            if row.get("group_id") == group.get("group_id"):
                groups[idx] = pending_group
                break
        activity["groups"] = groups
        return pending_group, True

    if converting_auto_solo:
        group["is_auto_solo"] = False

    mentee = None
    if ObjectId.is_valid(mentee_id):
        mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    _promote_mentee_into_group(activity, mentee_id, group, mentee=mentee)
    _cleanup_empty_auto_solo_groups(activity)
    return group, False


def upsert_activity_group(activity: dict, payload: dict, admin: dict) -> tuple[dict, bool]:
    groups = activity.get("groups") or []
    target_id = (payload.get("group_id") or "").strip()
    requires_l1 = admin_requires_l1_approval(admin)
    now = datetime.now(timezone.utc)
    approval_status = (
        PROFILE_ACTIVITY_APPROVAL_PENDING if requires_l1 else PROFILE_ACTIVITY_APPROVAL_APPROVED
    )
    normalized = _group_payload(payload, approval_status=approval_status)
    if requires_l1:
        normalized["submitted_by_admin_id"] = str(admin["_id"])
        normalized["submitted_at"] = now
        normalized["notification_sent_at"] = None
        normalized["approved_at"] = None
        normalized["approved_by_admin_id"] = ""
    elif not target_id:
        normalized["approved_at"] = now
        normalized["approved_by_admin_id"] = str(admin["_id"])
    if target_id:
        for idx, group in enumerate(groups):
            if group.get("group_id") == target_id:
                merged = {**group, **normalized, "group_id": target_id}
                if requires_l1:
                    merged["notification_sent_at"] = None
                elif group_is_approved(group):
                    merged["approval_status"] = PROFILE_ACTIVITY_APPROVAL_APPROVED
                    merged.setdefault("approved_at", group.get("approved_at") or now)
                    merged.setdefault("approved_by_admin_id", group.get("approved_by_admin_id") or str(admin["_id"]))
                groups[idx] = merged
                activity["groups"] = groups
                return merged, requires_l1
    groups.append(normalized)
    activity["groups"] = groups
    return normalized, requires_l1


def _find_group(activity: dict, group_id: str) -> dict | None:
    return next((row for row in activity.get("groups", []) if row.get("group_id") == group_id), None)


PARTICIPANT_LIMIT_AUTO_REJECT_REASON = "Đã đủ số lượng tham gia"


def count_approved_participants(activity: dict) -> int:
    """Count distinct mentees whose participation has been approved by the mentor.

    Individual participants are approved automatically at registration (see
    ``register_for_activity``) unless later rejected. Group participants are
    counted once their group has been approved by the mentor (``approve_pending_group``
    or an L1-mentor's own instantly-approved group edit) — this intentionally does
    NOT require the mentee to have since personally confirmed via
    ``update_group_response``, since "duyệt" here refers to the mentor's approval
    action, not the mentee's own follow-up confirmation. Counts by mentee (person),
    not by group.
    """
    approved_mentee_ids: set[str] = set()
    for state in activity.get("mentee_states") or []:
        mentee_id = str(state.get("mentee_id") or "")
        if not mentee_id or not state.get("registered_at"):
            continue
        if (state.get("group_response_status") or "").strip().lower() == "rejected":
            continue
        pending_reject = state.get("mentor_reject_pending") or {}
        if pending_reject.get("approval_status") == PROFILE_ACTIVITY_APPROVAL_PENDING:
            continue
        if _is_individual_participant(activity, state):
            approved_mentee_ids.add(mentee_id)
        elif _is_group_participant(activity, state):
            if _find_mentee_display_group(activity, mentee_id, state):
                approved_mentee_ids.add(mentee_id)
    return len(approved_mentee_ids)


def enforce_participant_capacity(activity: dict) -> dict:
    """If ``activity`` has hit its ``participant_limit``, auto-reject everyone still
    pending (not yet approved, not already rejected) for it.

    "Pending" here covers: (1) groups not yet approved by the mentor (rejected via
    the existing ``reject_pending_group``), and (2) registered "group"-choice
    mentees not yet placed into any approved group (rejected via the same
    ``_apply_mentor_reject`` path a manual mentor rejection uses). Mentees already
    approved/confirmed by the time the limit is reached are never retroactively
    un-approved — call this right after an approval action so it only ever rejects
    people who were still waiting at that moment.

    Known edge cases intentionally NOT handled here (documented, not silently
    swallowed): new individual registrations are capped directly in
    ``register_for_activity`` instead (individuals are confirmed immediately at
    registration, so there's no separate pending state to intercept once already
    registered); and moving/removing mentees between existing groups
    (``move_mentee_to_group`` / ``remove_mentee_from_group``) does not re-run this
    check, since those actions don't approve anyone new.
    """
    limit = _normalize_participant_limit(activity.get("participant_limit"))
    if limit <= 0 or count_approved_participants(activity) < limit:
        return activity

    updated = activity
    for group in list(updated.get("groups") or []):
        if _is_auto_solo_group(group) or group_is_approved(group):
            continue
        updated = reject_pending_group(updated, group.get("group_id"), reason=PARTICIPANT_LIMIT_AUTO_REJECT_REASON)

    for state in list(updated.get("mentee_states") or []):
        mentee_id = str(state.get("mentee_id") or "")
        if not mentee_id or not state.get("registered_at"):
            continue
        if not ObjectId.is_valid(mentee_id):
            continue
        response = (state.get("group_response_status") or "").strip().lower()
        if response == "rejected":
            continue
        if _is_individual_participant(updated, state):
            continue
        if not _is_group_participant(updated, state):
            continue
        if _find_mentee_display_group(updated, mentee_id, state):
            continue
        mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
        if not mentee:
            continue
        _apply_mentor_reject(updated, mentee, PARTICIPANT_LIMIT_AUTO_REJECT_REASON)
        now = datetime.now(timezone.utc)
        profile_activities.update_one(
            {"_id": updated["_id"]},
            {"$set": {"mentee_states": updated.get("mentee_states", []), "updated_at": now}},
        )
        updated = profile_activities.find_one({"_id": updated["_id"]}) or updated

    return updated


def approve_pending_group(activity: dict, group_id: str, admin: dict) -> dict:
    group = _find_group(activity, group_id)
    if not group:
        return activity
    now = datetime.now(timezone.utc)
    move_from_group_id = (group.pop("move_from_group_id", None) or "").strip()
    if move_from_group_id and move_from_group_id != group_id:
        source_group = _find_group(activity, move_from_group_id)
        if source_group:
            new_member_ids = [str(item) for item in (group.get("mentee_ids") or [])]
            source_group["mentee_ids"] = [
                str(item)
                for item in (source_group.get("mentee_ids") or [])
                if str(item) not in new_member_ids
            ]
    group["approval_status"] = PROFILE_ACTIVITY_APPROVAL_APPROVED
    group["approved_at"] = now
    group["approved_by_admin_id"] = str(admin["_id"])
    for mentee_id in (group.get("mentee_ids") or []):
        _promote_mentee_into_group(activity, str(mentee_id), group)
    _cleanup_empty_auto_solo_groups(activity)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "groups": activity.get("groups", []),
                "mentee_states": activity.get("mentee_states", []),
                "updated_at": now,
            }
        },
    )
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    approved_group = _find_group(refreshed, group_id)
    if approved_group and not approved_group.get("notification_sent_at"):
        notify_group_assignment(refreshed, approved_group)
        refreshed = profile_activities.find_one({"_id": activity["_id"]}) or refreshed
    refreshed = enforce_participant_capacity(refreshed)
    return refreshed


def reject_pending_group(activity: dict, group_id: str, reason: str = "") -> dict:
    group = _find_group(activity, group_id)
    groups = [row for row in activity.get("groups", []) if row.get("group_id") != group_id]
    activity["groups"] = groups
    now = datetime.now(timezone.utc)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": groups, "updated_at": now}},
    )
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    reason = (reason or "").strip()
    if reason and group:
        member_ids = [ObjectId(item) for item in (group.get("mentee_ids") or []) if ObjectId.is_valid(item)]
        for mentee in users.find({"_id": {"$in": member_ids}, "role": {"$ne": ROLE_PARENT}}):
            notify_mentee_mentor_activity(
                mentee,
                action="profile_activity_rejected",
                title="Mentor từ chối phân nhóm",
                description=(
                    f"Nhóm của bạn cho hoạt động '{activity.get('activity_name')}' đã bị từ chối. "
                    f"Lý do: {reason}"
                ),
                mentor_name=activity.get("mentor_name", ""),
            )
    return refreshed


class ProfileActivityGroupDeleteError(ValueError):
    pass


def delete_activity_group(activity: dict, group_id: str, admin: dict) -> dict:
    group = _find_group(activity, group_id)
    if not group:
        raise ProfileActivityGroupDeleteError("Nhóm không tồn tại.")
    if _is_auto_solo_group(group):
        raise ProfileActivityGroupDeleteError("Không thể xóa nhóm cá nhân tự động.")

    mentee_ids = [str(item) for item in (group.get("mentee_ids") or []) if str(item)]
    if mentee_ids and admin_requires_l1_approval(admin):
        raise ProfileActivityGroupDeleteError(
            "Nhóm còn thành viên — vui lòng xóa hết thành viên trước hoặc liên hệ mentor cấp 1."
        )

    now = datetime.now(timezone.utc)
    activity["groups"] = [
        row for row in activity.get("groups", []) if row.get("group_id") != group_id
    ]

    for mentee_id in mentee_ids:
        state = _get_mentee_state(activity, mentee_id)
        if not state:
            continue
        state["group_response_status"] = None
        state["group_response_note"] = ""
        state["group_response_at"] = None
        if _is_group_participant(activity, state):
            keeptrack = _normalize_keeptrack(state.get("keeptrack"))
            if keeptrack.get("active"):
                _clear_keeptrack_on_reject(state)

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "groups": activity.get("groups", []),
                "mentee_states": activity.get("mentee_states", []),
                "updated_at": now,
            }
        },
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


class ProfileActivityDeleteError(ValueError):
    pass


def delete_activity(activity_id: str, admin: dict) -> tuple[bool, str]:
    """Permanently delete a whole profile activity (HDNK) — not just one of its groups.

    Unlike ``delete_activity_group`` (which only removes a group within an activity),
    this removes the entire ``profile_activities`` document plus everything denormalized
    from it onto mentee ``users`` documents and the shared ``mentor_inbox`` collection,
    so no orphaned references are left behind:

    - Active "Keep track" (HDNK/NCKH) entries the activity created on mentee user docs
      (``users.hdnk_nckh_entries``), matched via each mentee_state's
      ``keeptrack.hdnk_entry_id`` — the only structured link between an activity and a
      mentee's keeptrack panel.
    - ``mentor_inbox`` tasks about this activity. These tasks don't store a structured
      activity_id, so cleanup is best-effort: scoped to participants of this activity
      (mentee_states), to ``profile_activity*`` actions, and to tasks whose title or
      description literally mentions this activity's name.

    Permission convention mirrors ``delete_activity_group``: deleting an activity that
    already has real mentee registrations is restricted to L1 mentors (or super admins);
    an empty/placeholder activity with no registrations yet may be deleted by any
    approved admin in the same mentor scope.
    """
    try:
        oid = ObjectId(activity_id)
    except (InvalidId, TypeError):
        return False, "Hoạt động không tồn tại."

    activity = profile_activities.find_one({"_id": oid})
    if not activity:
        return False, "Hoạt động không tồn tại."

    mentee_states = activity.get("mentee_states") or []
    has_registrations = any(state.get("registered_at") for state in mentee_states)
    if has_registrations and admin_requires_l1_approval(admin):
        return False, "Hoạt động đã có mentee báo danh — vui lòng liên hệ mentor cấp 1 để xóa."

    activity_name = (activity.get("activity_name") or "").strip()
    mentee_ids: list[str] = []
    for state in mentee_states:
        mentee_id = str(state.get("mentee_id") or "")
        if not mentee_id or not ObjectId.is_valid(mentee_id):
            continue
        mentee_ids.append(mentee_id)

        entry_id = (state.get("keeptrack") or {}).get("hdnk_entry_id")
        if entry_id:
            mentee = users.find_one({"_id": ObjectId(mentee_id)})
            if mentee:
                _restore_mentee_hdnk_entry(mentee, entry_id, None)

    removed_inbox_count = 0
    mentee_ids = sorted(set(mentee_ids))
    if activity_name and mentee_ids:
        result = mentor_inbox.delete_many(
            {
                "mentee_id": {"$in": mentee_ids},
                "action": {"$regex": "^profile_activity"},
                "$or": [
                    {"description": {"$regex": re.escape(activity_name)}},
                    {"title": {"$regex": re.escape(activity_name)}},
                ],
            }
        )
        removed_inbox_count = result.deleted_count

    profile_activities.delete_one({"_id": oid})
    return True, f"Đã xóa hoạt động và {removed_inbox_count} thông báo liên quan trong inbox mentor."


def _apply_mentor_reject(activity: dict, mentee: dict, note: str = "") -> None:
    state = _get_or_create_state(activity, str(mentee["_id"]))
    if _is_individual_participant(activity, state):
        _remove_keeptrack_hdnk_entry(mentee, state)
    else:
        _clear_keeptrack_on_reject(state)
    state.pop("keeptrack_abandon_pending", None)
    state.pop("keeptrack_abandon_last_rejection", None)
    state["group_response_status"] = "rejected"
    state["group_response_note"] = (note or "").strip()
    state["group_response_at"] = datetime.now(timezone.utc)
    state.pop("mentor_reject_pending", None)
    notify_mentee_mentor_activity(
        mentee,
        action="profile_activity_rejected",
        title="Mentor từ chối báo danh",
        description=(
            f"Mentor đã từ chối báo danh của bạn cho hoạt động "
            f"'{activity.get('activity_name')}'."
            + (f" Ghi chú: {note.strip()}" if note.strip() else "")
        ),
        mentor_name=activity.get("mentor_name", ""),
    )


def submit_mentor_reject_registration(
    activity: dict, mentee: dict, admin: dict, note: str = ""
) -> tuple[dict, bool]:
    mentee_id = str(mentee["_id"])
    requires_l1 = admin_requires_l1_approval(admin)
    now = datetime.now(timezone.utc)
    if requires_l1:
        state = _get_or_create_state(activity, mentee_id)
        state["mentor_reject_pending"] = {
            "note": (note or "").strip(),
            "approval_status": PROFILE_ACTIVITY_APPROVAL_PENDING,
            "submitted_by_admin_id": str(admin["_id"]),
            "submitted_at": now,
        }
        profile_activities.update_one(
            {"_id": activity["_id"]},
            {
                "$set": {
                    "mentee_states": activity.get("mentee_states", []),
                    "updated_at": now,
                }
            },
        )
        refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
        return refreshed, True
    _apply_mentor_reject(activity, mentee, note)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "mentee_states": activity.get("mentee_states", []),
                "updated_at": now,
            }
        },
    )
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    return refreshed, False


def approve_pending_mentor_reject(activity: dict, mentee_id: str, admin: dict) -> dict:
    mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    if not mentee:
        return activity
    state = _get_mentee_state(activity, mentee_id) or {}
    pending = state.get("mentor_reject_pending") or {}
    note = pending.get("note", "")
    _apply_mentor_reject(activity, mentee, note)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "mentee_states": activity.get("mentee_states", []),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def reject_pending_mentor_reject(activity: dict, mentee_id: str) -> dict:
    state = _get_mentee_state(activity, mentee_id)
    if state:
        state.pop("mentor_reject_pending", None)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "mentee_states": activity.get("mentee_states", []),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    maybe_start_individual_keeptrack(refreshed, mentee_id)
    return profile_activities.find_one({"_id": activity["_id"]}) or refreshed


def admin_can_review_profile_activity(admin: dict) -> bool:
    from services.admins import is_super_admin
    from services.apply_progress import admin_is_level1_mentor

    return bool(is_super_admin(admin) or admin_is_level1_mentor(admin))


def mentor_profile_activities_query(admin: dict) -> dict:
    mentor_name = (admin.get("mentor_name") or "").strip()
    if mentor_name:
        return {"mentor_name": mentor_name}
    return {}


def count_pending_actions_for_activity(activity: dict, admin: dict) -> int:
    count = 0
    if admin_can_review_profile_activity(admin):
        if _normalize_approval_status(activity.get("approval_status")) == PROFILE_ACTIVITY_APPROVAL_PENDING:
            count += 1
        count += len(list_pending_l1_group_actions(activity))

    for state in activity.get("mentee_states", []):
        if not state.get("registered_at"):
            continue
        mentee_id = state.get("mentee_id", "")
        if _mentee_awaiting_group_assignment(activity, mentee_id, state):
            count += 1
        pending_keeptrack = state.get("keeptrack_pending_review") or {}
        if pending_keeptrack.get("status") == "pending":
            count += 1
        abandon_pending = state.get("keeptrack_abandon_pending") or {}
        if abandon_pending.get("status") == "pending":
            count += 1

    return count


def count_total_pending_profile_actions(admin: dict) -> int:
    total = 0
    for doc in profile_activities.find(mentor_profile_activities_query(admin)):
        total += count_pending_actions_for_activity(doc, admin)
    return total


def list_pending_l1_group_actions(activity: dict) -> list[dict]:
    pending: list[dict] = []
    for group in activity.get("groups", []):
        if _normalize_approval_status(group.get("approval_status")) != PROFILE_ACTIVITY_APPROVAL_PENDING:
            continue
        pending.append(
            {
                "action_type": "assign_group",
                "group_id": group.get("group_id", ""),
                "group_name": group.get("group_name", ""),
                "mentee_ids": group.get("mentee_ids", []),
                "submitted_at": group.get("submitted_at").isoformat()
                if group.get("submitted_at")
                else "",
            }
        )
    for state in activity.get("mentee_states", []):
        pending_reject = state.get("mentor_reject_pending") or {}
        if pending_reject.get("approval_status") != PROFILE_ACTIVITY_APPROVAL_PENDING:
            continue
        mentee_id = state.get("mentee_id", "")
        mentee = users.find_one({"_id": ObjectId(mentee_id)}) if ObjectId.is_valid(mentee_id) else None
        pending.append(
            {
                "action_type": "reject_mentee",
                "mentee_id": mentee_id,
                "mentee_name": (
                    (mentee.get("full_name") or mentee.get("username") or mentee.get("email", ""))
                    if mentee
                    else mentee_id
                ),
                "note": pending_reject.get("note", ""),
                "submitted_at": pending_reject.get("submitted_at").isoformat()
                if pending_reject.get("submitted_at")
                else "",
            }
        )
    return pending


def _profile_activity_label(activity: dict) -> str:
    return (activity.get("activity_name") or activity.get("description") or "Hoạt động hồ sơ").strip()


def _mentee_display_name(mentee_id: str) -> str:
    if not ObjectId.is_valid(mentee_id):
        return mentee_id
    mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
    if not mentee:
        return mentee_id
    return (
        mentee.get("full_name") or mentee.get("username") or mentee.get("email") or mentee_id
    ).strip()


def _parse_profile_activity_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def list_profile_activity_synthetic_inbox_items(admin: dict) -> list[dict]:
    from inbox_tasks import build_synthetic_inbox_item

    mentor_name = (admin.get("mentor_name") or "").strip()
    items: list[dict] = []
    nav_path = "/profile-activities"

    for activity in profile_activities.find(mentor_profile_activities_query(admin)).sort("updated_at", -1):
        activity_id = str(activity["_id"])
        activity_label = _profile_activity_label(activity)

        if admin_can_review_profile_activity(admin):
            if _normalize_approval_status(activity.get("approval_status")) == PROFILE_ACTIVITY_APPROVAL_PENDING:
                created_at = _coerce_utc_datetime(activity.get("updated_at")) or _coerce_utc_datetime(
                    activity.get("created_at")
                )
                items.append(
                    build_synthetic_inbox_item(
                        item_id=f"synthetic:pa-approval:{activity_id}",
                        mentor_name=mentor_name,
                        action="profile_activity_pending_approval",
                        title=activity_label,
                        description=f"Hoạt động chờ duyệt L1: {activity_label}",
                        mentee_name="Hệ thống",
                        created_at=created_at,
                        nav_path=nav_path,
                    )
                )

            for pending in list_pending_l1_group_actions(activity):
                if pending.get("action_type") == "assign_group":
                    group_name = (pending.get("group_name") or "").strip() or "nhóm"
                    created_at = _parse_profile_activity_timestamp(pending.get("submitted_at"))
                    items.append(
                        build_synthetic_inbox_item(
                            item_id=f"synthetic:pa-group:{activity_id}:{pending.get('group_id', '')}",
                            mentor_name=mentor_name,
                            action="profile_activity_pending_group",
                            title=activity_label,
                            description=f"Chờ duyệt phân nhóm {group_name} · {activity_label}",
                            mentee_name="Hệ thống",
                            created_at=created_at,
                            nav_path=nav_path,
                        )
                    )
                elif pending.get("action_type") == "reject_mentee":
                    mentee_name = (pending.get("mentee_name") or "").strip() or "Mentee"
                    created_at = _parse_profile_activity_timestamp(pending.get("submitted_at"))
                    items.append(
                        build_synthetic_inbox_item(
                            item_id=f"synthetic:pa-reject:{activity_id}:{pending.get('mentee_id', '')}",
                            mentor_name=mentor_name,
                            action="profile_activity_pending_reject",
                            title=activity_label,
                            description=f"Chờ duyệt từ chối báo danh · {activity_label}",
                            mentee_name=mentee_name,
                            mentee_id=pending.get("mentee_id", ""),
                            created_at=created_at,
                            nav_path=nav_path,
                        )
                    )

        for group in activity.get("groups", []) or []:
            if not group_needs_finalize_reminder(group):
                continue
            group_name = (group.get("group_name") or "").strip() or "nhóm"
            member_count = len(group.get("mentee_ids") or [])
            created_at = (
                _coerce_utc_datetime(group.get("finalize_reminder_dismissed_at"))
                or _coerce_utc_datetime(group.get("approved_at"))
                or _coerce_utc_datetime(activity.get("updated_at"))
            )
            items.append(
                build_synthetic_inbox_item(
                    item_id=f"synthetic:pa-finalize:{activity_id}:{group.get('group_id', '')}",
                    mentor_name=mentor_name,
                    action="profile_activity_finalize_group",
                    title=activity_label,
                    description=f"Nhóm {group_name} ({member_count} thành viên) cần chốt nhóm · {activity_label}",
                    mentee_name="Hệ thống",
                    created_at=created_at,
                    nav_path=nav_path,
                )
            )

        for state in activity.get("mentee_states", []) or []:
            if not state.get("registered_at"):
                continue
            mentee_id = state.get("mentee_id", "")
            if not _mentee_awaiting_group_assignment(activity, mentee_id, state):
                continue
            mentee_name = _mentee_display_name(mentee_id)
            created_at = _coerce_utc_datetime(state.get("registered_at"))
            items.append(
                build_synthetic_inbox_item(
                    item_id=f"synthetic:pa-assign:{activity_id}:{mentee_id}",
                    mentor_name=mentor_name,
                    action="profile_activity_assign_group",
                    title=activity_label,
                    description=f"Mentee cần phân nhóm · {activity_label}",
                    mentee_name=mentee_name,
                    mentee_id=mentee_id,
                    created_at=created_at,
                    nav_path=nav_path,
                )
            )

    return items



def _build_finalize_group_notification(group: dict) -> tuple[str, str]:
    group_name = (group.get("group_name") or "").strip() or "nhóm"
    member_count = len(group.get("mentee_ids") or [])
    title = f"Mentor đã phân bạn vào nhóm {group_name}"
    description = (
        f"Mentor đã phân bạn vào nhóm {group_name} bao gồm {member_count} thành viên (Xem)"
    )
    return title, description


def notify_group_assignment(activity: dict, group: dict) -> dict:
    """Mark group as assigned internally; mentee notification happens on chốt nhóm."""
    if not group_is_approved(group) or _is_auto_solo_group(group):
        return activity
    group["notification_sent_at"] = datetime.now(timezone.utc)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "groups": activity.get("groups", []),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return activity


class ProfileActivityGroupResponseError(ValueError):
    pass


def update_group_response(activity: dict, mentee: dict, status: str, note: str = "") -> dict:
    response = (status or "").strip().lower()
    if response not in {"confirmed", "rejected"}:
        response = "pending"
    mentee_id = str(mentee["_id"])
    state = _get_or_create_state(activity, mentee_id)
    if not _mentee_requires_group_confirmation(activity, mentee_id, state) and response in {
        "confirmed",
        "rejected",
    }:
        raise ProfileActivityGroupResponseError("Bạn không cần xác nhận nhóm cho hình thức tham gia này.")
    state["group_response_status"] = response
    state["group_response_note"] = (note or "").strip()
    state["group_response_at"] = datetime.now(timezone.utc)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": datetime.now(timezone.utc)}},
    )
    refreshed = profile_activities.find_one({"_id": activity["_id"]}) or activity
    if response == "confirmed":
        maybe_start_group_keeptrack(refreshed, mentee_id)
        refreshed = profile_activities.find_one({"_id": activity["_id"]}) or refreshed
    return refreshed


def finalize_group_and_sync_hdnk(activity: dict, group_id: str, admin_name: str = "") -> dict:
    target_group = _find_group(activity, group_id)
    if not target_group or not group_is_approved(target_group):
        return activity
    if _is_auto_solo_group(target_group):
        raise ProfileActivityKeeptrackError("Hình thức cá nhân không cần chốt nhóm.")

    now = datetime.now(timezone.utc)
    member_ids = [ObjectId(item) for item in target_group.get("mentee_ids", []) if ObjectId.is_valid(item)]
    notify_title, notify_description = _build_finalize_group_notification(target_group)
    for mentee in users.find({"_id": {"$in": member_ids}, "role": {"$ne": ROLE_PARENT}}):
        mentee_id = str(mentee["_id"])
        state = _get_or_create_state(activity, mentee_id)
        if state.get("participation_choice") != "individual" and _normalize_participation_mode(
            activity.get("participation_mode")
        ) != "individual":
            state["group_response_status"] = "pending"
            state["group_response_note"] = ""
            state["group_response_at"] = None
            notify_mentee_mentor_activity(
                mentee,
                action="profile_activity_finalized",
                title=notify_title,
                description=notify_description,
                mentor_name=activity.get("mentor_name", ""),
            )

    target_group["finalized_at"] = now
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "groups": activity.get("groups", []),
                "mentee_states": activity.get("mentee_states", []),
                "updated_at": now,
            }
        },
    )
    return activity


class ProfileActivityGroupLeaderError(ValueError):
    pass


def set_group_leader(activity: dict, group_id: str, mentee_id: str) -> dict:
    group = _find_group(activity, group_id)
    if not group:
        raise ProfileActivityGroupLeaderError("Nhóm không tồn tại.")
    if not group_is_approved(group):
        raise ProfileActivityGroupLeaderError("Nhóm đang chờ mentor cấp 1 duyệt.")
    if _is_auto_solo_group(group):
        raise ProfileActivityGroupLeaderError("Hình thức cá nhân không cần chọn nhóm trưởng.")
    if not group.get("finalized_at"):
        raise ProfileActivityGroupLeaderError("Cần chốt nhóm trước khi chọn nhóm trưởng.")

    mentee_id = str(mentee_id or "").strip()
    member_ids = [str(item) for item in (group.get("mentee_ids") or [])]
    if mentee_id not in member_ids:
        raise ProfileActivityGroupLeaderError("Mentee không thuộc nhóm này.")

    now = datetime.now(timezone.utc)
    group["leader_mentee_id"] = mentee_id
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": activity.get("groups", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity


def _has_progress_keeptrack(state: dict) -> bool:
    raw = state.get("keeptrack")
    if not raw:
        return False
    keeptrack = _normalize_keeptrack(raw)
    if keeptrack.get("hdnk_entry_id"):
        return True
    return keeptrack.get("progress_status") in {
        KEEPTRACK_PROGRESS_IN_PROGRESS,
        KEEPTRACK_PROGRESS_COMPLETED,
    }


def _keeptrack_status_fields(state: dict) -> tuple[str, str, str]:
    keeptrack = _normalize_keeptrack(state.get("keeptrack"))
    status = keeptrack.get("progress_status") or KEEPTRACK_PROGRESS_IN_PROGRESS
    label = KEEPTRACK_UI_LABELS.get(status, "Đang tiến hành")
    return status, label, keeptrack.get("start_date") or ""


def _aggregate_group_keeptrack_status(member_states: list[dict]) -> tuple[str, str, str]:
    dates: list[str] = []
    statuses: list[str] = []
    for state in member_states:
        if not _has_progress_keeptrack(state):
            continue
        status, _label, start_date = _keeptrack_status_fields(state)
        statuses.append(status)
        if start_date:
            dates.append(start_date)
    if not statuses:
        return "", "", ""
    agg_status = (
        KEEPTRACK_PROGRESS_IN_PROGRESS
        if any(item == KEEPTRACK_PROGRESS_IN_PROGRESS for item in statuses)
        else KEEPTRACK_PROGRESS_COMPLETED
    )
    return agg_status, KEEPTRACK_UI_LABELS.get(agg_status, ""), min(dates) if dates else ""


def _mentee_display_name(mentee: dict) -> str:
    return mentee.get("full_name") or mentee.get("username") or mentee.get("email", "")


def _build_progress_tracking_members(group: dict) -> list[dict]:
    leader_id = str(group.get("leader_mentee_id") or "").strip()
    member_ids = [str(item) for item in (group.get("mentee_ids") or []) if str(item)]
    object_ids = [ObjectId(item) for item in member_ids if ObjectId.is_valid(item)]
    users_by_id = {
        str(user["_id"]): user
        for user in users.find({"_id": {"$in": object_ids}, "role": {"$ne": ROLE_PARENT}})
    }
    ordered_ids = member_ids[:]
    if leader_id and leader_id in ordered_ids:
        ordered_ids = [leader_id] + [item for item in ordered_ids if item != leader_id]
    members: list[dict] = []
    for member_id in ordered_ids:
        user = users_by_id.get(member_id)
        if not user:
            continue
        members.append(
            {
                "mentee_id": member_id,
                "name": _mentee_display_name(user),
                "is_leader": member_id == leader_id,
            }
        )
    return members


def _group_qualifies_for_progress_tracking(group: dict) -> bool:
    if not group_is_approved(group):
        return False
    if _is_auto_solo_group(group):
        return False
    return bool(group.get("mentee_ids"))


def list_progress_tracking_for_admin(admin: dict) -> list[dict]:
    activities_out: list[dict] = []
    for activity in profile_activities.find(mentor_profile_activities_query(admin)).sort("updated_at", -1):
        if not activity_visible_to_mentee(activity):
            continue

        states_by_id = {
            str(state.get("mentee_id", "")): state
            for state in activity.get("mentee_states", [])
            if state.get("mentee_id")
        }
        rows: list[dict] = []
        covered_mentee_ids: set[str] = set()

        for group in activity.get("groups", []):
            if not _group_qualifies_for_progress_tracking(group):
                continue
            member_ids = [str(item) for item in (group.get("mentee_ids") or []) if str(item)]
            tracked_states = [
                states_by_id[member_id]
                for member_id in member_ids
                if member_id in states_by_id and _has_progress_keeptrack(states_by_id[member_id])
            ]
            if not tracked_states:
                continue
            status, status_label, start_date = _aggregate_group_keeptrack_status(tracked_states)
            if not status:
                continue
            members = _build_progress_tracking_members(group)
            if not members:
                continue
            covered_mentee_ids.update(member_ids)
            rows.append(
                {
                    "row_id": f"group:{group.get('group_id')}",
                    "type": "group",
                    "group_id": group.get("group_id", ""),
                    "group_name": (group.get("group_name") or "").strip() or "Nhóm",
                    "members": members,
                    "start_date": start_date,
                    "status": status,
                    "status_label": status_label,
                    "mentee_ids": [member["mentee_id"] for member in members],
                    "finalized": bool(group.get("finalized_at")),
                }
            )

        for state in activity.get("mentee_states", []):
            if not state.get("registered_at"):
                continue
            mentee_id = str(state.get("mentee_id", ""))
            if mentee_id in covered_mentee_ids:
                continue
            if not _is_individual_participant(activity, state):
                continue
            if not _has_progress_keeptrack(state):
                continue
            if not ObjectId.is_valid(mentee_id):
                continue
            mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
            if not mentee:
                continue
            status, status_label, start_date = _keeptrack_status_fields(state)
            rows.append(
                {
                    "row_id": f"individual:{mentee_id}",
                    "type": "individual",
                    "group_id": "",
                    "group_name": "",
                    "members": [
                        {
                            "mentee_id": mentee_id,
                            "name": _mentee_display_name(mentee),
                            "is_leader": False,
                        }
                    ],
                    "start_date": start_date,
                    "status": status,
                    "status_label": status_label,
                    "mentee_ids": [mentee_id],
                    "finalized": True,
                }
            )

        if rows:
            activities_out.append(
                {
                    "activity_id": str(activity["_id"]),
                    "activity_name": compose_activity_name(activity),
                    "rows": rows,
                }
            )

    return activities_out


def remove_progress_tracking_row(
    activity: dict,
    *,
    row_type: str,
    group_id: str = "",
    mentee_id: str = "",
    admin: dict | None = None,
) -> dict:
    _ = admin  # reserved for future audit fields
    row_type = (row_type or "").strip().lower()
    now = datetime.now(timezone.utc)
    activity_name = compose_activity_name(activity)

    if row_type == "individual":
        if not mentee_id:
            raise ProfileActivityKeeptrackError("Thiếu mentee.")
        state = _get_mentee_state(activity, mentee_id)
        if not state or not _has_progress_keeptrack(state):
            raise ProfileActivityKeeptrackError("Không có tiến độ để xóa.")
        mentee = users.find_one({"_id": ObjectId(mentee_id), "role": {"$ne": ROLE_PARENT}})
        if not mentee:
            raise ProfileActivityKeeptrackError("Mentee không tồn tại.")
        _remove_keeptrack_hdnk_entry(mentee, state)
        notify_mentee_mentor_activity(
            mentee,
            action="profile_activity_keeptrack_removed",
            title="Mentor đã gỡ tiến độ hoạt động",
            description=(
                f"Mentor đã gỡ hoạt động '{activity_name}' khỏi bảng theo dõi tiến độ."
            ),
            mentor_name=activity.get("mentor_name", ""),
        )
    elif row_type == "group":
        group = _find_group(activity, group_id)
        if not group:
            raise ProfileActivityKeeptrackError("Nhóm không tồn tại.")
        removed_any = False
        group_name = (group.get("group_name") or "").strip() or "Nhóm"
        for member_id in [str(item) for item in (group.get("mentee_ids") or []) if str(item)]:
            state = _get_mentee_state(activity, member_id)
            if not state or not _has_progress_keeptrack(state):
                continue
            mentee = users.find_one({"_id": ObjectId(member_id), "role": {"$ne": ROLE_PARENT}})
            if not mentee:
                continue
            _remove_keeptrack_hdnk_entry(mentee, state)
            notify_mentee_mentor_activity(
                mentee,
                action="profile_activity_keeptrack_removed",
                title="Mentor đã gỡ tiến độ hoạt động",
                description=(
                    f"Mentor đã gỡ nhóm '{group_name}' khỏi bảng theo dõi tiến độ ({activity_name})."
                ),
                mentor_name=activity.get("mentor_name", ""),
            )
            removed_any = True
        if not removed_any:
            raise ProfileActivityKeeptrackError("Không có tiến độ để xóa.")
    else:
        raise ProfileActivityKeeptrackError("Loại dòng không hợp lệ.")

    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": now}},
    )
    return profile_activities.find_one({"_id": activity["_id"]}) or activity
