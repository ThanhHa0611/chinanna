
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import uuid
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from flask import g, jsonify, make_response, request, send_file
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.utils import secure_filename

from config import *
from database import *

def get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def device_fingerprint(user_agent: str) -> str:
    ua = (user_agent or "").strip()
    if not ua:
        return "unknown"
    return hashlib.sha256(ua.encode("utf-8")).hexdigest()[:16]


def device_label_from_user_agent(user_agent: str) -> str:
    ua = (user_agent or "").strip()
    return ua[:160] if ua else "Thiết bị không xác định"


def short_device_label(label: str) -> str:
    text = (label or "").strip()
    if not text:
        return "—"
    if len(text) <= 48 and not text.startswith("Mozilla"):
        return text

    browser = ""
    if "Edg/" in text:
        browser = "Edge"
    elif "OPR/" in text or "Opera" in text:
        browser = "Opera"
    elif "Chrome/" in text:
        browser = "Chrome"
    elif "Firefox/" in text:
        browser = "Firefox"
    elif "Safari/" in text:
        browser = "Safari"

    os_name = ""
    if "Windows" in text:
        os_name = "Windows"
    elif "Mac OS" in text or "Macintosh" in text:
        os_name = "macOS"
    elif "Android" in text:
        os_name = "Android"
    elif "iPhone" in text or "iPad" in text:
        os_name = "iOS"
    elif "Linux" in text:
        os_name = "Linux"

    if browser and os_name:
        return f"{browser} · {os_name}"
    if browser:
        return browser
    if os_name:
        return os_name
    return text[:48] + ("…" if len(text) > 48 else "")


