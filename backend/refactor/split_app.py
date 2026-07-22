"""One-time refactor: split monolithic app.py into backend modules."""
from __future__ import annotations

import ast
import re
import shutil
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
APP_PY = BACKEND / "app.py"
LEGACY = BACKEND / "app_legacy.py"
SOURCE_PY = LEGACY if LEGACY.is_file() else APP_PY


def classify_route(path: str) -> str:
    if path == "/api/health":
        return "routes.health"
    if path.startswith("/api/auth/"):
        return "routes.auth"
    if path.startswith("/api/admin/auth/"):
        return "routes.admin_auth"
    if path.startswith("/api/admin/mentees/"):
        if "/documents/" in path or path.endswith("/documents/remind-missing"):
            return "routes.admin_documents"
        return "routes.admin_mentees"
    if path.startswith("/api/admin/inbox"):
        return "routes.admin_inbox"
    if path.startswith("/api/admin/feedback"):
        return "routes.admin_feedback"
    if path.startswith("/api/admin/stats") or path.startswith("/api/admin/activities"):
        return "routes.admin_stats"
    if path.startswith("/api/admin/access-requests") or path.startswith("/api/admin/users/"):
        return "routes.admin_access"
    if path.startswith("/api/admin/language-updates"):
        return "routes.admin_documents"
    if path.startswith("/api/email/"):
        return "routes.email_actions"
    if path.startswith("/api/feedback"):
        return "routes.feedback"
    if path.startswith("/api/documents/"):
        return "routes.documents"
    if path.startswith("/api/superadmin/"):
        return "routes.superadmin"
    if path.startswith("/api/parent/"):
        return "routes.parent"
    return "routes.misc"


