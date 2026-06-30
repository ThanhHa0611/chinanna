from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from config import ROLE_PARENT
from database import profile_activities, users
from services.apply_documents import mentor_apply_direction_label
from services.hdnk_nckh import get_hdnk_nckh_entries_raw, normalize_hdnk_nckh_entry
from services.notifications import notify_mentee_mentor_activity

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


def compose_activity_name(data: dict) -> str:
    activity_type = (data.get("activity_type") or "").strip() or "Khác"
    organizer = (data.get("organizer") or "").strip()
    content = (data.get("content") or "").strip()
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


def _normalize_importance(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_PROFILE_ACTIVITY_IMPORTANCE
    return max(1, min(5, value))


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


def resolve_initial_approval_status(admin: dict) -> str:
    from services.admins import is_super_admin
    from services.apply_progress import admin_is_level1_mentor

    if is_super_admin(admin) or admin_is_level1_mentor(admin):
        return PROFILE_ACTIVITY_APPROVAL_APPROVED
    return PROFILE_ACTIVITY_APPROVAL_PENDING


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
    }
    cleaned["activity_name"] = compose_activity_name(cleaned)
    return cleaned


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
        "group_response_status": "pending",
        "group_response_note": "",
        "group_response_at": None,
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


def format_activity_feed_line(activity: dict, mentee: dict | None = None) -> str:
    line = compose_activity_name(activity)
    stored = (activity.get("activity_name") or "").strip()
    if stored and line in {"Khác", "Hoạt động hồ sơ"} and len(stored) > len(line):
        line = stored
    if not line:
        line = "Hoạt động hồ sơ"
    link = (activity.get("link") or "").strip()
    if link:
        line = f"{line} {link}"
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


def serialize_profile_activity_for_feed(doc: dict, mentee: dict, *, include_hidden: bool = False) -> dict:
    mentee_id = str(mentee["_id"])
    state = _get_or_create_state(doc, mentee_id)
    if state.get("hidden") and not include_hidden:
        return {}
    registration_count = sum(1 for item in doc.get("mentee_states", []) if item.get("registered_at"))
    payload = {
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
        "read": bool(state.get("read_at")),
        "hidden": bool(state.get("hidden")),
        "registered": bool(state.get("registered_at")),
        "group_response_status": state.get("group_response_status", "pending"),
        "group_response_note": state.get("group_response_note", ""),
        "highlight_star": activity_matches_mentee_major(doc, mentee),
        "importance": _normalize_importance(doc.get("importance", DEFAULT_PROFILE_ACTIVITY_IMPORTANCE)),
        "registration_count": registration_count,
        "deadline_badge": get_deadline_badge(doc.get("deadline", "")),
    }
    payload["feed_line"] = format_activity_feed_line(payload, mentee)
    return payload


def serialize_admin_profile_activity(doc: dict) -> dict:
    mentee_states = doc.get("mentee_states") or []
    registrations = [item for item in mentee_states if item.get("registered_at")]
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
        "groups": doc.get("groups", []),
        "importance": _normalize_importance(doc.get("importance", DEFAULT_PROFILE_ACTIVITY_IMPORTANCE)),
        "approval_status": _normalize_approval_status(doc.get("approval_status")),
        "created_by_admin_id": doc.get("created_by_admin_id", ""),
        "approved_at": doc.get("approved_at").isoformat() if doc.get("approved_at") else "",
        "approved_by_admin_id": doc.get("approved_by_admin_id", ""),
        "rejected_at": doc.get("rejected_at").isoformat() if doc.get("rejected_at") else "",
        "rejected_by_admin_id": doc.get("rejected_by_admin_id", ""),
        "deadline_badge": get_deadline_badge(doc.get("deadline", "")),
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
    return profile_activities.find_one({"_id": result.inserted_id}) or doc


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
        payload = serialize_profile_activity_for_feed(doc, mentee)
        if payload:
            items.append(payload)
    return items


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


