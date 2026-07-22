
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

def normalize_zalo_phone(value: str) -> str:
    return re.sub(r"\D", "", (value or "").strip())


def validate_zalo_phone(value: str) -> str | None:
    digits = normalize_zalo_phone(value)
    if not digits:
        return "Số Zalo là bắt buộc"
    if len(digits) < 9 or len(digits) > 11:
        return "Số Zalo không hợp lệ"
    if not digits.startswith("0"):
        return "Số Zalo phải bắt đầu bằng 0"
    return None


def validate_register(data: dict) -> str | None:
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    mentor = data.get("mentor", "").strip()
    zalo_phone = normalize_zalo_phone(data.get("zalo_phone", ""))

    if len(username) < 3:
        return "Tên đăng nhập phải có ít nhất 3 ký tự"
    if not EMAIL_REGEX.match(email):
        return "Email không hợp lệ"
    if len(password) < 6:
        return "Mật khẩu phải có ít nhất 6 ký tự"
    if not mentor:
        return "Vui lòng chọn team mentor"
    if mentor not in MENTOR_OPTIONS:
        return "Chọn team mentor: Team Mentor Thanh Hà"
    zalo_error = validate_zalo_phone(zalo_phone)
    if zalo_error:
        return zalo_error
    return None