def serialize_pending_login_requests(user: dict) -> list:
    def fmt_dt(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value or ""

    items = []
    for entry in user.get("pending_login_requests") or []:
        if entry.get("status") != LOGIN_REQUEST_PENDING:
            continue
        items.append(
            {
                "id": entry.get("id", ""),
                "ip": entry.get("ip", ""),
                "device_id": entry.get("device_id", ""),
                "device_label": entry.get("device_label", ""),
                "requested_at": fmt_dt(entry.get("requested_at")),
                "status": entry.get("status", LOGIN_REQUEST_PENDING),
                "location_label": entry.get("location_label", ""),
                "latitude": entry.get("latitude"),
                "longitude": entry.get("longitude"),
            },
        )
    return items


def count_pending_login_requests(user: dict) -> int:
    return len(serialize_pending_login_requests(user))


def format_location_label(
    *,
    location_label: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    last_location: str = "",
    last_latitude: float | None = None,
    last_longitude: float | None = None,
) -> str:
    label = (location_label or last_location or "").strip()
    if label:
        return label
    lat = latitude if latitude is not None else last_latitude
    lng = longitude if longitude is not None else last_longitude
    if lat is not None and lng is not None:
        return f"{lat:.5f}, {lng:.5f}"
    return ""


def get_primary_known_ip_info(user: dict) -> dict:
    approved_ips = set(user.get("approved_login_ips") or [])
    login_ips = list(user.get("login_ips") or [])
    candidates = [entry for entry in login_ips if entry.get("ip") in approved_ips]
    if not candidates:
        candidates = login_ips

    if not candidates:
        return {"ip": "", "location_label": ""}

    def sort_key(entry: dict) -> datetime:
        seen = entry.get("last_seen")
        if isinstance(seen, datetime):
            if seen.tzinfo is None:
                return seen.replace(tzinfo=timezone.utc)
            return seen
        return datetime.min.replace(tzinfo=timezone.utc)

    latest = max(candidates, key=sort_key)
    return {
        "ip": latest.get("ip", ""),
        "location_label": format_location_label(
            last_location=latest.get("last_location", ""),
            last_latitude=latest.get("last_latitude"),
            last_longitude=latest.get("last_longitude"),
        ),
    }


def get_primary_known_device_label(user: dict) -> str:
    approved_devices = set(user.get("approved_login_devices") or [])
    login_devices = list(user.get("login_devices") or [])
    candidates = [
        entry for entry in login_devices if entry.get("device_id") in approved_devices
    ]
    if not candidates:
        candidates = login_devices
    if not candidates:
        return ""

    def sort_key(entry: dict) -> datetime:
        seen = entry.get("last_seen")
        if isinstance(seen, datetime):
            if seen.tzinfo is None:
                return seen.replace(tzinfo=timezone.utc)
            return seen
        return datetime.min.replace(tzinfo=timezone.utc)

    latest = max(candidates, key=sort_key)
    return latest.get("label", "")


def get_login_context() -> tuple[str, str, str]:
    ip = get_client_ip()
    user_agent = request.headers.get("User-Agent", "")
    device_id = device_fingerprint(user_agent)
    return ip, device_id, device_label_from_user_agent(user_agent)


def reverse_geocode_label(latitude: float, longitude: float) -> str:
    try:
        url = (
            "https://nominatim.openstreetmap.org/reverse?"
            f"lat={latitude}&lon={longitude}&format=json&accept-language=vi"
        )
        req = urllib_request.Request(
            url,
            headers={"User-Agent": "PhongVanMentorTronTru/1.0 (internal login tracking)"},
        )
        with urllib_request.urlopen(req, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
            label = (payload.get("display_name") or "").strip()
            if label:
                return label[:220]
    except (urllib_error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        pass
    return f"{latitude:.5f}, {longitude:.5f}"


def parse_login_location(data: dict) -> tuple[dict | None, str | None]:
    if not data.get("location_granted"):
        return None, LOCATION_REQUIRED_MESSAGE
    try:
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))
    except (TypeError, ValueError):
        return None, LOCATION_REQUIRED_MESSAGE
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return None, LOCATION_REQUIRED_MESSAGE

    accuracy = data.get("accuracy")
    try:
        accuracy = float(accuracy) if accuracy is not None else None
    except (TypeError, ValueError):
        accuracy = None

    location = {
        "latitude": latitude,
        "longitude": longitude,
        "location_label": reverse_geocode_label(latitude, longitude),
        "accuracy": accuracy,
    }
    return location, None


def set_request_login_location(location: dict | None) -> None:
    g.login_location = location or {}


def get_request_login_location() -> dict:
    return getattr(g, "login_location", None) or {}


def apply_location_fields(entry: dict, location: dict, now: datetime) -> None:
    if not location:
        return
    entry["last_location"] = location.get("location_label", "")
    entry["last_latitude"] = location.get("latitude")
    entry["last_longitude"] = location.get("longitude")
    entry["last_location_at"] = now


def serialize_login_tracking(user: dict, include_superadmin_flags: bool = True) -> dict:
    login_ips = user.get("login_ips") or []
    login_devices = user.get("login_devices") or []

    def fmt_dt(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value or ""

    data = {
        "login_unique_ip_count": len(login_ips),
        "login_unique_device_count": len(login_devices),
        "login_ips": [
            {
                "ip": entry.get("ip", ""),
                "first_seen": fmt_dt(entry.get("first_seen")),
                "last_seen": fmt_dt(entry.get("last_seen")),
                "count": entry.get("count", 0),
                "approved": entry.get("ip", "") in (user.get("approved_login_ips") or []),
                "last_location": entry.get("last_location", ""),
                "last_location_at": fmt_dt(entry.get("last_location_at")),
                "last_latitude": entry.get("last_latitude"),
                "last_longitude": entry.get("last_longitude"),
            }
            for entry in login_ips
        ],
        "login_devices": [
            {
                "device_id": entry.get("device_id", ""),
                "label": entry.get("label", ""),
                "first_seen": fmt_dt(entry.get("first_seen")),
                "last_seen": fmt_dt(entry.get("last_seen")),
                "count": entry.get("count", 0),
                "last_ip": entry.get("last_ip", ""),
                "approved": entry.get("device_id", "")
                in (user.get("approved_login_devices") or []),
                "last_location": entry.get("last_location", ""),
                "last_location_at": fmt_dt(entry.get("last_location_at")),
                "last_latitude": entry.get("last_latitude"),
                "last_longitude": entry.get("last_longitude"),
            }
            for entry in login_devices
        ],
        "login_events": [
            {
                "at": fmt_dt(entry.get("at")),
                "ip": entry.get("ip", ""),
                "device_label": entry.get("device_label", ""),
                "location_label": entry.get("location_label", ""),
                "latitude": entry.get("latitude"),
                "longitude": entry.get("longitude"),
            }
            for entry in (user.get("login_events") or [])[:MAX_LOGIN_EVENTS]
        ],
        "pending_login_requests": serialize_pending_login_requests(user),
        "pending_login_requests_count": count_pending_login_requests(user),
        "login_anomaly": len(login_ips) >= 2 or len(login_devices) >= 2,
    }
    if include_superadmin_flags:
        data["login_anomaly_unread"] = bool(user.get("login_anomaly_superadmin_unread"))
    return data


def upsert_pending_login_request(user: dict, ip: str, device_id: str, device_label: str) -> str:
    now = datetime.now(timezone.utc)
    location = get_request_login_location()
    pending = list(user.get("pending_login_requests") or [])
    request_id = None
    for entry in pending:
        if (
            entry.get("status") == LOGIN_REQUEST_PENDING
            and entry.get("ip") == ip
            and entry.get("device_id") == device_id
        ):
            entry["requested_at"] = now
            entry["device_label"] = device_label
            entry["location_label"] = location.get("location_label", "")
            entry["latitude"] = location.get("latitude")
            entry["longitude"] = location.get("longitude")
            request_id = entry.get("id")
            break
    if not request_id:
        request_id = str(uuid.uuid4())
        pending.append(
            {
                "id": request_id,
                "ip": ip,
                "device_id": device_id,
                "device_label": device_label,
                "requested_at": now,
                "status": LOGIN_REQUEST_PENDING,
                "location_label": location.get("location_label", ""),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
            },
        )
    users.update_one(
        {"_id": user["_id"]},
        {"$set": {"pending_login_requests": pending, "pending_login_unread": True}},
    )
    return request_id


def notify_login_security_event(
    user: dict,
    ip: str,
    device_id: str,
    device_label: str,
    *,
    projected: bool = False,
) -> None:
    login_ips = user.get("login_ips") or []
    login_devices = user.get("login_devices") or []
    ip_set = {entry.get("ip") for entry in login_ips if entry.get("ip")}
    device_set = {entry.get("device_id") for entry in login_devices if entry.get("device_id")}
    if projected:
        ip_set.add(ip)
        device_set.add(device_id)
    unique_ips = len(ip_set)
    unique_devices = len(device_set)
    existing_ips = {entry.get("ip") for entry in login_ips}
    existing_devices = {entry.get("device_id") for entry in login_devices}
    new_ip = ip not in existing_ips
    new_device = device_id not in existing_devices
    anomaly = unique_ips >= 2 or unique_devices >= 2
    should_alert = anomaly and (new_ip or new_device or projected)

    updates = {}
    if anomaly:
        updates["login_anomaly_detected"] = True
        if not user.get("login_anomaly_detected_at"):
            updates["login_anomaly_detected_at"] = datetime.now(timezone.utc)
    if should_alert:
        updates["login_anomaly_superadmin_unread"] = True
    if updates:
        users.update_one({"_id": user["_id"]}, {"$set": updates})

    if should_alert:
        try:
            from email_notify import send_mentee_login_anomaly_email
            from services.notifications import mentor_branch_notify_emails

            mentee_page_url = os.getenv(
                "MENTOR_MENTEES_URL",
                "http://localhost:5174/mentees",
            ).strip()
            account_label = "Phụ huynh" if user.get("role") == ROLE_PARENT else "Mentee"
            mentor_name = (user.get("mentor") or "").strip()
            notify_emails = mentor_branch_notify_emails(mentor_name) if mentor_name else []
            for notify_email in notify_emails:
                send_mentee_login_anomaly_email(
                    to_email=notify_email,
                    mentee_name=f"{account_label}: {user.get('full_name') or user.get('username', '')}",
                    mentee_email=user.get("email", ""),
                    mentor_name=mentor_name,
                    unique_ip_count=unique_ips,
                    unique_device_count=unique_devices,
                    mentee_page_url=mentee_page_url,
                )
        except Exception:
            pass