def classify_helper(name: str) -> str:
    prefixes = [
        ("apply_doc_", "services.apply_documents"),
        ("apply_document", "services.apply_documents"),
        ("apply_missing", "services.apply_documents"),
        ("apply_score", "services.apply_documents"),
        ("serialize_apply_document", "services.apply_documents"),
        ("save_apply_document", "services.apply_documents"),
        ("mark_apply_document", "services.apply_documents"),
        ("count_unread_apply", "services.apply_documents"),
        ("count_uploaded_apply", "services.apply_documents"),
        ("prune_apply_missing", "services.apply_documents"),
        ("sync_apply_missing", "services.apply_documents"),
        ("build_apply_download", "services.apply_documents"),
        ("serialize_supporting", "services.apply_documents"),
        ("count_supporting", "services.apply_documents"),
        ("log_mentee_document", "services.apply_documents"),
        ("language_", "services.apply_documents"),
        ("skill_keys", "services.apply_documents"),
        ("empty_language", "services.apply_documents"),
        ("parse_score", "services.apply_documents"),
        ("should_update_score", "services.apply_documents"),
        ("normalize_language", "services.apply_documents"),
        ("normalize_scholarship", "services.apply_documents"),
        ("scholarship_system", "services.apply_documents"),
        ("normalize_apply_degree", "services.apply_documents"),
        ("apply_degree_level", "services.apply_documents"),
        ("normalize_term3", "services.apply_documents"),
        ("term3_2027", "services.apply_documents"),
        ("normalize_research", "services.apply_documents"),
        ("research_direction", "services.apply_documents"),
        ("normalize_mentor_apply", "services.apply_documents"),
        ("mentor_apply_direction", "services.apply_documents"),
        ("apply_doc_display", "services.apply_documents"),
        ("serialize_personal_declaration", "services.apply_documents"),
        ("personal_declaration", "services.apply_documents"),
        ("get_personal_declaration", "services.apply_documents"),
        ("make_download_response", "services.files"),
        ("make_inline_file_response", "services.files"),
        ("apply_doc_upload_dir", "services.files"),
        ("apply_progress_", "services.apply_progress"),
        ("serialize_apply_progress", "services.apply_progress"),
        ("get_apply_progress", "services.apply_progress"),
        ("mark_apply_progress", "services.apply_progress"),
        ("push_apply_progress", "services.apply_progress"),
        ("count_apply_progress", "services.apply_progress"),
        ("push_l2_mentor", "services.apply_progress"),
        ("ack_mentor_l2", "services.apply_progress"),
        ("serialize_mentor_l2", "services.apply_progress"),
        ("count_mentor_l2", "services.apply_progress"),
        ("mentor_l2_activity", "services.apply_progress"),
        ("admin_is_level1", "services.apply_progress"),
        ("is_thanh_ha_l1", "services.apply_progress"),
        ("is_l2_mentor", "services.apply_progress"),
        ("hdnk_nckh", "services.hdnk_nckh"),
        ("ensure_hdnk", "services.hdnk_nckh"),
        ("format_hdnk", "services.hdnk_nckh"),
        ("normalize_hdnk", "services.hdnk_nckh"),
        ("validate_hdnk", "services.hdnk_nckh"),
        ("get_hdnk", "services.hdnk_nckh"),
        ("feedback_", "services.feedback"),
        ("count_mentor_unread_feedback", "services.feedback"),
        ("count_mentee_unread_feedback", "services.feedback"),
        ("count_mentee_feedback", "services.feedback"),
        ("resolve_feedback", "services.feedback"),
        ("admin_can_see_feedback", "services.feedback"),
        ("notify_mentors_mentee_feedback", "services.notifications"),
        ("notify_mentors_mentee_document", "services.notifications"),
        ("notify_mentors_mentee_activity", "services.notifications"),
        ("notify_mentee_", "services.notifications"),
        ("mentor_branch_notify", "services.notifications"),
        ("apply_inbox_", "services.inbox"),
        ("build_inbox_", "services.inbox"),
        ("send_daily_inbox", "services.inbox"),
        ("create_email_action", "services.inbox"),
        ("email_action_urls", "services.inbox"),
        ("render_inbox_", "services.inbox"),
        ("render_email_", "services.inbox"),
        ("hash_password", "auth.security"),
        ("verify_password", "auth.security"),
        ("create_token", "auth.security"),
        ("decode_token", "auth.security"),
        ("get_token_from_header", "auth.security"),
        ("get_authenticated_", "auth.security"),
        ("require_mentee", "auth.security"),
        ("require_system_super", "auth.security"),
        ("normalize_zalo", "auth.validators"),
        ("validate_zalo", "auth.validators"),
        ("validate_register", "auth.validators"),
        ("registration_block", "auth.users"),
        ("record_mentee_login", "auth.users"),
        ("record_successful_login", "auth.users"),
        ("check_login_allowed", "auth.users"),
        ("user_response", "auth.users"),
        ("sync_parent", "auth.users"),
        ("get_linked_mentee", "auth.users"),
        ("mentee_users_query", "auth.users"),
        ("mentee_account_status", "auth.users"),
        ("mentee_is_approved", "auth.users"),
        ("approved_mentee", "auth.users"),
        ("parse_login_location", "auth.login_tracking"),
        ("set_request_login", "auth.login_tracking"),
        ("get_request_login", "auth.login_tracking"),
        ("apply_location_fields", "auth.login_tracking"),
        ("serialize_login_tracking", "auth.login_tracking"),
        ("upsert_pending_login", "auth.login_tracking"),
        ("notify_login_security", "auth.login_tracking"),
        ("reverse_geocode", "auth.login_tracking"),
        ("get_login_context", "auth.login_tracking"),
        ("get_client_ip", "auth.login_tracking"),
        ("device_fingerprint", "auth.login_tracking"),
        ("device_label", "auth.login_tracking"),
        ("serialize_pending_login", "auth.login_tracking"),
        ("count_pending_login", "auth.login_tracking"),
        ("admin_response", "services.admins"),
        ("admin_display_name", "services.admins"),
        ("admin_is_approved", "services.admins"),
        ("is_super_admin", "services.admins"),
        ("mentor_folder", "services.admins"),
        ("activity_branch", "services.admins"),
        ("admin_ids_for_branch", "services.admins"),
        ("admin_in_activity", "services.admins"),
        ("activity_admin_id", "services.admins"),
        ("access_branch", "services.admins"),
        ("team_admin", "services.admins"),
        ("admin_in_team", "services.admins"),
        ("log_mentor_activity", "services.admins"),
        ("activity_response", "services.admins"),
        ("activity_team", "services.admins"),
        ("serialize_superadmin", "services.admins"),
        ("serialize_access_admin", "services.admins"),
        ("get_mentee_for_superadmin", "services.admins"),
        ("get_mentee_for_admin", "services.admins"),
        ("mentee_filter_for_admin", "services.admins"),
        ("serialize_admin_mentee", "services.admins"),
        ("mentee_needs_attention", "services.admins"),
        ("count_mentees_needing", "services.admins"),
        ("remove_mentee_account", "services.admins"),
        ("apply_mentee_registration", "services.access"),
        ("serialize_pending_mentee", "services.access"),
        ("serialize_unified_access", "services.access"),
        ("list_pending_access", "services.access"),
        ("count_pending_access", "services.access"),
        ("admin_can_review_mentee", "services.access"),
        ("pending_mentee_registration", "services.access"),
        ("mentee_admin_list", "services.access"),
        ("apply_access_review", "services.access"),
        ("is_thanh_ha_mentee", "services.admins"),
        ("parse_iso_datetime", "services.utils"),
        ("count_submitted_apply", "services.apply_documents"),
        ("ensure_db", "database"),
        ("with_db", "database"),
    ]
    for prefix, module in prefixes:
        if name.startswith(prefix) or name == prefix.rstrip("_"):
            return module
    if name in {"add_geolocation_policy", "maybe_process_inbox_reminders"}:
        return "middleware"
    if name == "_parse_email_list":
        return "config"
    if name.startswith("_handle_email"):
        return "routes.email_actions"
    return "services.misc"


