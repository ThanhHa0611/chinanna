import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DEFAULT_TEMPLATE_ID = "1kqkknLDEgl55k6e_orngAfmkMbHCn2ND7_4BCfIG7ro"
DOC_ID_PATTERNS = (
    re.compile(r"/document/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"[?&]id=([a-zA-Z0-9_-]+)"),
)


def get_template_id() -> str:
    return os.getenv("GOOGLE_DOCS_TEMPLATE_ID", DEFAULT_TEMPLATE_ID).strip()


def build_doc_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/edit"


def get_manual_copy_url() -> str:
    return f"https://docs.google.com/document/d/{get_template_id()}/copy"


def parse_google_doc_id(url: str) -> str | None:
    cleaned = (url or "").strip()
    if not cleaned:
        return None
    for pattern in DOC_ID_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            return match.group(1)
    return None


def has_google_credentials() -> bool:
    account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

    if account_file:
        path = Path(account_file)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        return path.exists()

    return bool(account_json)


def _get_credentials():
    account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

    if account_file:
        path = Path(account_file)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        if not path.exists():
            raise RuntimeError(
                f"Không tìm thấy {path.name}. Tải JSON service account từ Google Cloud "
                "và đặt vào backend/service-account.json (chạy setup_google.bat để xem hướng dẫn)."
            )
        return service_account.Credentials.from_service_account_file(
            str(path),
            scopes=[DRIVE_SCOPE],
        )

    if account_json:
        info = json.loads(account_json)
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=[DRIVE_SCOPE],
        )

    raise RuntimeError(
        "Chưa cấu hình Google Drive. Tải file JSON service account, đặt tại "
        "backend/service-account.json, rồi chạy setup_google.bat để xem hướng dẫn."
    )


def _get_drive_service():
    credentials = _get_credentials()
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def create_personal_declaration_doc(username: str) -> dict:
    template_id = get_template_id()
    title = f"Kê khai thông tin - {username}"

    try:
        drive = _get_drive_service()
        copied = (
            drive.files()
            .copy(
                fileId=template_id,
                body={"name": title},
                supportsAllDrives=True,
            )
            .execute()
        )
        doc_id = copied["id"]

        drive.permissions().create(
            fileId=doc_id,
            body={
                "type": "anyone",
                "role": "writer",
                "allowFileDiscovery": False,
            },
            supportsAllDrives=True,
        ).execute()

        return {
            "doc_id": doc_id,
            "google_doc_id": doc_id,
            "google_doc_url": build_doc_url(doc_id),
            "url": build_doc_url(doc_id),
            "title": title,
            "mode": "google_docs",
        }
    except HttpError as exc:
        status = exc.resp.status if exc.resp else "unknown"
        if status == 404:
            raise RuntimeError(
                "Không truy cập được template Google Docs. Hãy share file mẫu cho "
                "email service account (quyền Viewer trở lên)."
            ) from exc
        raise RuntimeError(f"Google Drive API lỗi (HTTP {status}): {exc}") from exc


def download_template_docx() -> bytes | None:
    template_id = get_template_id()
    export_url = f"https://docs.google.com/document/d/{template_id}/export?format=docx"
    request = urllib.request.Request(
        export_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; PhongVan/1.0)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None

    if len(payload) < 1200:
        return None
    if payload[:2] != b"PK":
        return None
    return payload


def create_personal_declaration_local_copy(username: str) -> dict:
    """Tải file mẫu docx và trả về nội dung (``payload``) cùng metadata.

    Việc lưu file để cho lớp ``services.storage`` xử lý (local hoặc S3) nên
    hàm này không tự ghi ra đĩa.
    """
    payload = download_template_docx()
    if not payload:
        raise RuntimeError("Không tải được file mẫu docx từ Google Docs.")

    safe_username = re.sub(r"[^\w.-]+", "_", (username or "mentee").strip()) or "mentee"
    stored_name = f"Ke_khai_{safe_username}.docx"

    title = f"Kê khai thông tin - {username}"
    return {
        "doc_id": f"local-{stored_name}",
        "stored_name": stored_name,
        "title": title,
        "mode": "local_docx",
        "payload": payload,
    }
