import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId

from config import (
    EMAIL_REGEX,
    OTP_EXPIRE_MINUTES,
    OTP_MAX_ATTEMPTS,
    OTP_RESEND_SECONDS,
    ROLE_MENTEE,
    ROLE_PARENT,
)
from database import admins, password_reset_otps, users
from email_notify import send_password_reset_otp_email

ACCOUNT_MENTEE = "mentee"
ACCOUNT_MENTOR = "mentor"

_GENERIC_MESSAGE = (
    "Nếu email tồn tại trong hệ thống, mã OTP đã được gửi tới hộp thư của bạn."
)


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _find_account(email: str, account_type: str):
    if account_type == ACCOUNT_MENTOR:
        return admins.find_one({"email": email})
    return users.find_one({
        "email": email,
        "role": {"$in": [ROLE_MENTEE, ROLE_PARENT, None]},
    })


def request_password_reset_otp(*, email: str, account_type: str) -> tuple[dict, int]:
    email = (email or "").strip().lower()
    if not email or not EMAIL_REGEX.match(email):
        return {"detail": "Email không hợp lệ"}, 400

    if account_type not in {ACCOUNT_MENTEE, ACCOUNT_MENTOR}:
        return {"detail": "Loại tài khoản không hợp lệ"}, 400

    now = datetime.now(timezone.utc)
    existing = password_reset_otps.find_one({"email": email, "account_type": account_type})
    if existing and existing.get("sent_at"):
        sent_at = _as_utc(existing["sent_at"])
        elapsed = (now - sent_at).total_seconds()
        if elapsed < OTP_RESEND_SECONDS:
            wait = int(OTP_RESEND_SECONDS - elapsed)
            return {
                "detail": f"Vui lòng đợi {wait} giây trước khi gửi lại mã OTP",
            }, 429

    account = _find_account(email, account_type)
    if not account:
        return {"message": _GENERIC_MESSAGE}, 200

    otp = _generate_otp()
    password_reset_otps.update_one(
        {"email": email, "account_type": account_type},
        {
            "$set": {
                "email": email,
                "account_type": account_type,
                "otp_hash": _hash_otp(otp),
                "sent_at": now,
                "expires_at": now + timedelta(minutes=OTP_EXPIRE_MINUTES),
                "attempts": 0,
            }
        },
        upsert=True,
    )

    label = "Mentor Trơn Tru" if account_type == ACCOUNT_MENTOR else "Trơn Tru"
    sent = send_password_reset_otp_email(
        to_email=email,
        otp=otp,
        account_label=label,
        expire_minutes=OTP_EXPIRE_MINUTES,
    )
    if not sent:
        password_reset_otps.delete_one({"email": email, "account_type": account_type})
        return {
            "detail": "Không gửi được email OTP. Kiểm tra cấu hình SMTP trên server.",
        }, 503

    return {"message": _GENERIC_MESSAGE}, 200


def reset_password_with_otp(
    *,
    email: str,
    otp: str,
    new_password: str,
    account_type: str,
) -> tuple[dict, int]:
    email = (email or "").strip().lower()
    otp = (otp or "").strip()
    new_password = new_password or ""

    if not email or not EMAIL_REGEX.match(email):
        return {"detail": "Email không hợp lệ"}, 400
    if not otp or not otp.isdigit() or len(otp) != 6:
        return {"detail": "Mã OTP phải gồm 6 chữ số"}, 400
    if len(new_password) < 6:
        return {"detail": "Mật khẩu mới phải có ít nhất 6 ký tự"}, 400

    record = password_reset_otps.find_one({"email": email, "account_type": account_type})
    if not record:
        return {"detail": "Mã OTP không hợp lệ hoặc đã hết hạn"}, 400

    expires_at = record.get("expires_at")
    if not expires_at or _as_utc(expires_at) < datetime.now(timezone.utc):
        password_reset_otps.delete_one({"_id": record["_id"]})
        return {"detail": "Mã OTP đã hết hạn. Vui lòng yêu cầu mã mới."}, 400

    attempts = int(record.get("attempts") or 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        password_reset_otps.delete_one({"_id": record["_id"]})
        return {"detail": "Đã nhập sai quá số lần cho phép. Vui lòng yêu cầu mã OTP mới."}, 400

    if _hash_otp(otp) != record.get("otp_hash"):
        password_reset_otps.update_one(
            {"_id": record["_id"]},
            {"$inc": {"attempts": 1}},
        )
        remaining = max(0, OTP_MAX_ATTEMPTS - attempts - 1)
        return {"detail": f"Mã OTP không đúng. Còn {remaining} lần thử."}, 400

    account = _find_account(email, account_type)
    if not account:
        password_reset_otps.delete_one({"_id": record["_id"]})
        return {"detail": "Tài khoản không tồn tại"}, 404

    from auth.security import hash_password

    hashed = hash_password(new_password)
    if account_type == ACCOUNT_MENTOR:
        admins.update_one(
            {"_id": ObjectId(account["_id"])},
            {"$set": {"password": hashed}},
        )
    else:
        updates = {"password": hashed}
        role = account.get("role") or ROLE_MENTEE
        if role == ROLE_MENTEE:
            updates["mentor_visible_password"] = new_password
        users.update_one({"_id": ObjectId(account["_id"])}, {"$set": updates})

    password_reset_otps.delete_one({"_id": record["_id"]})
    return {"message": "Đặt lại mật khẩu thành công. Bạn có thể đăng nhập ngay."}, 200
