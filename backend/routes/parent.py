
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

from extensions import app
from database import with_db
from auth.security import *
from auth.users import *
from auth.login_tracking import *
from auth.validators import *
from services.access import *
from services.admins import *
from services.apply_documents import *
from services.apply_progress import *
from services.feedback import *
from services.files import *
from services.hdnk_nckh import *
from services.inbox import *
from services.notifications import *
from services.utils import *

@app.get("/api/parent/child")
@with_db
def parent_get_child():
    parent, error_response = get_authenticated_user()
    if error_response:
        return error_response

    if (parent.get("role") or ROLE_MENTEE) != ROLE_PARENT:
        return jsonify({"detail": "Chỉ tài khoản phụ huynh mới truy cập được"}), 403

    mentee, error = get_linked_mentee_for_parent(parent)
    if error:
        return error

    apply_docs = mentee.get("apply_documents") or {}
    documents = [
        serialize_apply_document(doc_id, apply_docs.get(doc_id), mentee)
        for doc_id in sorted(VALID_APPLY_DOC_IDS)
    ]
    uploaded_count = count_uploaded_apply_documents(mentee)

    return jsonify(
        {
            "child": {
                "id": str(mentee["_id"]),
                "full_name": mentee.get("full_name", ""),
                "username": mentee.get("username", ""),
                "email": mentee.get("email", ""),
                "mentor": mentee.get("mentor", ""),
                "date_of_birth": mentee.get("date_of_birth", ""),
                "scholarship_system": mentee.get("scholarship_system", ""),
                "scholarship_system_label": scholarship_system_label(
                    mentee.get("scholarship_system", ""),
                ),
                "apply_clone_email": mentee.get("apply_clone_email", ""),
                "apply_clone_password": mentee.get("apply_clone_password", ""),
                "parent_email": mentee.get("parent_email", ""),
                "zalo_phone": mentee.get("zalo_phone", ""),
                "apply_direction": mentee.get("apply_direction", ""),
                "apply_degree_level": mentee.get("apply_degree_level", ""),
                "apply_degree_level_label": apply_degree_level_label(
                    mentee.get("apply_degree_level", ""),
                ),
                "term3_2027_language_semester": mentee.get("term3_2027_language_semester", "")
                if is_thanh_ha_mentee(mentee)
                else "",
                "term3_2027_language_semester_label": term3_2027_language_semester_label(
                    mentee.get("term3_2027_language_semester", ""),
                )
                if is_thanh_ha_mentee(mentee)
                else "",
                "preferred_schools_note": mentee.get("preferred_schools_note", ""),
                "personal_declaration": serialize_personal_declaration_response(
                    mentee.get("personal_declaration") or {},
                )
                if personal_declaration_has_form(mentee.get("personal_declaration") or {})
                else {},
            },
            "apply_progress": serialize_apply_progress_payload(mentee, "parent"),
            "documents": documents,
            "uploaded_count": uploaded_count,
            "total_count": len(VALID_APPLY_DOC_IDS),
        },
    )


@app.get("/api/parent/child/documents/<doc_id>/file")
@with_db
def parent_view_child_document(doc_id: str):
    parent, error_response = get_authenticated_user()
    if error_response:
        return error_response

    if (parent.get("role") or ROLE_MENTEE) != ROLE_PARENT:
        return jsonify({"detail": "Chỉ tài khoản phụ huynh mới truy cập được"}), 403

    if doc_id not in VALID_APPLY_DOC_IDS or doc_id in NO_FILE_UPLOAD_DOC_IDS:
        return jsonify({"detail": "Mục giấy tờ không hợp lệ"}), 400

    mentee, error = get_linked_mentee_for_parent(parent)
    if error:
        return error

    record = (mentee.get("apply_documents") or {}).get(doc_id) or {}
    stored_name = record.get("stored_name")
    if not stored_name:
        return jsonify({"detail": "Chưa có file tải lên"}), 404

    from services import storage
    from services.files import make_inline_file_response

    data = storage.read_bytes(storage.storage_key(mentee["_id"], doc_id, stored_name))
    if data is None:
        return jsonify({"detail": "File không tồn tại trên hệ thống"}), 404

    return make_inline_file_response(
        data,
        record.get("original_name") or stored_name,
        record.get("mime_type") or None,
    )

