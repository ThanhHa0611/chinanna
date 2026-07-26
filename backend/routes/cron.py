
import os

from flask import jsonify, request

from database import ensure_db, with_db
from extensions import app
from services.mentee_activity_digest import process_mentee_activity_digests
from services.mentor_inbox_digest import process_mentor_inbox_digests


def _cron_authorized() -> bool:
    secret = (os.getenv("CRON_SECRET") or "").strip()
    if not secret:
        return False
    provided = (
        request.headers.get("X-Cron-Secret")
        or request.args.get("secret")
        or ""
    ).strip()
    return provided == secret


@app.post("/api/cron/mentee-activity-digest")
@with_db
def cron_mentee_activity_digest():
    if not _cron_authorized():
        return jsonify({"detail": "Unauthorized"}), 401

    dry_run = request.args.get("dry_run", "").lower() in {"1", "true", "yes"}
    try:
        ensure_db()
        payload = process_mentee_activity_digests(dry_run=dry_run)
        return jsonify({"ok": True, **payload})
    except Exception as exc:
        return jsonify({"ok": False, "detail": str(exc)}), 500


@app.post("/api/cron/mentor-inbox-digest")
@with_db
def cron_mentor_inbox_digest():
    if not _cron_authorized():
        return jsonify({"detail": "Unauthorized"}), 401

    dry_run = request.args.get("dry_run", "").lower() in {"1", "true", "yes"}
    try:
        ensure_db()
        payload = process_mentor_inbox_digests(dry_run=dry_run)
        return jsonify({"ok": True, **payload})
    except Exception as exc:
        return jsonify({"ok": False, "detail": str(exc)}), 500