def register_for_activity(activity: dict, mentee: dict) -> dict:
    mentee_id = str(mentee["_id"])
    state = _get_or_create_state(activity, mentee_id)
    if not state.get("registered_at"):
        state["registered_at"] = datetime.now(timezone.utc)
        profile_activities.update_one(
            {"_id": activity["_id"]},
            {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": datetime.now(timezone.utc)}},
        )
    return activity


def _group_payload(group: dict) -> dict:
    return {
        "group_id": group.get("group_id") or str(uuid.uuid4()),
        "group_name": (group.get("group_name") or "").strip() or "Nhóm mới",
        "mentee_ids": [str(item) for item in (group.get("mentee_ids") or []) if str(item)],
        "notification_sent_at": group.get("notification_sent_at"),
        "finalized_at": group.get("finalized_at"),
    }


def _upsert_group(activity: dict, payload: dict) -> dict:
    groups = activity.get("groups") or []
    target_id = (payload.get("group_id") or "").strip()
    normalized = _group_payload(payload)
    if target_id:
        for idx, group in enumerate(groups):
            if group.get("group_id") == target_id:
                groups[idx] = {**group, **normalized, "group_id": target_id}
                activity["groups"] = groups
                return groups[idx]
    groups.append(normalized)
    activity["groups"] = groups
    return normalized


def _build_team_message(activity: dict, group: dict, member_profiles: list[dict]) -> str:
    teammates = ", ".join(
        f"{item.get('full_name') or item.get('username') or item.get('email')} ({item.get('zalo_phone') or 'chưa có Zalo'})"
        for item in member_profiles
    )
    return (
        f"Bạn đã được xếp nhóm '{group.get('group_name')}' cho hoạt động "
        f"'{activity.get('activity_name')}'. Thành viên: {teammates}."
    )


def notify_group_assignment(activity: dict, group: dict) -> dict:
    member_ids = [ObjectId(item) for item in group.get("mentee_ids", []) if ObjectId.is_valid(item)]
    members = list(users.find({"_id": {"$in": member_ids}, "role": {"$ne": ROLE_PARENT}}))
    message = _build_team_message(activity, group, members)
    for mentee in members:
        state = _get_or_create_state(activity, str(mentee["_id"]))
        state["group_response_status"] = "pending"
        state["group_response_note"] = ""
        state["group_response_at"] = None
        notify_mentee_mentor_activity(
            mentee,
            action="profile_activity_group",
            title="Bạn đã được xếp nhóm",
            description=message,
            mentor_name=activity.get("mentor_name", ""),
        )
    group["notification_sent_at"] = datetime.now(timezone.utc)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {
            "$set": {
                "groups": activity.get("groups", []),
                "mentee_states": activity.get("mentee_states", []),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return activity


def update_group_response(activity: dict, mentee: dict, status: str, note: str = "") -> dict:
    response = (status or "").strip().lower()
    if response not in {"confirmed", "rejected"}:
        response = "pending"
    state = _get_or_create_state(activity, str(mentee["_id"]))
    state["group_response_status"] = response
    state["group_response_note"] = (note or "").strip()
    state["group_response_at"] = datetime.now(timezone.utc)
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"mentee_states": activity.get("mentee_states", []), "updated_at": datetime.now(timezone.utc)}},
    )
    return activity


def finalize_group_and_sync_hdnk(activity: dict, group_id: str, admin_name: str = "") -> dict:
    target_group = None
    for group in activity.get("groups", []):
        if group.get("group_id") == group_id:
            target_group = group
            break
    if not target_group:
        return activity

    now = datetime.now(timezone.utc)
    member_ids = [ObjectId(item) for item in target_group.get("mentee_ids", []) if ObjectId.is_valid(item)]
    for mentee in users.find({"_id": {"$in": member_ids}, "role": {"$ne": ROLE_PARENT}}):
        entries = get_hdnk_nckh_entries_raw(mentee)
        new_entry = normalize_hdnk_nckh_entry(
            {
                "start_date": now.astimezone().strftime("%Y-%m-%d"),
                "category": activity.get("activity_name", ""),
                "participation_type": "nhóm Trơn Tru" if len(member_ids) > 1 else "cá nhân",
                "zalo_group_name": target_group.get("group_name", "") if len(member_ids) > 1 else "",
                "progress": "mới tạo nhóm",
                "has_award": False,
            },
        )
        entries.insert(0, new_entry)
        users.update_one(
            {"_id": mentee["_id"]},
            {
                "$set": {
                    "hdnk_nckh_entries": entries[:20],
                    "hdnk_nckh_l1_unread": True,
                    "hdnk_nckh_mentor_updated_at": now,
                }
            },
        )
        notify_mentee_mentor_activity(
            mentee,
            action="profile_activity_finalized",
            title="Nhóm hoạt động đã chốt",
            description=(
                f"Mentor {admin_name or activity.get('mentor_name') or ''} đã chốt nhóm "
                f"'{target_group.get('group_name')}' cho hoạt động '{activity.get('activity_name')}'."
            ).strip(),
            mentor_name=activity.get("mentor_name", ""),
        )

    target_group["finalized_at"] = now
    profile_activities.update_one(
        {"_id": activity["_id"]},
        {"$set": {"groups": activity.get("groups", []), "updated_at": now}},
    )
    return activity
