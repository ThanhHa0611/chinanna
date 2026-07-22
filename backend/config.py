
import os
import re
from pathlib import Path

def _parse_email_list(env_key: str, fallback: str) -> list[str]:
    raw = os.getenv(env_key, "").strip()
    if not raw:
        raw = os.getenv("SUPER_ADMIN_EMAIL", fallback).strip()
    return [email.strip().lower() for email in raw.split(",") if email.strip()]

BACKEND_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = BACKEND_DIR / "uploads"

# Lưu trữ file: để trống S3_BUCKET => dùng đĩa local (UPLOAD_ROOT).
# Đặt S3_BUCKET => dùng Amazon S3 (bền vững khi redeploy/nhiều instance).
S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
S3_PREFIX = os.getenv("S3_PREFIX", "uploads").strip().strip("/")
AWS_REGION = os.getenv("AWS_REGION", "").strip()

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "phong_van")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

ROLE_MENTEE = "mentee"
ROLE_PARENT = "parent"
ROLE_ADMIN = "admin"
PARENT_DEFAULT_PASSWORD = "DuHocTQ2027"
LOGIN_REQUEST_PENDING = "pending"
LOGIN_REQUEST_APPROVED = "approved"
LOGIN_REQUEST_REJECTED = "rejected"
LOCATION_REQUIRED_MESSAGE = (
    "Vì mục đích an toàn và đảm bảo quyền lợi cho mentee Du học Trung Quốc, "
    "bạn vui lòng đồng ý cấp quyền vị trí. Du học Trung Quốc chỉ sử dụng thông tin này nội bộ "
    "và không mang mục đích doanh nghiệp."
)
MAX_LOGIN_EVENTS = 100
FEEDBACK_STATUS_PENDING = "chờ xử lí"
FEEDBACK_STATUS_DONE = "đã xử lí"
FEEDBACK_MENTEE_RECEIVED = "Mentor đã nhận được tin nhắn của bạnn rùii"
APPLY_MISSING_REMINDER_MESSAGE = "Bạn cần làm các loại giấy tờ sau"
PROFILE_INFO_REMINDER_MESSAGE = "Vui lòng hoàn thiện thông tin cá nhân bạn nhé"
PROFILE_INFO_FIELD_LABELS = {
    "full_name": "Họ tên",
    "zalo_phone": "Số Zalo",
    "date_of_birth": "Ngày sinh",
    "scholarship_system": "App học bổng",
    "apply_degree_level": "Hệ apply",
    "parent_email": "Email phụ huynh",
    "apply_clone_email": "Email clone",
    "apply_clone_password": "Pass clone",
    "apply_clone_forward_installed": "Đã cài forward",
}
PROFILE_INFO_BOOLEAN_FIELDS = {"apply_clone_forward_installed"}
ADMIN_STATUS_PENDING = "pending"
ADMIN_STATUS_APPROVED = "approved"
ADMIN_STATUS_REJECTED = "rejected"


def _parse_email_list(env_key: str, fallback: str) -> list[str]:
    raw = os.getenv(env_key, "").strip()
    if not raw:
        raw = os.getenv("SUPER_ADMIN_EMAIL", fallback).strip()
    return [email.strip().lower() for email in raw.split(",") if email.strip()]


SUPER_ADMIN_EMAILS = _parse_email_list("SUPER_ADMIN_EMAILS", "cherrythanh06@gmail.com")
SUPER_ADMIN_EMAIL = SUPER_ADMIN_EMAILS[0] if SUPER_ADMIN_EMAILS else "cherrythanh06@gmail.com"
ADMIN_NOTIFY_EMAIL = os.getenv("ADMIN_NOTIFY_EMAIL", SUPER_ADMIN_EMAIL).strip().lower()
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://127.0.0.1:8000").strip().rstrip("/")
EMAIL_ACTION_TOKEN_DAYS = int(os.getenv("EMAIL_ACTION_TOKEN_DAYS", "7"))