def route_path_from_decorators(node: ast.FunctionDef) -> str | None:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if isinstance(dec.func.value, ast.Name) and dec.func.value.id == "app":
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    return dec.args[0].value
    return None


def build_module_header(module: str, is_route: bool) -> str:
    header = textwrap.dedent(
        """
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
        """
    )
    if module.startswith("auth."):
        pass
    elif module.startswith("services."):
        header += textwrap.dedent(
            """
            from auth.security import *
            from auth.users import *
            from auth.login_tracking import *
            from auth.validators import *
            from services.admins import *
            from services.apply_documents import *
            from services.apply_progress import *
            from services.feedback import *
            from services.files import *
            from services.hdnk_nckh import *
            from services.inbox import *
            from services.notifications import *
            from services.utils import *
            """
        )
    elif is_route:
        header += textwrap.dedent(
            """
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
            """
        )
    return header + "\n"


def main() -> None:
    source = SOURCE_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    # Backup legacy
    if not LEGACY.exists():
        shutil.copy2(APP_PY, LEGACY)
        print(f"Backed up to {LEGACY}")

    # --- config.py ---
    config_start = None
    config_end = None
    for i, line in enumerate(lines):
        if line.startswith("ROLE_MENTEE"):
            config_start = i
        if config_start is not None and line.startswith("def ensure_db"):
            config_end = i
            break
    config_body = "".join(lines[config_start:config_end])
    env_block = []
    for line in lines:
        if line.startswith(("MONGODB_URL", "DATABASE_NAME", "SECRET_KEY", "ACCESS_TOKEN_EXPIRE")):
            env_block.append(line)
    config_preamble = textwrap.dedent(
        '''
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
        '''
    )
    (BACKEND / "config.py").write_text(
        config_preamble
        + "\n"
        + "".join(env_block)
        + "\n"
        + config_body
        + "\nEMAIL_REGEX = re.compile(r'^[^@]+@[^@]+\\.[^@]+$')\nMENTOR_OPTIONS = {'Thanh Hà'}\n",
        encoding="utf-8",
    )

    # --- database.py ---
    db_block = []
    capture = False
    for line in lines:
        if line.startswith("client = MongoClient"):
            capture = True
        if capture:
            db_block.append(line)
            if line.startswith("feedback_app = "):
                capture = False
                break
    db_funcs = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {"ensure_db", "with_db"}:
            db_funcs.append("".join(lines[node.lineno - 1 : node.end_lineno]))
    (BACKEND / "database.py").write_text(
        textwrap.dedent(
            '''
            import certifi
            from functools import wraps
            from flask import jsonify
            from pymongo import MongoClient
            from pymongo.errors import PyMongoError

            from config import DATABASE_NAME, MONGODB_URL

            '''
        )
        + "".join(db_block)
        + "\n".join(db_funcs)
        + "\n",
        encoding="utf-8",
    )

    # --- extensions.py ---
    (BACKEND / "extensions.py").write_text(
        textwrap.dedent(
            '''
            import os
            from pathlib import Path

            from dotenv import load_dotenv
            from flask import Flask
            from flask_cors import CORS

            _tunnel_env = Path(__file__).resolve().parent / ".env.public-tunnel"
            load_dotenv()
            if _tunnel_env.is_file():
                load_dotenv(_tunnel_env, override=True)

            app = Flask(__name__)


            def create_app():
                """Create and configure the Flask application."""
                _cors_extra = [
                    origin.strip()
                    for origin in os.getenv("CORS_ORIGINS", "").split(",")
                    if origin.strip()
                ]
                CORS(
                    app,
                    origins=[
                        r"http://localhost:\\d+",
                        r"http://127\\.0\\.0\\.1:\\d+",
                        r"https://.*\\.trycloudflare\\.com",
                        r"https://.*\\.vercel\\.app",
                        *_cors_extra,
                    ],
                    supports_credentials=True,
                )
                import middleware  # noqa: F401 — registers hooks
            '''
        ),
        encoding="utf-8",
    )

    modules: dict[str, list[str]] = {}
    route_modules: dict[str, list[str]] = {}

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        start_line = node.lineno
        if node.decorator_list:
            start_line = min(d.lineno for d in node.decorator_list)
        fn_source = "".join(lines[start_line - 1 : node.end_lineno])
        path = route_path_from_decorators(node)
        if path:
            mod = classify_route(path)
            route_modules.setdefault(mod, []).append(fn_source)
        else:
            mod = classify_helper(node.name)
            modules.setdefault(mod, []).append(fn_source)

    # middleware
    mid_parts = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {
            "add_geolocation_policy",
            "maybe_process_inbox_reminders",
        }:
            start_line = node.lineno
            if node.decorator_list:
                start_line = min(d.lineno for d in node.decorator_list)
            mid_parts.append("".join(lines[start_line - 1 : node.end_lineno]))
    (BACKEND / "middleware.py").write_text(
        textwrap.dedent(
            '''
            import time
            from flask import request
            from extensions import app
            from database import ensure_db, mentor_inbox
            '''
        )
        + "\n\n".join(mid_parts)
        + "\n",
        encoding="utf-8",
    )

    def write_modules(mapping: dict[str, list[str]], is_route: bool) -> None:
        for mod, chunks in mapping.items():
            if mod in {"middleware", "config", "database"}:
                continue
            rel = mod.replace(".", "/") + ".py"
            path = BACKEND / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            header = build_module_header(mod, is_route)
            path.write_text(header + "\n\n".join(chunks) + "\n", encoding="utf-8")
            init_path = path.parent / "__init__.py"
            if not init_path.exists():
                init_path.write_text("", encoding="utf-8")

    write_modules(modules, False)
    write_modules(route_modules, True)

    # Register route modules in extensions.create_app
    register_lines = []
    for mod in sorted(route_modules.keys()):
        register_lines.append(f"    import {mod}  # noqa: F401")

    ext_path = BACKEND / "extensions.py"
    ext_content = ext_path.read_text(encoding="utf-8")
    ext_content = ext_content.rstrip() + "\n\n" + "\n".join(register_lines) + "\n\n    return app\n"
    ext_path.write_text(ext_content, encoding="utf-8")

    # Thin app.py entry
    new_app = textwrap.dedent(
        '''
        import os

        from extensions import app, create_app

        create_app()

        if __name__ == "__main__":
            if os.getenv("SERVE_PUBLIC", "").strip() == "1":
                from public_routes import register_public_routes

                register_public_routes(app)

            host = os.getenv("FLASK_HOST", "127.0.0.1").strip() or "127.0.0.1"
            port = int(os.getenv("FLASK_PORT", "8000"))
            app.run(host=host, port=port, debug=True)
        '''
    )
    APP_PY.write_text(new_app, encoding="utf-8")

    print(f"Split complete. Legacy backup: {LEGACY}")
    print(f"Helper modules: {len(modules)}, route modules: {len(route_modules)}")


if __name__ == "__main__":
    main()
