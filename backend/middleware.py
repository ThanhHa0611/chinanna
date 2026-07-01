
import time
from datetime import datetime

from flask import request

from database import ensure_db, mentor_inbox
from extensions import app
from services.inbox import send_daily_inbox_summary_for_mentor
from services.mentee_activity_digest import is_activity_digest_window, process_mentee_activity_digests
from services.mentor_inbox_digest import process_mentor_inbox_digests

_last_inbox_reminder_check = 0.0
_last_daily_digest_date = ""


@app.after_request
def add_geolocation_policy(response):
    response.headers["Permissions-Policy"] = "geolocation=(self)"
    return response


@app.before_request
def maybe_process_inbox_reminders():
    global _last_inbox_reminder_check, _last_daily_digest_date

    if request.path.startswith("/api/email/"):
        return None

    now = time.time()
    if now - _last_inbox_reminder_check < 900:
        return None
    _last_inbox_reminder_check = now

    try:
        ensure_db()
        from inbox_tasks import ensure_stale_pending_daily_reminders, process_due_reminders

        ensure_stale_pending_daily_reminders(mentor_inbox)
        process_due_reminders(mentor_inbox, send_daily_inbox_summary_for_mentor)

        if is_activity_digest_window():
            from zoneinfo import ZoneInfo

            today_key = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d")
            if _last_daily_digest_date != today_key:
                _last_daily_digest_date = today_key
                process_mentee_activity_digests()
                process_mentor_inbox_digests()
    except Exception:
        pass
    return None