VALID_APPLY_DOC_IDS = {
    "photo",
    "health",
    "passport",
    "criminal-record",
    "diploma",
    "transcript",
    "language",
    "work",
    "study-plan",
    "award",
    "research",
    "recommendation-1",
    "recommendation-2",
    "personal-declaration",
    "parents-id",
    "financial",
    "cv",
}
NO_FILE_UPLOAD_DOC_IDS = {"personal-declaration"}
MENTEE_UPLOAD_BLOCKED_DOC_IDS = frozenset({"study-plan", "cv"})
MENTOR_UPLOADABLE_DOC_IDS = frozenset(VALID_APPLY_DOC_IDS - NO_FILE_UPLOAD_DOC_IDS)
ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".doc", ".docx"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
DOC_MENTOR_STATUS_WAITING = "chờ phản hồi"
DOC_MENTOR_STATUS_APPROVED = "đã duyệt"
DOC_MENTOR_STATUS_REVISION = "cần chỉnh sửa"
APPLY_PROGRESS_ROW_COUNT = 8
APPLY_PROGRESS_ROW_DEFAULT = 8
APPLY_PROGRESS_ROW_MIN = 1
APPLY_PROGRESS_ROW_MAX = 20
APPLY_PROGRESS_FIELDS = (
    "school_name",
    "apply_major",
    "link",
    "scholarship_type",
    "allowance",
    "registration_fee",
    "progress",
    "note",
)
APPLY_PROGRESS_PENDING_WAITING = "chờ duyệt"
APPLY_PROGRESS_PENDING_REJECTED = "từ chối"
APPLY_PROGRESS_SCHOLARSHIP_TYPES = (
    "CSC",
    "CIS",
    "SGS",
    "Học bổng tỉnh/thành phố",
    "Học bổng trường",
    "Học bổng viện",
    "Tự phí",
)
APPLY_PROGRESS_PROGRESS_BASE = (
    "Chờ submit",
    "Đã submit",
    "Cần sửa",
    "Chờ phỏng vấn",
    "Đã phỏng vấn",
    "Nominate",
    "Được học bổng",
    "Trượt hb",
)
APPLY_PROGRESS_PROGRESS_L1_ONLY = "Chờ UP hồ sơ"
APPLY_PROGRESS_PROGRESS_L2_ONLY = "Đã up xong còn thiếu tài liệu"
HDNK_NCKH_GROUP_INTERNAL = "nhóm Du học Trung Quốc"
HDNK_NCKH_GROUP_INTERNAL_LEGACY = "nhóm Trơn Tru"
HDNK_NCKH_PARTICIPATION_TYPES = ("cá nhân", "nhóm ngoài", HDNK_NCKH_GROUP_INTERNAL)
HDNK_NCKH_PROGRESS_OPTIONS = ("mới tạo nhóm", "đang tiến hành", "đã hoàn thành")
HDNK_NCKH_AWARD_LEVELS = ("giải 1", "giải 2", "giải 3", "khác")
HDNK_NCKH_MAX_ENTRIES = 20
HDNK_NCKH_REMINDER_DAYS = 3
LANGUAGE_TYPES = {"english", "chinese"}
ENGLISH_SKILL_KEYS = ("overall", "listening", "speaking", "reading", "writing")
CHINESE_SKILL_KEYS = ("overall", "listening", "reading", "writing", "hskk")
ENGLISH_OVERALL_GROUP = ENGLISH_SKILL_KEYS
CHINESE_OVERALL_GROUP = ("overall", "listening", "reading", "writing")
CHINESE_HSKK_GROUP = ("hskk",)
LANGUAGE_VALUE_TYPES = {"old", "new"}
LANGUAGE_LABELS = {"english": "Tiếng Anh", "chinese": "Tiếng Trung"}
SKILL_LABELS = {
    "overall": "Overall",
    "listening": "Nghe",
    "speaking": "Nói",
    "reading": "Đọc",
    "writing": "Viết",
    "hskk": "HSKK",
}
APPLY_DOC_LABELS = {
    "photo": "Chụp ảnh",
    "health": "Giấy khám sức khỏe",
    "passport": "Hộ chiếu",
    "criminal-record": "Lý lịch tư pháp",
    "diploma": "Bằng tốt nghiệp",
    "transcript": "Bảng điểm",
    "language": "Chứng chỉ ngoại ngữ",
    "work": "Giấy xác nhận công tác",
    "study-plan": "Kế hoạch học tập",
    "award": "Giấy khen",
    "research": "Nghiên cứu / bài báo",
    "recommendation-1": "Thư giới thiệu 1",
    "recommendation-2": "Thư giới thiệu 2",
    "personal-declaration": "Kê khai thông tin cá nhân",
    "parents-id": "CCCD của bố mẹ",
    "financial": "Chứng minh tài chính (CMTC)",
    "cv": "CV học thuật / Portfolio",
    "supporting-materials": "Supporting Materials",
}
MENTOR_BRANCH_NOTIFY_EMAILS = {
    "Thanh Hà": "cherrythanh06@gmail.com",
}
SCHOLARSHIP_SYSTEMS = {"english", "chinese"}
SUPPORTING_MATERIAL_DOC_IDS = ("cv", "research", "award")
MENTOR_ONLY_APPLY_DOC_IDS = frozenset({"supporting-materials"})
APPLY_DOC_DOWNLOAD_NAMES = {
    "photo": ("Ảnh thẻ", "证件照", "ID Photo"),
    "passport": ("Hộ chiếu", "护照", "Passport"),
    "health": ("Giấy khám sức khỏe", "体检报告", "Medical Report"),
    "criminal-record": ("Lý lịch tư pháp (không án tích)", "无犯罪证明", "Non-criminal Certificate"),
    "diploma": ("Bằng tốt nghiệp cao nhất", "毕业证明", "Highest Diploma"),
    "transcript": ("Bảng điểm", "成绩单", "Academic Transcript"),
    "language": ("Chứng chỉ ngoại ngữ", "语言成绩证明", "Language Certificate"),
    "recommendation-1": ("Thư giới thiệu 1", "推荐信1", "Letter of Recommendation 1"),
    "recommendation-2": ("Thư giới thiệu 2", "推荐信2", "Letter of Recommendation 2"),
    "cv": ("CV", "个人简历", "Curriculum Vitae"),
    "work": ("Giấy xác nhận công tác", "工作证明", "Employment confirmation Letter"),
    "study-plan": ("Kế hoạch học tập", "来华计划书", "Study Plan"),
    "financial": ("Chứng minh tài chính", "财力证明", "Financial Statement"),
    "research": ("Bài báo", "发表文章", "Publications (Papers)"),
    "award": ("Tài liệu khác", "其他", "Other Documents"),
    "parents-id": ("Giấy khai sinh", "出生证明", "Birth Certificate"),
    "personal-declaration": ("Kê khai thông tin cá nhân", "个人简历", "Personal Information Form"),
    "supporting-materials": ("其他支撑材料", "其他支撑材料", "Supporting Materials"),
}
SCHOLARSHIP_SYSTEM_LABELS = {
    "english": "Học bổng hệ tiếng Anh",
    "chinese": "Học bổng hệ tiếng Trung",
}
APPLY_DEGREE_LEVELS = {"undergrad", "master", "phd"}
APPLY_DEGREE_LEVEL_LABELS = {
    "undergrad": "Hệ đại (本科)",
    "master": "Hệ thạc (硕士)",
    "phd": "Tiến sĩ (博士)",
}
TERM3_2027_LANGUAGE_VALUES = {"co", "khong"}
TERM3_2027_LANGUAGE_LABELS = {
    "co": "Có — dự định đi 1 kì tiếng",
    "khong": "Không",
}
RESEARCH_DIRECTION_VALUES = {"co", "khong"}
RESEARCH_DIRECTION_LABELS = {
    "co": "Hướng NC",
    "khong": "Không",
}
MENTOR_APPLY_DIRECTIONS = {
    "kinh_te",
    "giao_duc",
    "truyen_thong",
    "quan_he_quoc_te",
    "duoc",
    "khac",
}
MENTOR_APPLY_DIRECTION_LABELS = {
    "kinh_te": "Kinh tế",
    "giao_duc": "Giáo dục",
    "truyen_thong": "Truyền thông",
    "quan_he_quoc_te": "Quan hệ quốc tế",
    "duoc": "Dược",
    "khac": "Khác",
}
MENTOR_APPLY_DIRECTION_LEGACY = {
    "kinh tế": "kinh_te",
    "kinh te": "kinh_te",
    "giáo dục": "giao_duc",
    "giao duc": "giao_duc",
    "truyền thông": "truyen_thong",
    "truyen thong": "truyen_thong",
    "quan hệ quốc tế": "quan_he_quoc_te",
    "quan he quoc te": "quan_he_quoc_te",
    "dược": "duoc",
    "duoc": "duoc",
    "khác": "khac",
    "khac": "khac",
}

BACKEND_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = BACKEND_DIR / "uploads"

_db_initialized = False
_last_inbox_reminder_check = 0.0



EMAIL_REGEX = re.compile(r'^[^@]+@[^@]+\.[^@]+$')
MENTOR_OPTIONS = {'Thanh Hà'}

OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))
OTP_RESEND_SECONDS = int(os.getenv("OTP_RESEND_SECONDS", "60"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
